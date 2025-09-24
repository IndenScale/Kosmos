# 3. Kosmos 文档生命周期

一份文档在 Kosmos 系统中的生命周期是指从它被用户上传开始，直到其内容被完全解析、标准化，并可供上层智能Agent使用为止的全过程。这个过程是异步的、状态驱动的，并且具有高度的容错性。

## 核心阶段

文档的生命周期主要包括以下几个核心阶段：

1.  **上传 (Upload)**: 用户通过公共API上传文件。
2.  **入队 (Enqueuing)**: API服务完成初步处理后，将一个异步处理任务放入Dramatiq消息队列。
3.  **处理 (Processing)**: 后台的Dramatiq Worker获取任务，并根据文件类型执行相应的处理流水线。
4.  **回调 (Callback)**: Worker处理完成后，将结果通过内部API回调给主应用。
5.  **完成 (Completion)**: 主应用接收回调，原子性地更新数据库，将文档置为最终状态。

## 详细流程图

```mermaid
sequenceDiagram
    participant User as 用户
    participant PublicAPI as 公共API
    participant DocumentService as 文档服务
    participant Minio as 对象存储
    participant Redis as 消息队列
    participant Worker as 后台Worker
    participant ExtTools as 外部工具<br>(MinerU/LibreOffice)
    participant InternalAPI as 内部API
    participant DB as 数据库

    User->>+PublicAPI: POST /api/v1/documents/upload
    PublicAPI->>+DocumentService: create_document_from_upload()
    
    一份文档在 Kosmos 系统中的生命周期是指从它被用户上传开始，直到其内容被完全解析、结构化（分块）、并可供上层智能Agent使用为止的全过程。这个过程是异步的、状态驱动的，并且通过统一的 `Job` 模型进行管理，具有高度的容错性和可观测性。

## 核心阶段

文档的生命周期被清晰地划分为多个独立的、由 `Job` 驱动的阶段：

1.  **上传与初始处理 (Upload & Initial Processing)**:
    *   用户上传文件，系统触发一个 `document_processing` 类型的作业。
    *   此阶段负责将任意格式的输入文件（PDF, DOCX, TXT, PNG等）转换为统一的、规范化的Markdown格式 (`CanonicalContent`)，并提取出所有内嵌的图片等派生资产 (`Asset`)。
    *   此阶段完成后，`Document` 对象的状态被标记为 `processed`。

2.  **资产分析 (Asset Analysis)**:
    *   对于每一个在初始处理阶段提取出的 `Asset`，系统会自动为其创建一个 `asset_analysis` 类型的作业。
    *   此作业负责调用多模态大模型（VLM）对资产内容（如图片）进行深度分析，生成描述性的文本。
    *   这个过程是完全并行的，每个资产的分析都是一个独立的 `Job`。

3.  **文档分块 (Chunking)**:
    *   一旦 `Document` 的状态变为 `processed`，用户就可以为其手动或自动触发一个 `chunking` 类型的作业。
    *   此作业会消费 `CanonicalContent`，并依赖已完成的 `Asset` 分析结果，调用大语言模型（LLM）将整个文档智能地分解为具有语义的 `Chunk`（标题和内容块）。

## 详细流程图

```mermaid
sequenceDiagram
    participant User as 用户
    participant PublicAPI as 公共API
    participant DocumentService as 文档服务
    participant JobService as 作业服务
    participant Minio as 对象存储
    participant Redis as 消息队列
    participant Worker as 后台Worker
    participant ExtTools as 外部工具<br>(MinerU/LibreOffice)
    participant DB as 数据库

    User->>+PublicAPI: POST /api/v1/documents/upload
    PublicAPI->>+DocumentService: create_document_from_upload()
    
    DocumentService->>DocumentService: 1. 计算文件哈希, 去重
    DocumentService->>Minio: 2. 上传文件到 'originals' 桶
    DocumentService->>DB: 3. 创建 Original 和 Document 记录
    
    DocumentService->>+JobService: 4. create_job(type='document_processing')
    JobService->>DB: a. 创建 Job 记录 (status='PENDING')
    JobService->>Redis: b. 发送 process_document_actor 任务
    JobService-->>-DocumentService: 返回 Job 对象
    DocumentService-->>-PublicAPI: 返回 201 Created (DocumentRead)
    PublicAPI-->>-User: 响应成功

    Note right of Redis: API请求处理结束

    Worker->>+Redis: 5. 从队列中获取任务
    Redis-->>-Worker: 返回 process_document_actor 任务
    Worker->>+JobService: start_job()
    JobService->>DB: 更新 Job.status='RUNNING'
    JobService-->>-Worker: 
    
    Worker->>Worker: 6. 根据MIME类型选择流水线
    Worker->>ExtTools: 7. 调用外部工具 (如 MinerU)
    ExtTools-->>Worker: 返回处理结果 (Markdown, Images)
    
    Worker->>+Minio: 8. 上传处理后的资产和规范化内容
    Minio-->>-Worker: 上传成功
    
    Worker->>+JobService: complete_job()
    JobService->>DB: a. 原子性地创建/更新 CC, Asset, Links<br>b. 更新 Document.status='processed'<br>c. 更新 Job.status='COMPLETED'
    
    Note over JobService, DB: 初始处理作业完成
    
    JobService->>JobService: 9. [自动触发] 对每个新 Asset<br>创建 asset_analysis 作业
    JobService->>Redis: 发送 analyze_figure_asset_job 任务
    
    User->>PublicAPI: 10. [手动触发] POST /jobs/chunking/{doc_id}
    PublicAPI->>JobService: create_job(type='chunking')
    JobService->>Redis: 发送 chunk_document_actor 任务
