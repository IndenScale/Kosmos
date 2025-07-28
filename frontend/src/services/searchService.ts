import { SearchQuery, SearchResponse, ScreenshotInfo } from '../types/search';
import apiClient from './apiClient';

export const searchService = {
  // 执行语义搜索
  searchKnowledgeBase: async (kbId: string, query: SearchQuery): Promise<SearchResponse> => {
    const response = await apiClient.post(`/api/v1/kbs/${kbId}/search`, {
      query: query.query,
      top_k: query.top_k || 10,
      fragment_types: query.fragment_types || ['text'],
      must_tags: query.must_tags || [],
      must_not_tags: query.must_not_tags || [],
      like_tags: query.like_tags || [],
      parse_query: query.parse_query !== false,
      include_screenshots: query.include_screenshots || false,
      include_figures: query.include_figures || false
    });
    return response.data;
  },

  // 获取chunk详情
  getChunk: async (chunkId: string) => {
    const response = await apiClient.get(`/api/v1/chunks/${chunkId}`);
    return response.data;
  },

  // 获取截图信息
  getScreenshotInfo: async (screenshotId: string): Promise<ScreenshotInfo> => {
    const response = await apiClient.get(`/screenshots/${screenshotId}/info`);
    return response.data.data;
  },

  // 批量获取截图信息
  getScreenshotsBatch: async (screenshotIds: string[]): Promise<ScreenshotInfo[]> => {
    const response = await apiClient.post('/screenshots/batch', screenshotIds);
    return response.data.data.screenshots;
  },

  // 获取截图图片URL（已废弃，使用getScreenshotImageBlob代替）
  getScreenshotImageUrl: (screenshotId: string): string => {
    return `/screenshots/${screenshotId}/image`;
  },

  // 获取带认证的截图图片blob URL
  getScreenshotImageBlob: async (screenshotId: string): Promise<string> => {
    try {
      const response = await apiClient.get(`/screenshots/${screenshotId}/image`, {
        responseType: 'blob',
        headers: {
          'Accept': 'image/png'
        }
      });
      
      // 创建blob URL
      const blob = new Blob([response.data], { type: 'image/png' });
      const blobUrl = URL.createObjectURL(blob);
      
      return blobUrl;
    } catch (error) {
      console.error('获取截图失败:', error);
      throw error;
    }
  },

  // 获取文档的所有截图
  getDocumentScreenshots: async (documentId: string): Promise<ScreenshotInfo[]> => {
    const response = await apiClient.get(`/screenshots/document/${documentId}`);
    return response.data.data.screenshots;
  },

  // 获取fragment图片（截图或插图）
  getFragmentImage: async (fragmentId: string): Promise<string> => {
    try {
      const response = await apiClient.get(`/api/v1/fragments/${fragmentId}/image`, {
        responseType: 'blob',
        headers: {
          'Accept': 'image/*'
        }
      });
      
      // 创建blob URL
      const blob = new Blob([response.data], { 
        type: response.headers['content-type'] || 'image/png' 
      });
      const blobUrl = URL.createObjectURL(blob);
      
      return blobUrl;
    } catch (error) {
      console.error(`获取fragment图片失败 ${fragmentId}:`, error);
      throw error;
    }
  },
};