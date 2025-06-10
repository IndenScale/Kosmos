// src/services/documentService.ts
import apiClient from './apiClient';
import { API_BASE_URL } from './config';
export const documentService = {
  // 获取文档列表
  getDocuments: async (kbId: string) => {
    const response = await apiClient.get(`/api/v1/kbs/${kbId}/documents`);
    return response.data;
  },

  // 上传文档
  uploadDocument: async (kbId: string, file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await apiClient.post(
      `/api/v1/kbs/${kbId}/documents`,
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      }
    );
    return response.data;
  },

  // 获取文档详情
  getDocument: async (kbId: string, documentId: string) => {
    const response = await apiClient.get(`/api/v1/kbs/${kbId}/documents/${documentId}`);
    return response.data;
  },

  // 下载文档
  downloadDocument: async (kbId: string, documentId: string) => {
    const response = await apiClient.get(
      `/api/v1/kbs/${kbId}/documents/${documentId}/download`,
      {
        responseType: 'blob',
      }
    );
    return response.data;
  },

  // 删除文档
  deleteDocument: async (kbId: string, documentId: string) => {
    const response = await apiClient.delete(`/api/v1/kbs/${kbId}/documents/${documentId}`);
    return response.data;
  },

  // 新增：获取过时文档列表
  getOutdatedDocuments: async (kbId: string) => {
    const response = await apiClient.get(`/api/v1/kbs/${kbId}/documents/outdated`);
    return response.data;
  },
};