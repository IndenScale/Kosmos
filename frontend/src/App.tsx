import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, Outlet } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ConfigProvider } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import { LoginPage } from './pages/auth/LoginPage';
import { RegisterPage } from './pages/auth/RegisterPage';
import { Layout } from './components/layout/Layout';
import { KnowledgeBaseListPage } from './pages/KnowledgeBase/KnowledgeBaseListPage';
import { KnowledgeBaseDetailPage } from './pages/KnowledgeBase/KnowledgeBaseDetailPage';
import { useAuthStore } from './stores/authStore';
import './styles/globals.css';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

// 受保护的路由组件
const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { user } = useAuthStore();
  const token = localStorage.getItem('access_token');

  if (!user && !token) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
};

// 仪表盘占位组件
const DashboardPlaceholder: React.FC = () => (
  <div className="p-6">
    <h2 className="text-2xl font-bold mb-4">仪表盘</h2>
    <p className="text-gray-600">功能尚未实现</p>
  </div>
);

const ProtectedLayout: React.FC = () => (
  <ProtectedRoute>
    <Layout>
      <Outlet />
    </Layout>
  </ProtectedRoute>
);

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ConfigProvider locale={zhCN}>
        <Router>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />
            <Route path="/" element={<Navigate to="/dashboard" replace />} />

            {/* 修改：/dashboard 及其子路由的结构 */}
            <Route path="/dashboard" element={<ProtectedLayout />}>
              <Route index element={<DashboardPlaceholder />} />
              <Route path="knowledge-bases" element={<KnowledgeBaseListPage />} />

              {/* 修复：正确嵌套 kb/:kbId/* 路由 */}
              <Route path="kb/:kbId/*" element={<KnowledgeBaseDetailPage />}>
                <Route index element={<div>概览内容</div>} />
                <Route path="overview" element={<div>概览内容</div>} />
                <Route path="documents" element={<div>文档管理功能</div>} />
                <Route path="search" element={<div>语义搜索功能</div>} />
              </Route>
            </Route>
          </Routes>
        </Router>
      </ConfigProvider>
    </QueryClientProvider>
  );
}

export default App;
