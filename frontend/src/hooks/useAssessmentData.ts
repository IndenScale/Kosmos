// 评估数据管理的自定义Hook

import { useState, useCallback, useRef } from 'react'
import { createAssessmentService } from '../services/assessmentService'
import { useSystemConfig } from '../context/SystemConfigContext'
import { JobDetail, AssessmentFinding } from '../types/assessment'
import { useDebounceCallback } from './useDebounce'

export const useAssessmentData = () => {
  const { config } = useSystemConfig()
  const [job, setJob] = useState<JobDetail | null>(null)
  const [findings, setFindings] = useState<AssessmentFinding[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  
  // 使用ref跟踪当前加载的jobId，避免重复请求
  const currentJobIdRef = useRef<string | null>(null)
  const loadingRef = useRef<boolean>(false)

  const assessmentService = createAssessmentService(config.assessmentServerUrl)

  // 实际的数据加载函数
  const loadJobDataInternal = useCallback(async (jobId: string) => {
    if (!jobId) return
    
    // 如果正在加载相同的jobId，则跳过请求
    if (currentJobIdRef.current === jobId && loadingRef.current) {
      return
    }
    
    // 如果已经加载了相同的jobId且没有错误，则跳过请求
    if (currentJobIdRef.current === jobId && !error && (job || findings.length > 0)) {
      return
    }

    currentJobIdRef.current = jobId
    loadingRef.current = true
    setLoading(true)
    setError(null)

    try {
      // 并行获取作业信息和findings
      const [jobData, findingsData] = await Promise.all([
        assessmentService.getJobById(jobId),
        assessmentService.getFindingsByJobId(jobId)
      ])

      // 只有当jobId仍然是当前请求的jobId时才更新状态
      if (currentJobIdRef.current === jobId) {
        setJob(jobData)
        setFindings(findingsData)
      }
    } catch (err) {
      // 只有当jobId仍然是当前请求的jobId时才更新错误状态
      if (currentJobIdRef.current === jobId) {
        const errorMessage = err instanceof Error ? err.message : '加载数据失败'
        setError(errorMessage)
        console.error('Failed to load assessment data:', err)
      }
    } finally {
      if (currentJobIdRef.current === jobId) {
        loadingRef.current = false
        setLoading(false)
      }
    }
  }, [config.assessmentServerUrl])

  // 使用防抖的数据加载函数，延迟300ms执行
  const loadJobData = useDebounceCallback(loadJobDataInternal, 300, [loadJobDataInternal])

  const refreshFindings = useCallback(async (jobId: string) => {
    if (!jobId) return

    try {
      const findingsData = await assessmentService.getFindingsByJobId(jobId)
      setFindings(findingsData)
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : '刷新findings失败'
      setError(errorMessage)
      console.error('Failed to refresh findings:', err)
    }
  }, [assessmentService])

  // 重置数据的方法，当jobId变化时清理旧数据
  const resetData = useCallback(() => {
    setJob(null)
    setFindings([])
    setError(null)
    currentJobIdRef.current = null
    loadingRef.current = false
  }, [])

  return {
    job,
    findings,
    loading,
    error,
    loadJobData,
    refreshFindings,
    resetData
  }
}