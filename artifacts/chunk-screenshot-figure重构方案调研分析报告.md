# Chunk-Screenshot-Figure 重构方案调研分析报告

## 1. 背景与目标

当前 Kosmos 系统中，文档摄入 (Ingestion) 流程产生的中间产物有 Chunk、Screenshot 和未被显式建模的 Figure。这些产物分散在不同的模型和服务中，导致逻辑不够清晰，维护成本较高。

重构设计的目标是引入一个新的抽象层：**Fragment 层**。Fragment 工作在“能指”层面，旨在统一管理文本块、页面截图和图片内容，取代原有分散的 Chunk、Screenshot 和 Figure 概念，使系统架构更加清晰、扩展性更强。

## 2. 现有实现分析

### 2.1 核心模型

- **Chunk (`app/models/chunk.py`)**:
  - `Chunk` 表示文档的文本片段，包含 `content` (Markdown格式)、`tags` 和 `page_screenshot_ids`。
  - `page_screenshot_ids` 用于关联页面截图，但其关联逻辑较弱，仅存储 ID 列表。
  - `IngestionJob` 管理摄入任务的状态。

- **Document (`app/models/document.py`)**:
  - `Document` 表示用户上传的文档记录，关联到唯一的 `PhysicalDocument`。
  - `PhysicalDocument` 用于内容去重。

- **PageScreenshot (`app/models/page_screenshot.py`)**:
  - `PageScreenshot` 表示 PDF 文档单页的截图，记录了截图文件路径、页码等信息。

### 2.2 核心服务与处理器

- **IngestionService (`app/services/ingestion_service.py`)**:
  - 核心的文档摄入服务，协调处理器、分割器、AI 工具等完成摄入流程。
  - 负责调用 `ScreenshotService` 保存截图记录。
  - 负责将内容块 (content blocks) 传递给 `IntelligentTextSplitter` 进行分块 (chunking)。
  - 负责为每个 chunk 生成标签、嵌入向量，并尝试关联截图。
    - `_associate_chunks_with_screenshots` 方法尝试根据 chunk 内容中的页码标记或顺序推断来关联截图，但逻辑复杂且可能不够精确。

- **ScreenshotService (`app/services/screenshot_service.py`)**:
  - 提供对 `PageScreenshot` 模型的 CRUD 操作。

- **GenericProcessor (`app/processors/generic_processor.py`)**:
  - 使用 `markitdown` 库处理多种文档格式，将其转换为单一的 Markdown 文本块。
  - 不生成截图。

- **PDFProcessor (`app/processors/pdf_processor.py`)**:
  - 专门处理 PDF 文档。
  - 能够生成页面截图 (`_generate_page_screenshots`)。
  - 能够提取嵌入图片并调用 VLM (视觉语言模型) 生成图片描述 (`_process_embedded_images_on_page`)。
  - 将 PDF 内容转换为结构化的块列表 (`_process_page_to_blocks`)，包含文本、标题和图片描述。

### 2.3 现有问题

1. **概念分散**:
   - Chunk、Screenshot、Figure (图片描述) 是分散的概念，没有统一的抽象。
   - Chunk 通过 `page_screenshot_ids` 字段松散地关联截图，缺乏强关联和清晰的语义。

2. **关联逻辑复杂且不精确**:
   - `IngestionService` 中的 `_associate_chunks_with_screenshots` 方法试图将文本 chunk 与页面截图关联起来。
   - 该方法依赖于 chunk 内容中的页码标记（如 "## 第X页"）或基于 chunk 顺序的推断。
   - 对于非 PDF 文档或内容结构不清晰的文档，这种关联方式容易出错或不准确。

3. **图片处理不完整**:
   - PDF 处理器能够提取嵌入图片并生成描述，但这些描述最终只是作为文本块插入到 Markdown 中。
   - 这些图片描述没有被单独建模，也没有与原始图片或页面截图建立清晰的关联，无法支持更高级的图片搜索或溯源。

4. **扩展性差**:
   - 当前架构难以支持新的内容类型或更复杂的文档结构（如表格、公式等）。

## 3. Fragment 层重构方案

### 3.1 Fragment 抽象

引入 `Fragment` 基类，作为所有文档片段的统一基类。

```python
# app/models/fragment.py (概念模型)
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Integer
from sqlalchemy.sql import func
from app.db.database import Base

class Fragment(Base):
    """文档片段基类"""
    __tablename__ = "fragments"
    __table_args__ = {'extend_existing': True}

    id = Column(String, primary_key=True)  # UUID
    kb_id = Column(String, ForeignKey("knowledge_bases.id"), nullable=False)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False)
    fragment_index = Column(Integer, nullable=False)  # 在文档中的顺序
    fragment_type = Column(String, nullable=False)  # 'text', 'screenshot', 'figure'

    # 可选的原始内容 (如文本、文件路径等)
    raw_content = Column(Text, nullable=True)

    # 可选的元数据 (JSON格式)
    metadata = Column(Text, nullable=True)  # 例如: {"page_number": 1, "description": "..."}

    # 可选的标签 (JSON数组格式)
    tags = Column(Text, nullable=True)

    created_at = Column(DateTime, default=func.now())
```

