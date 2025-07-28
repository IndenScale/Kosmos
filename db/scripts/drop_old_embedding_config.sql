-- 删除知识库表中的旧embedding_config字段
-- 文件: drop_old_embedding_config.sql
-- 创建时间: 2025-07-26
-- 描述: 在确认数据迁移成功后，删除knowledge_bases表中的embedding_config字段
-- 警告: 请在执行前确保数据已成功迁移到新的表结构中！

-- 1. 备份embedding_config数据（可选，建议执行）
CREATE TABLE IF NOT EXISTS embedding_config_backup AS
SELECT id, embedding_config, created_at as backup_time
FROM knowledge_bases
WHERE embedding_config IS NOT NULL
AND embedding_config != '{}'
AND embedding_config != '';

-- 2. 检查备份表是否创建成功
DO $$
DECLARE
    backup_count INTEGER;
    original_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO backup_count FROM embedding_config_backup;
    SELECT COUNT(*) INTO original_count FROM knowledge_bases
    WHERE embedding_config IS NOT NULL
    AND embedding_config != '{}'
    AND embedding_config != '';

    RAISE NOTICE '原始embedding_config记录数: %', original_count;
    RAISE NOTICE '备份记录数: %', backup_count;

    IF backup_count != original_count THEN
        RAISE EXCEPTION '备份记录数与原始记录数不匹配，请检查备份！';
    END IF;
END $$;

-- 3. 验证新表结构是否正确
DO $$
DECLARE
    kb_count INTEGER;
    config_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO kb_count FROM knowledge_bases;
    SELECT COUNT(*) INTO config_count FROM kb_model_configs;

    RAISE NOTICE '知识库总数: %', kb_count;
    RAISE NOTICE '模型配置记录数: %', config_count;

    IF config_count < kb_count THEN
        RAISE EXCEPTION '模型配置记录数少于知识库数量，请先完成数据迁移！';
    END IF;
END $$;

-- 4. 删除embedding_config字段
-- 注意：这是不可逆操作，请确保已完成数据迁移和验证
ALTER TABLE knowledge_bases DROP COLUMN IF EXISTS embedding_config;

-- 5. 验证字段是否已删除
DO $$
DECLARE
    column_exists BOOLEAN;
BEGIN
    SELECT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'knowledge_bases'
        AND column_name = 'embedding_config'
    ) INTO column_exists;

    IF column_exists THEN
        RAISE EXCEPTION 'embedding_config字段删除失败！';
    ELSE
        RAISE NOTICE '✓ embedding_config字段已成功删除';
    END IF;
END $$;

-- 6. 添加注释记录此次变更
COMMENT ON TABLE knowledge_bases IS '知识库表 - 已于2025-07-26迁移embedding_config到独立的模型配置表';

PRINT '旧embedding_config字段删除完成！';
PRINT '备份数据保存在embedding_config_backup表中，如需要可以查看。';