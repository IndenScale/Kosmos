-- 移除凭证名称唯一约束
-- 文件: remove_credential_name_constraint.sql
-- 创建时间: 2025-07-26
-- 描述: 移除 model_access_credentials 表中的用户-凭证名称唯一约束，允许用户创建重复名称的凭证

-- 检查约束是否存在并删除
DO $$
BEGIN
    -- 检查约束是否存在
    IF EXISTS (
        SELECT 1
        FROM information_schema.table_constraints
        WHERE constraint_name = 'uq_user_credential_name'
        AND table_name = 'model_access_credentials'
    ) THEN
        -- 删除唯一约束
        ALTER TABLE model_access_credentials DROP CONSTRAINT uq_user_credential_name;
        RAISE NOTICE '已成功移除凭证名称唯一约束';
    ELSE
        RAISE NOTICE '凭证名称唯一约束不存在，无需移除';
    END IF;
END $$;