### 3.2 具体 Fragment 类型

#### 3.2.1 TextFragment

- 对应当前的 `Chunk`，但更侧重于“文本内容”这一语义。
- `fragment_type = 'text'`
- `raw_content` 存储纯文本或 Markdown 格式的文本内容。
- `metadata` 可存储与文本相关的元数据，如原始页码范围等。

#### 3.2.2 ScreenshotFragment

- 对应当前的 `PageScreenshot`，但作为 Fragment 的一种类型。
- `fragment_type = 'screenshot'`
- `raw_content` 存储截图文件路径。
- `metadata` 存储页码、尺寸等信息。

#### 3.2.3 FigureFragment

- 表示文档中的图片内容。
- `fragment_type = 'figure'`
- `raw_content` 可以存储图片文件路径或图片的 Base64 编码。
- `metadata` 存储图片描述 (`description`)、原始页码 (`page_number`)、位置信息等。
- 可以通过 `metadata` 与产生它的 `ScreenshotFragment` 建立关联。

### 3.3 重构后的摄入流程

1. **文档预处理**:
   - **文本 Document**: 直接进行智能分块，创建 `TextFragment`。
   - **图片 Document**: 统一转换为 PNG 格式，创建 `FigureFragment`。
   - **图文复合 Document (如 PDF)**:
     a. 生成页面截图，为每页创建 `ScreenshotFragment`。
     b. 提取嵌入图片，调用 VLM 生成描述，为每个图片创建 `FigureFragment`。
     c. 将图片描述替换到文本中的占位符。
     d. 对处理后的文本进行智能分块，创建 `TextFragment`。

2. **关联**:
   - `FigureFragment` 通过 `metadata` 与对应的 `ScreenshotFragment` 关联。
   - `TextFragment` 可以通过其内容或元数据与 `ScreenshotFragment` 或 `FigureFragment` 建立更精确的关联。

3. **索引**:
   - 目前仅为 `TextFragment` 创建 Milvus 索引。
   - 未来可以为 `FigureFragment` 的描述或视觉特征创建索引。

### 3.4 优势

1. **概念统一**:
   - 所有文档片段都继承自 `Fragment`，拥有统一的接口和生命周期管理。
   - 清晰地区分了文本、截图和图片内容。

2. **关联增强**:
   - Fragment 之间可以通过 `metadata` 或外键建立更明确、更灵活的关联。
   - 避免了在 `Chunk` 中存储松散的 ID 列表。

3. **易于扩展**:
   - 可以轻松添加新的 Fragment 类型，如 `TableFragment`、`FormulaFragment` 等。
   - 新的处理器可以更容易地集成到系统中。

4. **简化服务逻辑**:
   - `IngestionService` 的逻辑将更加清晰，只需负责创建不同类型的 Fragment。
   - 关联逻辑将内聚在 Fragment 模型或专门的关联服务中。

## 4. 实施建议

1. **新建 `Fragment` 模型**: 创建 `app/models/fragment.py` 文件，定义 `Fragment` 及其子类。
2. **重构处理器**:
   - 修改 `PDFProcessor`，使其在处理过程中创建 `ScreenshotFragment` 和 `FigureFragment`。
   - 修改 `GenericProcessor`，明确其输出为 `TextFragment` 的原始内容。
3. **重构 `IngestionService`**:
   - 修改 `_execute_pipeline` 方法，使其创建和管理 `Fragment` 而非直接操作 `Chunk` 和 `PageScreenshot`。
   - 移除或重构 `_associate_chunks_with_screenshots` 方法，因为关联逻辑将由 Fragment 模型处理。
4. **数据迁移**: 编写脚本，将现有的 `Chunk` 和 `PageScreenshot` 数据迁移至新的 `Fragment` 表结构。
5. **逐步替换**: 在新架构稳定后，逐步替换对旧 `Chunk` 和 `PageScreenshot` 模型的直接引用。

## 5. 结论

引入 Fragment 层是对 Kosmos 系统的一次重要重构。它将统一管理文档摄入过程中产生的各种内容片段，解决当前 Chunk-Screenshot-Figure 概念分散、关联不清晰的问题。该方案符合渐进式重构的原则，可以在不影响现有功能的前提下，逐步将新架构落地，为系统未来的扩展和优化奠定坚实的基础。