import React, { useEffect, useState } from 'react'
import { Modal, Tabs, Form, Input, Button, Space, Divider, Select, message, Spin } from 'antd'
import { useSystemConfig } from '@/context/SystemConfigContext'
import { createAssessmentService } from '@/services/assessmentService'
import { JobSummary } from '@/types/assessment'

const { TabPane } = Tabs

interface ConfigModalProps {
  visible: boolean
  onCancel: () => void
}

const ConfigModal: React.FC<ConfigModalProps> = ({ visible, onCancel }) => {
  const [form] = Form.useForm()
  const { config, updateConfig } = useSystemConfig()
  const [jobs, setJobs] = useState<JobSummary[]>([])
  const [loadingJobs, setLoadingJobs] = useState(false)

  
  // 当模态框打开时，将当前配置填入表单
  useEffect(() => {
    if (visible) {
      form.setFieldsValue(config)
      // 如果有评估服务器URL，尝试获取作业列表
      if (config.assessmentServerUrl) {
        fetchJobs(config.assessmentServerUrl)
      }
    }
  }, [visible, config, form])
  
  // 获取作业列表
  const fetchJobs = async (serverUrl: string) => {
    if (!serverUrl) return
    
    setLoadingJobs(true)
    try {
      const assessmentService = createAssessmentService(serverUrl)
      const jobList = await assessmentService.getJobs()
      setJobs(jobList)
    } catch (error) {
      console.error('获取作业列表失败:', error)
      message.error('获取作业列表失败，请检查服务器URL是否正确')
      setJobs([])
    } finally {
      setLoadingJobs(false)
    }
  }
  
  // 当评估服务器URL改变时，重新获取作业列表
  const handleServerUrlChange = (url: string) => {
    form.setFieldValue('assessmentServerUrl', url)
    if (url) {
      fetchJobs(url)
    } else {
      setJobs([])
    }
  }
  
  const handleOk = () => {
    form.validateFields().then(values => {
      console.log('配置信息:', values)
      // 更新全局配置
      updateConfig(values)
      onCancel()
    })
  }
  
  return (
    <Modal
      title="系统配置"
      open={visible}
      onOk={handleOk}
      onCancel={onCancel}
      width={800}
    >
      <Tabs defaultActiveKey="1">
        <TabPane tab="模型凭证配置" key="1">
          <Form form={form} layout="vertical">
            <Form.Item
              name="modelBaseUrl"
              label="模型Base URL"
              rules={[{ required: true, message: '请输入模型Base URL' }]}
            >
              <Input placeholder="请输入模型Base URL" />
            </Form.Item>
            <Form.Item
              name="modelName"
              label="模型名称"
              rules={[{ required: true, message: '请输入模型名称' }]}
            >
              <Input placeholder="请输入模型名称" />
            </Form.Item>
            <Form.Item
              name="apiKey"
              label="API Key"
              rules={[{ required: true, message: '请输入API Key' }]}
            >
              <Input placeholder="请输入API Key" />
            </Form.Item>
            
            <Divider />
            
            <Form.Item>
              <Space>
                <Button type="primary" htmlType="submit">
                  保存
                </Button>
                <Button htmlType="button" onClick={() => form.resetFields()}>
                  重置
                </Button>
              </Space>
            </Form.Item>
          </Form>
        </TabPane>
        
        <TabPane tab="系统设置" key="2">
          <Form form={form} layout="vertical">
            {/* 知识库配置 */}
            <h3>知识库配置</h3>
            <Form.Item
              name="knowledgeBaseUrl"
              label="知识库URL"
              rules={[{ required: true, message: '请输入知识库URL' }]}
            >
              <Input placeholder="请输入知识库URL" />
            </Form.Item>
            
            <Form.Item
              name="knowledgeBaseUsername"
              label="知识库用户名"
              rules={[{ required: true, message: '请输入知识库用户名' }]}
            >
              <Input placeholder="请输入知识库用户名" />
            </Form.Item>
            
            <Form.Item
              name="knowledgeBasePassword"
              label="知识库密码"
              rules={[{ required: true, message: '请输入知识库密码' }]}
            >
              <Input.Password placeholder="请输入知识库密码" />
            </Form.Item>
            
            <Divider />
            
            {/* 评估服务器配置 */}
            <h3>评估服务器配置</h3>
            <Form.Item
              name="assessmentServerUrl"
              label="评估服务器URL"
              rules={[{ required: true, message: '请输入评估服务器URL' }]}
            >
              <Input 
                placeholder="请输入评估服务器URL" 
                onChange={(e) => handleServerUrlChange(e.target.value)}
              />
            </Form.Item>
            
            <Form.Item
              name="assessmentJobId"
              label="评估作业ID"
              rules={[{ required: true, message: '请选择评估作业ID' }]}
            >
              <Select
                placeholder="请选择评估作业或输入作业ID"
                loading={loadingJobs}
                notFoundContent={loadingJobs ? <Spin size="small" /> : '暂无作业'}
                showSearch
                allowClear
                optionFilterProp="children"
                filterOption={(input, option) =>
                  (option?.label ?? '').toLowerCase().includes(input.toLowerCase())
                }
                options={jobs.map(job => ({
                  label: `${job.name} (${job.status})`,
                  value: job.id
                }))}
              />
            </Form.Item>
            
            <Divider />
            
            <Form.Item>
              <Space>
                <Button type="primary" htmlType="submit">
                  保存
                </Button>
                <Button htmlType="button" onClick={() => form.resetFields()}>
                  重置
                </Button>
              </Space>
            </Form.Item>
          </Form>
        </TabPane>
      </Tabs>
    </Modal>
  )
}

export default ConfigModal