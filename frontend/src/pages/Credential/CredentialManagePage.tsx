/**
 * 模型凭证管理页面
 */

import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Card,
  Table,
  Button,
  Space,
  Tag,
  Modal,
  message,
  Popconfirm,
  Typography,
  Select,
  Tooltip
} from 'antd';
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  EyeOutlined,
  EyeInvisibleOutlined
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';

import { credentialService } from '../../services/credentialService';
import { Credential, ModelType, ModelTypeInfo } from '../../types/credential';
import { CredentialForm } from '../../components/Credential/CredentialForm';

const { Title, Text } = Typography;
const { Option } = Select;

export const CredentialManagePage: React.FC = () => {
  const [selectedModelType, setSelectedModelType] = useState<ModelType | undefined>();
  const [isCreateModalVisible, setIsCreateModalVisible] = useState(false);
  const [isEditModalVisible, setIsEditModalVisible] = useState(false);
  const [editingCredential, setEditingCredential] = useState<Credential | null>(null);
  const [visibleApiKeys, setVisibleApiKeys] = useState<Set<string>>(new Set());

  const queryClient = useQueryClient();

  // 获取模型类型列表
  const { data: modelTypesData } = useQuery({
    queryKey: ['modelTypes'],
    queryFn: () => credentialService.getModelTypes(),
  });

  // 获取凭证列表
  const { data: credentialsData, isLoading } = useQuery({
    queryKey: ['credentials', selectedModelType],
    queryFn: () => credentialService.getUserCredentials(selectedModelType),
  });

  // 删除凭证
  const deleteMutation = useMutation({
    mutationFn: (credentialId: string) => credentialService.deleteCredential(credentialId),
    onSuccess: () => {
      message.success('凭证删除成功');
      queryClient.invalidateQueries({ queryKey: ['credentials'] });
    },
    onError: (error: any) => {
      message.error(`删除失败: ${error.response?.data?.detail || error.message}`);
    },
  });

  const handleCreateSuccess = () => {
    setIsCreateModalVisible(false);
    queryClient.invalidateQueries({ queryKey: ['credentials'] });
    message.success('凭证创建成功');
  };

  const handleEditSuccess = () => {
    setIsEditModalVisible(false);
    setEditingCredential(null);
    queryClient.invalidateQueries({ queryKey: ['credentials'] });
    message.success('凭证更新成功');
  };

  const handleEdit = (credential: Credential) => {
    setEditingCredential(credential);
    setIsEditModalVisible(true);
  };

  const handleDelete = (credentialId: string) => {
    deleteMutation.mutate(credentialId);
  };

  const toggleApiKeyVisibility = (credentialId: string) => {
    const newVisibleKeys = new Set(visibleApiKeys);
    if (newVisibleKeys.has(credentialId)) {
      newVisibleKeys.delete(credentialId);
    } else {
      newVisibleKeys.add(credentialId);
    }
    setVisibleApiKeys(newVisibleKeys);
  };

  const getModelTypeTag = (modelType: ModelType) => {
    const typeInfo = modelTypesData?.model_types.find(t => t.type === modelType);
    const colors = {
      [ModelType.EMBEDDING]: 'blue',
      [ModelType.RERANKER]: 'green',
      [ModelType.LLM]: 'purple',
      [ModelType.VLM]: 'orange',
    };
    
    return (
      <Tag color={colors[modelType]}>
        {typeInfo?.name || modelType}
      </Tag>
    );
  };

  const columns: ColumnsType<Credential> = [
    {
      title: '凭证名称',
      dataIndex: 'name',
      key: 'name',
      ellipsis: true,
    },
    {
      title: '服务提供商',
      dataIndex: 'provider',
      key: 'provider',
      ellipsis: true,
    },
    {
      title: '模型类型',
      dataIndex: 'model_type',
      key: 'model_type',
      render: (modelType: ModelType) => getModelTypeTag(modelType),
    },
    {
      title: 'API密钥',
      dataIndex: 'api_key_display',
      key: 'api_key_display',
      render: (apiKeyDisplay: string, record: Credential) => (
        <Space>
          <Text code>
            {visibleApiKeys.has(record.id) ? record.api_key_encrypted : apiKeyDisplay}
          </Text>
          <Button
            type="text"
            size="small"
            icon={visibleApiKeys.has(record.id) ? <EyeInvisibleOutlined /> : <EyeOutlined />}
            onClick={() => toggleApiKeyVisibility(record.id)}
          />
        </Space>
      ),
    },
    {
      title: 'Base URL',
      dataIndex: 'base_url',
      key: 'base_url',
      ellipsis: true,
      render: (url: string) => (
        <Tooltip title={url}>
          <Text ellipsis style={{ maxWidth: 200 }}>
            {url}
          </Text>
        </Tooltip>
      ),
    },
    {
      title: '状态',
      dataIndex: 'is_active',
      key: 'is_active',
      render: (isActive: string) => (
        <Tag color={isActive === 'true' ? 'success' : 'default'}>
          {isActive === 'true' ? '启用' : '禁用'}
        </Tag>
      ),
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (date: string) => new Date(date).toLocaleString(),
    },
    {
      title: '操作',
      key: 'actions',
      render: (_, record: Credential) => (
        <Space>
          <Button
            type="text"
            icon={<EditOutlined />}
            onClick={() => handleEdit(record)}
          >
            编辑
          </Button>
          <Popconfirm
            title="确定要删除这个凭证吗？"
            description="删除后无法恢复，请谨慎操作。"
            onConfirm={() => handleDelete(record.id)}
            okText="确定"
            cancelText="取消"
          >
            <Button
              type="text"
              danger
              icon={<DeleteOutlined />}
              loading={deleteMutation.isPending}
            >
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div className="p-6">
      <div className="mb-6">
        <Title level={2}>模型凭证管理</Title>
        <Text type="secondary">
          管理您的AI模型访问凭证，包括Embedding、Reranker、LLM和VLM模型
        </Text>
      </div>

      <Card>
        <div className="mb-4 flex justify-between items-center">
          <Space>
            <Select
              placeholder="筛选模型类型"
              allowClear
              style={{ width: 200 }}
              value={selectedModelType}
              onChange={setSelectedModelType}
            >
              {modelTypesData?.model_types.map((type: ModelTypeInfo) => (
                <Option key={type.type} value={type.type}>
                  {type.name}
                </Option>
              ))}
            </Select>
          </Space>
          
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => setIsCreateModalVisible(true)}
          >
            添加凭证
          </Button>
        </div>

        <Table
          columns={columns}
          dataSource={credentialsData?.credentials || []}
          rowKey="id"
          loading={isLoading}
          pagination={{
            total: credentialsData?.total || 0,
            pageSize: 20,
            showSizeChanger: true,
            showQuickJumper: true,
            showTotal: (total, range) => `第 ${range[0]}-${range[1]} 条，共 ${total} 条`,
          }}
        />
      </Card>

      {/* 创建凭证模态框 */}
      <Modal
        title="添加模型凭证"
        open={isCreateModalVisible}
        onCancel={() => setIsCreateModalVisible(false)}
        footer={null}
        width={600}
      >
        <CredentialForm
          onSuccess={handleCreateSuccess}
          onCancel={() => setIsCreateModalVisible(false)}
        />
      </Modal>

      {/* 编辑凭证模态框 */}
      <Modal
        title="编辑模型凭证"
        open={isEditModalVisible}
        onCancel={() => {
          setIsEditModalVisible(false);
          setEditingCredential(null);
        }}
        footer={null}
        width={600}
      >
        {editingCredential && (
          <CredentialForm
            credential={editingCredential}
            onSuccess={handleEditSuccess}
            onCancel={() => {
              setIsEditModalVisible(false);
              setEditingCredential(null);
            }}
          />
        )}
      </Modal>
    </div>
  );
};