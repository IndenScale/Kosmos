# 5. Kosmos AI 服务集成

Kosmos 的核心价值之一是其与多种AI服务的深度集成能力。为了实现灵活、可扩展且易于管理的AI服务调用，系统设计了一套完善的凭证管理、路由和服务提供者机制。

## 凭证管理 (`ModelCredential`)

系统的AI凭证管理具有以下特点：

1.  **用户所有权**: `ModelCredential` 记录直接与 `User` 关联 (`owner_id`)，而不是与知识空间绑定。这意味着用户只需创建一次凭证（例如，他们的OpenAI API Key），就可以在他们有权访问的多个知识空间中复用。

2.  **凭证类型 (`CredentialType`)**: 凭证被明确分类，例如：
    *   `VLM` (视觉语言模型)
    *   `LLM` (大语言模型)
    *   `EMBEDDING` (嵌入模型)
    *   `SLM` (小语言模型，通常用于低成本任务如Chunking)
    *   这使得系统可以根据任务类型精确地选择合适的凭证。

3.  **安全存储**: API Key等敏感信息通过 `security.py` 中的 `encrypt_api_key` 函数进行对称加密后存储在 `encrypted_api_key` 字段中，确保了数据库层面的安全。

4.  **用户默认凭证**: 用户可以为每种 `CredentialType` 设置一个 `is_default` 为 `True` 的凭证。当AI调用发生在用户个人上下文中（例如，用户直接请求分析某个资产，但未指定知识空间）时，系统会使用这个默认凭证。

## 知识空间凭证授权与路由

虽然凭证由用户拥有，但它们的使用场景通常是在特定的知识空间内。`KnowledgeSpaceModelCredentialLink` 表实现了这一授权和路由逻辑。

*   **链接机制**: 知识空间的管理员（`owner`或`editor`）可以将任何他们有权访问的 `ModelCredential` 链接到该知识空间。
*   **优先级 (`priority_level`)**: 数字**越大**，优先级越高。当为特定任务（如VLM分析）选择凭证时，系统会首先选择优先级最高的凭证。
*   **权重 (`weight`)**: 在同一优先级内，权重越高的凭证被选中的概率越大。这为未来实现基于权重的**负载均衡**或**A/B测试**提供了基础。

**示例场景**:
一个知识空间可以同时配置一个高成本、高质量的GPT-4 Vision模型（优先级0，权重1）和一个低成本的内部VLM模型（优先级1，权重10）。默认情况下，所有VLM任务都会路由到内部模型。当需要高质量分析时，可以临时将GPT-4的优先级调高。

## AIProviderService：智能客户端工厂

`services/ai_provider_service.py` 中的 `AIProviderService` 是整个AI服务集成的核心。它扮演着一个智能客户端工厂的角色，负责根据上下文选择最合适的凭证并实例化一个功能完备的AI客户端（目前主要是 `openai.OpenAI` 客户端）。

### `get_client()` 方法

这是最常用的方法，它根据**知识空间ID**和**任务类型**（`CredentialType`）来获取客户端。

**工作流程**:
1.  查询 `KnowledgeSpaceModelCredentialLink` 表，找出所有与该知识空间ID和凭证类型匹配的链接。
2.  如果没有找到任何链接，则抛出异常。
3.  在所有找到的链接中，确定最高的 `priority_level`。
4.  筛选出所有处于最高优先级的链接。
5.  根据这些顶级链接的 `weight` 进行加权随机抽样，选出一个最终的 `ModelCredential`。
6.  解密凭证中的 `encrypted_api_key`。
7.  根据凭证的 `model_family` (如 `openai`) 和 `base_url` (如果提供)，实例化并返回一个配置好的 `OpenAI` 客户端。

### `get_default_client_for_user()` 方法

此方法用于获取用户特定类型的默认客户端，不依赖于知识空间。

### 凭证查找链 (Credential Lookup Chain)

在 `tasks/asset_analyzing.py` 的 `_get_vlm_client_with_fallback` 函数中，我们看到了一个非常鲁棒的凭证查找链，这体现了系统的设计思想：

1.  **尝试知识空间**: 首先，尝试使用 `knowledge_space_id` 通过 `AIProviderService.get_client()` 获取凭证。这是最优先的、与上下文最相关的选择。
2.  **回退到用户默认**: 如果在知识空间中找不到合适的凭证（例如，知识空间尚未配置VLM凭证），系统会**自动回退**，尝试使用 `user_id` 通过 `AIProviderService.get_default_client_for_user()` 获取该用户的默认VLM凭证。
3.  **失败**: 如果两种尝试都失败了，则任务失败。

这个查找链确保了AI功能的最大可用性：优先使用知识空间的特定配置，但在配置缺失时，仍然可以利用用户的个人默认配置来完成任务。

## 实践案例：资产分析任务 (`analyze_figure_asset`)

`tasks/asset_analyzing.py` 中的 `analyze_figure_asset` actor是这套机制的完美实践：

1.  任务被触发时，接收 `asset_id`, `user_id`, `knowledge_space_id` 等参数。
2.  调用 `_get_vlm_client_with_fallback` 来获取一个VLM客户端，这个过程对任务本身是透明的。
3.  从Minio下载图片，转换为Base64编码。
4.  使用获取到的客户端调用VLM API进行分析。
5.  将分析结果（描述文本）存入Redis缓存，以供后续快速读取，并避免重复分析。
6.  同时，将完整的分析生命周期信息记录到 `AssetAnalysisTask` 表中，用于审计和调试。
7.  更新 `Asset` 表的 `analysis_status` 字段。
