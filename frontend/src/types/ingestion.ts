export interface IngestionJob {
  id: string;
  kb_id: string;
  document_id: string;
  status: IngestionJobStatus;
  created_at: string;
  updated_at: string;
  error_message?: string;
  progress?: number; // 添加进度字段
}

export enum IngestionJobStatus {
  PENDING = 'pending',
  RUNNING = 'running',
  COMPLETED = 'completed',
  FAILED = 'failed',
  CANCELLED = 'cancelled' // 添加取消状态
}

export interface IngestionStartRequest {
  document_id: string;
}

export interface IngestionStartResponse {
  id: string;
  status: IngestionJobStatus;
  message: string;
}

export interface BatchIngestionRequest {
  document_ids: string[];
}

export interface BatchIngestionResponse {
  jobs: IngestionStartResponse[];
  success_count: number;
  failed_count: number;
}

// 添加文档状态接口
export interface DocumentJobStatus {
  document_id: string;
  job_id?: string;
  status: IngestionJobStatus;
  progress?: number;
  error_message?: string;
}

export interface IngestionJobListResponse {
  jobs: IngestionJob[];
  total: number;
}