import apiClient from './apiClient';
import {
  IndexRequest,
  BatchIndexRequest,
  BatchIndexByFragmentsRequest,
  BatchIndexByDocumentsRequest,
  IndexResponse,
  IndexJobResponse,
  IndexStatsResponse,
  IndexProgressResponse,
  DocumentProcessStatus,
  BatchProcessResponse,
  IndexStatus
} from '../types/index';

// 导入任务相关类型
export interface JobResponse {
  id: string;
  kb_id: string;
  job_type: string;
  status: string;
  priority: number;
  config?: Record<string, any>;
  total_tasks: number;
  completed_tasks: number;
  failed_tasks: number;
  progress_percentage: number;
  error_message?: string;
  created_at: string;
  updated_at: string;
  started_at?: string;
  completed_at?: string;
  created_by?: string;
}

export interface IndexJobRequest {
  document_ids: string[];
  force_regenerate?: boolean;
  max_tags?: number;
  enable_multimodal?: boolean;
  multimodal_config?: Record<string, any>;
}

export class IndexService {
  private readonly baseUrl = '/api/v1/index';
  private readonly jobsUrl = '/api/v1/jobs';

  /**
   * 为单个Fragment创建索引
   */
  async createFragmentIndex(
    fragmentId: string, 
    request: IndexRequest = {}
  ): Promise<IndexResponse> {
    const response = await apiClient.post(
      `${this.baseUrl}/fragment/${fragmentId}`,
      request
    );
    return response.data;
  }

  /**
   * 批量创建索引（向后兼容）
   * @deprecated 使用 createBatchIndexByFragments 替代
   */
  async createBatchIndex(request: BatchIndexRequest): Promise<JobResponse> {
    const response = await apiClient.post(`${this.baseUrl}/batch`, request);
    return response.data;
  }

  /**
   * 基于Fragment ID列表批量创建索引
   */
  async createBatchIndexByFragments(request: BatchIndexByFragmentsRequest): Promise<JobResponse> {
    const response = await apiClient.post(`${this.baseUrl}/batch/fragments`, request);
    return response.data;
  }

  /**
   * 基于Document ID列表批量创建索引（返回Job）
   */
  async createBatchIndexByDocuments(request: BatchIndexByDocumentsRequest): Promise<JobResponse> {
    const response = await apiClient.post(`${this.baseUrl}/batch/documents`, request);
    return response.data;
  }

  /**
   * 单文档索引 - 异步任务版本
   */
  async indexDocument(
    documentId: string,
    options: {
      force_regenerate?: boolean;
      max_tags?: number;
      enable_multimodal?: boolean;
      multimodal_config?: Record<string, any>;
    } = {}
  ): Promise<JobResponse> {
    const request: BatchIndexByDocumentsRequest = {
      document_ids: [documentId],
      force_regenerate: options.force_regenerate || false,
      max_tags: options.max_tags || 20,
      enable_multimodal: options.enable_multimodal || false,
      multimodal_config: options.multimodal_config
    };
    
    return await this.createBatchIndexByDocuments(request);
  }

  /**
   * 批量文档索引 - 异步任务版本
   */
  async indexDocuments(
    documentIds: string[],
    options: {
      force_regenerate?: boolean;
      max_tags?: number;
      enable_multimodal?: boolean;
      multimodal_config?: Record<string, any>;
    } = {}
  ): Promise<JobResponse> {
    const request: BatchIndexByDocumentsRequest = {
      document_ids: documentIds,
      force_regenerate: options.force_regenerate || false,
      max_tags: options.max_tags || 20,
      enable_multimodal: options.enable_multimodal || false,
      multimodal_config: options.multimodal_config
    };
    
    return await this.createBatchIndexByDocuments(request);
  }

  /**
   * 获取任务状态
   */
  async getJobStatus(jobId: string): Promise<JobResponse> {
    const response = await apiClient.get(`${this.jobsUrl}/${jobId}`);
    return response.data;
  }

  /**
   * 获取正在运行的任务列表
   */
  async getRunningJobs(kbId?: string): Promise<JobResponse[]> {
    const params: any = {
      status: 'running',
      page_size: 100 // 获取足够多的正在运行任务
    };
    
    if (kbId) {
      params.kb_id = kbId;
    }
    
    const response = await apiClient.get(this.jobsUrl, { params });
    return response.data.jobs || [];
  }

