import { DocumentRecord, DocumentStatus } from '../types/document';
import { DocumentProcessStatus, IndexStatus } from '../types/index';

/**
 * 获取文档状态
 */
export const getDocumentStatus = (
  document: DocumentRecord,
  documentProcessStatuses: Map<string, DocumentProcessStatus>,
  lastTagDirectoryUpdateTime?: string,
  indexStats?: {
    total_fragments: number;
    indexed_fragments: number;
    pending_fragments: number;
    vector_count: number;
    last_index_time?: string;
  }
): DocumentStatus => {
  const processStatus = documentProcessStatuses.get(document.document_id);

  // 如果有处理状态信息，基于实际的fragment和index数量判断
  if (processStatus) {
    const { fragment_count, indexed_fragment_count } = processStatus;
    
    // 如果没有fragment，说明文档未解析
    if (fragment_count === 0) {
      return DocumentStatus.NOT_INGESTED;
    }
    
    // 如果有fragment但没有index，说明正在索引或等待索引
    if (indexed_fragment_count === 0) {
      return DocumentStatus.INGESTING;
    }
    
    // 如果fragment数量等于index数量，说明索引完成
    if (fragment_count === indexed_fragment_count) {
      // 检查是否过时
      if (lastTagDirectoryUpdateTime && processStatus.last_updated) {
        const lastProcessTime = new Date(processStatus.last_updated);
        const lastUpdateTime = new Date(lastTagDirectoryUpdateTime);
        if (lastUpdateTime > lastProcessTime) {
          return DocumentStatus.OUTDATED;
        }
      }
      return DocumentStatus.INGESTED;
    }
    
    // 如果有部分index，说明正在索引中
    if (indexed_fragment_count > 0 && indexed_fragment_count < fragment_count) {
      return DocumentStatus.INGESTING;
    }
    
    // 其他情况视为索引失败
    return DocumentStatus.NOT_INGESTED;
  }

  // 回退到基于文档信息的判断
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
 * 获取处理进度
 */
export const getProcessProgress = (
  documentId: string,
  documentProcessStatuses: Map<string, DocumentProcessStatus>
): number | undefined => {
  const processStatus = documentProcessStatuses.get(documentId);
  if (!processStatus) return undefined;

  // 基于实际的fragment和index数量计算进度
  const { fragment_count, indexed_fragment_count } = processStatus;
  
  // 如果没有fragment，说明文档未解析，进度为0
  if (fragment_count === 0) {
    return 0;
  }
  
  // 如果有fragment但没有index，说明正在索引，进度为0
  if (indexed_fragment_count === 0) {
    return 0;
  }
  
  // 计算索引进度百分比
  const progress = (indexed_fragment_count / fragment_count) * 100;
  return Math.min(Math.round(progress), 100);
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