# Kosmos 代理与系统框架解析

本文档旨在阐明 Kosmos 平台的核心组件、它们之间的交互方式，以及关键的内部工作机制。

## 1. Kosmos 整体框架

Kosmos 平台是一个采用现代**事件驱动**和分布式架构的复杂系统，主要由四个核心部分构成：**Kosmos知识库 (KB)**、**事件中继 (Event Relay)**、**任务触发器 (Triggers)** 和 **任务执行单元 (Actors)**。

### 1.1. 核心组件

#### a. Kosmos 知识库 (KB) - 后端 (`backend`)

这是系统的核心，扮演着数据、逻辑和事实的唯一来源。

-   **功能**:
    -   **数据持久化**: 使用SQL数据库（如PostgreSQL或SQLite）存储所有元数据，包括文档、用户、知识空间、分块、作业和**领域事件**。
    -   **对象存储**: 通过MinIO管理所有二进制文件。
    -   **向量存储**: 利用Milvus对文本分块进行向量化索引。
    -   **API服务**: 暴露一个主RESTful API (`main.py`)，供CLI和其他服务进行交互。
    -   **事件生成**: 在核心业务逻辑（如文档注册）的数据库事务中，原子性地创建**领域事件**并将其存入`domain_events`表（**事务性发件箱模式**）。
-   **交互**: KB是所有其他组件的中心枢纽。CLI直接与其API交互。它负责产生所有变化的“事实”（领域事件），但不直接调用后台任务。

#### b. 事件与任务系统 (Event & Task System)

这是一个高度解耦的分布式系统，负责协调和执行所有后台任务。它由三个关键角色组成：

1.  **事件中继 (Event Relay)**
    -   **角色**: 这是一个独立的后台进程，是**事务性发件箱模式**的另一半。
    -   **功能**: 定期轮询数据库中的`domain_events`表，将状态为`pending`的事件发布到Redis的发布/订阅（Pub/Sub）频道中，然后将事件状态更新为`processed`。
    -   **交互**: 从KB的数据库读取，向Redis发布消息。

2.  **任务触发器 (Triggers)**
    -   **角色**: 多个独立的后台进程，每个进程都订阅一个或多个特定的Redis频道。
    -   **功能**: 监听Redis频道中的事件消息。当接收到一个它关心的事件时（例如，`content_extraction_trigger`监听到`DocumentRegistered`事件），它的职责是**创建一个具体的工作票据（Job）**并将其存入数据库。
    -   **交互**: 从Redis订阅消息，向KB的数据库写入`Job`记录，并将`Job ID`发送到Dramatiq任务队列。

3.  **任务执行单元 (Actors / Workers)**
    -   **角色**: 这是系统的“劳动力”，是执行具体任务的Dramatiq工作进程。
    -   **功能**: 监听Dramatiq任务队列（同样由Redis支持）。当获取到一个`Job ID`时，它会从数据库加载`Job`的详细信息，并执行所有耗时和计算密集型的任务（如格式转换、内容提取、分块、索引等）。
    -   **交互**: 从Dramatiq队列获取任务，从KB读取执行任务所需的数据，并通过API更新`Job`的状态。**任务完成后，Actor可能会产生新的领域事件**，从而触发后续的处理流程。

#### c. Kosmos 命令行接口 (CLI)

这是用户或自动化代理与Kosmos平台交互的主要入口。

-   **功能**:
    -   **用户接口**: 提供一套丰富的命令，用于管理知识空间、上传文档、执行搜索等。
    -   **交互**: CLI是命令的发起者。它只与核心KB的API或专用服务（如`assessment_service`）的API进行通信，**从不直接与后台任务系统交互**。

### 1.2. 环境与工作流程

#### 事件驱动的文档摄入流程

此流程展示了系统如何通过事件驱动的链式反应来处理文档。

