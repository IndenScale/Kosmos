import React, { useState } from 'react';
import { Form, Input, Button, Card, message, Alert } from 'antd';
import { MailOutlined, ArrowLeftOutlined } from '@ant-design/icons';
import { Link } from 'react-router-dom';

export const ForgotPasswordPage: React.FC = () => {
  const [form] = Form.useForm();
  const [isSubmitted, setIsSubmitted] = useState(false);

  const onFinish = (values: { email: string }) => {
    // 模拟提交，实际上后端密码重置功能尚未实现
    console.log('Password reset requested for:', values.email);
    setIsSubmitted(true);
    message.info('密码重置功能尚未实现，请联系管理员');
  };

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8">
        <div className="text-center">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">Kosmos</h1>
          <h2 className="text-xl text-gray-600">重置您的密码</h2>
        </div>
        
        <Card className="shadow-lg border-0">
          {!isSubmitted ? (
            <>
              <Alert
                message="功能开发中"
                description="密码重置功能正在开发中，如需重置密码请联系系统管理员。"
                type="info"
                showIcon
                className="mb-6"
              />
              
              <Form
                form={form}
                name="forgot-password"
                onFinish={onFinish}
                layout="vertical"
                size="large"
              >
                <Form.Item
                  name="email"
                  label="邮箱地址"
                  rules={[
                    { required: true, message: '请输入邮箱地址' },
                    { type: 'email', message: '请输入有效的邮箱地址' }
                  ]}
                >
                  <Input
                    prefix={<MailOutlined className="text-gray-400" />}
                    placeholder="请输入您的邮箱地址"
                    className="rounded-lg"
                  />
                </Form.Item>

                <Form.Item>
                  <Button
                    type="primary"
                    htmlType="submit"
                    className="w-full h-12 bg-gray-900 border-gray-900 hover:bg-gray-800 rounded-lg"
                  >
                    发送重置链接
                  </Button>
                </Form.Item>
              </Form>
            </>
          ) : (
            <div className="text-center py-8">
              <div className="mb-4">
                <MailOutlined className="text-4xl text-gray-400" />
              </div>
              <h3 className="text-lg font-semibold text-gray-900 mb-2">
                重置链接已发送
              </h3>
              <p className="text-gray-600 mb-6">
                如果该邮箱地址存在于我们的系统中，您将收到一封包含密码重置链接的邮件。
              </p>
              <Alert
                message="注意"
                description="由于密码重置功能尚未完全实现，您可能不会收到邮件。请联系管理员获取帮助。"
                type="warning"
                showIcon
              />
            </div>
          )}

          <div className="text-center mt-6">
            <Link 
              to="/login" 
              className="text-gray-900 hover:text-gray-700 inline-flex items-center"
            >
              <ArrowLeftOutlined className="mr-1" />
              返回登录
            </Link>
          </div>
        </Card>
      </div>
    </div>
  );
};