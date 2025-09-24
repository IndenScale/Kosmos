# 2. Kosmos 数据模型详解

Kosmos 的数据模型是其实现高效、可追溯和可扩展知识管理的核心。模型设计遵循几个关键原则，特别是“内容寻址”和“引用计数”，这使得系统在存储和管理上极为高效。

所有数据模型均通过 SQLAlchemy ORM 定义，基类为 `backend.app.models.base.Base`。

## 核心设计原则：内容寻址与引用计数

为了实现全局的数据去重和高效的存储管理，系统中的三大核心二进制内容对象——`Original`, `Asset`, 和 `CanonicalContent`——都采用了**内容寻址（Content-Addressing）**的设计模式。

*   **内容哈希 (`*_hash`)**: 每个对象不使用随机UUID作为其唯一标识，而是使用其二进制内容的SHA256哈希值。这意味着，无论一个文件被上传多少次，只要其内容完全相同，它的哈希值就永远不变。
*   **引用计数 (`reference_count`)**: 每个内容寻址的对象都有一个引用计数字段。该字段记录了系统中有多少个其他对象（如`Document`）正在引用这个内容。
    *   当一个新文档引用此内容时，`reference_count` 加 1。
    *   当引用该内容的文档被删除时，`reference_count` 减 1。
    *   当`reference_count`降至 0 时，意味着该内容不再被任何文档使用，可以被后台的垃圾回收任务安全地从对象存储中删除。

这个组合带来了巨大的优势：
1.  **自动去重**: 同样的文件或资产在系统中只会被存储一次，极大地节省了存储空间。
2.  **数据完整性**: 哈希值可以作为校验和，确保数据在传输和存储过程中没有损坏。
3.  **简化的垃圾回收**: 只需一个简单的后台任务定期清理引用计数为零的对象即可。

### 关系图示例

```mermaid
graph LR
    subgraph "逻辑层 (Documents)"
        DocA[Document A<br>original_id: O1_id<br>asset_links: [A1_id]]
        DocB[Document B<br>original_id: O1_id<br>asset_links: [A1_id, A2_id]]
        DocC[Document C<br>original_id: O2_id<br>asset_links: [A2_id]]
    end

    subgraph "物理存储层 (Content-Addressable Objects)"
        O1[Original 1<br>hash: hash_O1<br>ref_count: 2]
        O2[Original 2<br>hash: hash_O2<br>ref_count: 1]
        A1[Asset 1<br>hash: hash_A1<br>ref_count: 2]
        A2[Asset 2<br>hash: hash_A2<br>ref_count: 2]
    end

    DocA -- 引用 --> O1
    DocB -- 引用 --> O1
    DocC -- 引用 --> O2
    
    DocA -- 引用 --> A1
    DocB -- 引用 --> A1
    DocB -- 引用 --> A2
    DocC -- 引用 --> A2
```
*在这个例子中，文档A和B共享同一个原始文件（`Original 1`）和同一个资产（`Asset 1`）。*

## 主要数据模型

### 1. 内容寻址模型

*   **`Original`**: 存储用户上传的原始、未经修改的文件。
    *   `original_hash`: 文件的SHA256哈希。
    *   `storage_path`: 在Minio中的存储路径。
    *   `reference_count`: 被`Document`引用的次数。

*   **`Asset`**: 存储从文档中提取出的派生资产，如图片、音视频等。
    *   `asset_hash`: 资产文件的SHA256哈希。
    *   `storage_path`: 在Minio中的存储路径。
    *   `reference_count`: 被`DocumentAssetLink`或`ChunkAssetLink`引用的次数。
    *   `analysis_status`: 资产的智能分析状态（如`completed`, `failed`）。

*   **`CanonicalContent`**: 存储文档经过解析和标准化后的核心内容（通常是Markdown格式）。一份`Document`只有一个`CanonicalContent`。
    *   `content_hash`: 规范化内容的SHA256哈希。
    *   `storage_path`: 在Minio中的存储路径。

### 2. 核心业务模型

*   **`User`**: 系统用户。
*   **`KnowledgeSpace`**: 知识空间，是文档和本体论的组织容器。每个知识空间由一个用户拥有。
*   **`Document`**: 文档的核心元数据记录。它本身不存储文件内容，而是通过外键关联到`Original`和`CanonicalContent`。
    *   `knowledge_space_id`: 所属知识空间。
    *   `original_id`: 关联到`Original`表，指向原始文件。
    *   `canonical_content_id`: 关联到`CanonicalContent`表，指向规范化内容。
    *   `status`: 文档的**初始处理**状态（如`uploaded`, `processing`, `processed`, `failed`）。一旦文档状态变为 `processed`，其生命周期将交由 `Job` 系统进行后续管理（如Chunking、分析等）。

*   **`Chunk`**: 文档内容的语义块。这是未来智能Agent进行精细化知识管理的基础。
    *   `document_id`: 所属文档。
    *   `parent_id`: 指向父级Chunk，用于构建内容的层次结构。
    *   `type`: 块类型（如`heading`, `content`）。
    *   `raw_content`: 从`CanonicalContent`中根据行号提取的原始文本。

*   **`Job`**: **[核心变更]** 用于跟踪和管理所有长耗时后台任务的统一模型，取代了旧的、分散的状态管理机制。
    *   `id`: 作业的唯一标识符。
    *   `job_type`: 作业类型，是一个枚举值，如 `document_processing`, `asset_analysis`, `chunking`。
    *   `status`: 作业的当前状态，如 `PENDING`, `RUNNING`, `COMPLETED`, `FAILED`, `PAUSED`。
    *   `initiator_id`: 发起该作业的用户ID。
    *   `knowledge_space_id`: 作业所属的知识空间。
    *   `document_id`: （可选）作业关联的文档。
    *   `asset_id`: （可选）作业关联的资产。
    *   `progress`: (JSON) 存储可量化的任务进度，例如 `{'current_line': 1024, 'total_lines': 4096}`，用于任务恢复和前端展示。
    *   `context`: (JSON) 存储任务执行所需的非结构化上下文信息。
    *   `result`: (JSON) 存储任务成功执行后的结果。
    *   `reason`: (String) 记录任务失败或暂停的原因。

### 3. 关联与权限模型

*   **`KnowledgeSpaceMember`**: 用户和知识空间的关联表，定义了用户在空间中的角色（`owner`, `editor`, `viewer`）。
*   **`DocumentAssetLink`**: `Document`和`Asset`之间的多对多关联表。
*   **`ChunkAssetLink`**: `Chunk`和`Asset`之间的多对多关联表。
*   **`ModelCredential`**: 用户拥有的AI模型凭证（API Key等），已加密存储。
*   **`KnowledgeSpaceModelCredentialLink`**: `KnowledgeSpace`和`ModelCredential`的关联表，允许将用户凭证授权给特定知识空间使用，并定义了路由的**优先级**和**权重**。

### 4. 本体论模型 (Git-like)

*   **`Ontology`**: 本体论仓库，每个知识空间有且只有一个。
*   **`OntologyVersion`**: 代表本体论的一次“提交”（Commit），记录了版本号、作者、提交信息和该版本的完整节点快照 (`serialized_nodes`)。
*   **`OntologyNode`**: 本体论中的一个概念节点，拥有一个在所有版本中都保持不变的`stable_id`。
*   **`OntologyVersionNodeLink`**: `OntologyVersion`和`OntologyNode`的关联表，用于构建特定版本下的树状层级结构。

这个数据模型的设计为Kosmos提供了一个既健壮又灵活的基础，能够高效地处理大规模、多关联的知识数据。
