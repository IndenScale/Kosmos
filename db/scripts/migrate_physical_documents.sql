-- 迁移 physical_documents 表结构
-- 添加新字段并移除 file_path 字段

BEGIN TRANSACTION;

-- 1. 创建新的临时表，包含所有新字段
CREATE TABLE physical_documents_new (
    content_hash TEXT PRIMARY KEY,
    mime_type TEXT NOT NULL,
    extension TEXT(20) NOT NULL,  -- 扩展长度到20
    url TEXT NOT NULL,  -- 新字段，替代 file_path
    file_size INTEGER NOT NULL DEFAULT 0,  -- 新字段
    reference_count INTEGER NOT NULL DEFAULT 1,
    encoding TEXT,  -- 新字段，可选
    language TEXT,  -- 新字段，可选
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP  -- 新字段
);

-- 2. 创建索引
CREATE INDEX idx_physical_documents_content_hash ON physical_documents_new(content_hash);
CREATE INDEX idx_physical_documents_mime_type ON physical_documents_new(mime_type);

-- 3. 迁移现有数据（如果表存在）
INSERT INTO physical_documents_new (
    content_hash, 
    mime_type, 
    extension, 
    url,  -- 将 file_path 转换为 file:/// URL
    file_size,
    reference_count,
    created_at
)
SELECT 
    content_hash,
    mime_type,
    extension,
    'file:///' || file_path as url,  -- 转换路径为 file:/// URL
    COALESCE(file_size, 0) as file_size,  -- 如果字段不存在则默认为0
    COALESCE(reference_count, 1) as reference_count,
    COALESCE(created_at, CURRENT_TIMESTAMP) as created_at
FROM physical_documents
WHERE EXISTS (SELECT name FROM sqlite_master WHERE type='table' AND name='physical_documents');

-- 4. 删除旧表（如果存在）
DROP TABLE IF EXISTS physical_documents;

-- 5. 重命名新表
ALTER TABLE physical_documents_new RENAME TO physical_documents;

-- 6. 创建触发器以自动更新 updated_at 字段
CREATE TRIGGER update_physical_documents_updated_at 
    AFTER UPDATE ON physical_documents
    FOR EACH ROW
BEGIN
    UPDATE physical_documents 
    SET updated_at = CURRENT_TIMESTAMP 
    WHERE content_hash = NEW.content_hash;
END;

COMMIT;

-- 验证迁移结果
SELECT 'Migration completed. Table structure:' as message;
PRAGMA table_info(physical_documents);

SELECT 'Sample data (first 5 rows):' as message;
SELECT content_hash, mime_type, extension, url, file_size, reference_count, created_at, updated_at 
FROM physical_documents 
LIMIT 5;