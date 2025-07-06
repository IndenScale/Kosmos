-- 创建SDTM任务表
CREATE TABLE IF NOT EXISTS sdtm_jobs (
    id VARCHAR(36) PRIMARY KEY,
    kb_id VARCHAR(36) NOT NULL,
    mode VARCHAR(20) NOT NULL,
    batch_size INTEGER DEFAULT 10,
    auto_apply BOOLEAN DEFAULT TRUE,
    status VARCHAR(20) DEFAULT 'pending',
    task_id VARCHAR(36),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    error_message TEXT,
    result TEXT,
    FOREIGN KEY (kb_id) REFERENCES knowledge_bases(id)
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_sdtm_jobs_kb_id ON sdtm_jobs(kb_id);
CREATE INDEX IF NOT EXISTS idx_sdtm_jobs_status ON sdtm_jobs(status);
CREATE INDEX IF NOT EXISTS idx_sdtm_jobs_created_at ON sdtm_jobs(created_at);
CREATE INDEX IF NOT EXISTS idx_sdtm_jobs_task_id ON sdtm_jobs(task_id); 