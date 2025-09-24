import React, { useState, useEffect } from 'react'
import { Card, Form, Select, Input, Button, Space, Typography, Alert, Spin, List, Tag } from 'antd'
import { useSessionData } from '@/hooks/useSessionData'
import { JudgementEnum, AssessmentFinding } from '@/types/assessment'

const { Title, Text } = Typography
const { Option } = Select

// 判定结果颜色映射
const getJudgementColor = (judgement: JudgementEnum | null): string => {
  switch (judgement) {
    case JudgementEnum.CONFORMANT:
      return 'green'
    case JudgementEnum.NON_CONFORMANT:
      return 'red'
    case JudgementEnum.PARTIALLY_CONFORMANT:
      return 'orange'
    case JudgementEnum.NOT_APPLICABLE:
      return 'gray'
    case JudgementEnum.UNCONFIRMED:
      return 'blue'
    default:
      return 'default'
  }
}

interface AssessmentResultProps {
  activeControl: string | null // 实际是sessionId
}

const AssessmentResult: React.FC<AssessmentResultProps> = ({ activeControl }) => {
  const { activeSession, sessionFindings, sessionLoading, error } = useSessionData()
  const [selectedFinding, setSelectedFinding] = useState<AssessmentFinding | null>(null)
  
  // 当activeSession变化时，重置选中的finding
  useEffect(() => {
    if (activeSession && sessionFindings.length > 0) {
      setSelectedFinding(sessionFindings[0]) // 默认选择第一个finding
    } else {
      setSelectedFinding(null)
    }
  }, [activeSession, sessionFindings])
  
  if (!activeControl) {
    return (
      <div style={{ textAlign: 'center', padding: '24px' }}>
        <Text type="secondary">请选择一个批次查看评估结论</Text>
      </div>
    )
  }

  if (sessionLoading) {
    return (
      <Card title={<Title level={5} style={{ margin: 0 }}>评估结论</Title>} size="small">
        <div style={{ textAlign: 'center', padding: '24px' }}>
          <Spin size="large" />
          <div style={{ marginTop: '16px' }}>
            <Text type="secondary">正在加载评估数据...</Text>
          </div>
        </div>
      </Card>
    )
  }

  if (error) {
    return (
      <Card title={<Title level={5} style={{ margin: 0 }}>评估结论</Title>} size="small">
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

  if (!activeSession || sessionFindings.length === 0) {
    return (
      <Card title={<Title level={5} style={{ margin: 0 }}>评估结论</Title>} size="small">
        <div style={{ textAlign: 'center', padding: '24px' }}>
          <Text type="secondary">当前批次暂无评估发现</Text>
        </div>
      </Card>
    )
  }

  return (
    <Card 
      title={<Title level={5} style={{ margin: 0 }}>评估结论</Title>} 
      size="small"
    >
      <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
        {/* 发现列表 */}
        <div style={{ marginBottom: '16px', maxHeight: '200px', overflow: 'auto' }}>
          <Text strong style={{ marginBottom: '8px', display: 'block' }}>
            评估发现 ({sessionFindings.length})
          </Text>
          <List
            size="small"
            dataSource={sessionFindings}
            renderItem={(finding) => (
              <List.Item
                onClick={() => setSelectedFinding(finding)}
                style={{
                  cursor: 'pointer',
                  backgroundColor: selectedFinding?.id === finding.id ? '#f0f8ff' : 'transparent',
                  padding: '8px',
                  border: selectedFinding?.id === finding.id ? '1px solid #1890ff' : '1px solid transparent',
                  borderRadius: '4px',
                  marginBottom: '4px'
                }}
              >
                <div style={{ width: '100%' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <Text strong style={{ fontSize: '12px' }}>
                      {finding.control_item_definition.display_id}
                    </Text>
                    <Tag color={getJudgementColor(finding.judgement)}>
                       {finding.judgement || '未评估'}
                     </Tag>
                  </div>
                  <Text type="secondary" style={{ fontSize: '11px' }}>
                    {finding.control_item_definition.content.substring(0, 50)}...
                  </Text>
                </div>
              </List.Item>
            )}
          />
        </div>
        
        {/* 选中发现的详细信息 */}
        {selectedFinding && (
          <AssessmentForm finding={selectedFinding} />
        )}
      </div>
    </Card>
  )
}

// 评估表单组件
const AssessmentForm: React.FC<{
  finding: AssessmentFinding
}> = ({ finding }) => {
  const [form] = Form.useForm()
  
  useEffect(() => {
    form.setFieldsValue({
      judgement: finding.judgement,
      comment: finding.comment || '',
      supplement: finding.supplement || ''
    })
  }, [finding, form])
  
  const onFinish = (values: any) => {
    console.log('保存评估结论:', {
      findingId: finding.id,
      ...values
    })
    // TODO: 实现保存功能，将数据提交到评估服务
  }
  
  return (
    <div style={{ flex: 1 }}>
      <div style={{ marginBottom: '12px', padding: '8px', backgroundColor: '#fafafa', borderRadius: '4px' }}>
        <Text strong style={{ display: 'block', marginBottom: '4px' }}>
          {finding.control_item_definition.display_id} - {finding.control_item_definition.details?.heading}
        </Text>
        <Text type="secondary" style={{ fontSize: '12px' }}>
          {finding.control_item_definition.content}
        </Text>
      </div>
      
      <Form form={form} layout="vertical" onFinish={onFinish} size="small">
        <Form.Item
          name="judgement"
          label="判定结果"
          rules={[{ required: true, message: '请选择判定结果' }]}
        >
          <Select placeholder="请选择判定结果" size="small">
            <Option value={JudgementEnum.CONFORMANT}>符合</Option>
            <Option value={JudgementEnum.NON_CONFORMANT}>不符合</Option>
            <Option value={JudgementEnum.PARTIALLY_CONFORMANT}>部分符合</Option>
            <Option value={JudgementEnum.NOT_APPLICABLE}>不涉及</Option>
            <Option value={JudgementEnum.UNCONFIRMED}>无法确认</Option>
          </Select>
        </Form.Item>
        
        <Form.Item
          name="comment"
          label="评估意见"
        >
          <Input.TextArea placeholder="请输入评估意见" rows={2} size="small" />
        </Form.Item>
        
        <Form.Item
          name="supplement"
          label="补充说明"
        >
          <Input.TextArea placeholder="请输入补充说明" rows={2} size="small" />
        </Form.Item>
        
        <Form.Item style={{ marginBottom: 0 }}>
          <Button type="primary" size="small" onClick={() => form.submit()}>
            保存结论
          </Button>
        </Form.Item>
      </Form>
    </div>
  )
}

export default AssessmentResult