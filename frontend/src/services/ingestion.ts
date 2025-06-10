import axios from 'axios';

import { API_BASE_URL } from './config';

// 创建axios实例
const api = axios.create({
  baseURL: API_BASE_URL,
});

// 请求拦截器
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export const ingestionService = {
  // 启动摄取任务
  startIngestion: async (kbId: string, documentId: string) => {
    const response = await api.post(`/api/v1/kbs/${kbId}/documents/${documentId}/ingest`);
    return response.data;
  },

  // 获取任务状态
  getJobStatus: async (jobId: string) => {
    const response = await api.get(`/api/v1/jobs/${jobId}`);
    return response.data;
  },

  // 获取知识库的所有任务
  getKBJobs: async (kbId: string) => {
    const response = await api.get(`/api/v1/kbs/${kbId}/jobs`);
    return response.data;
  },
};