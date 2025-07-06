import React from 'react';
import { Routes, Route, useParams, useNavigate, useLocation } from 'react-router-dom';
import { Tabs } from 'antd';
import { KBOverviewPage } from './KBOverviewPage';
import { KBDocumentManagePage } from './KBDocumentManagePage';
import { KBSearchPage } from './KBSearchPage';
import { KBSDTMPage } from './KBSDTMPage';

export const KnowledgeBaseDetailPage: React.FC = () => {
  const { kbId } = useParams();
  const navigate = useNavigate();
  const location = useLocation();

  const getActiveKey = () => {
    const path = location.pathname;
    if (path.includes('/documents')) return 'documents';
    if (path.includes('/search')) return 'search';
    if (path.includes('/sdtm')) return 'sdtm';
    return 'overview';
  };

  const tabItems = [
    { key: 'overview', label: '概览' },
    { key: 'documents', label: '文档管理' },
    { key: 'search', label: '语义搜索' },
    { key: 'sdtm', label: 'SDTM优化' },
  ];

  const handleTabChange = (key: string) => {
    if (key === 'overview') {
      navigate(`/dashboard/kb/${kbId}`);
    } else {
      navigate(`/dashboard/kb/${kbId}/${key}`);
    }
  };

  return (
    <div className="p-6">
      <h2 className="text-2xl font-bold mb-4">知识库详情</h2>
      <Tabs
        activeKey={getActiveKey()}
        items={tabItems}
        onChange={handleTabChange}
        className="mb-4"
      />
      <Routes>
        <Route index element={<KBOverviewPage />} />
        <Route path="documents" element={<KBDocumentManagePage />} />
        <Route path="search" element={<KBSearchPage />} />
        <Route path="sdtm" element={<KBSDTMPage />} />
      </Routes>
    </div>
  );
};