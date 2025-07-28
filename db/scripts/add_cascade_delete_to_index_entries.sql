-- 为 index_entries 表的 fragment_id 外键添加 CASCADE DELETE 约束
-- 文件: add_cascade_delete_to_index_entries.sql
-- 创建时间: 2025-07-26
-- 描述: 修复外键约束问题，确保删除 fragments 时自动删除相关的 index_entries

-- 1. 首先检查当前的外键约束
SELECT
    tc.constraint_name,
    tc.table_name,
    kcu.column_name,
    ccu.table_name AS foreign_table_name,
    ccu.column_name AS foreign_column_name,
    rc.delete_rule
FROM
    information_schema.table_constraints AS tc
    JOIN information_schema.key_column_usage AS kcu
      ON tc.constraint_name = kcu.constraint_name
      AND tc.table_schema = kcu.table_schema
    JOIN information_schema.constraint_column_usage AS ccu
      ON ccu.constraint_name = tc.constraint_name
      AND ccu.table_schema = tc.table_schema
    JOIN information_schema.referential_constraints AS rc
      ON tc.constraint_name = rc.constraint_name
      AND tc.table_schema = rc.constraint_schema
WHERE tc.constraint_type = 'FOREIGN KEY'
  AND tc.table_name = 'index_entries'
  AND kcu.column_name = 'fragment_id';

-- 2. 删除现有的外键约束（如果存在）
DO $$
DECLARE
    constraint_name_var TEXT;
BEGIN
    -- 查找现有的 fragment_id 外键约束名称
    SELECT tc.constraint_name INTO constraint_name_var
    FROM information_schema.table_constraints AS tc
    JOIN information_schema.key_column_usage AS kcu
      ON tc.constraint_name = kcu.constraint_name
    WHERE tc.constraint_type = 'FOREIGN KEY'
      AND tc.table_name = 'index_entries'
      AND kcu.column_name = 'fragment_id';

    -- 如果找到约束，则删除它
    IF constraint_name_var IS NOT NULL THEN
        EXECUTE 'ALTER TABLE index_entries DROP CONSTRAINT ' || constraint_name_var;
        RAISE NOTICE '已删除现有外键约束: %', constraint_name_var;
    ELSE
        RAISE NOTICE '未找到现有的 fragment_id 外键约束';
    END IF;
END $$;

-- 3. 添加新的外键约束，包含 CASCADE DELETE
ALTER TABLE index_entries
ADD CONSTRAINT fk_index_entries_fragment_id
FOREIGN KEY (fragment_id)
REFERENCES fragments(id)
ON DELETE CASCADE;

-- 4. 验证新的外键约束
SELECT
    tc.constraint_name,
    tc.table_name,
    kcu.column_name,
    ccu.table_name AS foreign_table_name,
    ccu.column_name AS foreign_column_name,
    rc.delete_rule
FROM
    information_schema.table_constraints AS tc
    JOIN information_schema.key_column_usage AS kcu
      ON tc.constraint_name = kcu.constraint_name
      AND tc.table_schema = kcu.table_schema
    JOIN information_schema.constraint_column_usage AS ccu
      ON ccu.constraint_name = tc.constraint_name
      AND ccu.table_schema = tc.table_schema
    JOIN information_schema.referential_constraints AS rc
      ON tc.constraint_name = rc.constraint_name
      AND tc.table_schema = rc.constraint_schema
WHERE tc.constraint_type = 'FOREIGN KEY'
  AND tc.table_name = 'index_entries'
  AND kcu.column_name = 'fragment_id';

-- 5. 添加注释
COMMENT ON CONSTRAINT fk_index_entries_fragment_id ON index_entries IS
'外键约束：当删除 fragments 时自动删除相关的 index_entries，解决解析时的外键约束违反问题';

RAISE NOTICE '✅ index_entries 表的 fragment_id 外键约束已更新为 CASCADE DELETE';