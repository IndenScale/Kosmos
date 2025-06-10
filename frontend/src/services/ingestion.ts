import axios from 'axios';

import { API_BASE_URL } from './config';

// 创建axios实例
const api = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true, // 添加跨域凭证支持
});

// 请求拦截器
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// 响应拦截器
api.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error('摄取服务请求错误:', error);
    if (error.response?.status === 401) {
      localStorage.removeItem('access_token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

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