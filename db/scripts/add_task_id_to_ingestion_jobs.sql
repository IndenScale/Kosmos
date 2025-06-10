-- 为 ingestion_jobs 表添加 task_id 字段的迁移脚本
-- 执行日期: 2024年

-- 添加 task_id 字段
ALTER TABLE ingestion_jobs ADD COLUMN task_id TEXT;

-- 为新字段创建索引（可选，用于查询优化）
CREATE INDEX IF NOT EXISTS idx_ingestion_jobs_task_id ON ingestion_jobs(task_id);

-- 验证表结构
.schema ingestion_jobs