import { useState, useEffect } from 'react'
import { createAssessmentService } from '@/services/assessmentService'
import { AssessmentFinding } from '@/types/assessment'
import { useSystemConfig } from '@/context/SystemConfigContext'

export const useAssessmentFindings = () => {
  const [findings, setFindings] = useState<AssessmentFinding[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const { config } = useSystemConfig()

  const fetchFindings = async (jobId?: string) => {
    const targetJobId = jobId || config.assessmentJobId
    
    if (!config.assessmentServerUrl || !targetJobId) {
      setError('缺少评估服务器URL或作业ID配置')
      return
    }

    setLoading(true)
    setError(null)
    
    try {
      const assessmentService = createAssessmentService(config.assessmentServerUrl)
      const findingsData = await assessmentService.getFindingsByJobId(targetJobId)
      setFindings(findingsData)
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : '获取findings失败'
      setError(errorMessage)
      console.error('获取findings失败:', err)
    } finally {
      setLoading(false)
    }
  }

  // 根据控制项ID查找对应的finding
  const getFindingByControlId = (controlId: string): AssessmentFinding | undefined => {
    return findings.find(finding => 
      finding.control_item_definition?.id === controlId ||
      finding.control_item_definition?.display_id === controlId
    )
  }

  // 自动获取findings（当配置改变时）
  useEffect(() => {
    if (config.assessmentServerUrl && config.assessmentJobId) {
      fetchFindings()
    }
  }, [config.assessmentServerUrl, config.assessmentJobId])

  return {
    findings,
    loading,
    error,
    fetchFindings,
    getFindingByControlId,
    refetch: () => fetchFindings()
  }
}