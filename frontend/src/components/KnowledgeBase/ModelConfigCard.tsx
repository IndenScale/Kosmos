import React, { useState } from 'react';
import { Card, Space, Typography, Button, Modal, Descriptions, Tag, Spin, message, Empty, Form, Select, Input, Divider } from 'antd';
import { SettingOutlined, EyeOutlined, EditOutlined, SaveOutlined, CloseOutlined } from '@ant-design/icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { credentialService } from '../../services/credentialService';
import { KBModelConfig, Credential, ModelType, KBModelConfigCreate, KBModelConfigUpdate } from '../../types/credential';

const { Text, Title } = Typography;
const { TextArea } = Input;

interface ModelConfigCardProps {
  kbId: string;
}

// 预定义的模型类型配置
const MODEL_TYPES = [
  { key: 'llm', label: '大语言模型', color: 'orange', description: '用于对话和文本生成' },
  { key: 'vlm', label: '视觉语言模型', color: 'purple', description: '用于图像理解和多模态任务' },
  { key: 'embedding', label: 'Embedding模型', color: 'blue', description: '用于文本向量化和语义搜索' },
  { key: 'reranker', label: 'Reranker模型', color: 'green', description: '用于搜索结果重排序' },
];

export const ModelConfigCard: React.FC<ModelConfigCardProps> = ({ kbId }) => {
  const [selectedCredential, setSelectedCredential] = useState<Credential | null>(null);
  const [credentialModalVisible, setCredentialModalVisible] = useState(false);
  const [editModalVisible, setEditModalVisible] = useState(false);
  const [editingModelType, setEditingModelType] = useState<string>('');
  const [editingConfig, setEditingConfig] = useState<KBModelConfig | null>(null);
  const [editForm] = Form.useForm();
  const queryClient = useQueryClient();

  // 获取知识库模型配置
  const { data: configsData, isLoading } = useQuery({
    queryKey: ['kbModelConfigs', kbId],
    queryFn: () => credentialService.getKBModelConfigs(kbId),
    enabled: !!kbId,
  });

  // 获取用户的所有凭证
  const { data: credentialsData } = useQuery({
    queryKey: ['userCredentials'],
    queryFn: () => credentialService.getUserCredentials(),
  });

  // 创建模型配置
  const createConfigMutation = useMutation({
    mutationFn: (data: KBModelConfigCreate) => credentialService.createKBModelConfig(data),
    onSuccess: () => {
      message.success('模型配置创建成功');
      setEditModalVisible(false);
      editForm.resetFields();
      queryClient.invalidateQueries({ queryKey: ['kbModelConfigs', kbId] });
    },
    onError: (error: any) => {
      message.error(error.response?.data?.detail || '创建失败');
    },
  });

  // 更新模型配置
  const updateConfigMutation = useMutation({
    mutationFn: ({ configId, data }: { configId: string; data: KBModelConfigUpdate }) => 
      credentialService.updateKBModelConfig(configId, data),
    onSuccess: () => {
      message.success('模型配置更新成功');
      setEditModalVisible(false);
      setEditingConfig(null);
      editForm.resetFields();
      queryClient.invalidateQueries({ queryKey: ['kbModelConfigs', kbId] });
    },
    onError: (error: any) => {
      message.error(error.response?.data?.detail || '更新失败');
    },
  });

  // 删除模型配置
  const deleteConfigMutation = useMutation({
    mutationFn: (configId: string) => credentialService.deleteKBModelConfig(configId),
    onSuccess: () => {
      message.success('模型配置删除成功');
      queryClient.invalidateQueries({ queryKey: ['kbModelConfigs', kbId] });
    },
    onError: (error: any) => {
      message.error(error.response?.data?.detail || '删除失败');
    },
  });

  const handleViewCredential = (credential: Credential) => {
    setSelectedCredential(credential);
    setCredentialModalVisible(true);
  };

  const handleEditConfig = (modelType: string, existingConfig?: KBModelConfig) => {
    setEditingModelType(modelType);
    setEditingConfig(existingConfig || null);
    
    if (existingConfig) {
      // 编辑现有配置
      editForm.setFieldsValue({
        model_name: existingConfig.model_name,
        credential_id: existingConfig.credential_id,
        config_params: JSON.stringify(existingConfig.config_params || {}, null, 2),
      });
    } else {
      // 新建配置（实际上是为该模型类型创建配置）
      editForm.resetFields();
      editForm.setFieldsValue({
        config_params: '{}',
      });
    }
    setEditModalVisible(true);
  };

  const handleSaveConfig = () => {
    editForm.validateFields().then(values => {
      try {
        const configParams = values.config_params ? JSON.parse(values.config_params) : {};
        
        if (editingConfig) {
          // 更新现有配置
          updateConfigMutation.mutate({
            configId: editingConfig.id,
            data: {
              model_name: values.model_name,
              credential_id: values.credential_id,
              config_params: configParams,
            }
          });
        } else {
          // 为该模型类型创建新配置
          createConfigMutation.mutate({
            kb_id: kbId,
            model_name: values.model_name,
            credential_id: values.credential_id,
            config_params: configParams,
          });
        }
      } catch (error) {
        message.error('配置参数JSON格式错误');
      }
    });
  };

  const handleDeleteConfig = (configId: string) => {
    Modal.confirm({
      title: '确认删除',
      content: '确定要删除这个模型配置吗？此操作不可撤销。',
      okText: '删除',
      okType: 'danger',
      cancelText: '取消',
      onOk: () => {
        deleteConfigMutation.mutate(configId);
      },
    });
  };

  const getModelTypeLabel = (credential: Credential | undefined) => {
    if (!credential) return '未知类型';
    const typeMap: Record<string, string> = {
      'embedding': 'Embedding模型',
      'reranker': 'Reranker模型',
      'llm': '大语言模型',
      'vlm': '视觉语言模型'
    };
    return typeMap[credential.model_type] || credential.model_type;
  };

  const getModelTypeColor = (credential: Credential | undefined) => {
    if (!credential) return 'default';
    const colorMap: Record<string, string> = {
      'embedding': 'blue',
      'reranker': 'green',
      'llm': 'orange',
      'vlm': 'purple'
    };
    return colorMap[credential.model_type] || 'default';
  };

  const renderConfigParams = (params: Record<string, any> | undefined) => {
    if (!params || Object.keys(params).length === 0) {
      return <Text type="secondary" className="text-xs">无特殊配置</Text>;
    }

    const entries = Object.entries(params);
    
    // 如果参数较多，只显示前3个，其余用省略号表示
    if (entries.length > 3) {
      return (
        <div className="space-y-1">
          {entries.slice(0, 3).map(([key, value]) => (
            <div key={key} className="flex items-center space-x-2">
              <Text code className="text-xs bg-blue-50 px-1 rounded">{key}</Text>
              <Text className="text-xs text-gray-600 truncate" style={{ maxWidth: '80px' }} title={String(value)}>
                {String(value)}
              </Text>
            </div>
          ))}
          <Text type="secondary" className="text-xs">
            +{entries.length - 3} 个参数...
          </Text>
        </div>
      );
    }

    return (
      <div className="space-y-1">
        {entries.map(([key, value]) => (
          <div key={key} className="flex items-center space-x-2">
            <Text code className="text-xs bg-blue-50 px-1 rounded">{key}</Text>
            <Text className="text-xs text-gray-600 truncate" style={{ maxWidth: '100px' }} title={String(value)}>
              {String(value)}
            </Text>
          </div>
        ))}
      </div>
    );
  };

  if (isLoading) {
    return (
      <Card
        title={
          <Space>
            <SettingOutlined />
            模型配置
          </Space>
        }
        className="mb-6"
      >
        <div className="flex justify-center items-center h-32">
          <Spin size="large" />
        </div>
      </Card>
    );
  }

  const configs = configsData?.configs || [];
  
  // 为每种模型类型找到对应的配置
  const getConfigForType = (modelType: string) => {
    return configs.find((config: KBModelConfig) => 
      config.credential?.model_type === modelType
    );
  };

  return (
    <>
      <Card
        title={
          <Space>
            <SettingOutlined />
            模型配置
          </Space>
        }
        className="mb-6"
      >
        <div className="space-y-4">
          {MODEL_TYPES.map((modelType) => {
            const existingConfig = getConfigForType(modelType.key);
            
            return (
              <div key={modelType.key} className="p-4 bg-gray-50 rounded-lg border border-gray-200 hover:border-blue-300 transition-colors">
                {/* 头部：模型类型和操作按钮 */}
                <div className="flex justify-between items-center mb-3">
                  <div className="flex items-center space-x-3">
                    <Tag color={modelType.color} className="text-sm font-medium">
                      {modelType.label}
                    </Tag>
                    <Text type="secondary" className="text-xs">
                      {modelType.description}
                    </Text>
                  </div>
                  <div className="flex items-center space-x-1">
                    {existingConfig?.credential && (
                      <Button
                        type="text"
                        size="small"
                        icon={<EyeOutlined />}
                        onClick={() => handleViewCredential(existingConfig.credential!)}
                        className="text-gray-500 hover:text-blue-500"
                        title="查看凭证"
                      />
                    )}
                    <Button
                      type="text"
                      size="small"
                      icon={<EditOutlined />}
                      onClick={() => handleEditConfig(modelType.key, existingConfig)}
                      className="text-gray-500 hover:text-green-500"
                      title={existingConfig ? "编辑配置" : "配置模型"}
                    />
                  </div>
                </div>
                
                {/* 配置详情 */}
                {existingConfig ? (
                  <div className="space-y-2 text-sm">
                    <div className="flex items-center">
                      <Text className="w-16 text-gray-500 flex-shrink-0">模型：</Text>
                      <Text strong className="text-gray-800" title={existingConfig.model_name}>
                        {existingConfig.model_name}
                      </Text>
                    </div>
                    <div className="flex items-center">
                      <Text className="w-16 text-gray-500 flex-shrink-0">凭证：</Text>
                      <Text className="text-gray-700 truncate" title={existingConfig.credential?.name}>
                        {existingConfig.credential?.name || '未配置'}
                      </Text>
                    </div>
                    <div className="flex items-center">
                      <Text className="w-16 text-gray-500 flex-shrink-0">服务商：</Text>
                      <Text className="text-gray-700">
                        {existingConfig.credential?.provider || '未配置'}
                      </Text>
                    </div>
                    <div className="flex items-start">
                      <Text className="w-16 text-gray-500 flex-shrink-0 mt-0.5">参数：</Text>
                      <div className="flex-1 min-w-0">
                        {renderConfigParams(existingConfig.config_params)}
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="text-center py-4">
                    <Text type="secondary" className="text-sm">
                      尚未配置此类型模型
                    </Text>
                    <br />
                    <Button
                      type="link"
                      size="small"
                      onClick={() => handleEditConfig(modelType.key)}
                      className="mt-1"
                    >
                      点击配置
                    </Button>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </Card>

      {/* 凭证详情模态框 */}
      <Modal
        title="凭证详情"
        open={credentialModalVisible}
        onCancel={() => setCredentialModalVisible(false)}
        footer={[
          <Button key="close" onClick={() => setCredentialModalVisible(false)}>
            关闭
          </Button>
        ]}
        width={600}
      >
        {selectedCredential && (
          <Descriptions column={1} bordered>
            <Descriptions.Item label="凭证名称">
              {selectedCredential.name}
            </Descriptions.Item>
            <Descriptions.Item label="服务提供商">
              {selectedCredential.provider}
            </Descriptions.Item>
            <Descriptions.Item label="模型类型">
              <Tag color={getModelTypeColor(selectedCredential)}>
                {getModelTypeLabel(selectedCredential)}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="Base URL">
              <Text code>{selectedCredential.base_url}</Text>
            </Descriptions.Item>
            <Descriptions.Item label="API密钥">
              <Text code>{selectedCredential.api_key_display}</Text>
            </Descriptions.Item>
            <Descriptions.Item label="状态">
              <Tag color={selectedCredential.is_active === 'true' ? 'green' : 'red'}>
                {selectedCredential.is_active === 'true' ? '启用' : '禁用'}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="创建时间">
              {new Date(selectedCredential.created_at).toLocaleString()}
            </Descriptions.Item>
            <Descriptions.Item label="更新时间">
              {new Date(selectedCredential.updated_at).toLocaleString()}
            </Descriptions.Item>
            {selectedCredential.description && (
              <Descriptions.Item label="描述">
                {selectedCredential.description}
              </Descriptions.Item>
            )}
          </Descriptions>
        )}
      </Modal>

      {/* 编辑模型配置模态框 */}
      <Modal
        title={`${editingConfig ? '编辑' : '配置'}${MODEL_TYPES.find(t => t.key === editingModelType)?.label || '模型'}`}
        open={editModalVisible}
        onCancel={() => {
          setEditModalVisible(false);
          setEditingConfig(null);
          setEditingModelType('');
          editForm.resetFields();
        }}
        footer={[
          <Button 
            key="cancel" 
            onClick={() => {
              setEditModalVisible(false);
              setEditingConfig(null);
              setEditingModelType('');
              editForm.resetFields();
            }}
          >
            取消
          </Button>,
          <Button
            key="save"
            type="primary"
            icon={<SaveOutlined />}
            loading={createConfigMutation.isPending || updateConfigMutation.isPending}
            onClick={handleSaveConfig}
          >
            保存
          </Button>
        ]}
        width={800}
        destroyOnClose
      >
        <Form
          form={editForm}
          layout="vertical"
          initialValues={{
            config_params: '{}',
          }}
        >
          {/* 显示当前配置的模型类型 */}
          <div className="mb-4 p-3 bg-blue-50 rounded">
            <Text strong>模型类型：</Text>
            <Tag color={MODEL_TYPES.find(t => t.key === editingModelType)?.color} className="ml-2">
              {MODEL_TYPES.find(t => t.key === editingModelType)?.label}
            </Tag>
            <br />
            <Text type="secondary" className="text-sm">
              {MODEL_TYPES.find(t => t.key === editingModelType)?.description}
            </Text>
          </div>

          <Form.Item
            name="model_name"
            label="模型名称"
            rules={[
              { required: true, message: '请输入模型名称' },
              { max: 100, message: '模型名称不能超过100个字符' }
            ]}
          >
            <Input placeholder="例如：gpt-4, text-embedding-ada-002" />
          </Form.Item>

          <Form.Item
            name="credential_id"
            label="选择凭证"
            rules={[{ required: true, message: '请选择一个凭证' }]}
          >
            <Select
              placeholder="请选择模型访问凭证"
              showSearch
              optionFilterProp="children"
              loading={!credentialsData}
            >
              {credentialsData?.credentials
                ?.filter((credential: Credential) => 
                  credential.model_type === editingModelType
                )
                ?.map((credential: Credential) => (
                <Select.Option key={credential.id} value={credential.id}>
                  <div className="flex items-center justify-between">
                    <span>{credential.name}</span>
                    <Text type="secondary" className="text-xs">
                      {credential.provider}
                    </Text>
                  </div>
                </Select.Option>
              ))}
            </Select>
          </Form.Item>

          <Form.Item
            name="config_params"
            label="配置参数 (JSON格式)"
            rules={[
              {
                validator: (_, value) => {
                  if (!value) return Promise.resolve();
                  try {
                    JSON.parse(value);
                    return Promise.resolve();
                  } catch {
                    return Promise.reject(new Error('请输入有效的JSON格式'));
                  }
                }
              }
            ]}
          >
            <TextArea
              rows={8}
              placeholder={`请输入JSON格式的配置参数，例如：
{
  "temperature": 0.7,
  "max_tokens": 1000,
  "top_p": 0.9
}`}
              style={{ fontFamily: 'monospace' }}
            />
          </Form.Item>

          <div className="text-sm text-gray-500 bg-blue-50 p-3 rounded">
            <Text>
              💡 配置参数将传递给模型API调用。常见参数包括：
              <br />• temperature: 控制输出随机性 (0-2)
              <br />• max_tokens: 最大输出长度
              <br />• top_p: 核采样参数 (0-1)
              <br />• frequency_penalty: 频率惩罚 (-2 到 2)
            </Text>
          </div>
        </Form>
      </Modal>
    </>
  );
};