import React, { useState, useEffect, useMemo } from 'react'
import { Tree, Input, Spin, Alert } from 'antd'
import { SearchOutlined } from '@ant-design/icons'
import { useAssessmentData } from '../../hooks/useAssessmentData'
import { buildControlTree, getExpandableKeys, TreeNode } from '../../utils/controlTreeBuilder'

const { Search } = Input

interface ControlNavProps {
  activeControl: string | null
  setActiveControl: (controlId: string | null) => void
  jobId?: string // 新增作业ID属性
}

const ControlNav: React.FC<ControlNavProps> = ({ 
  activeControl, 
  setActiveControl,
  jobId
}) => {
  const [searchValue, setSearchValue] = useState('')
  const [expandedKeys, setExpandedKeys] = useState<string[]>([])
  
  // 使用评估数据Hook
  const { findings, loading, error, loadJobData, resetData } = useAssessmentData()
  
  // 当作业ID变化时加载数据
  useEffect(() => {
    if (jobId) {
      loadJobData(jobId)
    } else {
      // 如果没有jobId，重置数据
      resetData()
    }
  }, [jobId]) // 移除loadJobData和resetData依赖项，避免无限更新
  
  // 从findings构建树状结构
  const treeData = useMemo(() => {
    // 确保findings是有效数组
    if (!findings || !Array.isArray(findings) || findings.length === 0) {
      return []
    }
    return buildControlTree(findings)
  }, [findings])
  
  // 设置默认展开的节点
  useEffect(() => {
    if (treeData.length > 0) {
      const expandableKeys = getExpandableKeys(treeData)
      setExpandedKeys(expandableKeys.slice(0, 10)) // 限制展开数量避免性能问题
    }
  }, [treeData])
  
  // 过滤树数据
  const filteredTreeData = useMemo(() => {
    if (!searchValue) return treeData
    
    const filterTree = (nodes: TreeNode[]): TreeNode[] => {
      return nodes.reduce((acc: TreeNode[], node) => {
        const matchesSearch = node.title.toLowerCase().includes(searchValue.toLowerCase())
        const filteredChildren = node.children ? filterTree(node.children) : []
        
        if (matchesSearch || filteredChildren.length > 0) {
          acc.push({
            ...node,
            children: filteredChildren.length > 0 ? filteredChildren : node.children
          })
        }
        
        return acc
      }, [])
    }
    
    return filterTree(treeData)
  }, [treeData, searchValue])
  
  const onSelect = (selectedKeys: React.Key[]) => {
    if (selectedKeys.length > 0) {
      setActiveControl(selectedKeys[0] as string)
    } else {
      setActiveControl(null)
    }
  }
  
  const onSearch = (value: string) => {
    setSearchValue(value)
    // 搜索时展开所有匹配的节点
    if (value) {
      const allExpandableKeys = getExpandableKeys(filteredTreeData)
      setExpandedKeys(allExpandableKeys)
    }
  }
  
  const onExpand = (expandedKeysValue: React.Key[]) => {
    setExpandedKeys(expandedKeysValue as string[])
  }
  
  return (
    <div style={{ padding: '16px', height: '100%', display: 'flex', flexDirection: 'column' }}>
      <Search 
        placeholder="搜索控制项" 
        prefix={<SearchOutlined />} 
        style={{ marginBottom: '16px' }} 
        onChange={(e) => onSearch(e.target.value)}
        allowClear
      />
      
      {loading && (
        <div style={{ textAlign: 'center', padding: '20px' }}>
          <Spin size="large" />
          <div style={{ marginTop: '8px' }}>加载控制项数据...</div>
        </div>
      )}
      
      {error && (
        <Alert
          message="加载失败"
          description={error}
          type="error"
          showIcon
          style={{ marginBottom: '16px' }}
        />
      )}
      
      {!loading && !error && treeData.length === 0 && jobId && (
        <Alert
          message="暂无数据"
          description="当前作业没有找到控制项数据"
          type="info"
          showIcon
        />
      )}
      
      {!loading && !error && treeData.length === 0 && !jobId && (
        <Alert
          message="请选择作业"
          description="请先选择一个评估作业以查看控制项"
          type="info"
          showIcon
        />
      )}
      
      {!loading && !error && filteredTreeData.length > 0 && (
        <div style={{ flex: 1, overflow: 'auto' }}>
          <Tree
            showLine
            expandedKeys={expandedKeys}
            selectedKeys={activeControl ? [activeControl] : []}
            onSelect={onSelect}
            onExpand={onExpand}
            treeData={filteredTreeData}
          />
        </div>
      )}
    </div>
  )
}

export default ControlNav