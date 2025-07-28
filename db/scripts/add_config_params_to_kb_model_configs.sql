-- 为 kb_model_configs 表添加各种模型类型的配置参数字段
-- 用于存储不同模型类型的调用参数（JSON格式）
-- 移除旧的通用config_params字段，改为使用分离的字段

-- 移除旧的config_params字段（如果存在）
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'kb_model_configs' 
        AND column_name = 'config_params'
    ) THEN
        ALTER TABLE kb_model_configs DROP COLUMN config_params;
        RAISE NOTICE '已移除旧的 config_params 字段';
    ELSE
        RAISE NOTICE '旧的 config_params 字段不存在，无需移除';
    END IF;
END $$;

-- 检查并添加 embedding_config_params 字段
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'kb_model_configs' 
        AND column_name = 'embedding_config_params'
    ) THEN
        ALTER TABLE kb_model_configs 
        ADD COLUMN embedding_config_params TEXT DEFAULT '{}';
        
        RAISE NOTICE '已成功添加 embedding_config_params 字段到 kb_model_configs 表';
    ELSE
        RAISE NOTICE 'embedding_config_params 字段已存在于 kb_model_configs 表中';
    END IF;
END $$;

-- 检查并添加 reranker_config_params 字段
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'kb_model_configs' 
        AND column_name = 'reranker_config_params'
    ) THEN
        ALTER TABLE kb_model_configs 
        ADD COLUMN reranker_config_params TEXT DEFAULT '{}';
        
        RAISE NOTICE '已成功添加 reranker_config_params 字段到 kb_model_configs 表';
    ELSE
        RAISE NOTICE 'reranker_config_params 字段已存在于 kb_model_configs 表中';
    END IF;
END $$;

-- 检查并添加 llm_config_params 字段
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'kb_model_configs' 
        AND column_name = 'llm_config_params'
    ) THEN
        ALTER TABLE kb_model_configs 
        ADD COLUMN llm_config_params TEXT DEFAULT '{}';
        
        RAISE NOTICE '已成功添加 llm_config_params 字段到 kb_model_configs 表';
    ELSE
        RAISE NOTICE 'llm_config_params 字段已存在于 kb_model_configs 表中';
    END IF;
END $$;

-- 检查并添加 vlm_config_params 字段
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'kb_model_configs' 
        AND column_name = 'vlm_config_params'
    ) THEN
        ALTER TABLE kb_model_configs 
        ADD COLUMN vlm_config_params TEXT DEFAULT '{}';
        
        RAISE NOTICE '已成功添加 vlm_config_params 字段到 kb_model_configs 表';
    ELSE
        RAISE NOTICE 'vlm_config_params 字段已存在于 kb_model_configs 表中';
    END IF;
END $$;

-- 为新字段添加注释
COMMENT ON COLUMN kb_model_configs.embedding_config_params IS 'Embedding模型配置参数，JSON格式存储调用参数如dimensions等';
COMMENT ON COLUMN kb_model_configs.reranker_config_params IS 'Reranker模型配置参数，JSON格式存储调用参数如top_n等';
COMMENT ON COLUMN kb_model_configs.llm_config_params IS 'LLM模型配置参数，JSON格式存储调用参数如temperature、max_tokens等';
COMMENT ON COLUMN kb_model_configs.vlm_config_params IS 'VLM模型配置参数，JSON格式存储调用参数如max_tokens、detail等';

-- 验证字段添加结果
SELECT 
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns 
WHERE table_name = 'kb_model_configs' 
AND column_name IN ('embedding_config_params', 'reranker_config_params', 'llm_config_params', 'vlm_config_params')
ORDER BY column_name;