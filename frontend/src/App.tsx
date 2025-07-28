/**
 * Kosmos V2 前端重构版本
 * 
 * 重构原则：
 * 1. 移除过时的概念（如ingest等混杂概念）
 * 2. 建立清晰的心智模型
 * 3. 逐步集成页面与组件
 * 4. 删除过时代码
 */

import React, { useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, Outlet } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ConfigProvider } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import './styles/globals.css';

// V2 用户管理功能
import { LoginPage } from './pages/auth/LoginPage';
import { RegisterPage } from './pages/auth/RegisterPage';
import { ForgotPasswordPage } from './pages/auth/ForgotPasswordPage';
import { ProfilePage } from './pages/auth/ProfilePage';
import { ProtectedRoute } from './components/auth/ProtectedRoute';
import { useAuthStore } from './stores/authStore';

// V2 知识库管理功能
import { Layout } from './components/layout/Layout';
import { KnowledgeBaseListPage } from './pages/KnowledgeBase/KnowledgeBaseListPage';
import { KnowledgeBaseDetailPage } from './pages/KnowledgeBase/KnowledgeBaseDetailPage';

// V2 模型凭证管理功能
import { CredentialManagePage } from './pages/Credential/CredentialManagePage';

// ============================================================================
// V2 基础配置
// ============================================================================

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

// ============================================================================
// V2 空白页面组件（逐步集成其他功能）
// ============================================================================

const BlankPage: React.FC = () => {
  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center">
      <div className="max-w-md w-full bg-white rounded-lg shadow-lg p-8 text-center">
        <div className="mb-6">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">
            Kosmos V2
          </h1>
          <p className="text-gray-600">
            知识管理系统 - 重构版本
          </p>
        </div>
        
        <div className="space-y-4">
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
            <h3 className="text-lg font-semibold text-blue-900 mb-2">
              🚧 重构进行中
            </h3>
            <p className="text-blue-700 text-sm">
              正在重构前端架构，建立清晰的心智模型
            </p>
          </div>
          
          <div className="bg-green-50 border border-green-200 rounded-lg p-4">
            <h3 className="text-lg font-semibold text-green-900 mb-2">
              ✅ 技术栈
            </h3>
            <div className="text-green-700 text-sm space-y-1">
              <p>• React 18 + TypeScript</p>
              <p>• Vite + Tailwind CSS</p>
              <p>• Ant Design + Zustand</p>
              <p>• React Query</p>
            </div>
          </div>
          
          <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
            <h3 className="text-lg font-semibold text-yellow-900 mb-2">
              📋 重构计划
            </h3>
            <div className="text-yellow-700 text-sm space-y-1">
              <p>1. 清理过时概念（ingest等）</p>
              <p>2. 重新设计页面结构</p>
              <p>3. 逐步集成核心功能</p>
              <p>4. 优化用户体验</p>
            </div>
          </div>
        </div>
        
        <div className="mt-6 pt-6 border-t border-gray-200">
          <p className="text-xs text-gray-500">
            Version 2.0.0 - 重构版本
          </p>
        </div>
      </div>
    </div>
  );
};

// ============================================================================
// V2 受保护的布局组件
// ============================================================================

const ProtectedLayout: React.FC = () => (
  <ProtectedRoute>
    <Layout>
      <Outlet />
    </Layout>
  </ProtectedRoute>
);

// ============================================================================
// V2 主应用组件
// ============================================================================

function App() {
  const { logout } = useAuthStore();

  useEffect(() => {
    // 监听认证错误事件
    const handleUnauthorized = () => {
      logout();
      // 使用 setTimeout 确保状态更新后再重定向
      setTimeout(() => {
        window.location.href = '/login';
      }, 100);
    };

    window.addEventListener('auth:unauthorized', handleUnauthorized);

    return () => {
      window.removeEventListener('auth:unauthorized', handleUnauthorized);
    };
  }, [logout]);

  return (
    <QueryClientProvider client={queryClient}>
      <ConfigProvider locale={zhCN}>
        <Router>
          <Routes>
            {/* 认证相关路由 */}
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />
            <Route path="/forgot-password" element={<ForgotPasswordPage />} />
            
            {/* 受保护的路由 */}
            <Route path="/profile" element={
              <ProtectedRoute>
                <ProfilePage />
              </ProtectedRoute>
            } />
            
            {/* 主应用布局 */}
            <Route path="/dashboard" element={<ProtectedLayout />}>
              {/* 默认重定向到知识库管理 */}
              <Route index element={<Navigate to="knowledge-bases" replace />} />
              
              {/* 知识库管理 */}
              <Route path="knowledge-bases" element={<KnowledgeBaseListPage />} />
              
              {/* 知识库详情页面 */}
              <Route path="kb/:kbId/*" element={<KnowledgeBaseDetailPage />} />
              
              {/* 模型凭证管理 */}
              <Route path="credentials" element={<CredentialManagePage />} />
            </Route>
            
            {/* 默认重定向 */}
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            
            {/* 404 页面 */}
            <Route path="*" element={
              <div className="min-h-screen bg-gray-50 flex items-center justify-center">
                <div className="text-center">
                  <h1 className="text-6xl font-bold text-gray-900">404</h1>
                  <p className="text-xl text-gray-600 mt-4">页面未找到</p>
                </div>
              </div>
            } />
          </Routes>
        </Router>
      </ConfigProvider>
    </QueryClientProvider>
  );
}

export default App;

// ============================================================================
// 注释掉的V1代码 - 逐步迁移
// ============================================================================

/*
// V1 导入 - 待重构
// import { LoginPage } from './pages/auth/LoginPage';
// import { RegisterPage } from './pages/auth/RegisterPage';
// import { Layout } from './components/layout/Layout';
// import { KnowledgeBaseListPage } from './pages/KnowledgeBase/KnowledgeBaseListPage';
// import { KnowledgeBaseDetailPage } from './pages/KnowledgeBase/KnowledgeBaseDetailPage';
// import { useAuthStore } from './stores/authStore';

// V1 路由结构 - 待重构
// <Route path="/login" element={<LoginPage />} />
// <Route path="/register" element={<RegisterPage />} />
// <Route path="/" element={<Navigate to="/dashboard" replace />} />
// <Route path="/dashboard" element={<ProtectedLayout />}>
//   <Route index element={<DashboardPlaceholder />} />
//   <Route path="knowledge-bases" element={<KnowledgeBaseListPage />} />
//   <Route path="kb/:kbId/*" element={<KnowledgeBaseDetailPage />}>
//     <Route index element={<div>概览内容</div>} />
//     <Route path="overview" element={<div>概览内容</div>} />
//     <Route path="documents" element={<div>文档管理功能</div>} />
//     <Route path="search" element={<div>语义搜索功能</div>} />
//   </Route>
// </Route>

// V1 组件 - 待重构
// const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
//   const { user } = useAuthStore();
//   const token = localStorage.getItem('access_token');
//   if (!user && !token) {
//     return <Navigate to="/login" replace />;
//   }
//   return <>{children}</>;
// };

// const DashboardPlaceholder: React.FC = () => (
//   <div className="p-6">
//     <h2 className="text-2xl font-bold mb-4">仪表盘</h2>
//     <p className="text-gray-600">功能尚未实现</p>
//   </div>
// );

// const ProtectedLayout: React.FC = () => (
//   <ProtectedRoute>
//     <Layout>
//       <Outlet />
//     </Layout>
//   </ProtectedRoute>
// );
*/
