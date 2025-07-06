-- 修复chunks表的tags字段为可空
-- 这是为了支持skip_tagging功能，允许chunks在没有标签的情况下存储

-- SQLite不支持直接修改列的约束，需要重新创建表
BEGIN TRANSACTION;

-- 1. 备份现有数据
CREATE TABLE chunks_backup AS SELECT * FROM chunks;

-- 2. 删除原表
DROP TABLE chunks;

-- 3. 重新创建表（tags字段允许为NULL）
CREATE TABLE chunks (
    id TEXT PRIMARY KEY,
    kb_id TEXT NOT NULL,
    document_id TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    tags TEXT,  -- 现在允许为NULL
    page_screenshot_ids TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (kb_id) REFERENCES knowledge_bases(id),
    FOREIGN KEY (document_id) REFERENCES documents(id)
);

-- 4. 恢复数据
INSERT INTO chunks SELECT * FROM chunks_backup;

-- 5. 删除备份表
DROP TABLE chunks_backup;

COMMIT;

-- 验证表结构
PRAGMA table_info(chunks); 