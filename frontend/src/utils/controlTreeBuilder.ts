// 从findings数据构建控制项树状结构的工具函数

import { AssessmentFinding } from '../types/assessment';

export interface TreeNode {
  title: string;
  key: string;
  children?: TreeNode[];
}

/**
 * 从findings数据中提取control_item_definition.heading并构建树状结构
 * @param findings 评估发现数据
 * @returns 树状结构数据
 */
export function buildControlTree(findings: AssessmentFinding[]): TreeNode[] {
  // 检查输入参数是否为有效数组
  if (!findings || !Array.isArray(findings) || findings.length === 0) {
    return [];
  }

  // 用于存储所有节点的映射
  const nodeMap = new Map<string, TreeNode>();
  // 用于去重，确保每个控制项只处理一次
  const processedControlIds = new Set<string>();
  // 用于存储已创建的控制项节点，避免重复创建
  const createdControlNodes = new Set<string>();
  
  // 遍历所有findings，提取heading信息
  findings.forEach(finding => {
    const { control_item_definition } = finding;
    const { heading } = control_item_definition.details;
    
    if (!heading) return;
    
    // 如果这个控制项已经处理过，跳过
    if (processedControlIds.has(control_item_definition.id)) {
      return;
    }
    processedControlIds.add(control_item_definition.id);
    
    // 解析heading，通常格式为 "7.2 合规性评估/7.2.1 正当必要性评估"
    const parts = heading.split('/');
    
    // 构建层级结构
    let currentPath = '';
    let parentKey = '';
    
    parts.forEach((part, index) => {
      const trimmedPart = part.trim();
      currentPath = currentPath ? `${currentPath}/${trimmedPart}` : trimmedPart;
      const nodeKey = currentPath;
      
      // 如果节点不存在，创建新节点
      if (!nodeMap.has(nodeKey)) {
        const newNode: TreeNode = {
          title: trimmedPart,
          key: nodeKey,
          children: []
        };
        
        nodeMap.set(nodeKey, newNode);
        
        // 如果有父节点，将当前节点添加到父节点的children中
        if (parentKey && nodeMap.has(parentKey)) {
          const parentNode = nodeMap.get(parentKey)!;
          if (!parentNode.children) {
            parentNode.children = [];
          }
          // 检查是否已存在，避免重复添加
          if (!parentNode.children.find(child => child.key === nodeKey)) {
            parentNode.children.push(newNode);
          }
        }
      }
      
      parentKey = nodeKey;
    });
    
    // 如果有display_id，添加具体的控制项节点
    if (control_item_definition.display_id) {
      const controlKey = control_item_definition.id; // 使用control_item_definition.id作为key
      
      // 检查是否已经创建过这个控制项节点
      if (!createdControlNodes.has(controlKey)) {
        const controlNode: TreeNode = {
          title: `${control_item_definition.display_id} ${control_item_definition.content.substring(0, 50)}...`,
          key: controlKey
        };
        
        if (!nodeMap.has(controlKey)) {
          nodeMap.set(controlKey, controlNode);
          createdControlNodes.add(controlKey);
          
          // 添加到父节点
          if (parentKey && nodeMap.has(parentKey)) {
            const parentNode = nodeMap.get(parentKey)!;
            if (!parentNode.children) {
              parentNode.children = [];
            }
            if (!parentNode.children.find(child => child.key === controlKey)) {
              parentNode.children.push(controlNode);
            }
          }
        }
      }
    }
  });
  
  // 找出根节点（没有父节点的节点）
  const rootNodes: TreeNode[] = [];
  const allKeys = Array.from(nodeMap.keys());
  
  allKeys.forEach(key => {
    const isRoot = !allKeys.some(otherKey => 
      otherKey !== key && key.startsWith(otherKey + '/')
    );
    
    if (isRoot) {
      const node = nodeMap.get(key)!;
      rootNodes.push(node);
    }
  });
  
  // 对节点进行排序
  const sortNodes = (nodes: TreeNode[]): TreeNode[] => {
    return nodes.sort((a, b) => {
      // 提取数字进行排序
      const aMatch = a.title.match(/^(\d+(?:\.\d+)*)/);
      const bMatch = b.title.match(/^(\d+(?:\.\d+)*)/);
      
      if (aMatch && bMatch) {
        const aParts = aMatch[1].split('.').map(Number);
        const bParts = bMatch[1].split('.').map(Number);
        
        for (let i = 0; i < Math.max(aParts.length, bParts.length); i++) {
          const aNum = aParts[i] || 0;
          const bNum = bParts[i] || 0;
          if (aNum !== bNum) {
            return aNum - bNum;
          }
        }
      }
      
      return a.title.localeCompare(b.title);
    }).map(node => ({
      ...node,
      children: node.children ? sortNodes(node.children) : undefined
    }));
  };
  
  return sortNodes(rootNodes);
}

/**
 * 获取所有可展开的节点key
 * @param nodes 树节点数组
 * @returns 可展开的key数组
 */
export function getExpandableKeys(nodes: TreeNode[]): string[] {
  const keys: string[] = [];
  
  const traverse = (nodeList: TreeNode[]) => {
    nodeList.forEach(node => {
      if (node.children && node.children.length > 0) {
        keys.push(node.key);
        traverse(node.children);
      }
    });
  };
  
  traverse(nodes);
  return keys;
}