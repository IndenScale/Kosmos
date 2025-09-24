# Kosmos Chunking Agent: 设计与实现详解

## 1. 概述与核心原则

### 1.1. Chunk在Kosmos中的定义

在Kosmos系统中，一个“Chunk”**不是**对文本的任意物理分割。它是一个**由LLM识别并提炼的、具有独立语义的、最小的知识单元**。每个Chunk都代表了一个连贯的思想、一个具体的数据点或一个结构化的标题。

Chunking过程因此是一个**慢速的、以质量为核心的、深度语义的精炼过程**。它承担以下核心职责：

-   **结构识别**：识别文档的层级结构（章节、段落）。
-   **内容精炼**：为每个内容单元生成精确的摘要。
-   **边界决策**：智能地决定每个知识单元的起始和结束点。
-   **内容净化**：识别并改写/覆盖无意义、重复或包含隐私信息的内容。

**高质量的Chunk是整个Kosmos知识库的基石。**

### 1.2. 核心原则

-   **质量优先**：在速度与质量之间，永远优先保证输出Chunk的语义完整性和高质量。
-   **语义边界**：Chunk的分割点必须由文本的语义决定，而非固定的字符或行数。
-   **原子持久化**：每个成功生成的Chunk都应被视为一个独立的、有价值的成果，并被立即持久化，以防止在长任务中丢失进度。

---

## 2. 数据模型：标题-内容-资产

Chunking Agent的输出成果最终体现为`Chunk`表中的记录，并与其他模型（特别是`Asset`）建立关联。

### 2.1. `Chunk`模型核心字段

-   `id` (UUID): 唯一标识符。
-   `document_id` (FK): 关联的文档。
-   `parent_id` (FK, self-referential): **核心字段**，用于构建层级结构。一个内容Chunk的`parent_id`指向其所属的标题Chunk；一个子标题的`parent_id`指向其父标题。
-   `type` (String): `"heading"` 或 `"content"`，定义了Chunk的性质。
-   `level` (Integer):
    -   对于`heading`类型，表示其标题级别（例如，1对应H1, 2对应H2）。
    -   对于`content`类型，通常为-1，不适用。
-   `start_line`, `end_line` (Integer): 该Chunk在`CanonicalContent`中的精确行范围。
-   `raw_content` (Text): 从`CanonicalContent`中提取的原始文本。
-   `summary` (Text): 由LLM生成的该Chunk的核心摘要。
-   `assets` (Relationship): 通过`chunk_asset_links`中间表，实现与`Asset`模型的多对多关联。

### 2.2. 关系模型

```
[Heading Chunk (level=1)]
       |
       +---- parent_id ---- [Content Chunk]
       |                        |
       |                        +---- assets ---- [Asset 1]
       |                        +---- assets ---- [Asset 2]
       |
       +---- parent_id ---- [Heading Chunk (level=2)]
                                |
                                +---- parent_id ---- [Content Chunk]
```

---

## 3. Chunking Agent 核心流程

Chunking Agent 在 Dramatiq 中表现为一个幂等的、可恢复的 Actor (`chunk_document_actor`)，其所有状态管理都围绕 `Job` 模型展开。旧的、理论上的“Orchestrator”概念已被废弃，取而代之的是一个更简单、更健壮的线性处理模型。

### 3.1. 作业启动与幂等性保障

1.  **触发**: 用户通过 API 为一个 `Document` 创建一个 `chunking` 类型的 `Job`。
2.  **前置检查**: API 层会进行权限和AI凭证的预检，确保任务具备执行的基本条件。
3.  **入队**: 一个包含 `job_id` 的消息被发送到 Dramatiq 队列。
4.  **任务开始**: `chunk_document_actor` 从队列中获取任务。
5.  **幂等性保障**: 作为任务的第一步，Actor 会**删除**该文档所有已存在的 `Chunk` 记录。这确保了即便是失败重试的作业，也能从一个干净的状态开始，防止数据污染。

### 3.2. 线性批处理循环

Agent 不再使用复杂的“边界块”和“前向上下文传递”机制，而是采用一个简单的、基于进度的线性批处理循环。

1.  **恢复进度**: Actor 从 `Job` 记录的 `progress` 字段中读取 `current_line`（默认为1）和 `total_lines`。
2.  **读取数据块**: 从 `current_line` 开始，从 `CanonicalContent` 中读取一个固定大小的文本块（`megachunk`，例如200行）。
3.  **构建LLM上下文**:
    *   将 `megachunk` 文本加上行号。
    *   从数据库中查询最新的、已处理的标题和已分析的资产信息，作为上下文提供给LLM。
4.  **调用LLM**: 将上下文和 `megachunk` 发送给LLM，要求其使用“LLM即索引器”模式返回工具调用（Tool Calls），识别出文本块中的标题和内容块。
5.  **处理响应与持久化**:
    *   Actor 接收 LLM 返回的工具调用。
    *   根据工具调用中的行号，从原始文本中提取内容，创建 `Chunk` 对象（包括标题和内容块）。
    *   将新创建的 `Chunk` 对象存入数据库。
