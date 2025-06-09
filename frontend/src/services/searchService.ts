import axios from 'axios';
import { SearchQuery, SearchResponse } from '../types/search';

const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
});

// 请求拦截器：添加认证token
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token'); // 修改为 'access_token'
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// 响应拦截器：处理错误
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('access_token'); // 修改为 'access_token'
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export const searchService = {
  // 执行语义搜索
  searchKnowledgeBase: async (kbId: string, query: SearchQuery): Promise<SearchResponse> => {
    const response = await api.post(`/api/v1/kbs/${kbId}/search`, query);
    return response.data;
  },

  // 获取chunk详情
  getChunk: async (chunkId: string) => {
    const response = await api.get(`/api/v1/chunks/${chunkId}`);
    return response.data;
  },
};