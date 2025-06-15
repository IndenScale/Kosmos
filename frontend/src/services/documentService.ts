import apiClient from './apiClient';
import {
  DocumentRecord,
  DocumentListResponse,
  DocumentUploadRequest,
  DocumentUploadResponse,
  DocumentDeleteResponse,
  BatchAction
} from '../types/document';

export class DocumentService {
  private readonly baseUrl = '/api/v1/kbs';

  /**
   * 获取知识库文档列表
   */
  async getDocuments(kbId: string, page = 1, size = 20): Promise<DocumentListResponse> {
    const response = await apiClient.get(`${this.baseUrl}/${kbId}/documents`, {
      params: { page, size }
    });
    return response.data;
  }

  /**
   * 上传文档
   */
  async uploadDocument(kbId: string, file: File): Promise<DocumentUploadResponse> {
    const formData = new FormData();
    formData.append('file', file);

    const response = await apiClient.post(
      `${this.baseUrl}/${kbId}/documents`,
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        timeout: 300000 // 增加到5分钟（300秒）
      }
    );
    return response.data;
  }

  /**
   * 批量上传文档
   */
  async uploadDocuments(kbId: string, files: File[]): Promise<DocumentUploadResponse[]> {
    const uploadPromises = files.map(file => this.uploadDocument(kbId, file));
    return Promise.all(uploadPromises);
  }

  /**
   * 获取文档详情
   */
  async getDocument(kbId: string, documentId: string): Promise<DocumentRecord> {
    const response = await apiClient.get(`${this.baseUrl}/${kbId}/documents/${documentId}`);
    return response.data;
  }

  /**
   * 下载文档
   */
  async downloadDocument(kbId: string, documentId: string): Promise<Blob> {
    const response = await apiClient.get(
      `${this.baseUrl}/${kbId}/documents/${documentId}/download`,
      {
        responseType: 'blob',
      }
    );
    return response.data;
  }

  /**
   * 批量下载文档
   */
  async downloadDocuments(kbId: string, documentIds: string[]): Promise<Blob[]> {
    const downloadPromises = documentIds.map(id => this.downloadDocument(kbId, id));
    return Promise.all(downloadPromises);
  }

  /**
   * 删除文档
   */
  async deleteDocument(kbId: string, documentId: string): Promise<DocumentDeleteResponse> {
    const response = await apiClient.delete(`${this.baseUrl}/${kbId}/documents/${documentId}`, {
      timeout: 30000 // 增加到30秒
    });
    return response.data || { success: true };
  }

  /**
   * 批量删除文档
   */
  async deleteDocuments(kbId: string, documentIds: string[]): Promise<DocumentDeleteResponse[]> {
    try {
      // 调用新的批量删除接口
      const response = await apiClient.delete(`${this.baseUrl}/${kbId}/documents/batch`, {
        data: { document_ids: documentIds },
        timeout: 60000 // 批量操作增加超时时间
      });

      const batchResult = response.data;

      // 将批量结果转换为原有格式，保持兼容性
      return documentIds.map(id => ({
        success: batchResult.results[id] || false,
        message: batchResult.results[id] ? '删除成功' : '删除失败'
      }));
    } catch (error) {
      console.warn('批量删除失败，回退到逐个删除:', error);
      // 如果批量删除失败，回退到原有的逐个删除方式
      const deletePromises = documentIds.map(id => this.deleteDocument(kbId, id));
      try {
        return await Promise.all(deletePromises);
      } catch (fallbackError) {
        console.warn('批量删除过程中出现错误，部分操作可能已成功:', fallbackError);
        // 即使有错误，也返回部分成功的结果
        const results = await Promise.allSettled(deletePromises);
        return results.map(result =>
          result.status === 'fulfilled'
            ? result.value
            : { success: false , message: result.reason}
        );
      }
    }
  }

  /**
   * 获取过时文档列表
   */
  async getOutdatedDocuments(kbId: string): Promise<DocumentRecord[]> {
    const response = await apiClient.get(`${this.baseUrl}/${kbId}/documents/outdated`);
    return response.data;
  }

  /**
   * 检查文档是否过时
   */
  isDocumentOutdated(document: DocumentRecord, kbLastTagUpdate?: string): boolean {
    if (!document.last_ingest_time || !kbLastTagUpdate) {
      return false;
    }
    return new Date(document.last_ingest_time) < new Date(kbLastTagUpdate);
  }

  /**
   * 验证文件类型
   */
  validateFileType(file: File): { isValid: boolean; error?: string } {
    const allowedMimeTypes = [
      'application/pdf',
      'text/plain',
      'text/markdown',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      'application/msword',
      'application/vnd.openxmlformats-officedocument.presentationml.presentation',
      'image/png',
      'image/jpeg',
      'image/jpg'
    ];

    const allowedExtensions = [
      'pdf', 'txt', 'md', 'docx', 'doc', 'pptx', 'xlsx',
      'py', 'js', 'ts', 'java', 'c', 'cpp', 'png', 'jpg', 'jpeg'
    ];

    const filename = file.name.toLowerCase();
    const fileExtension = filename.slice(((filename.lastIndexOf(".") - 1) >>> 0) + 2);
    const isValidType = allowedMimeTypes.includes(file.type) || allowedExtensions.includes(fileExtension);

    if (!isValidType) {
      return {
        isValid: false,
        error: '支持的文件格式：PDF、TXT、MD、DOC、DOCX、PPTX、图片(PNG/JPG)及代码文件'
      };
    }

    return { isValid: true };
  }

  /**
   * 验证文件大小
   */
  validateFileSize(file: File, maxSizeMB = 1024): { isValid: boolean; error?: string } {
    const isValidSize = file.size / 1024 / 1024 < maxSizeMB;

    if (!isValidSize) {
      return {
        isValid: false,
        error: `文件大小不能超过 ${maxSizeMB}MB`
      };
    }

    return { isValid: true };
  }

  /**
   * 格式化文件大小
   */
  formatFileSize(bytes: number): string {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  }
}

// 导出单例实例
export const documentService = new DocumentService();