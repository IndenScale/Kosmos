-- Fragment和Index表性能优化索引
-- 文件: optimize_fragment_index_performance.sql
-- 创建时间: 2025-07-26
-- 描述: 针对搜索服务的关键查询路径添加索引，压缩搜索延迟

-- ========================================
-- 1. Fragment表索引优化
-- ========================================

-- 为Fragment表的document_id添加索引（如果不存在）
-- 用于快速查找文档的所有Fragment
CREATE INDEX IF NOT EXISTS idx_fragments_document_id
ON fragments(document_id);

-- 为Fragment表的fragment_type添加索引
-- 用于按类型过滤Fragment（text, screenshot, figure）
CREATE INDEX IF NOT EXISTS idx_fragments_type
ON fragments(fragment_type);

-- 为Fragment表的content_hash添加索引（如果不存在）
-- 用于快速查找相同内容的Fragment
CREATE INDEX IF NOT EXISTS idx_fragments_content_hash
ON fragments(content_hash);

-- 复合索引：document_id + fragment_type
-- 用于同时按文档和类型过滤的查询
CREATE INDEX IF NOT EXISTS idx_fragments_doc_type
ON fragments(document_id, fragment_type);

-- 复合索引：fragment_type + created_at
-- 用于按类型和时间排序的查询
CREATE INDEX IF NOT EXISTS idx_fragments_type_created
ON fragments(fragment_type, created_at);

-- ========================================
-- 2. Index表索引优化
-- ========================================

-- 为Index表的kb_id添加索引（如果不存在）
-- 这是搜索服务中最频繁的查询条件
CREATE INDEX IF NOT EXISTS idx_index_entries_kb_id
ON index_entries(kb_id);

-- 为Index表的fragment_id添加索引（如果不存在）
-- 用于Fragment和Index的JOIN查询
CREATE INDEX IF NOT EXISTS idx_index_entries_fragment_id
ON index_entries(fragment_id);

-- 复合索引：kb_id + fragment_id
-- 这是搜索服务中最关键的查询路径
CREATE INDEX IF NOT EXISTS idx_index_entries_kb_fragment
ON index_entries(kb_id, fragment_id);

-- 复合索引：kb_id + created_at
-- 用于按知识库和时间排序的查询
CREATE INDEX IF NOT EXISTS idx_index_entries_kb_created
ON index_entries(kb_id, created_at);

-- ========================================
-- 3. KBFragment表索引优化
-- ========================================

-- 为KBFragment表的kb_id添加索引（如果不存在）
-- 用于快速查找知识库的所有Fragment
CREATE INDEX IF NOT EXISTS idx_kb_fragments_kb_id
ON kb_fragments(kb_id);

-- 为KBFragment表的fragment_id添加索引（如果不存在）
-- 用于反向查找Fragment属于哪些知识库
CREATE INDEX IF NOT EXISTS idx_kb_fragments_fragment_id
ON kb_fragments(fragment_id);

-- 复合索引：kb_id + added_at
-- 用于按知识库和添加时间排序的查询
CREATE INDEX IF NOT EXISTS idx_kb_fragments_kb_added
ON kb_fragments(kb_id, added_at);

-- ========================================
-- 4. 针对搜索服务的特殊优化索引
-- ========================================

-- 为Fragment表的meta_info字段创建GIN索引（PostgreSQL特有）
-- 用于快速查询JSON字段中的activated状态
-- 注意：这个索引只在PostgreSQL中有效，SQLite会忽略
CREATE INDEX IF NOT EXISTS idx_fragments_meta_info_gin
ON fragments USING GIN (meta_info);

-- 为Index表的tags字段创建索引
-- 用于标签相关的查询和过滤
CREATE INDEX IF NOT EXISTS idx_index_entries_tags
ON index_entries(tags);

-- ========================================
-- 5. 覆盖索引优化（减少回表查询）
-- ========================================

-- 覆盖索引：包含搜索服务常用的所有字段
-- 这个索引可以避免回表查询，直接从索引中获取所有需要的数据
CREATE INDEX IF NOT EXISTS idx_index_entries_search_coverage
ON index_entries(kb_id, fragment_id, content, tags, created_at, updated_at);

-- Fragment表的覆盖索引
-- 包含搜索结果中需要的Fragment字段
CREATE INDEX IF NOT EXISTS idx_fragments_search_coverage
ON fragments(id, document_id, fragment_type, meta_info, created_at, updated_at);

-- ========================================
-- 6. 统计信息更新
-- ========================================

-- 更新表的统计信息以帮助查询优化器选择最佳执行计划
-- 注意：这些命令在不同数据库中语法可能不同

-- PostgreSQL语法
-- ANALYZE fragments;
-- ANALYZE index_entries;
-- ANALYZE kb_fragments;

-- SQLite语法
-- ANALYZE fragments;
-- ANALYZE index_entries;
-- ANALYZE kb_fragments;

-- ========================================
-- 7. 索引创建完成提示
-- ========================================

-- 输出创建完成的消息
SELECT 'Fragment和Index表性能优化索引创建完成！' as message;

-- 显示创建的索引列表
SELECT
    'idx_fragments_document_id' as index_name,
    'fragments表document_id索引' as description
UNION ALL
SELECT 'idx_fragments_type', 'fragments表fragment_type索引'
UNION ALL
SELECT 'idx_fragments_content_hash', 'fragments表content_hash索引'
UNION ALL
SELECT 'idx_fragments_doc_type', 'fragments表复合索引(document_id, fragment_type)'
UNION ALL
SELECT 'idx_fragments_type_created', 'fragments表复合索引(fragment_type, created_at)'
UNION ALL
SELECT 'idx_index_entries_kb_id', 'index_entries表kb_id索引'
UNION ALL
SELECT 'idx_index_entries_fragment_id', 'index_entries表fragment_id索引'
UNION ALL
SELECT 'idx_index_entries_kb_fragment', 'index_entries表复合索引(kb_id, fragment_id)'
UNION ALL
SELECT 'idx_index_entries_kb_created', 'index_entries表复合索引(kb_id, created_at)'
UNION ALL
SELECT 'idx_kb_fragments_kb_id', 'kb_fragments表kb_id索引'
UNION ALL
SELECT 'idx_kb_fragments_fragment_id', 'kb_fragments表fragment_id索引'
UNION ALL
SELECT 'idx_kb_fragments_kb_added', 'kb_fragments表复合索引(kb_id, added_at)'
UNION ALL
SELECT 'idx_fragments_meta_info_gin', 'fragments表meta_info GIN索引'
UNION ALL
SELECT 'idx_index_entries_tags', 'index_entries表tags索引'
UNION ALL
SELECT 'idx_index_entries_search_coverage', 'index_entries表搜索覆盖索引'
UNION ALL
SELECT 'idx_fragments_search_coverage', 'fragments表搜索覆盖索引';