  /**
   * 轮询任务状态直到完成
   */
  async pollJobUntilComplete(
    jobId: string,
    onProgress?: (job: JobResponse) => void,
    pollInterval: number = 5000 // 5秒轮询间隔
  ): Promise<JobResponse> {
    return new Promise((resolve, reject) => {
      const poll = async () => {
        try {
          const job = await this.getJobStatus(jobId);
          
          // 调用进度回调
          if (onProgress) {
            onProgress(job);
          }
          
          // 检查任务是否完成
          if (job.status === 'completed') {
            resolve(job);
            return;
          } else if (job.status === 'failed' || job.status === 'cancelled') {
            reject(new Error(job.error_message || `任务${job.status}`));
            return;
          }
          
          // 继续轮询
          setTimeout(poll, pollInterval);
        } catch (error) {
          reject(error);
        }
      };
      
      poll();
    });
  }

  /**
   * 检查文档是否已有索引
   */
  async checkDocumentIndexStatus(kbId: string, documentIds: string[]): Promise<{
    indexed: string[];
    notIndexed: string[];
  }> {
    try {
      const indexed: string[] = [];
      const notIndexed: string[] = [];
      
      // 对每个文档检查是否有实际的 fragments
      for (const docId of documentIds) {
        try {
          const fragmentsResponse = await apiClient.get(`/api/v1/fragments/document/${docId}`, {
            params: { fragment_type: 'text' }
          });
          const fragments = fragmentsResponse.data || [];
          
          // 如果文档有 fragments，则认为已索引
          if (fragments.length > 0) {
            indexed.push(docId);
          } else {
            notIndexed.push(docId);
          }
        } catch (error) {
          console.error(`检查文档 ${docId} 的 fragments 失败:`, error);
          // 如果检查失败，假设没有索引
          notIndexed.push(docId);
        }
      }
      
      return { indexed, notIndexed };
    } catch (error) {
      console.error('检查文档索引状态失败:', error);
      // 如果检查失败，假设都没有索引
      return { indexed: [], notIndexed: documentIds };
    }
  }

  /**
   * 获取知识库索引统计
   */
  async getIndexStats(kbId: string): Promise<IndexStatsResponse> {
    const response = await apiClient.get(`${this.baseUrl}/kb/${kbId}/stats`);
    return response.data;
  }

  /**
   * 删除Fragment索引
   */
  async deleteFragmentIndex(fragmentId: string): Promise<{ message: string }> {
    const response = await apiClient.delete(`${this.baseUrl}/fragment/${fragmentId}`);
    return response.data;
  }

  /**
   * 删除文档的所有索引
   */
  async deleteDocumentIndex(documentId: string): Promise<{ message: string }> {
    const response = await apiClient.delete(`${this.baseUrl}/document/${documentId}`);
    return response.data;
  }

  /**
   * 列出已索引的Fragment
   */
  async listIndexedFragments(
    kbId: string, 
    skip: number = 0, 
    limit: number = 100
  ): Promise<IndexResponse[]> {
    const response = await apiClient.get(`${this.baseUrl}/kb/${kbId}/fragments`, {
      params: { skip, limit }
    });
    return response.data;
  }

  /**
   * 为文档创建索引（替代原有的摄取功能）
   * 这个方法会触发文档的解析和索引创建
   * @deprecated 使用 indexDocument 替代
   */
  async processDocument(
    kbId: string, 
    documentId: string, 
    forceRegenerate: boolean = false
  ): Promise<BatchProcessResponse> {
    // 添加防护，确保 documentId 有效
    if (!documentId || documentId === 'undefined') {
      throw new Error('Invalid document ID');
    }

    // 首先获取文档的fragments
    const fragmentsResponse = await apiClient.get(`/api/v1/fragments/document/${documentId}`, {
      params: { fragment_type: 'text' }
    });
    const fragments = fragmentsResponse.data;

    if (!fragments || fragments.length === 0) {
      // 如果没有fragments，说明文档还没有被解析，需要先触发解析
      await this.triggerDocumentParsing(kbId, documentId);
      
      // 等待解析完成后再获取fragments
      // 这里可能需要轮询或者使用WebSocket来监听解析状态
      throw new Error('文档正在解析中，请稍后再试');
    }

    // 为所有fragments创建索引
    const fragmentIds = fragments.map((f: any) => f.id);
    const indexJob = await this.createBatchIndexByFragments({
      fragment_ids: fragmentIds,
      force_regenerate: forceRegenerate
    });

    return {
      success_count: 1,
      failed_count: 0,
      results: [{
        document_id: documentId,
        parse_status: 'completed',
        index_status: IndexStatus.PROCESSING,
        fragment_count: fragmentIds.length,
        indexed_fragment_count: 0,
        last_updated: new Date().toISOString()
      }]
    };
  }

