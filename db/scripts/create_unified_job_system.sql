-- 统一任务系统表结构
-- 创建时间: 2025-07-26
-- 描述: 支持解析、索引等多种任务类型的统一任务队列系统

-- 任务作业表 (Job - 高层级的业务任务)
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    kb_id TEXT NOT NULL,
    job_type TEXT NOT NULL,  -- 'parse', 'index', 'batch_parse', 'batch_index'
    status TEXT NOT NULL DEFAULT 'pending',  -- 'pending', 'running', 'completed', 'failed', 'cancelled'
    priority INTEGER NOT NULL DEFAULT 0,  -- 优先级，数字越大优先级越高

    -- 任务配置
    config TEXT,  -- JSON格式的任务配置

    -- 进度跟踪
    total_tasks INTEGER DEFAULT 0,
    completed_tasks INTEGER DEFAULT 0,
    failed_tasks INTEGER DEFAULT 0,

    -- 错误信息
    error_message TEXT,

    -- 时间戳
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    started_at DATETIME,
    completed_at DATETIME,

    -- 创建者
    created_by TEXT,

    FOREIGN KEY (kb_id) REFERENCES knowledge_bases(id) ON DELETE CASCADE,
    FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
);

-- 任务表 (Task - 具体的执行单元)
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL,
    task_type TEXT NOT NULL,  -- 'parse_document', 'index_fragment', 'batch_parse_documents', 'batch_index_fragments'
    status TEXT NOT NULL DEFAULT 'pending',  -- 'pending', 'running', 'completed', 'failed', 'cancelled'

    -- 任务目标
    target_id TEXT,  -- document_id 或 fragment_id
    target_type TEXT,  -- 'document', 'fragment'

    -- 任务配置
    config TEXT,  -- JSON格式的任务特定配置

    -- 执行信息
    worker_id TEXT,  -- 执行该任务的worker标识
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,

    -- 结果
    result TEXT,  -- JSON格式的执行结果
    error_message TEXT,

    -- 时间戳
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    started_at DATETIME,
    completed_at DATETIME,

    FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_jobs_kb_id ON jobs(kb_id);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_job_type ON jobs(job_type);
CREATE INDEX IF NOT EXISTS idx_jobs_priority ON jobs(priority);
CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON jobs(created_at);

CREATE INDEX IF NOT EXISTS idx_tasks_job_id ON tasks(job_id);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_task_type ON tasks(task_type);
CREATE INDEX IF NOT EXISTS idx_tasks_target_id ON tasks(target_id);
CREATE INDEX IF NOT EXISTS idx_tasks_target_type ON tasks(target_type);
CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON tasks(created_at);