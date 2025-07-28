import React from 'react';
import { Card, Button, Space, Tag, Typography, Form, Input, message } from 'antd';
import { InfoCircleOutlined, EditOutlined, SaveOutlined, CloseOutlined, CopyOutlined } from '@ant-design/icons';
import { KBDetail } from '../../types/knowledgeBase';

const { Text } = Typography;
const { TextArea } = Input;

interface BasicInfoCardProps {
  kbDetail?: KBDetail;
  isEditing: boolean;
  form: any;
  onEdit: () => void;
  onSave: () => void;
  onCancel: () => void;
  loading?: boolean;
}

export const BasicInfoCard: React.FC<BasicInfoCardProps> = ({
  kbDetail,
  isEditing,
  form,
  onEdit,
  onSave,
  onCancel,
  loading = false
}) => {
  const handleCopyId = async () => {
    try {
      await navigator.clipboard.writeText(kbDetail?.id || '');
      message.success('知识库ID已复制到剪贴板');
    } catch (error) {
      // 如果浏览器不支持clipboard API，使用传统方法
      const textArea = document.createElement('textarea');
      textArea.value = kbDetail?.id || '';
      document.body.appendChild(textArea);
      textArea.select();
      document.execCommand('copy');
      document.body.removeChild(textArea);
      message.success('知识库ID已复制到剪贴板');
    }
  };
  return (
    <Card
      title={
        <Space>
          <InfoCircleOutlined />
          基本信息
        </Space>
      }
      extra={
        !isEditing ? (
          <Button
            icon={<EditOutlined />}
            onClick={onEdit}
            type="text"
          >
            编辑
          </Button>
        ) : (
          <Space>
            <Button
              icon={<SaveOutlined />}
              type="primary"
              size="small"
              onClick={onSave}
              loading={loading}
            >
              保存
            </Button>
            <Button
              icon={<CloseOutlined />}
              size="small"
              onClick={onCancel}
            >
              取消
            </Button>
          </Space>
        )
      }
      className="mb-6"
    >
      {!isEditing ? (
        <div className="space-y-4">
          <div className="flex items-center">
            <Text strong className="w-20 text-gray-600">名称：</Text>
            <Text>{kbDetail?.name}</Text>
          </div>
          <div className="flex items-start">
            <Text strong className="w-20 text-gray-600">描述：</Text>
            <Text>{kbDetail?.description || '暂无描述'}</Text>
          </div>
          <div className="flex items-center">
            <Text strong className="w-20 text-gray-600">创建者：</Text>
            <Text>{kbDetail?.owner_username}</Text>
          </div>
          <div className="flex items-center">
            <Text strong className="w-20 text-gray-600">创建时间：</Text>
            <Text>{new Date(kbDetail?.created_at || '').toLocaleString()}</Text>
          </div>
          <div className="flex items-center">
            <Text strong className="w-20 text-gray-600">状态：</Text>
            <Tag color={kbDetail?.is_public ? 'green' : 'blue'}>
              {kbDetail?.is_public ? '公开' : '私有'}
            </Tag>
          </div>
          <div className="flex items-center">
            <Text strong className="w-20 text-gray-600">知识库ID：</Text>
            <div className="flex items-center space-x-2 flex-1">
              <Text 
                code 
                className="flex-1 bg-gray-50 px-2 py-1 rounded text-sm font-mono"
              >
                {kbDetail?.id}
              </Text>
              <Button
                type="text"
                size="small"
                icon={<CopyOutlined />}
                onClick={handleCopyId}
                className="hover:bg-blue-50 hover:text-blue-600"
                title="复制知识库ID"
              >
                复制
              </Button>
            </div>
          </div>
          <div className="text-xs text-gray-500 bg-blue-50 p-3 rounded-lg">
            <Text>
              💡 此ID可用于外部系统集成时访问特定知识库，请妥善保管
            </Text>
          </div>
        </div>
      ) : (
        <Form form={form} layout="vertical">
          <Form.Item
            name="name"
            label="知识库名称"
            rules={[
              { required: true, message: '请输入知识库名称' },
              { max: 100, message: '名称长度不能超过100个字符' }
            ]}
          >
            <Input placeholder="请输入知识库名称" />
          </Form.Item>
          <Form.Item
            name="description"
            label="描述"
            rules={[
              { max: 500, message: '描述长度不能超过500个字符' }
            ]}
          >
            <TextArea
              rows={3}
              placeholder="请输入知识库描述"
              showCount
              maxLength={500}
            />
          </Form.Item>
        </Form>
      )}
    </Card>
  );
};