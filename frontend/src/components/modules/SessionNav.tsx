import React, { useState, useEffect } from 'react'
import { List, Input, Spin, Alert, Badge, Typography } from 'antd'
import { SearchOutlined, ClockCircleOutlined, CheckCircleOutlined, ExclamationCircleOutlined } from '@ant-design/icons'
import { useSessionData } from '../../hooks/useSessionData'
import { SessionSummary, SessionStatus } from '../../types/assessment'

const { Search } = Input
const { Text } = Typography

interface SessionNavProps {
  activeSession: string | null
  setActiveSession: (sessionId: string | null) => void
  jobId?: string
}

// 状态颜色映射
const getStatusColor = (status: SessionStatus): string => {
  switch (status) {
    case SessionStatus.SUBMITTED_FOR_REVIEW:
      return '#1890ff' // 蓝色
    case SessionStatus.IN_PROGRESS:
      return '#faad14' // 橙色
    case SessionStatus.COMPLETED:
      return '#52c41a' // 绿色
    case SessionStatus.CANCELLED:
      return '#f5222d' // 红色
    default:
      return '#d9d9d9' // 灰色
  }
}

// 状态图标映射
const getStatusIcon = (status: SessionStatus) => {
  switch (status) {
    case SessionStatus.SUBMITTED_FOR_REVIEW:
      return <ExclamationCircleOutlined />
    case SessionStatus.IN_PROGRESS:
      return <ClockCircleOutlined />
    case SessionStatus.COMPLETED:
      return <CheckCircleOutlined />
    case SessionStatus.CANCELLED:
      return <ExclamationCircleOutlined />
    default:
      return <ClockCircleOutlined />
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

// 格式化创建时间
const formatCreatedAt = (createdAt: string): string => {
  const date = new Date(createdAt)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))
  
  if (diffDays === 0) {
    return '今天'
  } else if (diffDays === 1) {
    return '昨天'
  } else if (diffDays < 7) {
    return `${diffDays}天前`
  } else {
    return date.toLocaleDateString('zh-CN')
  }
}

// 生成批次显示文本
const getBatchText = (session: SessionSummary, index: number): string => {
  return `第${index + 1}批次`
}

const SessionNav: React.FC<SessionNavProps> = ({ 
  activeSession, 
  setActiveSession,
  jobId
}) => {
  const [searchValue, setSearchValue] = useState('')
  
  // 使用session数据Hook
  const { 
    sessions, 
    loading, 
    error, 
    loadSessions, 
    activateSession,
    resetData 
  } = useSessionData()
  
  // 当作业ID变化时加载sessions
  useEffect(() => {
    if (jobId) {
      loadSessions(jobId)
    } else {
      // 如果没有jobId，重置数据
      resetData()
    }
  }, [jobId, loadSessions, resetData])
  
  // 过滤sessions
  const filteredSessions = sessions.filter(session => {
    if (!searchValue) return true
    
    const batchIndex = sessions.indexOf(session)
    const batchText = getBatchText(session, batchIndex)
    const statusText = getStatusText(session.status)
    const createdText = formatCreatedAt(session.created_at)
    
    return (
      batchText.toLowerCase().includes(searchValue.toLowerCase()) ||
      statusText.toLowerCase().includes(searchValue.toLowerCase()) ||
      createdText.toLowerCase().includes(searchValue.toLowerCase()) ||
      session.id.toLowerCase().includes(searchValue.toLowerCase())
    )
  })
  
  const onSearch = (value: string) => {
    setSearchValue(value)
  }
  
  const handleSessionClick = (session: SessionSummary) => {
    if (activeSession === session.id) {
      // 如果点击的是当前激活的session，则取消激活
      setActiveSession(null)
    } else {
      // 激活新的session
      setActiveSession(session.id)
      activateSession(session.id)
    }
  }
  
  return (
    <div style={{ padding: '16px', height: '100%', display: 'flex', flexDirection: 'column' }}>
      <Search 
        placeholder="搜索批次" 
        prefix={<SearchOutlined />} 
        style={{ marginBottom: '16px' }} 
        onChange={(e) => onSearch(e.target.value)}
        allowClear
      />
      
      {loading && (
        <div style={{ textAlign: 'center', padding: '20px' }}>
          <Spin size="large" />
          <div style={{ marginTop: '8px' }}>加载批次数据...</div>
        </div>
      )}
      
      {error && (
        <Alert
          message="加载失败"
          description={error}
          type="error"
          showIcon
          style={{ marginBottom: '16px' }}
        />
      )}
      
      {!loading && !error && sessions.length === 0 && jobId && (
        <Alert
          message="暂无数据"
          description="当前作业没有找到批次数据"
          type="info"
          showIcon
        />
      )}
      
      {!loading && !error && sessions.length === 0 && !jobId && (
        <Alert
          message="请选择作业"
          description="请先选择一个评估作业以查看批次"
          type="info"
          showIcon
        />
      )}
      
      {!loading && !error && filteredSessions.length > 0 && (
        <div style={{ flex: 1, overflow: 'auto' }}>
          <List
            dataSource={filteredSessions}
            renderItem={(session, index) => {
              const originalIndex = sessions.indexOf(session)
              const batchText = getBatchText(session, originalIndex)
              const statusColor = getStatusColor(session.status)
              const statusIcon = getStatusIcon(session.status)
              const statusText = getStatusText(session.status)
              const createdText = formatCreatedAt(session.created_at)
              const isActive = activeSession === session.id
              
              return (
                <List.Item
                  key={session.id}
                  style={{
                    cursor: 'pointer',
                    padding: '12px 16px',
                    backgroundColor: isActive ? '#e6f7ff' : 'transparent',
                    border: isActive ? '1px solid #1890ff' : '1px solid transparent',
                    borderRadius: '6px',
                    marginBottom: '8px',
                    transition: 'all 0.3s ease'
                  }}
                  onClick={() => handleSessionClick(session)}
                >
                  <List.Item.Meta
                    avatar={
                      <Badge 
                        color={statusColor} 
                        style={{ marginTop: '4px' }}
                      />
                    }
                    title={
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <Text strong>{batchText}</Text>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '4px', color: statusColor }}>
                          {statusIcon}
                          <Text style={{ color: statusColor, fontSize: '12px' }}>
                            {statusText}
                          </Text>
                        </div>
                      </div>
                    }
                    description={
                      <div style={{ fontSize: '12px', color: '#666' }}>
                        <div>创建时间: {createdText}</div>
                        <div>发现数量: {session.findings_count}</div>
                        <div>操作数量: {session.action_count}/{session.action_limit}</div>
                      </div>
                    }
                  />
                </List.Item>
              )
            }}
          />
        </div>
      )}
    </div>
  )
}

export default SessionNav