1.  **用户/代理** 通过 `kosmos upload` 命令使用 **CLI** 上传一个文档。
2.  **CLI** 将文件发送到 **Kosmos KB** 的 `POST /documents/upload` API端点。
3.  **KB 后端服务 (`IngestionService`)** 在一个**数据库事务**中执行以下操作：
    a.  处理容器文件（如`.docx`），提取所有内嵌文档。
    b.  对父文档和所有子文档进行**内容去重**，创建或获取`Original`记录。
    c.  为每个文档创建`Document`记录，并建立父子关联。
    d.  为每个新注册的文档，在`domain_events`表中创建一个类型为`DocumentRegisteredPayload`的**领域事件**，状态为`pending`。
    e.  **原子性地提交事务**。此时，文档和待处理的事件被一同持久化。
4.  **事件中继 (Event Relay)** 进程在下一次轮询时：
    a.  从`domain_events`表中查询到这个`pending`的事件。
    b.  根据路由规则，将该事件发布到Redis的`kosmos:events:registration`频道。
    c.  更新数据库中该事件的状态为`processed`。
5.  **内容提取触发器 (Content Extraction Trigger)** 进程：
    a.  它正在监听`kosmos:events:registration`频道，并接收到该事件。
    b.  根据事件内容（`document_id`, `initiator_id`等），在数据库中创建一个类型为`CONTENT_EXTRACTION`的`Job`记录。
    c.  将新创建的`Job ID`发送到Dramatiq的`content_extraction`任务队列。
6.  一个空闲的 **任务执行单元 (Content Extraction Actor)**：
    a.  从`content_extraction`队列中获取该`Job ID`。
    b.  从数据库加载`Job`详情，开始执行内容提取管道（LibreOffice -> MinerU -> Serializer）。
    c.  处理完成后，在一个数据库事务中：
        i.  更新`Job`状态为`completed`。
        ii. **创建一个新的领域事件**，类型为`DocumentContentExtractedPayload`，并存入`domain_events`表。
7.  **链式反应开始**:
    a.  **事件中继**再次检测到这个新的`DocumentContentExtracted`事件，并将其发布到`kosmos:events:ingestion`频道。
    b.  **分块触发器 (Chunking Trigger)** 和 **资产分析触发器 (Asset Analysis Trigger)** 都在监听此频道。它们会各自被激活，分别为该文档创建`CHUNKING`和`ASSET_ANALYSIS`类型的`Job`。
    c.  这个过程会一直持续下去（`Chunking` -> `Indexing`），直到整个文档摄入管道完成。

---

## 2. Kosmos KB 核心实现细节

### 2.1. 内容去重存储

Kosmos在多个层面实施了基于SHA256哈希的内容去重，以最大化存储效率和数据一致性。

-   **原始文件 (`Originals`)**:
    -   当一个文件被上传时，系统首先计算其完整内容的SHA256哈希。
    -   `originals` 表以 `original_hash` 作为唯一键。如果哈希已存在，则仅增加该记录的 `reference_count` 计数，而不会在MinIO中重复存储文件。
    -   一个新的 `documents` 记录仍会被创建，但它会指向已存在的`Original`实体。

-   **范式化内容 (`CanonicalContents`)**:
    -   在文档摄入管道中，从原始文件提取出的核心文本内容被序列化为统一的Markdown格式。
    -   系统计算这个Markdown文本的SHA256哈希。
    -   `canonical_contents` 表以 `content_hash` 作为唯一键。与原始文件类似，如果范式化内容已存在，则新的`Document`记录会链接到已存在的`CanonicalContent`实体，避免了重复存储。

-   **资产 (`Assets`)**:
    -   从文档中提取的每个资产（如图片、表格转换的图片）同样会被计算SHA256哈希。
    -   `assets` 表以 `asset_hash` 作为唯一键，实现了与上述机制相同的去重逻辑。

这种设计确保了无论一个相同内容的文件或资产被上传多少次、出现在多少个文档中，其二进制数据在对象存储中只存在一份。

### 2.2. 文档摄入管道

文档摄入是一个由后台任务服务器执行的、健壮的、多阶段的**事件驱动**异步流程。它旨在将异构的原始文档转化为结构化、可搜索的知识。

1.  **触发 (事件: `DocumentRegistered`)**:
    -   **执行者**: `content_extraction` actor。
    -   **逻辑**: 当一个文档被注册后，此actor被触发以开始处理。

