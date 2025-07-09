import { DocumentRecord, DocumentStatus } from '../types/document';
import { IngestionJobStatus, DocumentJobStatus } from '../types/ingestion';

/**
 * 获取文档状态
 */
export const getDocumentStatus = (
  document: DocumentRecord,
  documentJobStatuses: Map<string, DocumentJobStatus>,
  lastTagDirectoryUpdateTime?: string,
  ingestionStats?: {
    total_chunks: number;
    tagged_chunks: number;
    untagged_chunks: number;
    tagging_completion_rate: number;
  },
  taggingJobStatuses?: Map<string, any> // 标注任务状态
): DocumentStatus => {
  const jobStatus = documentJobStatuses.get(document.document_id);
  const taggingJobStatus = taggingJobStatuses?.get(document.document_id);

  // 检查是否正在标注中
  if (taggingJobStatus && (
    taggingJobStatus.status === 'pending' ||
    taggingJobStatus.status === 'running'
  )) {
    return DocumentStatus.TAGGING;
  }

  // 检查是否正在摄取中
  if (jobStatus && (
    jobStatus.status === IngestionJobStatus.PENDING ||
    jobStatus.status === IngestionJobStatus.RUNNING
  )) {
    return DocumentStatus.INGESTING;
  }

  // 检查是否已摄取
  if (document.chunk_count && document.chunk_count > 0) {
    // 检查是否过时（摄取层面）
    if (lastTagDirectoryUpdateTime && document.last_ingest_time) {
      const lastIngestTime = new Date(document.last_ingest_time);
      const lastUpdateTime = new Date(lastTagDirectoryUpdateTime);
      if (lastUpdateTime > lastIngestTime) {
        return DocumentStatus.OUTDATED;
      }
    }

    // 如果有摄入统计信息，进一步判断标注状态
    if (ingestionStats) {
      // 简化判断：如果有未标注的chunks，说明需要标注
      if (ingestionStats.untagged_chunks > 0) {
        return DocumentStatus.INGESTED_NOT_TAGGED;
      }
      
      // 如果标注完成率很高，认为已标注
      if (ingestionStats.tagging_completion_rate > 90) {
        // 检查标注是否过时
        if (lastTagDirectoryUpdateTime && document.last_ingest_time) {
          const lastIngestTime = new Date(document.last_ingest_time);
          const lastUpdateTime = new Date(lastTagDirectoryUpdateTime);
          if (lastUpdateTime > lastIngestTime) {
            return DocumentStatus.TAGGING_OUTDATED;
          }
        }
        return DocumentStatus.TAGGED;
      }
      
      // 部分标注的情况，可能需要补充标注
      return DocumentStatus.INGESTED_NOT_TAGGED;
    }

    // 没有摄入统计信息时，默认认为是已摄取状态
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