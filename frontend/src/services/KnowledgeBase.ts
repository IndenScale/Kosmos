// src/services/KnowledgeBase.ts
import { KBCreate, KBUpdate, KnowledgeBase, KBDetail } from '../types/knowledgeBase';
import apiClient from './apiClient';
import { TagDictionary } from '../types/knowledgeBase';

export const KnowledgeBaseService = {
  async createKB(data: KBCreate): Promise<KnowledgeBase> {
    const response = await apiClient.post('/api/v1/kbs', data);
    return response.data;
  },

  async getMyKBs(): Promise<KnowledgeBase[]> {
    const response = await apiClient.get('/api/v1/kbs');
    return response.data;
  },

  async getKBDetail(kbId: string): Promise<KBDetail> {
    const response = await apiClient.get(`/api/v1/kbs/${kbId}`);
    return response.data;
  },

  async updateKB(kbId: string, data: KBUpdate): Promise<KnowledgeBase> {
    const response = await apiClient.patch(`/api/v1/kbs/${kbId}`, data);
    return response.data;
  },

  async deleteKB(kbId: string): Promise<void> {
    await apiClient.delete(`/api/v1/kbs/${kbId}`);
  },

  updateTagDictionary: (kbId: string, tagDictionary: TagDictionary) => {
    return apiClient.put(`/api/v1/kbs/${kbId}/tags`, { tag_dictionary: tagDictionary });
  },

  async getKBStats(kbId: string): Promise<{
    document_count: number;
    chunk_count: number;
    tag_dictionary: TagDictionary;
  }> {
    const response = await apiClient.get(`/api/v1/kbs/${kbId}/stats`);
    return response.data;
  },

  async updateKBBasicInfo(kbId: string, data: { name?: string; description?: string }): Promise<KnowledgeBase> {
    const response = await apiClient.patch(`/kbs/${kbId}/basic`, data);
    return response.data;
  },

  // 新增：获取过时文档统计
  async getOutdatedDocuments(kbId: string): Promise<any[]> {
    const response = await apiClient.get(`/api/v1/kbs/${kbId}/documents/outdated`);
    return response.data;
  },

  // 验证JSON格式的标签字典
  validateTagDictionary(jsonString: string): { isValid: boolean; data?: Record<string, string[]>; error?: string } {
    try {
      const parsed = JSON.parse(jsonString);

      if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
        return { isValid: false, error: '标签字典必须是一个对象' };
      }

      const cleaned: Record<string, string[]> = {};
      for (const [key, value] of Object.entries(parsed)) {
        if (typeof key !== 'string' || key.trim() === '') {
          return { isValid: false, error: '分类名称必须是非空字符串' };
        }

        if (Array.isArray(value)) {
          const tags = value.filter(item => typeof item === 'string' && item.trim() !== '');
          cleaned[key.trim()] = tags.map(tag => tag.trim());
        } else {
          return { isValid: false, error: `分类 "${key}" 的值必须是字符串数组` };
        }
      }

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