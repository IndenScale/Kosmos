### **开发备忘录：实现多文档及知识空间Grep功能**

**日期:** 2025年9月11日
**状态:** 草案
**作者:** Agent

#### **1. 目标**

本项目旨在对Kosmos平台的`grep`功能进行系统性升级，将其从一个单文档查询工具扩展为一个强大的、支持多文档乃至整个知识空间范围的精确模式匹配引擎。此举旨在为Agent和用户在小规模知识集中提供一个比语义`search`更可靠、更具确定性的信息定位手段。

最终实现的命令语法为：
`kosmos grep <pattern> [--doc <doc_ref>...] [--ks <ks_ref>]`

#### **2. 核心设计原则**

*   **灵活性与易用性**: 用户可以通过ID或易于记忆的名称来指定文档（`--doc`）和知识空间（`--ks`）。
*   **向后兼容**: 原有的 `kosmos grep <pattern> <doc_id>` 语法将继续有效，以确保现有脚本和工作流不受影响。
*   **智能默认行为**: 当用户未指定 `--doc` 或 `--ks` 时，命令将默认在当前激活的知识空间范围内执行搜索，提升用户体验。
*   **责任分离**: **Kosmos CLI** 负责处理用户友好的输入（如名称解析），而 **Kosmos KB** 后端则专注于接收标准化的ID并高效执行核心`grep`任务。

#### **3. 各组件改造分析**

##### **3.1. Kosmos KB (后端) 改造分析**

后端的修改是本次升级的核心，需要提供一个全新的、统一的`grep`端点，并确保有支持名称解析的辅助接口。

*   **主要任务: 创建系统性Grep端点**
    *   **新增API路由**:
        *   在后端应用中创建一个新的API路由模块，例如 `backend/app/api/v1/endpoints/grep.py`。
        *   将此新路由注册到主FastAPI应用中（位于 `backend/app/main.py`）。
    *   **API端点设计**:
        *   **Endpoint**: `POST /api/v1/grep`
        *   **请求体 (Request Body)**:
            ```json
            {
              "pattern": "your_regex_pattern",
              "case_sensitive": false, // 可选
              "scope": {
                "doc_ids": ["uuid-1", "uuid-2"], // 与 ks_id 互斥
                "ks_id": "ks-uuid-1"             // 与 doc_ids 互斥
              }
            }
            ```
        *   **响应体 (Response Body)**:
            ```json
            {
              "summary": { "documents_searched": 10, "documents_with_matches": 2, "total_matches": 5 },
              "results": [
                {
                  "document_id": "uuid-1",
                  "document_name": "doc1.pdf",
                  "matches": [ { "match_line_number": 42, "lines": ["... line with match ..."] } ]
                },
                {
                  "document_id": "uuid-2",
                  "document_name": "doc2.docx",
                  "matches": [ { "match_line_number": 101, "lines": ["..."] }, { "match_line_number": 203, "lines": ["..."] } ]
                }
              ]
            }
            ```
    *   **核心实现逻辑**:
        1.  根据请求体中的`scope`，确定要搜索的文档ID列表。如果提供`ks_id`，则从数据库查询该知识空间下的所有文档。
        2.  **采用并行处理机制**（如线程池或异步任务），为每个目标文档启动一个独立的`grep`工作单元。
        3.  每个工作单元从MinIO拉取对应文档的范式化Markdown内容，执行正则表达式匹配。
        4.  聚合所有工作单元的结果，构建标准化的响应体并返回。

*   **辅助任务: 支持名称解析**
    *   需要确保或创建以下API，以供CLI进行名称到ID的转换：
        *   `GET /api/v1/knowledge-spaces?name=<ks_name>`: 根据名称查询知识空间。
        *   `GET /api/v1/documents?name=<doc_name>[&ks_id=<ks_id>]`: 根据名称查询文档，可选地在特定知识空间内查询以提高准确性。

##### **3.2. Kosmos CLI 改造分析**

CLI的改造重点在于实现新的命令参数、用户输入的解析逻辑以及与新后端端点的交互。

*   **文件定位**: 修改 `cli/main.py` 或可能存在的 `cli/commands/grep.py`。
*   **参数解析**:
    *   使用`argparse`（或项目使用的类似库）更新`grep`命令的解析器。
    *   添加 `--doc` 参数，并设置其可以接收多个值 (`nargs='+'`)。
    *   添加 `--ks` 参数。
    *   实现 `--doc` 和 `--ks` 的互斥逻辑。
    *   实现默认行为：如果两者均未提供，则将当前激活的知识空间ID用于后续查询。
*   **名称解析逻辑**:
    *   在执行`grep`命令的函数中，检查所有 `--doc` 和 `--ks` 的值。
    *   如果值不是UUID格式，则调用相应的后端辅助API（`GET /knowledge-spaces` 或 `GET /documents`）进行查询。
    *   **必须处理歧义**：如果名称解析返回0个或多个结果，应向用户报错并提供清晰的提示（例如，"文档名称 'report.docx' 不唯一，请使用ID指定"）。
*   **API调用与结果展示**:
    *   在所有引用都解析为ID后，构建 `POST /api/v1/grep` 的请求体。
    *   调用新端点，并接收响应。
    *   将返回的JSON数据格式化为人类可读的输出，清晰地展示每个匹配项来源的文档名和行号。

##### **3.3. Assessment Service 改造分析**

为了让Agent在评估会话中也能利用这一强大的新功能，Assessment Service作为Agent与KB之间的受控代理，也需要进行相应升级。

*   **任务: 扩展Agent接口**
    *   **新增API端点**: 在Assessment Service中增加一个新的代理端点，例如 `POST /agent/grep`。
    *   **请求与响应**: 此端点的请求和响应格式应与 `Kosmos KB` 的 `POST /api/v1/grep` 完全一致。
    *   **实现逻辑**:
        1.  接收来自 `kosmos agent grep ...` 命令的请求。
        2.  验证当前是否存在活动的评估会话。
        3.  **作为代理**，将收到的请求体直接转发给 `Kosmos KB` 的 `POST /api/v1/grep` 端点。
        4.  在会话的行动日志中记录此次`grep`操作，以保证可审计性。
        5.  将从KB收到的结果原样返回给CLI。
