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
    const response = await apiClient.put(`/api/v1/kbs/${kbId}`, data);
    return response.data;
  },

  // 新增：获取过时文档统计
  async getOutdatedDocuments(kbId: string): Promise<any[]> {
    const response = await apiClient.get(`/api/v1/kbs/${kbId}/documents/outdated`);
    return response.data;
  },

  // 验证JSON格式的标签字典
  validateTagDictionary(jsonString: string): { isValid: boolean; data?: any; error?: string } {
    try {
      const parsed = JSON.parse(jsonString);

      if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
        return { isValid: false, error: '标签字典必须是一个对象' };
      }

      // 递归验证嵌套字典结构
      const validateNestedStructure = (obj: any, path: string = ''): { isValid: true; tagCount: number } | { isValid: false; error: string } => {
        let totalTagCount = 0;

        for (const [key, value] of Object.entries(obj)) {
          if (typeof key !== 'string' || key.trim() === '') {
            return { isValid: false, error: `路径 "${path}" 中的键名必须是非空字符串` };
          }

          const currentPath = path ? `${path}.${key}` : key;

          if (Array.isArray(value)) {
            // 叶子节点：必须是字符串数组
            const validTags = value.filter(item => typeof item === 'string' && item.trim() !== '');
            if (validTags.length !== value.length) {
              return { isValid: false, error: `路径 "${currentPath}" 中的标签数组包含非字符串或空字符串元素` };
            }
            totalTagCount += validTags.length;
          } else if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
            // 嵌套对象：递归验证
            const nestedResult = validateNestedStructure(value, currentPath);
            if (!nestedResult.isValid) {
              return nestedResult;
            }
            totalTagCount += nestedResult.tagCount;
          } else {
            return { isValid: false, error: `路径 "${currentPath}" 的值必须是对象或字符串数组` };
          }
        }

        return { isValid: true, tagCount: totalTagCount };
      };

      const validationResult = validateNestedStructure(parsed);
      if (!validationResult.isValid) {
        return { isValid: false, error: validationResult.error };
      }

      if (validationResult.tagCount > 250) {
        return { isValid: false, error: `标签总数 (${validationResult.tagCount}) 超过限制 (250)` };
      }

      return { isValid: true, data: parsed };
    } catch (error) {
      return { isValid: false, error: 'JSON 格式无效' };
    }
  },
};