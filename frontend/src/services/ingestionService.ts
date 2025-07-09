import apiClient from './apiClient';
import {
  IngestionJob,
  IngestionJobStatus,
  IngestionStartRequest,
  IngestionStartResponse,
  BatchIngestionRequest,
  BatchIngestionResponse,
  DocumentJobStatus
} from '../types/ingestion';

export class IngestionService {
  private readonly baseUrl = '/api/v1';

  /**
   * 启动文档摄取/重摄入任务（合并索引和重索引功能）
   */
  async processDocument(kbId: string, documentId: string, forceReingest: boolean = false, skipTagging: boolean = true): Promise<IngestionStartResponse> {
    const endpoint = forceReingest ? 'reingest' : 'ingest';
    const params = { skip_tagging: skipTagging };
    const response = await apiClient.post(
      `${this.baseUrl}/kbs/${kbId}/documents/${documentId}/${endpoint}`,
      {},
      { params }
    );
    return response.data;
  }

  /**
   * 批量处理文档（智能选择摄取或重摄入）
   */
  async processBatchDocuments(kbId: string, documentIds: string[], forceReingest: boolean = false, skipTagging: boolean = true): Promise<BatchIngestionResponse> {
    const promises = documentIds.map(id => this.processDocument(kbId, id, forceReingest, skipTagging));
    const results = await Promise.allSettled(promises);

    const jobs: IngestionStartResponse[] = [];
    let successCount = 0;
    let failedCount = 0;

    results.forEach((result) => {
      if (result.status === 'fulfilled') {
        jobs.push(result.value);
        successCount++;
      } else {
        failedCount++;
      }
    });

    return {
      jobs,
      success_count: successCount,
      failed_count: failedCount
    };
  }

  /**
   * 获取单个任务状态
   */
  async getJobStatus(jobId: string): Promise<IngestionJob> {
    const response = await apiClient.get(`${this.baseUrl}/jobs/${jobId}`);
    return response.data;
  }

  /**
   * 获取知识库的所有任务
   */
  async getKBJobs(kbId: string): Promise<IngestionJob[]> {
    const response = await apiClient.get(`${this.baseUrl}/kbs/${kbId}/jobs`);
    return response.data;
  }

  /**
   * 获取知识库中所有文档的任务状态
   */
  async getDocumentJobStatuses(kbId: string): Promise<DocumentJobStatus[]> {
    const response = await apiClient.get(`${this.baseUrl}/kbs/${kbId}/job-statuses`);
    return response.data.jobs; // 返回 jobs 数组而不是整个响应对象
  }

  /**
   * 获取特定文档的当前任务状态
   */
  async getDocumentJobStatus(kbId: string, documentId: string): Promise<DocumentJobStatus | null> {
    try {
      const response = await apiClient.get(`${this.baseUrl}/kbs/${kbId}/documents/${documentId}/job-status`);
      return response.data;
    } catch (error: any) {
      if (error.response?.status === 404) {
        return null; // 没有正在进行的任务
      }
      throw error;
    }
  }

  /**
   * 取消任务
   */
  async cancelJob(jobId: string): Promise<void> {
    await apiClient.post(`${this.baseUrl}/jobs/${jobId}/cancel`);
  }

  /**
   * 获取知识库的摄入统计信息
   */
  async getIngestionStats(kbId: string): Promise<{
    total_chunks: number;
    tagged_chunks: number;
    untagged_chunks: number;
    tagging_completion_rate: number;
    ready_for_sdtm: boolean;
    ready_for_tagging_service: boolean;
  }> {
    const response = await apiClient.get(`${this.baseUrl}/kbs/${kbId}/ingestion-stats`);
    return response.data;
  }
}

// 导出单例实例
export const ingestionService = new IngestionService();