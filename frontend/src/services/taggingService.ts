import apiClient from './apiClient';

export interface TaggingStats {
  total_chunks: number;
  tagged_chunks: number;
  untagged_chunks: number;
  tagging_progress: number;
}

export interface TaggingResult {
  success: boolean;
  message: string;
  processed_count: number;
  failed_count: number;
}

export interface UntaggedChunk {
  id: string;
  content: string;
  chunk_index: number;
  document_id: string;
}

export interface UntaggedChunksResponse {
  total_untagged: number;
  chunks: UntaggedChunk[];
}

export class TaggingService {
  private readonly baseUrl = '/api/v1/tagging';

  /**
   * 为指定的chunks生成标签
   */
  async tagChunks(kbId: string, chunkIds?: string[]): Promise<TaggingResult> {
    const response = await apiClient.post(`${this.baseUrl}/${kbId}/tag-chunks`, {
      chunk_ids: chunkIds
    });
    return response.data;
  }

  /**
   * 为指定文档的所有chunks生成标签
   */
  async tagDocument(kbId: string, documentId: string): Promise<TaggingResult> {
    const response = await apiClient.post(`${this.baseUrl}/${kbId}/tag-document/${documentId}`);
    return response.data;
  }

  /**
   * 批量为多个文档生成标签
   */
  async tagDocuments(kbId: string, documentIds: string[]): Promise<TaggingResult[]> {
    const promises = documentIds.map(documentId => 
      this.tagDocument(kbId, documentId)
    );
    
    const results = await Promise.allSettled(promises);
    
    return results.map(result => {
      if (result.status === 'fulfilled') {
        return result.value;
      } else {
        return {
          success: false,
          message: '标注失败',
          processed_count: 0,
          failed_count: 1
        };
      }
    });
  }

  /**
   * 获取知识库的标注统计信息
   */
  async getTaggingStats(kbId: string): Promise<TaggingStats> {
    const response = await apiClient.get(`${this.baseUrl}/${kbId}/stats`);
    return response.data;
  }

  /**
   * 获取未标注的chunks列表
   */
  async getUntaggedChunks(kbId: string, limit?: number): Promise<UntaggedChunksResponse> {
    const params = limit ? { limit } : {};
    const response = await apiClient.get(`${this.baseUrl}/${kbId}/untagged-chunks`, { params });
    return response.data;
  }
}

// 导出单例实例
export const taggingService = new TaggingService(); 