  /**
   * 批量处理文档
   * @deprecated 使用 indexDocuments 替代
   */
  async processBatchDocuments(
    kbId: string, 
    documentIds: string[], 
    forceRegenerate: boolean = false
  ): Promise<BatchProcessResponse> {
    const promises = documentIds.map(id => 
      this.processDocument(kbId, id, forceRegenerate).catch(error => ({
        success_count: 0,
        failed_count: 1,
        results: [{
          document_id: id,
          parse_status: 'failed' as const,
          index_status: IndexStatus.FAILED,
          fragment_count: 0,
          indexed_fragment_count: 0,
          last_updated: new Date().toISOString(),
          error_message: error.message
        }]
      }))
    );

    const results = await Promise.all(promises);
    
    return {
      success_count: results.reduce((sum, r) => sum + r.success_count, 0),
      failed_count: results.reduce((sum, r) => sum + r.failed_count, 0),
      results: results.flatMap(r => r.results)
    };
  }

  /**
   * 直接批量处理文档（使用后端的批量文档索引端点）
   * @deprecated 使用 indexDocuments 替代
   */
  async processBatchDocumentsDirect(
    documentIds: string[], 
    forceRegenerate: boolean = false,
    maxTags: number = 20
  ): Promise<JobResponse> {
    return await this.createBatchIndexByDocuments({
      document_ids: documentIds,
      force_regenerate: forceRegenerate,
      max_tags: maxTags
    });
  }

  /**
   * 触发文档解析（这应该在文档上传时自动触发）
   */
  private async triggerDocumentParsing(kbId: string, documentId: string): Promise<void> {
    // 调用解析接口
    await apiClient.post(`/api/v1/kbs/${kbId}/documents/${documentId}/parse`);
  }

  /**
   * 获取文档处理状态（使用新的API）
   */
  async getDocumentProcessStatus(kbId: string, documentId: string): Promise<DocumentProcessStatus> {
    // 添加防护，确保 documentId 有效
    if (!documentId || documentId === 'undefined') {
      return {
        document_id: documentId || 'unknown',
        parse_status: 'failed',
        index_status: IndexStatus.FAILED,
        fragment_count: 0,
        indexed_fragment_count: 0,
        last_updated: new Date().toISOString(),
        error_message: 'Invalid document ID'
      };
    }

    try {
      // 使用新的文档状态API
      const response = await apiClient.get(`/api/v1/kbs/${kbId}/documents/${documentId}/status`);
      const statusData = response.data;
      
      return {
        document_id: documentId,
        parse_status: statusData.fragment_count > 0 ? 'completed' : 'pending',
        index_status: statusData.status === 'completed' ? IndexStatus.COMPLETED : 
                     statusData.status === 'indexing' ? IndexStatus.PROCESSING : IndexStatus.PENDING,
        fragment_count: statusData.fragment_count,
        indexed_fragment_count: statusData.indexed_count,
        last_updated: new Date().toISOString()
      };
    } catch (error) {
      return {
        document_id: documentId,
        parse_status: 'failed',
        index_status: IndexStatus.FAILED,
        fragment_count: 0,
        indexed_fragment_count: 0,
        last_updated: new Date().toISOString(),
        error_message: error instanceof Error ? error.message : '未知错误'
      };
    }
  }

  /**
   * 获取知识库中所有文档的处理状态（使用新的批量API）
   */
  async getKBDocumentStatuses(kbId: string): Promise<DocumentProcessStatus[]> {
    try {
      // 使用新的批量文档状态API
      const response = await apiClient.get(`/api/v1/kbs/${kbId}/documents/status/batch`);
      const statusData = response.data;
      
      // 转换为DocumentProcessStatus格式
      return Object.values(statusData).map((status: any) => ({
        document_id: status.document_id,
        parse_status: status.fragment_count > 0 ? 'completed' : 'pending',
        index_status: status.status === 'completed' ? IndexStatus.COMPLETED : 
                     status.status === 'indexing' ? IndexStatus.PROCESSING : IndexStatus.PENDING,
        fragment_count: status.fragment_count,
        indexed_fragment_count: status.indexed_count,
        last_updated: new Date().toISOString()
      }));
    } catch (error) {
      console.error('获取文档状态失败:', error);
      return [];
    }
  }
}

// 导出单例实例
export const indexService = new IndexService();