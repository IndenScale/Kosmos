import apiClient from './apiClient';
import {
  IngestionJob,
  IngestionJobStatus,
  IngestionStartRequest,
  IngestionStartResponse,
  BatchIngestionRequest,
  BatchIngestionResponse
} from '../types/ingestion';

export class IngestionService {
  private readonly baseUrl = '/api/v1';

  /**
   * 启动文档摄取/重摄入任务（合并索引和重索引功能）
   */
  async processDocument(kbId: string, documentId: string, forceReingest: boolean = false): Promise<IngestionStartResponse> {
    const endpoint = forceReingest ? 'reingest' : 'ingest';
    const response = await apiClient.post(
      `${this.baseUrl}/kbs/${kbId}/documents/${documentId}/${endpoint}`
    );
    return response.data;
  }

  /**
   * 批量处理文档（智能选择摄取或重摄入）
   */
  async processBatchDocuments(kbId: string, documentIds: string[], forceReingest: boolean = false): Promise<BatchIngestionResponse> {
    const promises = documentIds.map(id => this.processDocument(kbId, id, forceReingest));
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
   * 获取任务状态
   */
  async getJobStatus(jobId: string): Promise<IngestionJob> {
    const response = await apiClient.get(`${this.baseUrl}/jobs/${jobId}`);
    return response.data;
  }

  async getKBJobs(kbId: string): Promise<IngestionJob[]> {
    const response = await apiClient.get(`${this.baseUrl}/kbs/${kbId}/jobs`);
    return response.data;
  }

  async cancelJob(jobId: string): Promise<void> {
    await apiClient.post(`${this.baseUrl}/jobs/${jobId}/cancel`);
  }
}

// 导出单例实例
export const ingestionService = new IngestionService();