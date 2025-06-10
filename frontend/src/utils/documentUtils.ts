import { DocumentRecord, DocumentStatus } from '../types/document';
import { IngestionJobStatus, DocumentJobStatus } from '../types/ingestion';

/**
 * 获取文档状态
 */
export const getDocumentStatus = (
  document: DocumentRecord,
  documentJobStatuses: Map<string, DocumentJobStatus>,
  lastTagDirectoryUpdateTime?: string
): DocumentStatus => {
  const jobStatus = documentJobStatuses.get(document.document_id);

  // 检查是否正在处理中
  if (jobStatus && (
    jobStatus.status === IngestionJobStatus.PENDING ||
    jobStatus.status === IngestionJobStatus.RUNNING
  )) {
    return DocumentStatus.INGESTING;
  }

  // 检查是否已摄取
  if (document.chunk_count && document.chunk_count > 0) {
    // 检查是否过时
    if (lastTagDirectoryUpdateTime && document.last_ingest_time) {
      const lastIngestTime = new Date(document.last_ingest_time);
      const lastUpdateTime = new Date(lastTagDirectoryUpdateTime);
      if (lastUpdateTime > lastIngestTime) {
        return DocumentStatus.OUTDATED;
      }
    }
    return DocumentStatus.INGESTED;
  }

  return DocumentStatus.NOT_INGESTED;
};

/**
 * 获取任务进度
 */
export const getJobProgress = (
  documentId: string,
  documentJobStatuses: Map<string, DocumentJobStatus>
): number | undefined => {
  const jobStatus = documentJobStatuses.get(documentId);
  return jobStatus?.progress;
};

/**
 * 检查文档是否过时
 */
export const isDocumentOutdated = (
  document: DocumentRecord,
  lastTagDirectoryUpdateTime?: string
): boolean => {
  if (!lastTagDirectoryUpdateTime || !document.last_ingest_time) {
    return false;
  }

  const lastIngestTime = new Date(document.last_ingest_time);
  const lastUpdateTime = new Date(lastTagDirectoryUpdateTime);
  return lastUpdateTime > lastIngestTime;
};

/**
 * 格式化文件大小
 */
export const formatFileSize = (bytes: number): string => {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
};