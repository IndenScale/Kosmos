import { useState, useEffect } from 'react';
import { useSystemConfig } from '@/context/SystemConfigContext';
import { createAssessmentService } from '@/services/assessmentService';
import { JobSummary, JobDetail } from '@/types/assessment';

interface UseAutoAssessmentReturn {
  isLoading: boolean;
  error: string | null;
  jobs: JobSummary[];
  currentJob: JobDetail | null;
  knowledgeSpaceId: string | null;
  refreshJobs: () => Promise<void>;
}

/**
 * 自动化评估作业管理Hook
 * 1. 自动获取评估作业列表
 * 2. 自动选择第一个作业ID
 * 3. 从作业详情中提取知识空间ID
 */
export const useAutoAssessment = (): UseAutoAssessmentReturn => {
  const { config, updateConfig } = useSystemConfig();
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [jobs, setJobs] = useState<JobSummary[]>([]);
  const [currentJob, setCurrentJob] = useState<JobDetail | null>(null);
  const [knowledgeSpaceId, setKnowledgeSpaceId] = useState<string | null>(null);

  // 创建评估服务实例
  const assessmentService = createAssessmentService(config.assessmentServerUrl);

  // 获取评估作业列表
  const fetchJobs = async () => {
    try {
      setIsLoading(true);
      setError(null);

      const jobsData = await assessmentService.getJobs();
      setJobs(jobsData);

      // 如果有作业且当前没有选择作业ID，自动选择第一个
      if (jobsData.length > 0 && !config.assessmentJobId) {
        const firstJobId = jobsData[0].id;
        updateConfig({ assessmentJobId: firstJobId });
      }

    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : '获取评估作业列表失败';
      setError(errorMessage);
      console.error('Failed to fetch assessment jobs:', err);
    } finally {
      setIsLoading(false);
    }
  };

  // 获取当前作业详情并提取知识空间ID
  const fetchCurrentJobDetail = async (jobId: string) => {
    try {
      setIsLoading(true);
      setError(null);

      const jobDetail = await assessmentService.getJobById(jobId);
      setCurrentJob(jobDetail);

      // 从作业详情中提取知识空间ID
      const knowledgeSpaces = jobDetail?.knowledge_spaces;
      const knowledgeSpaceId = knowledgeSpaces?.[0]?.ks_id;
      
      if (!knowledgeSpaceId) {
        setError('无法获取知识空间ID');
        return;
      }
      
      setKnowledgeSpaceId(knowledgeSpaceId);

    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : '获取作业详情失败';
      setError(errorMessage);
      console.error('Failed to fetch job detail:', err);
    } finally {
      setIsLoading(false);
    }
  };

  // 刷新作业列表
  const refreshJobs = async () => {
    await fetchJobs();
  };

  // 初始化时获取作业列表
  useEffect(() => {
    fetchJobs();
  }, []);

  // 当作业ID变化时，获取作业详情
  useEffect(() => {
    if (config.assessmentJobId) {
      fetchCurrentJobDetail(config.assessmentJobId);
    } else {
      setCurrentJob(null);
      setKnowledgeSpaceId(null);
    }
  }, [config.assessmentJobId]);

  return {
    isLoading,
    error,
    jobs,
    currentJob,
    knowledgeSpaceId,
    refreshJobs,
  };
};