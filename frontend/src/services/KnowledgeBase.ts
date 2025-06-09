// src/services/KnowledgeBase.ts:
import axios from 'axios';
import { KBCreate, KBUpdate, KnowledgeBase, KBDetail } from '../types/KnowledgeBase';
import apiClient from './apiClient';
import { TagDictionary } from '../types/KnowledgeBase';

// Remove the duplicate axios.create() declaration and use the imported apiClient instead
const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000/api/v1';

// const apiClient = axios.create({
//   baseURL: API_BASE_URL,
//   timeout: 10000,
// });

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
    const response = await apiClient.get('/api/v1/kbs');
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

  // 确保updateTagDictionary方法接受TagDictionary类型
  updateTagDictionary: (kbId: string, tagDictionary: TagDictionary) => {
    return apiClient.put(`/kbs/${kbId}/tags`, { tag_dictionary: tagDictionary });
  },

  async getKBStats(kbId: string): Promise<{
    document_count: number;
    chunk_count: number;
    top_level_tags: string[]
  }> {
    const response = await apiClient.get(`/kbs/${kbId}/stats`);
    return response.data;
  },
  async updateKBBasicInfo(kbId: string, data: { name?: string; description?: string }): Promise<KnowledgeBase> {
    const response = await apiClient.patch(`/kbs/${kbId}/basic`, data);
    return response.data;
  },

  // 验证JSON格式的标签字典（在 updateTagDictionary 方法后添加）
  validateTagDictionary(jsonString: string): { isValid: boolean; data?: Record<string, string[]>; error?: string } {
    try {
      const parsed = JSON.parse(jsonString);

      // 检查是否为对象
      if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
        return { isValid: false, error: '标签字典必须是一个对象' };
      }

      // 验证和清理数据
      const cleaned: Record<string, string[]> = {};
      for (const [key, value] of Object.entries(parsed)) {
        if (typeof key !== 'string' || key.trim() === '') {
          return { isValid: false, error: '分类名称必须是非空字符串' };
        }

        if (Array.isArray(value)) {
          // 验证数组中的每个元素都是字符串
          const tags = value.filter(item => typeof item === 'string' && item.trim() !== '');
          cleaned[key.trim()] = tags.map(tag => tag.trim());
        } else {
          return { isValid: false, error: `分类 "${key}" 的值必须是字符串数组` };
        }
      }

      // 检查标签总数
      const totalTags = Object.values(cleaned).flat().length;
      if (totalTags > 250) {
        return { isValid: false, error: `标签总数 (${totalTags}) 超过限制 (250)` };
      }

      return { isValid: true, data: cleaned };
    } catch (error) {
      return { isValid: false, error: 'JSON 格式无效' };
    }
  },
};