2.  **格式转换 (VRD -> PDF)**:
    -   **逻辑**: 对于非PDF的Office文档（如`.docx`, `.pptx`），系统调用 **LibreOffice** 的命令行接口，将其无头转换为标准化的PDF格式。这个PDF是后续所有提取步骤的权威输入源。
    -   **产物**: 一个标准化的PDF文件，存储在MinIO的`kosmos-pdfs`桶中。

3.  **内容提取 (PDF -> 结构化JSON)**:
    -   **逻辑**: 使用 **MinerU** 工具处理标准化的PDF。MinerU利用视觉语言模型（VLM）来解析文档布局，提取文本、表格、图片，并理解它们的逻辑关系。
    -   **产物**:
        -   `_content_list.json`: 一个包含页面所有元素（文本块、图片路径、表格HTML）及其坐标和元数据的结构化JSON文件。
        -   `images/` 目录: 包含从PDF中提取的所有图片。

4.  **资产处理与文本序列化**:
    -   **逻辑**: `serializer.py`模块负责处理`_content_list.json`和`images/`目录。
        -   它遍历所有图片，为每个图片计算哈希，创建或更新`Asset`记录（实现去重），并上传到MinIO。
        -   它将JSON中的元素（文本、表格HTML、**资产引用URI**）转换为一个单一的、干净的Markdown文件。
        -   在此过程中，系统会生成`ContentPageMapping`记录，精确地将Markdown中的**每一行**映射回原始PDF的**页码**。
    -   **产物**:
        -   一个范式化的Markdown文件，存储在`kosmos-canonical-contents`桶。
        -   一系列`ContentPageMapping`数据库记录。
        -   一系列`Asset`和`DocumentAssetContext`数据库记录。

5.  **触发下游 (事件: `DocumentContentExtracted`)**:
    -   **逻辑**: 内容提取成功后，actor会创建一个`DocumentContentExtracted`领域事件。
    -   **结果**: 此事件会同时被**资产分析触发器**和**分块触发器**捕获，并行启动后续处理。

6.  **资产分析 (事件: `AssetAnalysisCompleted`)**:
    -   **执行者**: `analyze_asset` actor。
    -   **逻辑**: (并行任务) 为文档中的每个资产调用VLM生成详细的文本描述。完成后，创建`AssetAnalysisCompleted`事件。

7.  **文本分割 (Chunking) (事件: `DocumentChunkingCompleted`)**:
    -   **执行者**: `chunk_document` actor。
    -   **逻辑**: (并行任务) 读取范式化的Markdown文件，将其分割成语义化的`Chunks`。完成后，创建`DocumentChunkingCompleted`事件。

8.  **向量索引 (事件: `DocumentIndexingCompleted` - 假设)**:
    -   **执行者**: `indexing` actor。
    -   **逻辑**: 监听到`DocumentChunkingCompleted`事件后，获取文档的所有`Chunks`，调用嵌入模型生成向量，并存入Milvus。

### 2.3. 任务协调机制：事务性发件箱模式

Kosmos使用**领域事件**、**事件中继**和**Dramatiq**构建了一个高度可靠和解耦的后台任务协调系统。

-   **生产者 (核心API)**: 后端API服务是事件的唯一生产者。当核心业务状态发生变化时（如文档被注册），它**在同一个数据库事务中**创建一个`DomainEvent`记录。这保证了业务状态和“通知”的原子性。
-   **发件箱 (Outbox - `domain_events`表)**: `domain_events`表充当了一个可靠的“发件箱”。即使消息系统出现故障，事件也安全地存储在数据库中，不会丢失。
-   **中继 (Event Relay)**: 这是一个独立的进程，负责将“发件箱”中的事件安全地发布到**Redis Pub/Sub**，并标记事件为已处理。它将数据库与消息系统解耦。
-   **消费者 (Triggers & Actors)**:
    -   **Triggers**: 监听Redis频道的轻量级进程，负责将事件转化为具体的`Job`。
    -   **Actors**: Dramatiq的worker进程，负责执行`Job`所定义的繁重任务。

