import React from 'react'
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import { ConfigProvider } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import AppLayout from '@/components/layout/AppLayout'
import { SystemConfigProvider } from '@/context/SystemConfigContext'

const App: React.FC = () => {
  return (
    <SystemConfigProvider>
      <ConfigProvider locale={zhCN}>
        <Router>
          <Routes>
            <Route path="/" element={<AppLayout />} />
            <Route path="/*" element={<AppLayout />} />
          </Routes>
        </Router>
      </ConfigProvider>
    </SystemConfigProvider>
  )
}

export default App