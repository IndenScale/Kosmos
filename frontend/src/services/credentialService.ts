/**
 * 模型凭证管理服务
 */

import apiClient from './apiClient';
import {
  Credential,
  CredentialCreate,
  CredentialUpdate,
  CredentialListResponse,
  ModelType,
  ModelTypesResponse,
  KBModelConfig,
  KBModelConfigCreate,
  KBModelConfigUpdate,
  KBModelConfigsResponse
} from '../types/credential';

export class CredentialService {
  private baseUrl = '/api/v1/credentials';

  /**
   * 获取支持的模型类型列表
   */
  async getModelTypes(): Promise<ModelTypesResponse> {
    const response = await apiClient.get(`${this.baseUrl}/model-types`);
    return response.data;
  }

  /**
   * 创建新的模型访问凭证
   */
  async createCredential(credentialData: CredentialCreate): Promise<Credential> {
    const response = await apiClient.post(this.baseUrl, credentialData);
    return response.data;
  }

  /**
   * 获取当前用户的所有凭证
   */
  async getUserCredentials(modelType?: ModelType): Promise<CredentialListResponse> {
    const params = modelType ? { model_type: modelType } : {};
    const response = await apiClient.get(this.baseUrl, { params });
    return response.data;
  }

  /**
   * 获取指定的凭证详情
   */
  async getCredential(credentialId: string): Promise<Credential> {
    const response = await apiClient.get(`${this.baseUrl}/${credentialId}`);
    return response.data;
  }

  /**
   * 更新凭证
   */
  async updateCredential(credentialId: string, credentialData: CredentialUpdate): Promise<Credential> {
    const response = await apiClient.put(`${this.baseUrl}/${credentialId}`, credentialData);
    return response.data;
  }

  /**
   * 删除凭证
   */
  async deleteCredential(credentialId: string): Promise<void> {
    await apiClient.delete(`${this.baseUrl}/${credentialId}`);
  }

  /**
   * 为知识库创建模型配置
   */
  async createKBModelConfig(configData: KBModelConfigCreate): Promise<KBModelConfig> {
    const response = await apiClient.post(`${this.baseUrl}/kb-configs`, configData);
    return response.data;
  }

  /**
   * 获取知识库的所有模型配置
   */
  async getKBModelConfigs(kbId: string): Promise<KBModelConfigsResponse> {
    const response = await apiClient.get(`${this.baseUrl}/kb-configs/${kbId}`);
    return response.data;
  }

  /**
   * 更新知识库模型配置
   */
  async updateKBModelConfig(configId: string, configData: KBModelConfigUpdate): Promise<KBModelConfig> {
    const response = await apiClient.put(`${this.baseUrl}/kb-configs/${configId}`, configData);
    return response.data;
  }

  /**
   * 删除知识库模型配置
   */
  async deleteKBModelConfig(configId: string): Promise<void> {
    await apiClient.delete(`${this.baseUrl}/kb-configs/${configId}`);
  }
}

export const credentialService = new CredentialService();