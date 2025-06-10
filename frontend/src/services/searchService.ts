import { SearchQuery, SearchResponse } from '../types/search';
import apiClient from './apiClient';

export const searchService = {
  // 执行语义搜索
  searchKnowledgeBase: async (kbId: string, query: SearchQuery): Promise<SearchResponse> => {
    const response = await apiClient.post(`/api/v1/kbs/${kbId}/search`, query);
    return response.data;
  },

  // 获取chunk详情
  getChunk: async (chunkId: string) => {
    const response = await apiClient.get(`/api/v1/chunks/${chunkId}`);
    return response.data;
  },
};