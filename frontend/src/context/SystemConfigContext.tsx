import React, { createContext, useContext, useState, ReactNode } from 'react';

// 定义配置项的类型
export interface SystemConfig {
  // 知识库配置
  knowledgeBaseUrl: string;
  knowledgeBaseUsername: string;
  knowledgeBasePassword: string;
  
  // 评估服务器配置
  assessmentServerUrl: string;
  assessmentJobId: string;
  
  // 模型凭证配置
  modelBaseUrl: string;
  modelName: string;
  apiKey: string;
}

// 定义Context的类型
interface SystemConfigContextType {
  config: SystemConfig;
  updateConfig: (newConfig: Partial<SystemConfig>) => void;
}

// 创建Context
const SystemConfigContext = createContext<SystemConfigContextType | undefined>(undefined);

// 定义Provider组件的props类型
interface SystemConfigProviderProps {
  children: ReactNode;
}

// 创建Provider组件
export const SystemConfigProvider: React.FC<SystemConfigProviderProps> = ({ children }) => {
  // 初始化配置，从localStorage中读取或使用默认值
  const [config, setConfig] = useState<SystemConfig>(() => {
    const savedConfig = localStorage.getItem('systemConfig');
    if (savedConfig) {
      try {
        return JSON.parse(savedConfig);
      } catch (e) {
        console.error('Failed to parse saved config', e);
      }
    }
    
    // 默认配置
    return {
      // 知识库配置
      knowledgeBaseUrl: 'http://10.17.99.13:8011',
      knowledgeBaseUsername: 'hxdi_wxy_prod',
      knowledgeBasePassword: 'Hxpti123-',
      
      // 评估服务器配置
      assessmentServerUrl: 'http://10.17.99.13:8015',
      assessmentJobId: '',
      
      // 模型凭证配置
      modelBaseUrl: 'http://10.17.99.25:30000/v1',
      modelName: 'Qwen3-30b-coder',
      apiKey: 'HXDI',
    };
  });

  // 更新配置的函数
  const updateConfig = (newConfig: Partial<SystemConfig>) => {
    const updatedConfig = { ...config, ...newConfig };
    setConfig(updatedConfig);
    // 保存到localStorage
    localStorage.setItem('systemConfig', JSON.stringify(updatedConfig));
  };

  return (
    <SystemConfigContext.Provider value={{ config, updateConfig }}>
      {children}
    </SystemConfigContext.Provider>
  );
};

// 创建自定义hook来使用配置
export const useSystemConfig = (): SystemConfigContextType => {
  const context = useContext(SystemConfigContext);
  if (context === undefined) {
    throw new Error('useSystemConfig must be used within a SystemConfigProvider');
  }
  return context;
};