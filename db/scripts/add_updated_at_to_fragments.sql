-- 为 fragments 表添加 updated_at 字段
-- 文件: add_updated_at_to_fragments.sql
-- 创建时间: 2025-07-26
-- 描述: 添加缺失的 updated_at 字段到 fragments 表

-- 添加 updated_at 字段（如果不存在）
ALTER TABLE fragments ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;

-- 为现有记录设置 updated_at 为 created_at 的值
UPDATE fragments SET updated_at = created_at WHERE updated_at IS NULL;

-- 创建触发器函数来自动更新 updated_at 字段
CREATE OR REPLACE FUNCTION update_fragments_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 删除旧触发器（如果存在）
DROP TRIGGER IF EXISTS trigger_update_fragments_updated_at ON fragments;

-- 创建新触发器
CREATE TRIGGER trigger_update_fragments_updated_at
    BEFORE UPDATE ON fragments
    FOR EACH ROW
    EXECUTE FUNCTION update_fragments_updated_at();