export interface IngestionJob {
    id: string;
    kb_id: string;
    document_id: string;
    status: IngestionJobStatus;
    created_at: string;
    updated_at: string;
    error_message?: string;
  }

  export enum IngestionJobStatus {
    PENDING = 'pending',
    RUNNING = 'running',
    COMPLETED = 'completed',
    FAILED = 'failed'
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