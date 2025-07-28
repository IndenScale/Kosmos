import apiClient from './apiClient';
import mammoth from 'mammoth';
import jsPDF from 'jspdf';
import {
  DocumentRecord,
  DocumentListResponse,
  DocumentUploadRequest,
  DocumentUploadResponse,
  DocumentDeleteResponse,
  BatchAction
} from '../types/document';
import { UploadConfig } from '../config/uploadConfig';


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
    if (!UploadConfig.isSupportedFile(file.name, file.type)) {
      const supportedExtensions = UploadConfig.getSupportedExtensions().join(', ');
      return {
        isValid: false,
        error: `不支持的文件类型。支持的格式：${supportedExtensions}`
      };
    }

    return { isValid: true };
  }

  /**
   * 验证文件大小
   */
  validateFileSize(file: File): { isValid: boolean; error?: string } {
    return UploadConfig.validateFileSize(file.name, file.size, file.type);
  }

  /**
   * 验证文件（类型和大小）
   */
  validateFile(file: File): { isValid: boolean; error?: string } {
    return UploadConfig.validateFile(file);
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

  /**
   * 获取文档预览URL
   */
  getPreviewUrl(kbId: string, documentId: string): string {
    return `${this.baseUrl}/${kbId}/documents/${documentId}/download`;
  }
  isSupportedForPreview(filename: string): { supported: boolean; type: 'image' | 'text' | 'pdf' | 'docx' | 'pptx' | 'unsupported' } {
    const extension = filename.toLowerCase().split('.').pop() || '';

    const imageTypes = ['png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp'];
    const textTypes = ['txt', 'md', 'js', 'ts', 'py', 'java', 'c', 'cpp', 'html', 'css', 'json', 'xml'];
    const pdfTypes = ['pdf'];
    const docxTypes = ['docx', 'doc'];
    const pptxTypes = ['pptx'];

    if (imageTypes.includes(extension)) {
      return { supported: true, type: 'image' };
    }
    if (textTypes.includes(extension)) {
      return { supported: true, type: 'text' };
    }
    if (pdfTypes.includes(extension)) {
      return { supported: true, type: 'pdf' };
    }
    if (docxTypes.includes(extension)) {
      return { supported: true, type: 'docx' };
    }
    if (pptxTypes.includes(extension)) {
      return { supported: true, type: 'pptx' };
    }

    return { supported: false, type: 'unsupported' };
  }

  /**
   * 获取文档预览内容（用于文本类文件）
   */
  async getDocumentPreview(kbId: string, documentId: string): Promise<string> {
    const response = await apiClient.get(
      `${this.baseUrl}/${kbId}/documents/${documentId}/download`,
      {
        responseType: 'text',
      }
    );
    return response.data;
  }

  async convertDocxToPdf(kbId: string, documentId: string): Promise<string> {
    try {
      // 下载docx文件
      const blob = await this.downloadDocument(kbId, documentId);
      const arrayBuffer = await blob.arrayBuffer();

      // 转换为HTML
      const result = await mammoth.convertToHtml({ arrayBuffer });

      // 创建PDF
      const pdf = new jsPDF();
      
      return new Promise((resolve, reject) => {
        pdf.html(result.value, {
          callback: function (pdf) {
            // 生成blob并创建URL
            const pdfBlob = pdf.output('blob');
            const url = URL.createObjectURL(pdfBlob);
            resolve(url);
          },
          x: 10,
          y: 10,
          width: 180, // 设置内容宽度
          windowWidth: 800 // 设置窗口宽度
        });
      });
    } catch (error) {
      throw new Error('DOCX转换失败');
    }
  }

  public async convertOfficeToPdf(kbId: string, documentId: string): Promise<string> {
    try {
      // 下载文件
      const blob = await this.downloadDocument(kbId, documentId);
      const arrayBuffer = await blob.arrayBuffer();

      // 检查文件类型 - 需要从document参数获取文件名
      // 暂时简化处理，假设是PPTX
      const pdf = new jsPDF();
      pdf.setFontSize(16);
      pdf.text('PPTX文件预览', 20, 30);
      pdf.setFontSize(12);
      pdf.text('此文件为PowerPoint演示文稿', 20, 50);
      pdf.text('请下载文件查看完整内容', 20, 70);
      pdf.text('或使用Microsoft PowerPoint等软件打开', 20, 90);

      // 生成blob并创建URL
      const pdfBlob = pdf.output('blob');
      const url = URL.createObjectURL(pdfBlob);
      return url;
    } catch (error) {
      throw new Error('文件转换失败');
    }
  }
}


// 导出单例实例
export const documentService = new DocumentService();