/**
 * 凭证表单组件
 */

import React, { useEffect } from 'react';
import { Form, Input, Select, Button, Space, message } from 'antd';
import { useMutation, useQuery } from '@tanstack/react-query';

import { credentialService } from '../../services/credentialService';
import { Credential, CredentialCreate, CredentialUpdate, ModelType, ModelTypeInfo } from '../../types/credential';

const { Option } = Select;
const { TextArea } = Input;

interface CredentialFormProps {
  credential?: Credential;
  onSuccess: () => void;
  onCancel: () => void;
}

export const CredentialForm: React.FC<CredentialFormProps> = ({
  credential,
  onSuccess,
  onCancel,
}) => {
  const [form] = Form.useForm();
  const isEditing = !!credential;

  // 获取模型类型列表
  const { data: modelTypesData } = useQuery({
    queryKey: ['modelTypes'],
    queryFn: () => credentialService.getModelTypes(),
  });

  // 创建凭证
  const createMutation = useMutation({
    mutationFn: (data: CredentialCreate) => credentialService.createCredential(data),
    onSuccess: () => {
      message.success('凭证创建成功');
      onSuccess();
    },
    onError: (error: any) => {
      message.error(`创建失败: ${error.response?.data?.detail || error.message}`);
    },
  });

  // 更新凭证
  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: CredentialUpdate }) =>
      credentialService.updateCredential(id, data),
    onSuccess: () => {
      message.success('凭证更新成功');
      onSuccess();
    },
    onError: (error: any) => {
      message.error(`更新失败: ${error.response?.data?.detail || error.message}`);
    },
  });

  useEffect(() => {
    if (credential) {
      form.setFieldsValue({
        name: credential.name,
        provider: credential.provider,
        model_type: credential.model_type,
        base_url: credential.base_url,
        description: credential.description,
      });
    }
  }, [credential, form]);

  const handleSubmit = async (values: any) => {
    try {
      if (isEditing) {
        const updateData: CredentialUpdate = {
          name: values.name,
          provider: values.provider,
          base_url: values.base_url,
          description: values.description,
        };
        
        // 只有在提供了新密钥时才更新
        if (values.api_key) {
          updateData.api_key = values.api_key;
        }

        updateMutation.mutate({
          id: credential!.id,
          data: updateData,
        });
      } else {
        const createData: CredentialCreate = {
          name: values.name,
          provider: values.provider,
          model_type: values.model_type,
          api_key: values.api_key,
          base_url: values.base_url,
          description: values.description,
        };
        
        createMutation.mutate(createData);
      }
    } catch (error) {
      console.error('Form submission error:', error);
    }
  };

  const isLoading = createMutation.isPending || updateMutation.isPending;

  return (
    <Form
      form={form}
      layout="vertical"
      onFinish={handleSubmit}
      autoComplete="off"
    >
      <Form.Item
        label="凭证名称"
        name="name"
        rules={[
          { required: true, message: '请输入凭证名称' },
          { max: 100, message: '凭证名称不能超过100个字符' },
        ]}
      >
        <Input placeholder="请输入凭证名称，如：OpenAI GPT-4" />
      </Form.Item>

      <Form.Item
        label="服务提供商"
        name="provider"
        rules={[
          { required: true, message: '请输入服务提供商' },
          { max: 50, message: '服务提供商不能超过50个字符' },
        ]}
      >
        <Input placeholder="请输入服务提供商，如：OpenAI、Azure、Anthropic" />
      </Form.Item>

      {!isEditing && (
        <Form.Item
          label="模型类型"
          name="model_type"
          rules={[{ required: true, message: '请选择模型类型' }]}
        >
          <Select placeholder="请选择模型类型">
            {modelTypesData?.model_types.map((type: ModelTypeInfo) => (
              <Option key={type.type} value={type.type}>
                <div>
                  <div>{type.name}</div>
                  <div style={{ fontSize: '12px', color: '#666' }}>
                    {type.description}
                  </div>
                </div>
              </Option>
            ))}
          </Select>
        </Form.Item>
      )}

      <Form.Item
        label={isEditing ? "API密钥（留空则不更新）" : "API密钥"}
        name="api_key"
        rules={isEditing ? [] : [{ required: true, message: '请输入API密钥' }]}
      >
        <Input.Password 
          placeholder={isEditing ? "留空则不更新API密钥" : "请输入API密钥"}
          autoComplete="new-password"
        />
      </Form.Item>

      <Form.Item
        label="Base URL"
        name="base_url"
        rules={[
          { required: true, message: '请输入Base URL' },
          { type: 'url', message: '请输入有效的URL' },
        ]}
      >
        <Input placeholder="请输入API的Base URL，如：https://api.openai.com/v1" />
      </Form.Item>

      <Form.Item
        label="描述"
        name="description"
      >
        <TextArea
          rows={3}
          placeholder="请输入凭证描述（可选）"
          maxLength={500}
        />
      </Form.Item>

      <Form.Item>
        <Space>
          <Button
            type="primary"
            htmlType="submit"
            loading={isLoading}
          >
            {isEditing ? '更新' : '创建'}
          </Button>
          <Button onClick={onCancel}>
            取消
          </Button>
        </Space>
      </Form.Item>
    </Form>
  );
};