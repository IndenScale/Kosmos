/**
 * 统一任务系统服务
 * 文件: jobService.ts
 * 创建时间: 2025-07-26
 * 描述: 提供统一任务系统的前端接口
 */

import apiClient from './apiClient';

export interface CreateParseJobRequest {
  document_ids: string[];
  force_reparse?: boolean;
  priority?: number;
}

export interface CreateIndexJobRequest {
  document_ids?: string[];
  fragment_ids?: string[];
  force_reindex?: boolean;
  priority?: number;
  max_tags?: number;
}

export interface TaskResponse {
  id: string;
  job_id: string;
  task_type: string;
  status: string;
  target_id?: string;
  target_type?: string;
  worker_id?: string;
  retry_count: number;
  max_retries: number;
  error_message?: string;
  created_at: string;
  updated_at: string;
  started_at?: string;
  completed_at?: string;
}

export interface JobResponse {
  id: string;
  kb_id: string;
  job_type: string;
  status: string;
  priority: number;
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

export interface JobDetailResponse extends JobResponse {
  tasks: TaskResponse[];
  config?: Record<string, any>;
}

export interface JobListResponse {
  jobs: JobResponse[];
  total: number;
  page: number;
  page_size: number;
}

export interface JobStatsResponse {
  total_jobs: number;
  pending_jobs: number;
  running_jobs: number;
  completed_jobs: number;
  failed_jobs: number;
  total_tasks: number;
  pending_tasks: number;
  running_tasks: number;
  completed_tasks: number;
  failed_tasks: number;
}

export interface QueueStatsResponse {
  pending: number;
  running: number;
  total_tasks: number;
  completed: number;
  failed: number;
  timeout: number;
  queue_size: number;
  max_concurrent: number;
}

export class JobService {
  /**
   * 创建文档解析任务
   */
  async createParseJob(kbId: string, request: CreateParseJobRequest): Promise<JobResponse> {
    const response = await apiClient.post(`/api/v1/kbs/${kbId}/jobs/parse`, request);
    return response.data;
  }

  /**
   * 创建索引任务
   */
  async createIndexJob(kbId: string, request: CreateIndexJobRequest): Promise<JobResponse> {
    const response = await apiClient.post(`/api/v1/kbs/${kbId}/jobs/index`, request);
    return response.data;
  }

  /**
   * 获取任务列表
   */
  async listJobs(
    kbId: string,
    options: {
      status?: string;
      job_type?: string;
      page?: number;
      page_size?: number;
    } = {}
  ): Promise<JobListResponse> {
    const params = new URLSearchParams();
    if (options.status) params.append('status', options.status);
    if (options.job_type) params.append('job_type', options.job_type);
    if (options.page) params.append('page', options.page.toString());
    if (options.page_size) params.append('page_size', options.page_size.toString());

    const response = await apiClient.get(`/api/v1/kbs/${kbId}/jobs?${params.toString()}`);
    return response.data;
  }

  /**
   * 获取任务详情
   */
  async getJobDetail(kbId: string, jobId: string): Promise<JobDetailResponse> {
    const response = await apiClient.get(`/api/v1/kbs/${kbId}/jobs/${jobId}`);
    return response.data;
  }

  /**
   * 获取任务统计
   */
  async getJobStats(kbId: string): Promise<JobStatsResponse> {
    const response = await apiClient.get(`/api/v1/kbs/${kbId}/jobs/stats/summary`);
    return response.data;
  }

  /**
   * 获取队列统计
   */
  async getQueueStats(kbId: string): Promise<QueueStatsResponse> {
    const response = await apiClient.get(`/api/v1/kbs/${kbId}/jobs/queue/stats`);
    return response.data;
  }

  /**
   * 取消任务
   */
  async cancelJob(kbId: string, jobId: string): Promise<void> {
    await apiClient.post(`/api/v1/kbs/${kbId}/jobs/${jobId}/cancel`);
  }

  /**
   * 重试任务
   */
  async retryJob(kbId: string, jobId: string): Promise<void> {
    await apiClient.post(`/api/v1/kbs/${kbId}/jobs/${jobId}/retry`);
  }

  /**
   * 轮询任务状态直到完成
   */
  async pollJobUntilComplete(
    kbId: string,
    jobId: string,
    onProgress?: (job: JobResponse) => void,
    pollInterval: number = 2000
  ): Promise<JobResponse> {
    return new Promise((resolve, reject) => {
      const poll = async () => {
        try {
          const job = await this.getJobDetail(kbId, jobId);

          if (onProgress) {
            onProgress(job);
          }

          if (job.status === 'completed') {
            resolve(job);
          } else if (job.status === 'failed' || job.status === 'cancelled') {
            reject(new Error(`任务${job.status}: ${job.error_message || '未知错误'}`));
          } else {
            // 继续轮询
            setTimeout(poll, pollInterval);
          }
        } catch (error) {
          reject(error);
        }
      };

      poll();
    });
  }
}

export const jobService = new JobService();