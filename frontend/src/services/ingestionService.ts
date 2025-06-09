// src/services/ingestionService.ts
import apiClient from './apiClient';

export const ingestionService = {
  // 启动摄取任务
  startIngestion: async (kbId: string, documentId: string) => {
    const response = await apiClient.post(
      `/api/v1/kbs/${kbId}/documents/${documentId}/ingest`
    );
    return response.data;
  },

  // 获取任务状态
  getJobStatus: async (jobId: string) => {
    const response = await apiClient.get(`/api/v1/jobs/${jobId}`);
    return response.data;
  },

  // 获取知识库的所有任务
  getKBJobs: async (kbId: string) => {
    const response = await apiClient.get(`/api/v1/kbs/${kbId}/jobs`);
    return response.data;
  },
};