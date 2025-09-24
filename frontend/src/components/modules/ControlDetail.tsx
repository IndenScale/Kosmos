import React, { useEffect, useState } from 'react'
import { Card, Typography, Divider, Spin, Alert, Tag, Descriptions } from 'antd'
import { useSessionData } from '../../hooks/useSessionData'
import { SessionDetail, SessionStatus } from '../../types/assessment'
import { createAssessmentService } from '../../services/assessmentService'
import { useSystemConfig } from '../../context/SystemConfigContext'

const { Title, Text } = Typography

// 状态颜色映射
const getStatusColor = (status: SessionStatus): string => {
  switch (status) {
    case SessionStatus.SUBMITTED_FOR_REVIEW:
      return 'blue'
    case SessionStatus.IN_PROGRESS:
      return 'orange'
    case SessionStatus.COMPLETED:
      return 'green'
    case SessionStatus.CANCELLED:
      return 'red'
    default:
      return 'default'
  }
}

// 状态显示文本映射
const getStatusText = (status: SessionStatus): string => {
  switch (status) {
    case SessionStatus.SUBMITTED_FOR_REVIEW:
      return '待审核'
    case SessionStatus.IN_PROGRESS:
      return '进行中'
    case SessionStatus.COMPLETED:
      return '已完成'
    case SessionStatus.CANCELLED:
      return '已取消'
    default:
      return '未知'
  }
}

// 格式化时间
const formatDateTime = (dateTime: string): string => {
  const date = new Date(dateTime)
  return date.toLocaleString('zh-CN')
}

interface ControlDetailProps {
  activeControl: string | null // 这里实际上是activeSession
}

const ControlDetail: React.FC<ControlDetailProps> = ({ activeControl }) => {
  const [sessionDetail, setSessionDetail] = useState<SessionDetail | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const { config } = useSystemConfig()
  
  // 当activeControl（实际是sessionId）变化时，获取session详情
  useEffect(() => {
    if (!activeControl) {
      setSessionDetail(null)
      setError(null)
      return
    }
    
    const fetchSessionDetail = async () => {
      setLoading(true)
      setError(null)
      
      try {
        const assessmentService = createAssessmentService(config.assessmentServerUrl)
        const detail = await assessmentService.getSessionById(activeControl)
        setSessionDetail(detail)
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : '获取session详情失败'
        setError(errorMessage)
        console.error('获取session详情失败:', err)
      } finally {
        setLoading(false)
      }
    }
    
    fetchSessionDetail()
  }, [activeControl, config.assessmentServerUrl])
  
  if (!activeControl) {
    return (
      <div style={{ textAlign: 'center', padding: '24px' }}>
        <Text type="secondary">请选择一个批次查看详情</Text>
      </div>
    )
  }
  
  if (loading) {
    return (
      <Card title="批次详情" size="small">
        <div style={{ textAlign: 'center', padding: '24px' }}>
          <Spin size="large" />
          <div style={{ marginTop: '16px' }}>
            <Text type="secondary">正在加载批次详情...</Text>
          </div>
        </div>
      </Card>
    )
  }
  
  if (error) {
    return (
      <Card title="批次详情" size="small">
        <Alert
          message="加载失败"
          description={error}
          type="error"
          showIcon
          style={{ marginBottom: '16px' }}
        />
        <div style={{ textAlign: 'center' }}>
          <Text type="secondary">请检查网络连接或稍后重试</Text>
        </div>
      </Card>
    )
  }
  
  if (!sessionDetail) {
    return (
      <div style={{ textAlign: 'center', padding: '24px' }}>
        <Text type="secondary">未找到批次详情</Text>
      </div>
    )
  }
  
  return (
    <Card 
      title={
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span>批次详情</span>
          <Tag color={getStatusColor(sessionDetail.status)}>
            {getStatusText(sessionDetail.status)}
          </Tag>
        </div>
      } 
      size="small"
    >
      <Descriptions column={1} size="small">
        <Descriptions.Item label="批次ID">
          <Text code>{sessionDetail.id}</Text>
        </Descriptions.Item>
        
        <Descriptions.Item label="创建时间">
          <Text>{formatDateTime(sessionDetail.created_at)}</Text>
        </Descriptions.Item>
        
        <Descriptions.Item label="发现数量">
          <Text strong>{sessionDetail.findings_count}</Text>
        </Descriptions.Item>
        
        <Descriptions.Item label="操作限制">
          <Text>
            {sessionDetail.action_count} / {sessionDetail.action_limit}
            {sessionDetail.action_count >= sessionDetail.action_limit && (
              <Tag color="red" style={{ marginLeft: '8px' }}>已达上限</Tag>
            )}
          </Text>
        </Descriptions.Item>
        
        <Descriptions.Item label="关联发现">
          <Text>{sessionDetail.findings?.length || 0} 个发现</Text>
        </Descriptions.Item>
      </Descriptions>
    </Card>
  )
}

export default ControlDetail