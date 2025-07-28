import React, { useState } from 'react';
import { 
  Card, 
  Descriptions, 
  Button, 
  Modal, 
  Form, 
  Input, 
  message, 
  Space,
  Avatar,
  Typography,
  Divider,
  Tag
} from 'antd';
import { 
  UserOutlined, 
  EditOutlined, 
  LockOutlined, 
  LogoutOutlined,
  MailOutlined,
  CalendarOutlined
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { authService } from '../../services/auth';
import { userService } from '../../services/user';
import { useAuthStore } from '../../stores/authStore';

const { Title, Text } = Typography;

export const ProfilePage: React.FC = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { user, logout } = useAuthStore();
  const [editModalVisible, setEditModalVisible] = useState(false);
  const [passwordModalVisible, setPasswordModalVisible] = useState(false);
  const [editForm] = Form.useForm();
  const [passwordForm] = Form.useForm();

  // 获取用户信息
  const { data: currentUser, isLoading } = useQuery({
    queryKey: ['user', 'me'],
    queryFn: authService.getCurrentUser,
    initialData: user
  });

  // 更新用户信息
  const updateUserMutation = useMutation({
    mutationFn: userService.updateProfile,
    onSuccess: (data) => {
      message.success('个人信息更新成功');
      setEditModalVisible(false);
      queryClient.setQueryData(['user', 'me'], data);
      editForm.resetFields();
    },
    onError: (error: any) => {
      message.error(error.response?.data?.detail || '更新失败');
    }
  });

  // 修改密码
  const changePasswordMutation = useMutation({
    mutationFn: userService.changePassword,
    onSuccess: () => {
      message.success('密码修改成功');
      setPasswordModalVisible(false);
      passwordForm.resetFields();
    },
    onError: (error: any) => {
      message.error(error.response?.data?.detail || '密码修改失败');
    }
  });

  const handleEditProfile = () => {
    editForm.setFieldsValue({
      username: currentUser?.username,
      email: currentUser?.email
    });
    setEditModalVisible(true);
  };

  const handleUpdateProfile = (values: any) => {
    updateUserMutation.mutate(values);
  };

  const handleChangePassword = (values: any) => {
    changePasswordMutation.mutate({
      current_password: values.currentPassword,
      new_password: values.newPassword
    });
  };

  const handleLogout = () => {
    Modal.confirm({
      title: '确认登出',
      content: '您确定要登出吗？',
      onOk: () => {
        logout();
        navigate('/login');
      }
    });
  };

  const getRoleTag = (role: string) => {
    const roleMap = {
      'system_admin': { color: 'red', text: '系统管理员' },
      'admin': { color: 'orange', text: '管理员' },
      'user': { color: 'blue', text: '普通用户' }
    };
    const roleInfo = roleMap[role as keyof typeof roleMap] || { color: 'default', text: role };
    return <Tag color={roleInfo.color}>{roleInfo.text}</Tag>;
  };

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div>加载中...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* 页面标题 */}
        <div className="mb-8">
          <Title level={2}>个人中心</Title>
          <Text type="secondary">管理您的个人信息和账户设置</Text>
        </div>

        {/* 用户信息卡片 */}
        <Card className="mb-6">
          <div className="flex items-center space-x-4 mb-6">
            <Avatar size={64} icon={<UserOutlined />} className="bg-gray-600" />
            <div>
              <Title level={3} className="mb-1">{currentUser?.username}</Title>
              <Text type="secondary">{currentUser?.email}</Text>
              <div className="mt-2">
                {getRoleTag(currentUser?.role || 'user')}
              </div>
            </div>
          </div>

          <Descriptions column={1} bordered>
            <Descriptions.Item label="用户名">
              {currentUser?.username}
            </Descriptions.Item>
            <Descriptions.Item label="邮箱">
              <Space>
                <MailOutlined />
                {currentUser?.email}
              </Space>
            </Descriptions.Item>
            <Descriptions.Item label="角色">
              {getRoleTag(currentUser?.role || 'user')}
            </Descriptions.Item>
            <Descriptions.Item label="注册时间">
              <Space>
                <CalendarOutlined />
                {currentUser?.created_at ? new Date(currentUser.created_at).toLocaleString() : '未知'}
              </Space>
            </Descriptions.Item>
            <Descriptions.Item label="账户状态">
              <Tag color={currentUser?.is_active ? 'green' : 'red'}>
                {currentUser?.is_active ? '活跃' : '已停用'}
              </Tag>
            </Descriptions.Item>
          </Descriptions>
        </Card>

        {/* 操作按钮 */}
        <Card title="账户操作">
          <Space direction="vertical" size="middle" className="w-full">
            <Button 
              type="primary" 
              icon={<EditOutlined />}
              onClick={handleEditProfile}
              size="large"
            >
              编辑个人信息
            </Button>
            
            <Button 
              icon={<LockOutlined />}
              onClick={() => setPasswordModalVisible(true)}
              size="large"
            >
              修改密码
            </Button>
            
            <Divider />
            
            <Button 
              danger
              icon={<LogoutOutlined />}
              onClick={handleLogout}
              size="large"
            >
              登出账户
            </Button>
          </Space>
        </Card>

        {/* 编辑个人信息模态框 */}
        <Modal
          title="编辑个人信息"
          open={editModalVisible}
          onCancel={() => setEditModalVisible(false)}
          footer={null}
        >
          <Form
            form={editForm}
            layout="vertical"
            onFinish={handleUpdateProfile}
          >
            <Form.Item
              name="username"
              label="用户名"
              rules={[
                { required: true, message: '请输入用户名' },
                { min: 3, message: '用户名至少3个字符' }
              ]}
            >
              <Input placeholder="请输入用户名" />
            </Form.Item>

            <Form.Item
              name="email"
              label="邮箱"
              rules={[
                { required: true, message: '请输入邮箱' },
                { type: 'email', message: '请输入有效的邮箱地址' }
              ]}
            >
              <Input placeholder="请输入邮箱" />
            </Form.Item>

            <Form.Item>
              <Space>
                <Button 
                  type="primary" 
                  htmlType="submit"
                  loading={updateUserMutation.isPending}
                >
                  保存
                </Button>
                <Button onClick={() => setEditModalVisible(false)}>
                  取消
                </Button>
              </Space>
            </Form.Item>
          </Form>
        </Modal>

        {/* 修改密码模态框 */}
        <Modal
          title="修改密码"
          open={passwordModalVisible}
          onCancel={() => setPasswordModalVisible(false)}
          footer={null}
        >
          <Form
            form={passwordForm}
            layout="vertical"
            onFinish={handleChangePassword}
          >
            <Form.Item
              name="currentPassword"
              label="当前密码"
              rules={[{ required: true, message: '请输入当前密码' }]}
            >
              <Input.Password placeholder="请输入当前密码" />
            </Form.Item>

            <Form.Item
              name="newPassword"
              label="新密码"
              rules={[
                { required: true, message: '请输入新密码' },
                { min: 8, message: '密码至少8个字符' }
              ]}
            >
              <Input.Password placeholder="请输入新密码" />
            </Form.Item>

            <Form.Item
              name="confirmPassword"
              label="确认新密码"
              dependencies={['newPassword']}
              rules={[
                { required: true, message: '请确认新密码' },
                ({ getFieldValue }) => ({
                  validator(_, value) {
                    if (!value || getFieldValue('newPassword') === value) {
                      return Promise.resolve();
                    }
                    return Promise.reject(new Error('两次输入的密码不一致'));
                  },
                }),
              ]}
            >
              <Input.Password placeholder="请再次输入新密码" />
            </Form.Item>

            <Form.Item>
              <Space>
                <Button 
                  type="primary" 
                  htmlType="submit"
                  loading={changePasswordMutation.isPending}
                >
                  修改密码
                </Button>
                <Button onClick={() => setPasswordModalVisible(false)}>
                  取消
                </Button>
              </Space>
            </Form.Item>
          </Form>
        </Modal>
      </div>
    </div>
  );
};