```

## 关键步骤详解

1.  **统一作业入口**: 任何耗时操作（包括初始处理）都会首先在 `JobService` 中创建一个对应的 `Job` 记录。这使得所有类型的后台任务都拥有统一的生命周期管理、状态跟踪和进度报告机制。

2.  **`document_processing` 作业**:
    *   这是文档生命周期的第一个作业，由 `process_document_actor` 执行。
    *   它的核心职责是将任何输入格式转换为 `CanonicalContent` (Markdown) 和一系列 `Asset`。
    *   成功完成后，它会将 `Document` 的状态更新为 `processed`，并把自身的 `Job` 状态更新为 `COMPLETED`。

3.  **后续作业的触发**:
    *   **自动触发**: `JobService` 在 `document_processing` 作业成功的回调逻辑中，可以被配置为自动为所有新生成的 `Asset` 创建 `asset_analysis` 作业。
    *   **手动触发**: 像 `chunking` 这样昂贵且核心的作业，通常由用户通过API显式触发，从而创建一个 `chunking` 类型的 `Job`。

4.  **幂等性与状态驱动**:
    *   所有的后台 Actor (如 `process_document_actor`, `chunk_document_actor`) 都被设计为**幂等**的。例如，一个 `chunking` 作业在开始时会先清除该文档所有已存在的 `Chunk`，确保每次运行都从干净的状态开始。
    *   整个流程是严格状态驱动的。一个阶段的 `Job` 成功完成（`status='COMPLETED'`）是触发下一阶段作业的前提。

5.  **状态流转**:
    *   **`Document.status`**: 只管理初始处理阶段的状态 (`uploaded` -> `processing` -> `processed` / `failed`)。它标志着一份文档是否“准备好”被进一步处理。
    *   **`Job.status`**: 管理每一个具体后台任务的详细生命周期 (`PENDING`, `RUNNING`, `COMPLETED`, `FAILED`, `PAUSED`)。一份 `processed` 状态的文档，可能同时关联着多个不同状态的 `Job`（例如，一个已完成的 `asset_analysis` 作业和一个正在运行的 `chunking` 作业）。

这个精心设计的生命周期确保了Kosmos在处理文档时既高效又健壮，为构建可靠的知识管理系统奠定了基础。
    DocumentService->>DB: 2. 检查哈希是否存在 (Originals表)
    alt 文件内容已存在 (Cache Hit)
        DB-->>DocumentService: 返回已存在的Original记录
        DocumentService->>DB: Original.reference_count++
    else 文件内容不存在 (Cache Miss)
        DocumentService->>Minio: 3. 上传文件到'originals'桶
        Minio-->>DocumentService: 上传成功
        DocumentService->>DB: 4. 创建新的Original记录 (ref_count=1)
    end
    
    DocumentService->>DB: 5. 创建Document记录 (status='uploaded')
    DB-->>DocumentService: 返回新Document对象
    DocumentService->>Redis: 6. 发送 process_document_pipeline 任务
    Redis-->>DocumentService: 任务已入队
    DocumentService-->>-PublicAPI: 返回 201 Created (DocumentRead)
    PublicAPI-->>-User: 响应成功

    Note right of Redis: API请求处理结束，用户得到快速响应

    Worker->>+Redis: 7. 从队列中获取任务
    Redis-->>-Worker: 返回 process_document_pipeline 任务
    Worker->>DB: 更新Document.status='processing'
    Worker->>Worker: 8. 根据MIME类型选择流水线
    Worker->>ExtTools: 9. 调用外部工具 (如 MinerU)
    ExtTools-->>Worker: 返回处理结果 (Markdown, Images)
    
    Worker->>+Minio: 10. 上传处理后的资产 (Images)
    Minio-->>-Worker: 资产上传成功
    Worker->>+Minio: 11. 上传规范化内容 (Markdown)
    Minio-->>-Worker: 规范内容上传成功
    
    Worker->>+InternalAPI: 12. POST /processing-callback (含处理结果)
    InternalAPI->>+DB: 13. 原子性事务开始
    DB->>InternalAPI: 开启事务
    InternalAPI->>DB: a. 清理旧数据 (如有)<br>b. 创建/更新CanonicalContent<br>c. 创建/更新Asset记录<br>d. 创建DocumentAssetLink<br>e. 更新引用计数<br>f. 更新Document.status='processed'
    InternalAPI->>DB: 提交事务
    DB-->>InternalAPI: 事务成功
    InternalAPI-->>-Worker: 返回 202 Accepted
    Worker->>Redis: 任务处理完成
```

