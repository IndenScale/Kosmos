import React, { useState } from 'react'
import { Layout, Button, Space } from 'antd'
import {
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  SettingOutlined
} from '@ant-design/icons'
import Banner from './Banner'
import Workspace from './Workspace'
import ConfigModal from '@/components/common/ConfigModal'
import { useSystemConfig } from '@/context/SystemConfigContext'

const { Header, Content } = Layout

const AppLayout: React.FC = () => {
  const [collapsed, setCollapsed] = useState(false)
  const [configModalVisible, setConfigModalVisible] = useState(false)
  const [activeSession, setActiveSession] = useState<string | null>(null)
  const { config } = useSystemConfig()

  const toggleSidebar = () => {
    setCollapsed(!collapsed)
  }

  const showConfigModal = () => {
    setConfigModalVisible(true)
  }

  const handleConfigModalCancel = () => {
    setConfigModalVisible(false)
  }

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header style={{ 
        display: 'flex', 
        alignItems: 'center', 
        justifyContent: 'space-between',
        padding: '0 24px',
        background: '#fff',
        boxShadow: '0 2px 8px rgba(0, 0, 0, 0.1)'
      }}>
        <Banner />
        <Space>
          <Button
            type="text"
            icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
            onClick={toggleSidebar}
            style={{ fontSize: '16px' }}
          />
          <Button
            type="text"
            icon={<SettingOutlined />}
            onClick={showConfigModal}
            style={{ fontSize: '16px' }}
          />
        </Space>
      </Header>
      
      <Content style={{ margin: '24px' }}>
        <Workspace 
          collapsed={collapsed} 
          activeControl={activeControl}
          setActiveControl={setActiveControl}
        />
      </Content>
      
      <ConfigModal 
        visible={configModalVisible} 
        onCancel={handleConfigModalCancel} 
      />
    </Layout>
  )
}

export default AppLayout