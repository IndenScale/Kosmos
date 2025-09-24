import React, { useState, useEffect } from 'react'
import { Card, Typography, List, Button, Alert, Spin, Tag, Collapse } from 'antd'
import { FileTextOutlined, EyeOutlined } from '@ant-design/icons'
import { useSessionData } from '@/hooks/useSessionData'
import { Evidence, AssessmentFinding } from '@/types/assessment'

const { Text, Paragraph } = Typography
const { Panel } = Collapse

interface EvidencePreviewProps {
  activeControl: string | null // 实际是sessionId
}

const EvidencePreview: React.FC<EvidencePreviewProps> = ({ activeControl }) => {
  const { activeSession, sessionFindings, sessionLoading, error } = useSessionData()
  const [selectedEvidence, setSelectedEvidence] = useState<Evidence | null>(null)
  const [selectedFinding, setSelectedFinding] = useState<AssessmentFinding | null>(null)
  
  // 收集所有证据
  const allEvidences = React.useMemo(() => {
    const evidences: Array<Evidence & { finding: AssessmentFinding }> = []
    sessionFindings.forEach(finding => {
      finding.evidences.forEach(evidence => {
        evidences.push({ ...evidence, finding })
      })
    })
    return evidences
  }, [sessionFindings])
  
  // 当activeSession变化时，重置选中的证据
  useEffect(() => {
    if (allEvidences.length > 0) {
      setSelectedEvidence(allEvidences[0])
      setSelectedFinding(allEvidences[0].finding)
    } else {
      setSelectedEvidence(null)
      setSelectedFinding(null)
    }
  }, [allEvidences])
  
  if (!activeControl) {
    return (
      <div style={{ textAlign: 'center', padding: '24px' }}>
        <Text type="secondary">请选择一个批次查看证据</Text>
      </div>
    )
  }

  if (sessionLoading) {
    return (
      <Card title="证据预览" size="small">
        <div style={{ textAlign: 'center', padding: '24px' }}>
          <Spin size="large" />
          <div style={{ marginTop: '16px' }}>
            <Text type="secondary">正在加载证据数据...</Text>
          </div>
        </div>
      </Card>
    )
  }

  if (error) {
    return (
      <Card title="证据预览" size="small">
        <Alert
          message="加载失败"
          description={error}
          type="error"
          showIcon
          style={{ marginBottom: '16px' }}
        />
        <div style={{ textAlign: 'center' }}>
          <Text type="secondary">请检查评估服务配置或网络连接</Text>
        </div>
      </Card>
    )
  }

  if (!activeSession || allEvidences.length === 0) {
    return (
      <Card title="证据预览" size="small">
        <div style={{ textAlign: 'center', padding: '24px' }}>
          <Text type="secondary">当前批次暂无证据</Text>
        </div>
      </Card>
    )
  }

  return (
    <Card 
      title={
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span>证据预览</span>
          <Tag color="blue">{allEvidences.length} 个证据</Tag>
        </div>
      }
      size="small"
    >
      <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
        {/* 证据列表 */}
        <div style={{ marginBottom: '16px', maxHeight: '200px', overflow: 'auto' }}>
          <List
            size="small"
            dataSource={allEvidences}
            renderItem={(evidence) => (
              <List.Item
                onClick={() => {
                  setSelectedEvidence(evidence)
                  setSelectedFinding(evidence.finding)
                }}
                style={{
                  cursor: 'pointer',
                  backgroundColor: selectedEvidence?.id === evidence.id ? '#f0f8ff' : 'transparent',
                  padding: '8px',
                  border: selectedEvidence?.id === evidence.id ? '1px solid #1890ff' : '1px solid transparent',
                  borderRadius: '4px',
                  marginBottom: '4px'
                }}
              >
                <List.Item.Meta
                  avatar={<FileTextOutlined style={{ fontSize: '14px', color: '#1890ff' }} />}
                  title={
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <Text strong style={{ fontSize: '12px' }}>
                        {evidence.finding.control_item_definition.display_id}
                      </Text>
                      <Text type="secondary" style={{ fontSize: '11px' }}>
                        行 {evidence.start_line}-{evidence.end_line}
                      </Text>
                    </div>
                  }
                  description={
                    <Text type="secondary" style={{ fontSize: '11px' }}>
                      文档ID: {evidence.doc_id.substring(0, 8)}...
                    </Text>
                  }
                />
              </List.Item>
            )}
          />
        </div>
        
        {/* 选中证据的详细信息 */}
        {selectedEvidence && selectedFinding && (
          <div style={{ flex: 1, overflow: 'auto' }}>
            <Collapse defaultActiveKey={['1']} size="small">
              <Panel 
                header={
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <EyeOutlined />
                    <span>证据详情</span>
                  </div>
                } 
                key="1"
              >
                <div style={{ marginBottom: '12px' }}>
                  <Text strong style={{ display: 'block', marginBottom: '4px' }}>
                    控制项: {selectedFinding.control_item_definition.display_id}
                  </Text>
                  <Text type="secondary" style={{ fontSize: '12px' }}>
                    {selectedFinding.control_item_definition.content}
                  </Text>
                </div>
                
                <div style={{ marginBottom: '12px' }}>
                  <Text strong style={{ display: 'block', marginBottom: '4px' }}>
                    文档信息:
                  </Text>
                  <div style={{ padding: '8px', backgroundColor: '#fafafa', borderRadius: '4px' }}>
                    <Text style={{ fontSize: '12px', display: 'block' }}>
                      文档ID: <Text code>{selectedEvidence.doc_id}</Text>
                    </Text>
                    <Text style={{ fontSize: '12px', display: 'block' }}>
                      行范围: {selectedEvidence.start_line} - {selectedEvidence.end_line}
                    </Text>
                  </div>
                </div>
                
                <div style={{ marginBottom: '12px' }}>
                  <Text strong style={{ display: 'block', marginBottom: '4px' }}>
                    评估结论:
                  </Text>
                  <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                    <Tag color={selectedFinding.judgement === '符合' ? 'green' : 
                               selectedFinding.judgement === '不符合' ? 'red' : 'orange'}>
                      {selectedFinding.judgement || '未评估'}
                    </Tag>
                  </div>
                  {selectedFinding.comment && (
                    <Paragraph 
                      style={{ 
                        marginTop: '8px', 
                        fontSize: '12px',
                        backgroundColor: '#f9f9f9',
                        padding: '8px',
                        borderRadius: '4px'
                      }}
                    >
                      {selectedFinding.comment}
                    </Paragraph>
                  )}
                </div>
                
                <div style={{ textAlign: 'center', marginTop: '16px' }}>
                  <Button 
                    type="primary" 
                    size="small" 
                    icon={<EyeOutlined />}
                    onClick={() => {
                      // TODO: 实现查看完整文档功能
                      console.log('查看完整文档:', selectedEvidence.doc_id)
                    }}
                  >
                    查看完整文档
                  </Button>
                </div>
              </Panel>
            </Collapse>
          </div>
        )}
      </div>
    </Card>
  )
}

export default EvidencePreview