## 关键步骤详解

1.  **哈希与去重**: 在`DocumentService`中，系统首先完整读取上传文件的内容并计算其SHA256哈希。这个哈希被用来在`Originals`表中进行查找，如果找到匹配项，则直接复用已存在的`Original`记录并增加其引用计数，避免了重复存储。

2.  **异步任务触发**: 文档元数据和原始文件记录被创建后，API的职责便已完成。它通过调用`.send()`方法将一个包含`document_id`的消息发送到Dramatiq，然后立即向用户返回成功响应。这确保了即使用户上传一个巨大的文件，API也能在毫秒级内响应。

3.  **Worker与外部工具**:
    *   `document_processing.py`中的`process_document_pipeline` actor是任务的入口。它首先将文档状态更新为`processing`，防止重复处理。
    *   根据文档的MIME类型，它会分发到不同的处理流水线，如`run_pdf_pipeline`或`run_office_pipeline`。
    *   这些流水线会调用系统中集成的外部工具（如MinerU或LibreOffice）来执行实际的解析和转换工作。这些工具通常运行在隔离的临时目录中，以确保文件系统的清洁。

4.  **幂等的回调处理**:
    *   Worker完成所有处理和文件上传后，会构造一个包含所有结果（规范化内容的哈希、路径，所有资产的哈希、路径等）的JSON `payload`。
    *   它通过一个带内部密钥的HTTP POST请求将此`payload`发送到`internal_main.py`暴露的`/processing-callback`端点。
    *   该回调端点的实现是**幂等**的。它被设计为可以安全地重复执行。例如，在重新处理一个文档时，它会先原子性地解绑并删除旧的`CanonicalContent`和`Asset`链接，然后再绑定新的数据，从而保证了数据的一致性。

5.  **状态流转**:
    *   `uploaded`: 初始状态，表示文件已上传，但处理任务尚未开始。
    *   `processing`: Worker已获取任务，正在处理中。
    *   `processed`: Worker成功完成处理，并通过回调更新了所有数据。文档已准备好被上层应用使用。
    *   `failed`: 在处理或回调过程中发生不可恢复的错误。文档需要人工干预或重新触发处理。

这个精心设计的生命周期确保了Kosmos在处理文档时既高效又健壮，为构建可靠的知识管理系统奠定了基础。
