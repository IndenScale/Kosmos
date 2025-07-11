-- 原始文档表 (全局唯一)
CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,          -- 文件内容的 SHA256 哈希值
    filename TEXT NOT NULL,       -- 上传时的原始文件名
    file_type TEXT NOT NULL,      -- MIME 类型
    file_size INTEGER NOT NULL,   -- 文件大小 (bytes)
    file_path TEXT NOT NULL UNIQUE, -- 在本地文件系统的存储路径
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 知识库-文档关联表
CREATE TABLE IF NOT EXISTS kb_documents (
    kb_id TEXT NOT NULL,
    document_id TEXT NOT NULL,      -- 关联到 documents(id)
    uploaded_by TEXT NOT NULL,      -- 关联到 users(id)
    upload_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (kb_id, document_id),
    FOREIGN KEY (kb_id) REFERENCES knowledge_bases(id) ON DELETE CASCADE,
    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
    FOREIGN KEY (uploaded_by) REFERENCES users(id)
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_documents_created_at ON documents(created_at);
CREATE INDEX IF NOT EXISTS idx_kb_documents_kb_id ON kb_documents(kb_id);
CREATE INDEX IF NOT EXISTS idx_kb_documents_uploaded_by ON kb_documents(uploaded_by);