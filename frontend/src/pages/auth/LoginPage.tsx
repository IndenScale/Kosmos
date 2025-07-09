import React from 'react';
import { Form, Input, Button, Card, message } from 'antd';
import { UserOutlined, LockOutlined } from '@ant-design/icons';
import { Link, useNavigate } from 'react-router-dom';
import { useMutation } from '@tanstack/react-query';
import { authService } from '../../services/auth';
import { useAuthStore } from '../../stores/authStore';
import { LoginRequest } from '../../types/auth';

export const LoginPage: React.FC = () => {
  const navigate = useNavigate();
  const { setUser } = useAuthStore();
  const [form] = Form.useForm();

  const loginMutation = useMutation({
    mutationFn: authService.login,
    onSuccess: (data) => {
      localStorage.setItem('access_token', data.access_token);
      setUser(data.user);
      message.success('登录成功');
      navigate('/dashboard');
    },
    onError: (error: any) => {
      console.error('Login error:', error);
      
      let errorMessage = '登录失败，请检查用户名和密码';
      
      if (error.response?.data) {
        // 处理 FastAPI 验证错误格式
        if (error.response.data.detail) {
          if (typeof error.response.data.detail === 'string') {
            errorMessage = error.response.data.detail;
          } else if (Array.isArray(error.response.data.detail)) {
            // 处理验证错误数组
            errorMessage = error.response.data.detail
              .map((err: any) => err.msg || err.message || '验证错误')
              .join(', ');
          }
        }
      }
      
      message.error(errorMessage);
    }
  });

  const onFinish = (values: LoginRequest) => {
    loginMutation.mutate({
      username: values.username,
      password: values.password
    });
  };

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8">
        <div className="text-center">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">Kosmos</h1>
          <h2 className="text-xl text-gray-600">登录到您的账户</h2>
        </div>
        
        <Card className="shadow-lg border-0">
          <Form
            form={form}
            name="login"
            onFinish={onFinish}
            layout="vertical"
            size="large"
          >
            <Form.Item
              name="username"
              label="用户名"
              rules={[{ required: true, message: '请输入用户名' }]}
            >
              <Input
                prefix={<UserOutlined className="text-gray-400" />}
                placeholder="请输入用户名"
                className="rounded-lg"
              />
            </Form.Item>

            <Form.Item
              name="password"
              label="密码"
              rules={[{ required: true, message: '请输入密码' }]}
            >
              <Input.Password
                prefix={<LockOutlined className="text-gray-400" />}
                placeholder="请输入密码"
                className="rounded-lg"
              />
            </Form.Item>

            <Form.Item>
              <Button
                type="primary"
                htmlType="submit"
                loading={loginMutation.isPending}
                className="w-full h-12 bg-gray-900 border-gray-900 hover:bg-gray-800 rounded-lg"
              >
                登录
              </Button>
            </Form.Item>

            <div className="text-center">
              <span className="text-gray-600">还没有账户？</span>
              <Link to="/register" className="text-gray-900 hover:text-gray-700 ml-1">
                立即注册
              </Link>
            </div>
          </Form>
        </Card>
      </div>
    </div>
  );
};