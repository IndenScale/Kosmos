import React from 'react';
import { Card, Button, Space, Tag, Typography, Form, Input } from 'antd';
import { InfoCircleOutlined, EditOutlined, SaveOutlined, CloseOutlined } from '@ant-design/icons';
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