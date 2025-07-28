export enum IndexStatus {
  PENDING = 'pending',
  PROCESSING = 'processing',
  COMPLETED = 'completed',
  FAILED = 'failed'
}

// 统一任务管理系统的响应类型
export interface JobResponse {
  job_id: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  created_at: string;
  updated_at: string;
  progress?: number;
  error_message?: string;
  result?: any;
}

export interface IndexRequest {
  force_regenerate?: boolean;
  max_tags?: number;
  // 为未来多模态索引预留字段
  enable_multimodal?: boolean;
  multimodal_config?: Record<string, any>;
}

export interface BatchIndexByFragmentsRequest {
  fragment_ids: string[];
  force_regenerate?: boolean;
  max_tags?: number;
  // 为未来多模态索引预留字段
  enable_multimodal?: boolean;
  multimodal_config?: Record<string, any>;
}

export interface BatchIndexByDocumentsRequest {
  document_ids: string[];
  force_regenerate?: boolean;
  max_tags?: number;
  // 为未来多模态索引预留字段
  enable_multimodal?: boolean;
  multimodal_config?: Record<string, any>;
}

// 保持向后兼容性的别名
export interface BatchIndexRequest extends BatchIndexByFragmentsRequest {}

export interface IndexResponse {
  id: string;
  kb_id: string;
  fragment_id: string;
  tags?: string[];
  content: string;
  created_at: string;
  updated_at: string;
}

export interface IndexJobResponse {
  job_id: string;
  kb_id: string;
  status: IndexStatus;
  total_fragments: number;
  processed_fragments: number;
  failed_fragments: number;
  error_message?: string;
  created_at: string;
  updated_at: string;
}

export interface IndexStatsResponse {
  kb_id: string;
  total_fragments: number;
  indexed_fragments: number;
  pending_fragments: number;
  vector_count: number;
  last_index_time?: string;
}

export interface IndexProgressResponse {
  job_id: string;
  status: IndexStatus;
  progress: number; // 0-100
  current_fragment?: string;
  estimated_remaining_time?: number; // seconds
  error_message?: string;
}

// 文档处理状态
export interface DocumentProcessStatus {
  document_id: string;
  parse_status: 'pending' | 'processing' | 'completed' | 'failed';
  index_status: IndexStatus;
  fragment_count: number;
  indexed_fragment_count: number;
  last_updated: string;
  error_message?: string;
  job_id?: string; // V1遗留字段，保留以避免报错
}

// 批量处理响应
export interface BatchProcessResponse {
  success_count: number;
  failed_count: number;
  results: DocumentProcessStatus[];
}