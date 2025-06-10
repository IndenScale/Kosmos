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
    const response = await apiClient.delete(`${this.baseUrl}/${kbId}/documents/${documentId}`);
    return response.data;
  }

  /**
   * 批量删除文档
   */
  async deleteDocuments(kbId: string, documentIds: string[]): Promise<DocumentDeleteResponse[]> {
    const deletePromises = documentIds.map(id => this.deleteDocument(kbId, id));
    return Promise.all(deletePromises);
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
  validateFileSize(file: File, maxSizeMB = 10): { isValid: boolean; error?: string } {
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