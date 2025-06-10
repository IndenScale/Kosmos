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
   * 启动单个文档摄取任务
   */
  async startIngestion(kbId: string, documentId: string): Promise<IngestionStartResponse> {
    const response = await apiClient.post(
      `${this.baseUrl}/kbs/${kbId}/documents/${documentId}/ingest`
    );
    return response.data;
  }

  /**
   * 批量启动摄取任务
   */
  async startBatchIngestion(kbId: string, documentIds: string[]): Promise<BatchIngestionResponse> {
    const promises = documentIds.map(id => this.startIngestion(kbId, id));
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

  /**
   * 获取知识库的所有任务
   */
  async getKBJobs(kbId: string): Promise<IngestionJob[]> {
    const response = await apiClient.get(`${this.baseUrl}/kbs/${kbId}/jobs`);
    return response.data;
  }

  /**
   * 重新摄取文档（删除原有索引并重新摄取）
   */
  async reIngestDocument(kbId: string, documentId: string): Promise<IngestionStartResponse> {
    const response = await apiClient.post(
      `${this.baseUrl}/kbs/${kbId}/documents/${documentId}/reindex`
    );
    return response.data;
  }

  /**
   * 批量重新摄取文档
   */
  async reIngestDocuments(kbId: string, documentIds: string[]): Promise<BatchIngestionResponse> {
    const promises = documentIds.map(id => this.reIngestDocument(kbId, id));
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
   * 取消摄取任务
   */
  async cancelJob(jobId: string): Promise<void> {
    await apiClient.post(`${this.baseUrl}/jobs/${jobId}/cancel`);
  }
}

// 导出单例实例
export const ingestionService = new IngestionService();