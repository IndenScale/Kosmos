-- 清空所有表数据的SQL脚本
-- 创建时间: 2025-01-27
-- 描述: 清空Kosmos数据库中所有表的数据，保留表结构
-- 注意: 按照外键依赖关系的逆序删除数据

-- 禁用外键约束检查（PostgreSQL）
SET session_replication_role = replica;

-- 清空任务相关表（子表先删除）
TRUNCATE TABLE tasks CASCADE;
TRUNCATE TABLE jobs CASCADE;

-- 清空摄入相关表
TRUNCATE TABLE ingestion_jobs CASCADE;
TRUNCATE TABLE chunks CASCADE;

-- 清空文档相关表
TRUNCATE TABLE kb_documents CASCADE;
TRUNCATE TABLE documents CASCADE;

-- 清空知识库模型配置表
TRUNCATE TABLE kb_model_configs CASCADE;

-- 清空模型访问凭证表
TRUNCATE TABLE model_access_credentials CASCADE;

-- 清空知识库表
TRUNCATE TABLE knowledge_bases CASCADE;

-- 清空用户表
TRUNCATE TABLE users CASCADE;

-- 清空其他可能存在的表
TRUNCATE TABLE fragments CASCADE;
TRUNCATE TABLE index_entries CASCADE;
TRUNCATE TABLE credentials CASCADE;

-- 重新启用外键约束检查
SET session_replication_role = DEFAULT;

-- 重置序列（如果有自增ID）
-- ALTER SEQUENCE users_id_seq RESTART WITH 1;
-- ALTER SEQUENCE knowledge_bases_id_seq RESTART WITH 1;

SELECT 'All tables have been cleared successfully!' AS result;