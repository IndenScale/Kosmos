import { useSystemConfig } from '@/context/SystemConfigContext';

// 自定义hook，用于获取知识库相关的配置
export const useKnowledgeBaseConfig = () => {
  const { config } = useSystemConfig();
  
  return {
    baseUrl: config.knowledgeBaseUrl,
    username: config.knowledgeBaseUsername,
    password: config.knowledgeBasePassword,
    spaceId: config.knowledgeSpaceId
  };
};

// 自定义hook，用于获取评估服务相关的配置
export const useAssessmentConfig = () => {
  const { config } = useSystemConfig();
  
  return {
    serverUrl: config.assessmentServerUrl,
    jobId: config.assessmentJobId
  };
};

// 自定义hook，用于获取模型凭证配置
export const useModelConfig = () => {
  const { config } = useSystemConfig();
  
  return {
    apiKey: config.apiKey,
    endpoint: config.modelEndpoint
  };
};