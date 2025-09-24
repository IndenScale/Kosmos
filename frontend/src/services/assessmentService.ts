// 评估服务API客户端

import { JobSummary, JobDetail, AssessmentFinding, SessionSummary, SessionDetail } from '../types/assessment';

export class AssessmentService {
  private baseUrl: string;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl.replace(/\/$/, ''); // 移除末尾的斜杠
  }

  /**
   * 获取所有作业列表
   */
  async getJobs(skip: number = 0, limit: number = 100): Promise<JobSummary[]> {
    const response = await fetch(
      `${this.baseUrl}/api/v1/jobs/?skip=${skip}&limit=${limit}`,
      {
        method: 'GET',
        headers: {
          'Accept': 'application/json',
          'Content-Type': 'application/json',
        },
      }
    );

    if (!response.ok) {
      throw new Error(`获取作业列表失败: ${response.status} ${response.statusText}`);
    }

    return response.json();
  }

  /**
   * 根据作业ID获取作业详情
   */
  async getJobById(jobId: string): Promise<JobDetail> {
    const response = await fetch(
      `${this.baseUrl}/api/v1/jobs/${jobId}`,
      {
        method: 'GET',
        headers: {
          'Accept': 'application/json',
          'Content-Type': 'application/json',
        },
      }
    );

    if (!response.ok) {
      if (response.status === 404) {
        throw new Error('作业不存在');
      }
      throw new Error(`获取作业详情失败: ${response.status} ${response.statusText}`);
    }

    return response.json();
  }

  /**
   * 根据作业ID获取所有findings
   */
  async getFindingsByJobId(
    jobId: string, 
    judgements?: string[]
  ): Promise<AssessmentFinding[]> {
    let url = `${this.baseUrl}/api/v1/jobs/${jobId}`;
    
    if (judgements && judgements.length > 0) {
      const judgementsParam = judgements.map(j => `judgements=${encodeURIComponent(j)}`).join('&');
      url += `?${judgementsParam}`;
    }

    const response = await fetch(url, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error(`获取findings失败: ${response.status} ${response.statusText}`);
    }

    const jobDetail: JobDetail = await response.json();
    
    // 从JobDetail中提取findings数组
    return jobDetail.findings || [];
  }

  /**
   * 根据finding ID获取单个finding详情
   */
  async getFindingById(findingId: string): Promise<AssessmentFinding> {
    const response = await fetch(
      `${this.baseUrl}/api/v1/findings/${findingId}`,
      {
        method: 'GET',
        headers: {
          'Accept': 'application/json',
          'Content-Type': 'application/json',
        },
      }
    );

    if (!response.ok) {
      if (response.status === 404) {
        throw new Error('Finding不存在');
      }
      throw new Error(`获取finding详情失败: ${response.status} ${response.statusText}`);
    }

    return response.json();
  }

  /**
   * 导出作业的findings
   */
  async exportJobFindings(
    jobId: string,
    judgements?: string[]
  ): Promise<AssessmentFinding[]> {
    let url = `${this.baseUrl}/api/v1/jobs/${jobId}/export`;
    
    if (judgements && judgements.length > 0) {
      const judgementsParam = judgements.map(j => `judgements=${encodeURIComponent(j)}`).join('&');
      url += `?${judgementsParam}`;
    }

    const response = await fetch(url, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      if (response.status === 404) {
        throw new Error('作业不存在');
      }
      throw new Error(`导出findings失败: ${response.status} ${response.statusText}`);
    }

    return response.json();
  }

  /**
   * 根据作业ID获取所有sessions
   */
  async getSessionsByJobId(
    jobId: string,
    skip: number = 0,
    limit: number = 100
  ): Promise<SessionSummary[]> {
    const response = await fetch(
      `${this.baseUrl}/api/v1/sessions/?job_id=${jobId}&skip=${skip}&limit=${limit}`,
      {
        method: 'GET',
        headers: {
          'Accept': 'application/json',
          'Content-Type': 'application/json',
        },
      }
    );

    if (!response.ok) {
      throw new Error(`获取sessions失败: ${response.status} ${response.statusText}`);
    }

    return response.json();
  }

  /**
   * 根据session ID获取session详情
   */
  async getSessionById(sessionId: string): Promise<SessionDetail> {
    const response = await fetch(
      `${this.baseUrl}/api/v1/sessions/${sessionId}`,
      {
        method: 'GET',
        headers: {
          'Accept': 'application/json',
          'Content-Type': 'application/json',
        },
      }
    );

    if (!response.ok) {
      if (response.status === 404) {
        throw new Error('Session不存在');
      }
      throw new Error(`获取session详情失败: ${response.status} ${response.statusText}`);
    }

    return response.json();
  }

  /**
   * 根据session ID获取session的findings
   */
  async getFindingsBySessionId(sessionId: string): Promise<AssessmentFinding[]> {
    const response = await fetch(
      `${this.baseUrl}/api/v1/sessions/${sessionId}/findings`,
      {
        method: 'GET',
        headers: {
          'Accept': 'application/json',
          'Content-Type': 'application/json',
        },
      }
    );

    if (!response.ok) {
      throw new Error(`获取session findings失败: ${response.status} ${response.statusText}`);
    }

    return response.json();
  }
}

// 创建默认的服务实例工厂函数
export const createAssessmentService = (baseUrl: string): AssessmentService => {
  return new AssessmentService(baseUrl);
};