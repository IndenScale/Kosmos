# **备忘录：统一 `kosmos-cli` 的交互模式**

**致：** Kosmos 开发团队
**发件人：** Gemini
**日期：** 2025年9月9日
**主题：** 关于统一 `kosmos-cli` 交互模式的架构建议：从直接调用到任务框架代理

---

## 1. 背景与现状分析

目前，`kosmos-cli` 存在两种与后端服务交互的模式，这反映了其演进过程：

### 模式 A：直接命令模式 (Direct Command Mode)

-   **描述**: CLI 直接向 Kosmos KB (主后端) 的 API 端点发起请求并同步等待结果。
-   **示例**: `kosmos search`, `kosmos read`, `kosmos grep`, `kosmos documents list`。
-   **特点**:
    -   **优点**: 实时反馈，交互直接，非常适合快速、原子化的查询和数据检索操作。
    -   **缺点**: 无法处理长耗时、有状态或需要多步骤交互的复杂工作流。所有逻辑都封装在单个命令中。

### 模式 B：任务框架代理模式 (Task Framework Proxy Mode)

-   **描述**: CLI 通过向 **Assessment Service** (评估服务) 发起请求来启动一个“会话”（Session）。后续的所有操作（如 `search`, `read`）都作为该会話内的“行动”（Action），由评估服务**代理**执行。
-   **示例**: `kosmos assessment start-session`, `kosmos assessment add-evidence`。
-   **特点**:
    -   **优点**:
        1.  **状态管理**: 评估服务通过有限状态机（FSM）维护了任务的完整生命周期（`ASSESSING` -> `SUBMITTED` -> `COMPLETED`），这是直接命令模式无法做到的。
        2.  **审计与可追溯性**: 所有的“行动”都被记录在会话中，为 Agent 的行为提供了完整的审计日志。
        3.  **资源与安全约束**: 任务框架可以对行动施加限制（如 `action_limit`），防止 Agent 失控或滥用资源。
        4.  **解耦**: Agent (或 CLI 用户) 只需与评估服务这一个高级 API 交互，而无需关心底层 `kosmos-kb` 的复杂性。评估服务充当了一个智能代理层。
    -   **缺点**: 对于简单的查询操作，引入会话管理会增加额外的开销和复杂性。

## 2. 核心问题

我们已经实现了一个功能强大的任务框架（评估服务），但它的能力目前仅限于“评估”这一特定场景。而我们的日常调试和 Agent 开发工作，仍然依赖于功能相对简单、无状态的直接命令模式。

这导致了一个脱节：我们在调试 Agent 时使用的工具 (`kosmos search`, `grep`)，与 Agent 在真实任务中使用的环境（通过评估服务代理）**不一致**。

## 3. 架构演进建议：将 `assessment` 命令升级为通用的任务代理工具

我们不应该创建一个新的会话模式，而应该**强化现有的 `assessment` 模式**，使其成为一个功能完备的任务代理。

**核心思想**: 将所有对知识库的只读查询操作（`search`, `read`, `grep` 等）集成到 `assessment` 命令空间下，让它们作为会话内的“行动”被代理执行。

### 建议新增的 CLI 命令

1.  **`kosmos assessment search <query> [filters...]`**:
    -   **行为**: 在当前活动的评估会话（Session）内执行一次搜索。
    -   **后端交互**: 调用 Assessment Service 的一个新端点，如 `POST /api/v1/sessions/{session_id}/actions/search`。
    -   **收益**: 这次搜索操作将被记录为一个“行动”，计入 `action_count`，并且其参数和结果都可以被审计。

2.  **`kosmos assessment read <doc_ref> [options...]`**:
    -   **行为**: 在当前会话内读取一个文档或书签。
    -   **后端交互**: 调用 `POST /api/v1/sessions/{session_id}/actions/read`。
    -   **收益**: 记录 Agent 读取了哪些文档的哪些部分。

3.  **`kosmos assessment grep <pattern> <doc_id> [options...]`**:
    -   **行为**: 在当前会话内对指定文档执行 `grep` 操作。
    -   **后端交互**: 调用 `POST /api/v1/sessions/{session_id}/actions/grep`。
    -   **收益**: 精确记录 Agent 试图在文档中定位的关键信息。

### 4. 实现优势

-   **用户体验统一**: 用户和 Agent 开发者只需记住一个清晰的模式：
    -   要启动一个受控的任务 -> `kosmos assessment start-session`
    -   在任务中进行任何操作 -> `kosmos assessment <subcommand>`
    -   进行快速、无状态的查询 -> `kosmos <command>`
-   **开发成本可控**: 我们只需在 Assessment Service 中增加几个新的“行动”API 端点，这些端点的大部分逻辑可以直接复用现有的 `kosmos_client` 去调用 KB 后端。主要增加的是行动记录和边界检查的逻辑。
-   **立即获得价值**: 一旦实现，所有依赖 `assessment` 框架的 Agent 将立刻获得在一个完全受控、可审计的环境中进行搜索、读取和定位信息的能力。

### 5. 下一步行动

我们将按照以下顺序，逐步为 `assessment` 模块赋能：
1.  首先实现 `assessment search` 功能，因为它对于 Agent 的信息获取最为关键。
2.  接着实现 `assessment read` 和 `assessment grep`。
3.  更新 Agent 开发文档，指导开发者在评估会话中优先使用 `assessment` 前缀的命令。