任务的依赖关系如下

文档注册 <- 内容提取
内容提取 <- 文本分割
文本分割 <- 分块索引
内容提取 <- 资产分析

这种“**状态变更与事件创建在同一事务，事件发布与任务执行在后台**”的模式，确保了系统的最终一致性和极高的容错能力。

### 2.4. 内容访问方式

Kosmos KB提供了三种互补的内容访问方式，以满足不同场景的需求。

1.  **搜索 (Search)**:
    -   **接口**: `POST /api/v1/search/`
    -   **机制**: 这是最主要的知识发现方式。它采用一种混合搜索策略：
        a.  **向量召回**: 将用户查询转换为向量，在Milvus中进行语义相似度搜索，找出内容上最相关的分块。
        b.  **关键词召回**: 同时，使用数据库的全文检索引擎进行关键词匹配。
        c.  **重排序与过滤**: 对两路召回的结果进行合并、去重和重排序，并应用用户指定的过滤器。
    -   **适用场景**: 当用户不确定信息在何处，需要基于自然语言问题或关键词进行探索性查询时。

2.  **模式匹配 (Grep)**:
    -   **接口**: `POST /api/v1/documents/{document_id}/grep`
    -   **机制**: 提供在**单个指定文档**的范式化内容中执行**正则表达式**搜索的能力。
    -   **适用场景**: 当用户已经知道信息在哪个文档中，需要根据精确的文本模式来定位具体位置时。

3.  **定位读取 (Read)**:
    -   **接口**: `GET /api/v1/contents/{doc_ref}`
    -   **机制**: 提供对文档范式化内容进行**精确范围读取**的能力。
        -   **精确定位**: 用户可以指定起止**行号**或**百分比**来读取文档的任意片段。
        -   **元数据丰富**: 返回的内容不仅包含文本，还包括该文本片段关联的资产信息和其在原始PDF中的**页码**。
    -   **适用场景**:
        -   在通过“搜索”或“Grep”定位到信息的初始位置后，用于阅读上下文。
        -   通过书签直接跳转到文档的关键部分。
---
## 3. Kosmos CLI 开发备忘录

本文档为 `kosmos` 命令行接口（CLI）的开发者提供核心设计原则与实践指南，旨在确保CLI的可扩展性、一致性和对自动化Agent的友好性。

### 3.1. 鉴权方案 (Authentication Scheme)

CLI采用双模认证系统，以同时满足人类用户和自动化Agent的需求。所有认证逻辑由 `cli.knowledge_base_client.KosmosClient` 统一处理。

#### a. 用户会话模式 (User Session Mode)

-   **目标用户**: 人类开发者、管理员。
-   **触发方式**: 用户执行 `kosmos login` 命令。
-   **机制**:
    1.  CLI通过 `POST /api/v1/auth/token` 端点，使用用户名和密码换取有时效性的 **Access Token** 和长期有效的 **Refresh Token**。
    2.  这两个Token被安全地存储在用户主目录下的 `~/.kosmos/credentials` 文件中。该文件权限被设为 `600` (仅所有者可读写)。
    3.  在执行后续命令时，`KosmosClient` 会自动加载Access Token。如果Token过期，它会自动使用Refresh Token调用 `/api/v1/auth/token/refresh` 端点获取新的Access Token，对用户透明。
-   **开发者须知**: 在命令的 `run` 函数中，您无需关心Token的管理。只需使用传入的 `client` 实例调用API方法即可。

#### b. Agent/服务账户模式 (Agent/Service Account Mode)

-   **目标用户**: 自动化脚本、CI/CD流水线、其他后台服务。
-   **触发方式**: 在环境中设置 `KOSMOS_API_KEY` 环境变量。
-   **机制**:
    1.  `KosmosClient` 在初始化时会优先检查 `KOSMOS_API_KEY` 环境变量。
    2.  如果该变量存在，客户端将**忽略** `~/.kosmos/credentials` 文件，并直接使用此API Key作为Bearer Token进行所有API请求。
    3.  API Key是长期的，需要用户在后端（未来实现的UI或特定API）生成并妥善保管。
