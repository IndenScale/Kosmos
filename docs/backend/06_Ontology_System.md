# 6. Kosmos 本体论系统 (Git-like)

Kosmos 的本体论（Ontology）系统是其实现结构化、可演进知识管理的核心功能之一。其设计深受版本控制系统（如 Git）的启发，为每个知识空间提供了一个强大、可追溯的本体论仓库。

## 核心概念

*   **本体论仓库 (`Ontology`)**: 每个知识空间有且仅有一个本体论仓库。它本身不存储具体的本体论结构，而是作为所有版本（Versions）的容器，并拥有一个指向当前活动版本的“指针”（`active_version_id`），类似于 Git 中的 `HEAD`。

*   **版本 (`OntologyVersion`)**: 代表本体论在某个时间点的一个完整快照，类似于一次“提交”（Commit）。每个版本都包含：
    *   `version_number`: 递增的版本号。
    *   `commit_message`: 本次变更的说明。
    *   `created_by_user_id`: 提交者的ID。
    *   `parent_version_id`: 指向其父版本，形成了版本历史链。
    *   `serialized_nodes`: **[性能优化]** 一个JSON字段，存储了该版本下整个本体论树的完整、反规范化结构。这使得读取当前本体论树的操作极为高效，无需遍历关系表进行重建。

*   **节点 (`OntologyNode`)**: 代表本体论中的一个具体概念。
    *   **`stable_id`**: 节点的**稳定标识符**。这是一个UUID，用于在**不同版本之间**跟踪同一个概念。即使一个概念的名称、属性或在树中的位置发生了变化，它的`stable_id`也保持不变。
    *   **`content_hash`**: 节点内容的哈希值（基于`name`, `constraints`, `node_metadata`计算）。用于快速识别内容完全相同的节点，为未来的节点去重和复用提供了可能。

*   **版本-节点链接 (`OntologyVersionNodeLink`)**: 这是连接`OntologyVersion`和`OntologyNode`的“胶水”。它定义了**在一个特定的版本中**，哪些节点存在，以及它们之间的父子层级关系（通过`parent_node_id`字段）。

## “写时复制”的变更机制

Kosmos 的本体论变更机制是整个设计的精髓。它不直接修改现有版本（版本是不可变的），而是通过一种“写时复制”（Copy-on-Write）的策略来创建一个新版本。这个过程由 `OntologyService` 中的 `_commit_new_version_from_changes` 方法实现。

**当用户发起一个变更（如添加、删除、移动节点）时，系统内部会执行以下原子性操作：**

1.  **获取父版本**: 找到当前知识空间的活动版本（`active_version`）作为父版本。
2.  **创建新版本记录**: 在 `ontology_versions` 表中创建一个新的记录，其 `version_number` 是父版本的版本号加一，并记录提交信息和作者。
3.  **复制链接**: 将父版本的所有 `OntologyVersionNodeLink` 记录**复制**一份，并将其中的 `version_id` 指向新创建的版本ID。至此，新版本在逻辑上是父版本的一个完整克隆。
4.  **应用变更**: 在这个**新的链接集合**上执行用户请求的变更操作：
    *   **添加节点**: 创建一个新的 `OntologyNode` 记录，并在新版本的链接集合中添加一条指向其父节点的 `OntologyVersionNodeLink` 记录。
    *   **删除节点**: 从新版本的链接集合中，删除目标节点及其所有后代节点的 `OntologyVersionNodeLink` 记录。
    *   **更新节点**: 创建一个新的 `OntologyNode` 记录（具有相同的 `stable_id` 但新的 `content_hash`），然后更新新版本链接集合中对应记录的 `node_id`，使其指向这个新节点。
    *   **移动节点**: 在新版本的链接集合中，修改目标节点的 `OntologyVersionNodeLink` 记录，将其 `parent_node_id` 更新为新的父节点ID。
5.  **重建快照**: 在所有变更应用完毕后，系统会根据新版本的链接集合，在内存中完整地重建出新的本体论树结构。
6.  **序列化并存储**: 将重建的树序列化为JSON，并存入新版本记录的 `serialized_nodes` 字段中。
7.  **更新“HEAD”**: 将 `Ontology` 仓库的 `active_version_id` 指针更新为新版本的ID。

这个过程确保了：
*   **历史不可变**: 任何历史版本都可以被随时检出（check out）和审查。
*   **操作原子性**: 整个变更过程在一个数据库事务中完成。
*   **高效读取**: 读取操作直接访问 `serialized_nodes` JSON字段，速度极快。

## 服务接口 (`OntologyService`)

`OntologyService` 为上层应用提供了简洁的接口来操作本体论，隐藏了底层复杂的版本控制逻辑。

*   `get_active_ontology_tree()`: 获取当前知识空间的活动本体论树（直接读取快照）。
*   `add_node()`, `update_node()`, `move_node()`, `delete_node()`: 这些方法接收简单的业务参数（如父节点ID、新节点数据等），在内部将其转换为变更指令，并调用 `_commit_new_version_from_changes` 引擎来创建一个新版本。
*   `commit_version_from_json_tree()`: 这是一个更高级的接口，它允许客户端提交一个完整的本体论树JSON对象。服务会自动将其与当前版本进行**差异比较（diff）**，计算出必要的原子变更（add, update, move, delete），然后调用提交引擎。这为实现图形化的本体论编辑器提供了极大的便利。
