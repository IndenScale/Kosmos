import React from 'react'
import { Card, Statistic, Row, Col, Typography, Alert, Spin, Progress } from 'antd'
import { CheckCircleOutlined, CloseCircleOutlined, ExclamationCircleOutlined, QuestionCircleOutlined, MinusCircleOutlined } from '@ant-design/icons'
import { useAssessmentFindings } from '@/hooks/useAssessmentFindings'
import { JudgementEnum } from '@/types/assessment'

const { Title } = Typography

const FindingsOverview: React.FC = () => {
  const { findings, loading, error } = useAssessmentFindings()

  if (loading) {
    return (
      <Card title={<Title level={4} style={{ margin: 0 }}>评估概览</Title>}>
        <div style={{ textAlign: 'center', padding: '24px' }}>
          <Spin size="large" />
          <div style={{ marginTop: '16px' }}>正在加载评估数据...</div>
        </div>
      </Card>
    )
  }

  if (error) {
    return (
      <Card title={<Title level={4} style={{ margin: 0 }}>评估概览</Title>}>
        <Alert
          message="加载失败"
          description={error}
          type="error"
          showIcon
        />
      </Card>
    )
  }

  // 统计各种判定结果的数量
  const stats = findings.reduce((acc, finding) => {
    const judgement = finding.judgement
    if (judgement === JudgementEnum.CONFORMANT) {
      acc.conformant++
    } else if (judgement === JudgementEnum.NON_CONFORMANT) {
      acc.nonConformant++
    } else if (judgement === JudgementEnum.PARTIALLY_CONFORMANT) {
      acc.partiallyConformant++
    } else if (judgement === JudgementEnum.NOT_APPLICABLE) {
      acc.notApplicable++
    } else if (judgement === JudgementEnum.UNCONFIRMED) {
      acc.unconfirmed++
    } else {
      acc.pending++
    }
    return acc
  }, {
    conformant: 0,
    nonConformant: 0,
    partiallyConformant: 0,
    notApplicable: 0,
    unconfirmed: 0,
    pending: 0
  })

  const total = findings.length
  const completed = total - stats.pending
  const completionRate = total > 0 ? Math.round((completed / total) * 100) : 0

  return (
    <Card title={<Title level={4} style={{ margin: 0 }}>评估概览</Title>}>
      <Row gutter={[16, 16]} style={{ marginBottom: '24px' }}>
        <Col span={12}>
          <Card size="small">
            <Statistic
              title="总控制项"
              value={total}
              prefix={<ExclamationCircleOutlined />}
            />
          </Card>
        </Col>
        <Col span={12}>
          <Card size="small">
            <Statistic
              title="完成进度"
              value={completionRate}
              suffix="%"
              prefix={<Progress type="circle" percent={completionRate} size={24} />}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col span={8}>
          <Card size="small">
            <Statistic
              title="合规"
              value={stats.conformant}
              valueStyle={{ color: '#52c41a' }}
              prefix={<CheckCircleOutlined />}
            />
          </Card>
        </Col>
        <Col span={8}>
          <Card size="small">
            <Statistic
              title="不合规"
              value={stats.nonConformant}
              valueStyle={{ color: '#ff4d4f' }}
              prefix={<CloseCircleOutlined />}
            />
          </Card>
        </Col>
        <Col span={8}>
          <Card size="small">
            <Statistic
              title="部分符合"
              value={stats.partiallyConformant}
              valueStyle={{ color: '#faad14' }}
              prefix={<ExclamationCircleOutlined />}
            />
          </Card>
        </Col>
        <Col span={8}>
          <Card size="small">
            <Statistic
              title="不适用"
              value={stats.notApplicable}
              valueStyle={{ color: '#d9d9d9' }}
              prefix={<MinusCircleOutlined />}
            />
          </Card>
        </Col>
        <Col span={8}>
          <Card size="small">
            <Statistic
              title="无法确认"
              value={stats.unconfirmed}
              valueStyle={{ color: '#722ed1' }}
              prefix={<QuestionCircleOutlined />}
            />
          </Card>
        </Col>
        <Col span={8}>
          <Card size="small">
            <Statistic
              title="待评估"
              value={stats.pending}
              valueStyle={{ color: '#8c8c8c' }}
              prefix={<QuestionCircleOutlined />}
            />
          </Card>
        </Col>
      </Row>
    </Card>
  )
}

export default FindingsOverview