// Session数据管理的自定义Hook

import { useState, useCallback, useRef } from 'react'
import { createAssessmentService } from '../services/assessmentService'
import { useSystemConfig } from '../context/SystemConfigContext'
import { SessionSummary, SessionDetail, AssessmentFinding } from '../types/assessment'
import { useDebounceCallback } from './useDebounce'

export const useSessionData = () => {
  const { config } = useSystemConfig()
  const [sessions, setSessions] = useState<SessionSummary[]>([])
  const [activeSession, setActiveSession] = useState<SessionDetail | null>(null)
  const [sessionFindings, setSessionFindings] = useState<AssessmentFinding[]>([])
  const [loading, setLoading] = useState(false)
  const [sessionLoading, setSessionLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  
  // 使用ref跟踪当前加载的jobId和sessionId，避免重复请求
  const currentJobIdRef = useRef<string | null>(null)
  const currentSessionIdRef = useRef<string | null>(null)
  const loadingRef = useRef<boolean>(false)

  const assessmentService = createAssessmentService(config.assessmentServerUrl)

  // 加载sessions列表
  const loadSessionsInternal = useCallback(async (jobId: string) => {
    if (!jobId) return
    
    // 如果正在加载相同的jobId，则跳过请求
    if (currentJobIdRef.current === jobId && loadingRef.current) {
      return
    }
    
    // 如果已经加载了相同的jobId且没有错误，则跳过请求
    if (currentJobIdRef.current === jobId && !error && sessions.length > 0) {
      return
    }

    currentJobIdRef.current = jobId
    loadingRef.current = true
    setLoading(true)
    setError(null)

    try {
      const sessionsData = await assessmentService.getSessionsByJobId(jobId)
      
      // 只有当jobId仍然是当前请求的jobId时才更新状态
      if (currentJobIdRef.current === jobId) {
        setSessions(sessionsData)
      }
    } catch (err) {
      // 只有当jobId仍然是当前请求的jobId时才更新错误状态
      if (currentJobIdRef.current === jobId) {
        const errorMessage = err instanceof Error ? err.message : '加载sessions失败'
        setError(errorMessage)
        console.error('Failed to load sessions:', err)
      }
    } finally {
      if (currentJobIdRef.current === jobId) {
        loadingRef.current = false
        setLoading(false)
      }
    }
  }, [config.assessmentServerUrl, error, sessions.length])

  // 使用防抖的sessions加载函数，延迟300ms执行
  const loadSessions = useDebounceCallback(loadSessionsInternal, 300, [loadSessionsInternal])

  // 激活session并加载其详情和findings
  const activateSession = useCallback(async (sessionId: string) => {
    if (!sessionId) return

    // 如果正在加载相同的sessionId，则跳过请求
    if (currentSessionIdRef.current === sessionId && sessionLoading) {
      return
    }

    currentSessionIdRef.current = sessionId
    setSessionLoading(true)
    setError(null)

    try {
      // 并行获取session详情和findings
      const [sessionDetail, findings] = await Promise.all([
        assessmentService.getSessionById(sessionId),
        assessmentService.getFindingsBySessionId(sessionId)
      ])

      // 只有当sessionId仍然是当前请求的sessionId时才更新状态
      if (currentSessionIdRef.current === sessionId) {
        setActiveSession(sessionDetail)
        setSessionFindings(findings)
      }
    } catch (err) {
      // 只有当sessionId仍然是当前请求的sessionId时才更新错误状态
      if (currentSessionIdRef.current === sessionId) {
        const errorMessage = err instanceof Error ? err.message : '加载session详情失败'
        setError(errorMessage)
        console.error('Failed to load session details:', err)
      }
    } finally {
      if (currentSessionIdRef.current === sessionId) {
        setSessionLoading(false)
      }
    }
  }, [assessmentService, sessionLoading])

  // 重置数据的方法，当jobId变化时清理旧数据
  const resetData = useCallback(() => {
    setSessions([])
    setActiveSession(null)
    setSessionFindings([])
    setError(null)
    currentJobIdRef.current = null
    currentSessionIdRef.current = null
    loadingRef.current = false
  }, [])

  // 刷新sessions列表
  const refreshSessions = useCallback(async (jobId: string) => {
    if (!jobId) return

    try {
      const sessionsData = await assessmentService.getSessionsByJobId(jobId)
      setSessions(sessionsData)
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : '刷新sessions失败'
      setError(errorMessage)
      console.error('Failed to refresh sessions:', err)
    }
  }, [assessmentService])

  return {
    sessions,
    activeSession,
    sessionFindings,
    loading,
    sessionLoading,
    error,
    loadSessions,
    activateSession,
    refreshSessions,
    resetData
  }
}