-   **开发者须知**: 此模式对命令代码完全透明。

### 3.2. 输出与可视化方案 (Output & Visualization Strategy)

**核心原则：为机器而非人类设计 (Design for Machines, Not Humans)。**

CLI的主要用户是Agent和自动化脚本，因此，输出格式必须是结构化的、可预测的和易于解析的。

-   **标准输出 (`stdout`)**:
    -   **默认格式**: 所有成功的命令执行结果**必须**以格式化的JSON字符串输出到 `stdout`。
    -   **实现方式**: 在命令的 `run` 函数中，调用 `cli.utils.print_json_response()` 辅助函数来打印最终的API结果。
-   **标准错误 (`stderr`)**:
    -   所有非结果性的信息，如进度提示（例如 "正在登录..."）、警告、错误信息，都**必须**输出到 `stderr`。
    -   这确保了 `stdout` 的纯净性，使得Agent可以通过管道（pipe）或重定向轻松地捕获JSON结果，例如 `kosmos ks list > spaces.json`。
-   **人类可读性**:
    -   如果未来需要提供人类可读的表格化输出，它**必须**通过一个明确的标志（例如 `--pretty` 或 `--human-readable`）来启用，绝不能成为默认行为。

### 3.3. 新命令集成 (New Command Integration)

CLI采用动态模块加载机制，添加新命令无需修改核心入口文件 (`main.py`)。

-   **步骤**:
    1.  在 `cli/commands/` 目录下创建一个新的Python文件（例如 `my_command.py`）。
    2.  在该文件中，定义一个 `register_subparser` 函数。此函数接收 `subparsers` 对象和 `parent_parser` 对象，负责定义命令的名称、别名、帮助文本和参数。
    3.  为命令的每个动作定义一个 `run_*` 函数（例如 `run_list`, `run_create`）。
    4.  **函数签名**: `run` 函数必须遵循 `(client: KosmosClient, args, config: CliConfig)` 的签名。`client` 是已认证的API客户端实例，`args` 是解析后的命令行参数，`config` 是配置处理器。
    5.  在 `register_subparser` 中，使用 `parser.set_defaults(func=run_...)` 将每个子命令与其对应的 `run` 函数绑定。

### 3.4. 配置注入 (Configuration Injection)

命令的参数（如 `ks_id`）通过一个统一的配置注入系统来解析，该系统具有明确的优先级。

-   **优先级顺序**:
    1.  **命令行参数**: (最高) 例如 `--ks-id <uuid>`。
    2.  **环境变量**: 例如 `export KOSMOS_KS_ID=<uuid>`。
    3.  **.env 文件**: 在项目根目录下的 `.env` 文件中定义的变量。
-   **实现方式**:
    -   在命令的 `run` 函数中，使用注入的 `config: CliConfig` 对象来获取参数值。
    -   调用 `config.require(args.ks_id, "KOSMOS_KS_ID", "知识空间ID")`。
    -   此函数会按照上述优先级顺序查找值。如果所有来源都未提供该值，它会自动向用户报告错误并退出，简化了命令内部的参数校验逻辑。

## 网络安全评估系统

网络安全评估系统是使用Kosmos框架开发的第一个实用程序。它由知识库、评估服务与智能体三个子系统组成。

Kosmos知识库用于存储评估证据，为Agent提供便利、多样、规范的证据访问。
评估人员需要先在Kosmos知识库进行注册，创建知识空间，配置模型凭证，上传证据，评估智能体才能进行评估。

评估服务负责管理网络安全评估的生命周期。包括评估框架创建、评估控制项导入、评估作业创建、评估作业调度、评估报告导出等。
在创建评估作业时，需要提供有效的评估框架与Kosmos知识空间。调度评估作业时，需要提供有效的驱动Agent的模型凭证。

智能体负责具体执行评估。在评估时，它会首先将作业分解为多个批次，然后分别启动回话执行评估。在每个回话中，Agent会使用grep，read命令，灵活地在Kosmos知识库中寻找证据，根据评估框架与控制项，提交证据与发现，并最终将会话提交，等待评估人员审核。