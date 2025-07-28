-- 创建模型访问凭证相关表的迁移脚本
-- 文件: create_model_credential_tables.sql
-- 创建时间: 2025-07-26
-- 描述: 创建模型访问凭证表和知识库模型配置表，替换原有的embedding_config字段

-- 1. 创建模型访问凭证表
CREATE TABLE IF NOT EXISTS model_access_credentials (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL,
    name VARCHAR(255) NOT NULL,
    provider VARCHAR(50) NOT NULL,
    api_key_encrypted TEXT NOT NULL,
    base_url VARCHAR(1024),
    description TEXT,
    is_active VARCHAR(10) NOT NULL DEFAULT 'true',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- 外键约束
    CONSTRAINT fk_mac_user_id FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,

    -- 唯一约束：同一用户不能有重名的凭证
    CONSTRAINT uq_user_credential_name UNIQUE (user_id, name)
);

-- 2. 创建知识库模型配置表
CREATE TABLE IF NOT EXISTS kb_model_configs (
    id VARCHAR(36) PRIMARY KEY,
    kb_id VARCHAR(36) NOT NULL UNIQUE,

    -- Embedding 配置
    embedding_model_name VARCHAR(100) NOT NULL DEFAULT 'text-embedding-3-small',
    embedding_credential_id VARCHAR(36),

    -- Reranker 配置
    reranker_model_name VARCHAR(100),
    reranker_credential_id VARCHAR(36),

    -- LLM 配置
    llm_model_name VARCHAR(100) NOT NULL DEFAULT 'gpt-4-turbo-preview',
    llm_credential_id VARCHAR(36),

    -- VLM 配置
    vlm_model_name VARCHAR(100),
    vlm_credential_id VARCHAR(36),

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- 外键约束
    CONSTRAINT fk_kmc_kb_id FOREIGN KEY (kb_id) REFERENCES knowledge_bases(id) ON DELETE CASCADE,
    CONSTRAINT fk_kmc_embedding_cred FOREIGN KEY (embedding_credential_id) REFERENCES model_access_credentials(id) ON DELETE SET NULL,
    CONSTRAINT fk_kmc_reranker_cred FOREIGN KEY (reranker_credential_id) REFERENCES model_access_credentials(id) ON DELETE SET NULL,
    CONSTRAINT fk_kmc_llm_cred FOREIGN KEY (llm_credential_id) REFERENCES model_access_credentials(id) ON DELETE SET NULL,
    CONSTRAINT fk_kmc_vlm_cred FOREIGN KEY (vlm_credential_id) REFERENCES model_access_credentials(id) ON DELETE SET NULL,

    -- 唯一约束：每个知识库只能有一个模型配置
    CONSTRAINT uq_kb_model_config UNIQUE (kb_id)
);

-- 3. 创建索引以提高查询性能
CREATE INDEX IF NOT EXISTS idx_mac_user_id ON model_access_credentials(user_id);
CREATE INDEX IF NOT EXISTS idx_mac_provider ON model_access_credentials(provider);
CREATE INDEX IF NOT EXISTS idx_mac_is_active ON model_access_credentials(is_active);

CREATE INDEX IF NOT EXISTS idx_kmc_kb_id ON kb_model_configs(kb_id);
CREATE INDEX IF NOT EXISTS idx_kmc_embedding_cred ON kb_model_configs(embedding_credential_id);
CREATE INDEX IF NOT EXISTS idx_kmc_reranker_cred ON kb_model_configs(reranker_credential_id);
CREATE INDEX IF NOT EXISTS idx_kmc_llm_cred ON kb_model_configs(llm_credential_id);
CREATE INDEX IF NOT EXISTS idx_kmc_vlm_cred ON kb_model_configs(vlm_credential_id);

-- 4. 添加注释
COMMENT ON TABLE model_access_credentials IS '模型访问凭证表，存储用户的AI模型API访问凭证';
COMMENT ON COLUMN model_access_credentials.api_key_encrypted IS '加密后的API Key，不能明文存储';
COMMENT ON COLUMN model_access_credentials.provider IS '服务提供商：openai, azure, cohere, local等';
COMMENT ON COLUMN model_access_credentials.is_active IS '是否启用，使用字符串避免布尔类型问题';

COMMENT ON TABLE kb_model_configs IS '知识库模型配置表，存储知识库使用的具体模型配置';
COMMENT ON COLUMN kb_model_configs.embedding_model_name IS '嵌入模型名称，如text-embedding-3-small';
COMMENT ON COLUMN kb_model_configs.llm_model_name IS 'LLM模型名称，用于摘要、标签生成等任务';
COMMENT ON COLUMN kb_model_configs.vlm_model_name IS '视觉语言模型名称，用于图像处理';

-- 5. 为现有知识库创建默认模型配置
INSERT INTO kb_model_configs (id, kb_id, embedding_model_name, llm_model_name)
SELECT
    gen_random_uuid()::text,
    id,
    'text-embedding-3-small',
    'gpt-4-turbo-preview'
FROM knowledge_bases
WHERE id NOT IN (SELECT kb_id FROM kb_model_configs);

PRINT '模型访问凭证相关表创建完成！';