export interface PhysicalFile {
  id: string;
  filename: string;
  file_type: string;
  file_size: number;
  file_path: string;
  created_at: string;
}

export interface Document {
  id: string;
  filename: string;
  file_type: string;
  file_size: number;
  file_path: string;
  created_at: string;
}

export interface DocumentRecord {
  document_id: string;
  kb_id: string;
  uploaded_by: string;
  upload_at: string;
  last_ingest_time?: string;
  chunk_count?: number;
  document: Document;
  uploader_username?: string;
  is_outdated?: boolean;
}

export interface DocumentListResponse {
  documents: DocumentRecord[];
  total: number;
  page: number;
  size: number;
}

export interface DocumentUploadRequest {
  file: File;
}

export interface DocumentUploadResponse {
  id: string;
  filename: string;
  file_type: string;
  file_size: number;
  created_at: string;
}

export interface DocumentDeleteResponse {
  message: string;
  success: boolean;
}

// 选择状态枚举
export enum SelectionState {
  NONE = 'none',       // 未选择
  PARTIAL = 'partial', // 部分选择
  PAGE = 'page',       // 本页全选
  ALL = 'all'          // 全部选择
}

// 文档状态枚举
export enum DocumentStatus {
  NOT_INGESTED = 'not_ingested',
  INGESTING = 'ingesting',
  INGESTED = 'ingested',
  INGESTED_NOT_TAGGED = 'ingested_not_tagged',  // 已摄入但未标注
  TAGGING = 'tagging',                         // 标注中
  TAGGED = 'tagged',                           // 已标注
  OUTDATED = 'outdated',                       // 标签过时
  TAGGING_OUTDATED = 'tagging_outdated'        // 标注过时
}

// 文档操作类型
export enum DocumentAction {
  PREVIEW = 'preview',
  DOWNLOAD = 'download',
  INGEST = 'ingest',
  TAG = 'tag',           // 标注
  RETAG = 'retag',       // 重新标注
  DELETE = 'delete'
}

// 批量操作类型
export enum BatchAction {
  DOWNLOAD = 'download',
  INGEST = 'ingest',
  TAG = 'tag',           // 批量标注
  DELETE = 'delete'
}