6.  **更新进度**:
    *   计算本次批处理中最后一个被处理的行号 `last_processed_line`。
    *   将 `job.progress['current_line']` 更新为 `last_processed_line + 1`。
    *   将 `Job` 的进度变更提交到数据库。
7.  **循环或结束**:
    *   如果 `current_line` 小于 `total_lines`，则重复步骤2，进入下一个批处理循环。
    *   如果所有行都已处理完毕，则将 `Job` 状态标记为 `COMPLETED`，任务结束。

这个简化的流程消除了组件间复杂的状态传递，将所有状态都集中于 `Job` 模型中，使得任务的逻辑更清晰，也更容易调试和恢复。

### 3.3. 资产描述依赖处理

对资产分析结果的依赖处理被移至 `Job` 系统的不同层面，遵循**“尽早检查，延迟执行”**的原则。

1.  **API层预检 (可选)**: 在创建 `chunking` 作业时，可以增加一个非阻塞的检查，如果发现有资产正在分析，可以向用户返回提示，但不阻塞作业创建。
2.  **Actor内部等待**: `chunk_document_actor` 在其执行循环的**开始阶段**，会检查文档所有关联 `Asset` 的分析状态。
    *   如果存在仍在 `PENDING` 或 `RUNNING` 状态的分析作业，`chunking` 作业不会失败。
    *   它会将自身的 `Job` 状态设置为 `PAUSED`，并附上原因（如 "Waiting for asset analysis to complete"）。
    *   然后，它会**将自身重新入队并设置一个延迟**（例如60秒）。
    *   在延迟结束后，Worker会重新执行该任务，再次进行依赖检查。这个过程会一直持续，直到所有资产分析完成。

这种机制确保了 `Chunking` Agent 在处理文本时，总是能获取到最完整的上下文信息，而不会因为依赖未就绪而产生低质量的输出。

---

## 4. 输出校验与完整性检查

Agent在从LLM接收到结构化的Chunk输出后，**必须**在持久化之前执行严格的校验。

1.  **未归档行校验**：
    -   **规则**：在单个LLM调用中，允许存在未归档行。但在整个文档的Chunking Job完成时，不允许存在任何未归档行。
    -   **实现**：Orchestrator负责确保最后一个任务的输出中没有未归档行。

2.  **上级标题关联有效性**：
    -   **规则 A (存在性与类型)**：每个Chunk（根节点除外）的`parent_id`必须指向一个数据库中已存在的、且`type`为`"heading"`的Chunk。
    -   **规则 B (层级正确性)**：
        -   `content`类型的Chunk可以归属到**任意级别**的`heading` Chunk。
        -   `heading`类型的Chunk必须归属到**层级比自己更高**的`heading` Chunk。即，`child.level`必须大于`parent.level` (假设H1=level 1, H2=level 2)。

3.  **校验失败处理**：
    -   如果校验失败，意味着LLM返回了不合规的输出。
    -   Agent应将此视为一个可重试的错误。它会**抛出一个异常**，并将详细的校验失败信息记录在日志中。

---

## 5. 错误处理与容错机制

### 5.1. 重试机制

-   **触发**：当Agent遇到校验失败、LLM API调用失败、网络超时等临时性错误时，它会通过抛出异常来表明任务失败。
-   **执行**：Dramatiq的Broker会自动捕获这个异常，并根据Actor上配置的`max_retries`和退避策略（backoff）进行重试。这为从临时故障中恢复提供了机会。

### 5.2. 持久性失败处理 - “哨兵Chunk” (Sentinel Chunk)

-   **场景**：当一个文本块经过所有重试后，仍然无法被Agent成功处理（例如，文本内容本身导致LLM持续崩溃或返回非法结构），我们不能让整个文档的处理流程被永久阻塞。
-   **解决方案**：
    1.  当Dramatiq的重试次数耗尽后，可以触发一个`on_failure`钩子或由Orchestrator捕获最终的失败状态。
    2.  系统将**自动创建一个特殊的“哨兵Chunk”**来标记这个无法处理的区域。
    3.  这个哨兵Chunk具有以下特征：
        -   `type`: `"error"`
        -   `level`: `-99` (一个易于查询和识别的魔法数字)
        -   `start_line`, `end_line`: 覆盖整个失败的文本块范围。
        -   `summary` 或 `raw_content`: 存入详细的错误信息，例如："Chunking failed after 3 retries. Last error: Invalid parent heading reference."
    4.  创建哨兵Chunk后，Orchestrator会认为这个区域的“处理”已结束，并继续调度后续文本块的任务。

-   **优势**：
    -   **不阻塞流程**：保证了整个文档可以被完整处理，不会因为一小块“毒药文本”而卡住。
    -   **问题可追溯**：通过查询`level = -99`的Chunk，可以轻松地定位到所有处理失败的数据，便于后续的人工干预或算法迭代。
