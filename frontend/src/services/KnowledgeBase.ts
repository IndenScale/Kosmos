// src/services/KnowledgeBase.ts:
import axios from 'axios';
import { KBCreate, KBUpdate, KnowledgeBase, KBDetail } from '../types/KnowledgeBase';

const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000/api/v1';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
});

// Request interceptor
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Response interceptor
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('access_token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export const KnowledgeBaseService = {
  async createKB(data: KBCreate): Promise<KnowledgeBase> {
    const response = await apiClient.post('/kbs', data);
    return response.data;
  },

  async getMyKBs(): Promise<KnowledgeBase[]> {
    const response = await apiClient.get('/kbs');
    return response.data;
  },

  async getKBDetail(kbId: string): Promise<KBDetail> {
    const response = await apiClient.get(`/kbs/${kbId}`);
    return response.data;
  },

  async updateKB(kbId: string, data: KBUpdate): Promise<KnowledgeBase> {
    const response = await apiClient.patch(`/kbs/${kbId}`, data); // Changed from put to patch
    return response.data;
  },

  async deleteKB(kbId: string): Promise<void> {
    await apiClient.delete(`/kbs/${kbId}`);
  },

  async updateTagDictionary(kbId: string, tagDictionary: Record<string, string[]>): Promise<void> {
    await apiClient.put(`/kbs/${kbId}/tags`, {
      tag_dictionary: tagDictionary
    });
  },

  async getKBStats(kbId: string): Promise<{
    document_count: number;
    chunk_count: number;
    top_level_tags: string[]
  }> {
    const response = await apiClient.get(`/kbs/${kbId}/stats`);
    return response.data;
  }
};