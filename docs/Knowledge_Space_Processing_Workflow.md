# 知识空间处理工作流设计文档

## 1. 概述

当前系统的工作模式是围绕单个文档的处理来构建的。为了实现对知识空间（Knowledge Space）进行全面的、端到端的生命周期管理，我们需要引入一个新的工作流编排机制。

本设计旨在将系统能力从“处理单个文档”提升至“对整个知识空间进行批量处理”，涵盖从未处理的原始文件到最终可被检索的向量索引的全过程。

## 2. 核心设计原则

1.  **异步编排 (Asynchronous Orchestration)**: 针对整个知识空间的操作是长时任务，必须在后台异步执行。API端点只负责接收指令、验证权限并启动工作流，应立即返回响应，不产生长时间阻塞。

2.  **任务链与解耦 (Actor Chaining & Decoupling)**: 整个处理流程被分解为一系列独立的、可重试的任务（Actors），包括：文档处理、分块、资产分析、索引。前一个任务成功完成后，负责触发链条中的下一个任务。这种设计提高了系统的模块化程度、可维护性和容错能力。

3.  **状态驱动与幂等性 (State-Driven & Idempotent)**: 每个核心对象（Document, Chunk, Asset）都拥有自己的状态字段。任务的触发应基于这些状态（例如，只对 `status='processed'` 的文档进行分块）。这使得整个工作流可以安全地中断和续传。

4.  **广度优先处理 (Breadth-First Processing)**: 在处理容器文件时，父文档的处理任务会“注册”所有子文档，但不会立即处理它们。整个知识空间的处理将按层级进行，处理完第N层的所有文档后，再由用户或系统统一触发第N+1层文档的处理，避免了无限递归和单点故障。

## 3. 实施方案

### 阶段一：工作流编排API

我们需要一个顶层的API端点来启动整个工作流。

-   **端点**: `POST /api/v1/knowledge-spaces/{ks_id}/process`
-   **位置**: `backend/app/routers/knowledge_spaces.py`
-   **功能**:
    -   接收一个知识空间ID (`ks_id`) 作为路径参数。
    -   接收一个JSON请求体，用于指定要执行的工作阶段：
        ```json
        {
          "process_new_documents": true,
          "chunk_processed_documents": true,
          "analyze_assets": true,
          "index_new_chunks": true
        }
        ```
    -   **逻辑**:
        1.  验证用户对该知识空间是否具有操作权限（例如，`owner` 或 `editor`）。
        2.  根据请求体中的标志，查询数据库中所有符合条件的文档、块或资产。
        3.  为每个符合条件的实体，调度其对应的**第一阶段**任务（例如，为所有 `status='uploaded'` 的文档触发 `process_document_actor`）。
        4.  （可选，但推荐）在 `KnowledgeSpaceWorkflow` 表中创建一条记录，以跟踪此次批量操作的总体状态。
        5.  立即返回 `202 Accepted` 响应，表示任务已接收并在后台处理。

### 阶段二：任务链（Actor Chaining）实现

这是后台处理的核心，我们需要创建新的、职责单一的Actors，并改造现有的Actor以形成任务链。

**1. 扩展 `Job` 模型**

为了区分不同类型的后台任务，需要在 `Job` 模型中增加一个 `job_type` 字段。

-   **位置**: `backend/app/models/job.py`
-   **修改**:
    ```python
    import enum
    from sqlalchemy import Enum

    class JobType(str, enum.Enum):
        DOCUMENT_PROCESSING = "document_processing"
        CHUNKING = "chunking"
        ASSET_ANALYSIS = "asset_analysis"
        INDEXING = "indexing"

    # 在 Job 模型中添加:
    job_type = Column(Enum(JobType), default=JobType.DOCUMENT_PROCESSING, nullable=False)
    ```

**2. 创建新的 Actors**

-   **`chunking_actor`**:
    -   **输入**: `document_id`
    -   **职责**:
        1.  加载文档及其 `CanonicalContent`。
        2.  执行分块逻辑，生成 `Chunk` 记录并保存到数据库。
        3.  **触发下游**: 为每个新创建的 `Chunk` 调度一个 `indexing_actor` 任务。
-   **`indexing_actor`**:
    -   **输入**: `chunk_id`
    -   **职责**:
        1.  加载 `Chunk` 记录。
        2.  调用嵌入模型生成向量。
        3.  将向量写入 Milvus。
        4.  更新 `Chunk` 的状态为 `indexed`。
-   **`asset_analysis_actor`**:
    -   **输入**: `asset_id`, `document_id`
    -   **职责**:
        1.  执行VLM分析。
        2.  将结果保存到 `AssetAnalysis` 表中。
        3.  更新 `Asset` 的 `analysis_status`。

**3. 修改 `process_document_actor`**

-   **位置**: `backend/app/tasks/document_processing.py`
-   **修改**: 在其成功完成的逻辑末尾，增加新的调度代码：
    ```python
    # ... job_service.complete_job(job_uuid) 之前 ...

    # 1. 触发分块任务
    # 需要一种方式来创建或直接调度新的actor
    # 例如: chunking_actor.send(str(document.id))

    # 2. 触发资产分析任务
    # assets = query_assets_from_pipeline_result(pipeline_result)
    # for asset in assets:
    #     asset_analysis_actor.send(str(asset.id), str(document.id))
    ```

### 阶段三：数据库模型与状态更新

为了支持整个工作流的状态跟踪，需要确保相关模型包含状态字段。

-   **`Document` 模型**:
    -   `status`: (已有) `uploaded`, `processing`, `processed`, `failed`。
-   **`Chunk` 模型**:
    -   `status`: (需新增) `pending_indexing`, `indexing`, `indexed`, `failed`。
-   **`Asset` 模型**:
    -   `analysis_status`: (已有) `pending`, `running`, `completed`, `failed`。

## 4. 高阶工作流示意图

```
[ User Request: POST /ks/{id}/process ]
             |
             v
[ API Controller: Creates jobs for all docs with status='uploaded' ]
             |
             v
+--------------------------------+
| Dramatiq Broker (e.g., Redis)  |
| - process_document_actor(doc_1) |
| - process_document_actor(doc_2) |
| - ...                            |
+--------------------------------+
             |
             v
[ process_document_actor(doc_1) ] -- (Completes) --> [ Triggers downstream actors ]
             |                                             |
             |                                             +--> [ chunking_actor(doc_1) ] --> [ indexing_actor(chunk_A) ]
             |                                             |                             |
             |                                             |                             +-> [ indexing_actor(chunk_B) ]
             |                                             |
             |                                             +--> [ asset_analysis_actor(asset_X, doc_1) ]
             |                                             |
             |                                             +--> [ asset_analysis_actor(asset_Y, doc_1) ]
             |
             v
[ Document status: 'processed' ]
```
