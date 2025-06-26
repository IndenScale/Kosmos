import React from 'react';
import { Layout as AntLayout, Menu, Dropdown, Avatar, Button, Space } from 'antd';
import { UserOutlined, LogoutOutlined, DatabaseOutlined, DashboardOutlined, SearchOutlined } from '@ant-design/icons';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuthStore } from '../../stores/authStore';

const { Header, Sider, Content } = AntLayout;

interface LayoutProps {
  children: React.ReactNode;
}

export const Layout: React.FC<LayoutProps> = ({ children }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuthStore();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const userMenu = [
    {
      key: 'profile',
      icon: <UserOutlined />,
      label: '个人资料',
    },
    {
      type: 'divider' as const,
    },
    {
      key: 'logout',
      icon: <LogoutOutlined />,
      label: '退出登录',
      onClick: handleLogout,
    },
  ];

  const menuItems = [
    {
      key: '/dashboard',
      icon: <DashboardOutlined />,
      label: '仪表盘',
    },
    {
      key: '/dashboard/knowledge-bases',
      icon: <DatabaseOutlined />,
      label: '知识库管理',
    },
];

  const selectedKey = location.pathname;

  return (
    <AntLayout className="min-h-screen">
      <Header className="bg-white border-b border-gray-200 px-6 flex items-center justify-between">
        <div className="flex items-center">
          <h1 className="text-xl font-bold text-gray-900 mr-8">Kosmos</h1>
        </div>
        
        <div className="flex items-center">
          <Space>
            <span className="text-gray-600">欢迎, {user?.username}</span>
            <Dropdown menu={{ items: userMenu }} placement="bottomRight">
              <Avatar 
                icon={<UserOutlined />} 
                className="cursor-pointer bg-gray-600"
              />
            </Dropdown>
          </Space>
        </div>
      </Header>
      
      <AntLayout>
        <Sider 
          width={250} 
          className="bg-white border-r border-gray-200"
          theme="light"
        >
          <Menu
            mode="inline"
            selectedKeys={[selectedKey]}
            className="border-r-0 pt-4"
            onClick={({ key }) => navigate(key)}
            items={menuItems}
          />
        </Sider>
        
        <Content className="bg-gray-50">
          {children}
        </Content>
      </AntLayout>
    </AntLayout>
  );
};