import React from 'react'
import { Card, List, Typography, Tag } from 'antd'

const { Text } = Typography

// 模拟数据
const sessionHistory = [
  {
    id: 'session-1',
    timestamp: '2023-08-15 14:30:22',
    controlId: '1.1.1',
    status: 'completed',
    agent: 'assessment_agent'
  },
  {
    id: 'session-2',
    timestamp: '2023-08-15 15:45:10',
    controlId: '1.1.2',
    status: 'failed',
    agent: 'assessment_agent'
  },
  {
    id: 'session-3',
    timestamp: '2023-08-16 09:15:33',
    controlId: '2.1.1',
    status: 'in_progress',
    agent: 'audit_agent'
  }
]

const SessionHistory: React.FC = () => {
  const getStatusTag = (status: string) => {
    switch (status) {
      case 'completed':
        return <Tag color="green">已完成</Tag>
      case 'failed':
        return <Tag color="red">失败</Tag>
      case 'in_progress':
        return <Tag color="blue">进行中</Tag>
      default:
        return <Tag>{status}</Tag>
    }
  }
  
  return (
    <Card 
      title="会话历史" 
      size="small"
      style={{ height: '100%' }}
    >
      <List
        itemLayout="horizontal"
        dataSource={sessionHistory}
        renderItem={item => (
          <List.Item>
            <List.Item.Meta
              title={
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <Text strong>会话 {item.id}</Text>
                  {getStatusTag(item.status)}
                </div>
              }
              description={
                <div>
                  <Text type="secondary">{item.timestamp}</Text>
                  <br />
                  <Text>控制项: {item.controlId}</Text>
                  <br />
                  <Text>代理: {item.agent}</Text>
                </div>
              }
            />
          </List.Item>
        )}
      />
    </Card>
  )
}

export default SessionHistory