import React, { useState } from 'react'
import { Layout, Button } from 'antd'
import {
  MenuFoldOutlined,
  MenuUnfoldOutlined
} from '@ant-design/icons'
import SessionNav from '../modules/SessionNav'
import ControlDetail from '../modules/ControlDetail'
import AssessmentResult from '../modules/AssessmentResult'
import EvidencePreview from '../modules/EvidencePreview'
import SessionHistory from '../modules/SessionHistory'
import CommentInput from '../modules/CommentInput'
import ErrorBoundary from '../common/ErrorBoundary'
import { useSystemConfig } from '../../context/SystemConfigContext'

const { Sider, Content } = Layout

interface WorkspaceProps {
  collapsed: boolean
  activeSession: string | null
  setActiveSession: (sessionId: string | null) => void
}

const Workspace: React.FC<WorkspaceProps> = ({ 
  collapsed, 
  activeSession,
  setActiveSession
}) => {
  const [historyCollapsed, setHistoryCollapsed] = useState(false)
  const { config } = useSystemConfig()
  
  // 使用historyCollapsed状态来触发重渲染
  const toggleHistoryCollapse = () => {
    setHistoryCollapsed(!historyCollapsed)
  }
  
  return (
    <Layout style={{ height: 'calc(100vh - 160px)' }}>
      {/* 左侧控制项导航栏 */}
      <Sider 
        width={300} 
        collapsed={collapsed} 
        collapsible 
        collapsedWidth={0}
        trigger={null}
        zeroWidthTriggerStyle={{ top: '50%', transform: 'translateY(-50%)' }}
        style={{ 
          background: '#fff',
          border: '1px solid #f0f0f0',
          marginRight: '12px',
          height: '100%'
        }}
      >
        <ErrorBoundary fallback={
          <div style={{ padding: '20px', textAlign: 'center' }}>
            <div>控制项导航加载失败</div>
            <div style={{ fontSize: '12px', color: '#999', marginTop: '8px' }}>
              请检查数据格式或刷新页面重试
            </div>
          </div>
        }>
          <ControlNav 
            activeControl={activeControl}
            setActiveControl={setActiveControl}
            jobId={config.assessmentJobId}
          />
        </ErrorBoundary>
      </Sider>
      
      {/* 主内容区 */}
      <Layout>
        <Content 
          style={{ 
            display: 'flex',
            flexDirection: 'column',
            gap: '12px',
            overflow: 'auto',
            height: '100%'
          }}
        >
          <div style={{ 
            display: 'flex', 
            gap: '12px',
            flex: 1,
            overflow: 'hidden'
          }}>
            {/* 控制项详情 */}
            <div style={{ 
              flex: 1, 
              background: '#fff', 
              padding: '16px',
              border: '1px solid #f0f0f0',
              display: 'flex',
              flexDirection: 'column',
              overflow: 'auto'
            }}>
              <ControlDetail activeControl={activeControl} />
            </div>
            
            {/* 评估结论 */}
            <div style={{ 
              flex: 1, 
              background: '#fff', 
              padding: '16px',
              border: '1px solid #f0f0f0',
              display: 'flex',
              flexDirection: 'column',
              overflow: 'auto'
            }}>
              <AssessmentResult activeControl={activeControl} jobId={config.assessmentJobId} />
            </div>
            
            {/* 证据预览 */}
            <div style={{ 
              flex: 1, 
              background: '#fff', 
              padding: '16px',
              border: '1px solid #f0f0f0',
              display: 'flex',
              flexDirection: 'column',
              overflow: 'auto'
            }}>
              <EvidencePreview activeControl={activeControl} />
            </div>
          </div>
          
          {/* 底部评论输入框 */}
          <div style={{ 
            background: '#fff', 
            padding: '16px',
            border: '1px solid #f0f0f0',
            minHeight: '120px'
          }}>
            <CommentInput activeControl={activeControl} />
          </div>
        </Content>
      </Layout>
      
      {/* 右侧会话历史 */}
      <Sider 
        width={300} 
        collapsed={historyCollapsed} 
        collapsible 
        collapsedWidth={0}
        trigger={null}
        zeroWidthTriggerStyle={{ top: '50%', transform: 'translateY(-50%)' }}
        style={{ 
          background: '#fff',
          border: '1px solid #f0f0f0',
          marginLeft: '12px',
          height: '100%'
        }}
        reverseArrow
      >
        <div style={{ padding: '8px', textAlign: 'right' }}>
          <Button 
            type="text" 
            size="small"
            onClick={toggleHistoryCollapse}
            icon={historyCollapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
          >
            {historyCollapsed ? '展开' : '收起'}
          </Button>
        </div>
        <SessionHistory />
      </Sider>
    </Layout>
  )
}

export default Workspace