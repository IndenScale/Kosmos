import React from 'react'
import { Card, Typography, List, Button } from 'antd'
import { FileTextOutlined } from '@ant-design/icons'

const { Text } = Typography

// 模拟数据
const evidences: Record<string, any[]> = {
  'control-1.1.1': [
    {
      id: 'evidence-1',
      docId: 'network_design_doc.pdf',
      startLine: 15,
      endLine: 25,
      content: '核心交换机采用双机热备架构，确保网络高可用性...'
    },
    {
      id: 'evidence-2',
      docId: 'firewall_config.txt',
      startLine: 30,
      endLine: 40,
      content: '防火墙已配置冗余链路，主链路故障时自动切换...'
    }
  ]
}

interface EvidencePreviewProps {
  activeControl: string | null
}

const EvidencePreview: React.FC<EvidencePreviewProps> = ({ activeControl }) => {
  const evidenceList = activeControl ? evidences[activeControl] : []
  
  if (!activeControl) {
    return (
      <div style={{ textAlign: 'center', padding: '24px' }}>
        <Text type="secondary">请选择一个控制项查看证据</Text>
      </div>
    )
  }
  
  if (evidenceList.length === 0) {
    return (
      <div style={{ textAlign: 'center', padding: '24px' }}>
        <Text type="secondary">暂无相关证据</Text>
      </div>
    )
  }
  
  return (
    <Card 
      title="证据预览" 
      size="small"
      extra={
        <Button type="link" size="small">
          查看全部
        </Button>
      }
    >
      <List
        itemLayout="horizontal"
        dataSource={evidenceList}
        renderItem={item => (
          <List.Item>
            <List.Item.Meta
              avatar={<FileTextOutlined style={{ fontSize: '16px' }} />}
              title={item.docId}
              description={
                <div>
                  <Text type="secondary">行 {item.startLine}-{item.endLine}</Text>
                  <br />
                  <Text ellipsis={{ tooltip: item.content }}>{item.content}</Text>
                </div>
              }
            />
          </List.Item>
        )}
      />
    </Card>
  )
}

export default EvidencePreview