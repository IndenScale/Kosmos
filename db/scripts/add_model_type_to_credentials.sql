-- 添加 model_type 字段到 model_access_credentials 表
-- 文件: add_model_type_to_credentials.sql
-- 创建时间: 2025-07-26
-- 描述: 为模型访问凭证表添加 model_type 字段 (PostgreSQL 版本)

-- 添加 model_type 字段
ALTER TABLE model_access_credentials
ADD COLUMN model_type VARCHAR(20);

-- 为现有记录设置默认值（如果有的话）
UPDATE model_access_credentials
SET model_type = 'embedding'
WHERE model_type IS NULL;

-- 设置字段为非空
ALTER TABLE model_access_credentials
ALTER COLUMN model_type SET NOT NULL;

-- 添加检查约束确保只能是有效的模型类型
ALTER TABLE model_access_credentials
ADD CONSTRAINT chk_model_type
CHECK (model_type IN ('embedding', 'reranker', 'llm', 'vlm'));

-- 创建索引以提高查询性能
CREATE INDEX IF NOT EXISTS idx_credentials_user_model_type
ON model_access_credentials(user_id, model_type);