/**
 * 模型凭证相关类型定义
 */

export enum ModelType {
  EMBEDDING = 'embedding',
  RERANKER = 'reranker',
  LLM = 'llm',
  VLM = 'vlm'
}

export interface ModelTypeInfo {
  type: ModelType;
  name: string;
  description: string;
}

export interface CredentialBase {
  name: string;
  provider: string;
  model_type: ModelType;
  base_url: string;
  description?: string;
}

export interface CredentialCreate extends CredentialBase {
  api_key: string;
}

export interface CredentialUpdate {
  name?: string;
  provider?: string;
  api_key?: string;
  base_url?: string;
  description?: string;
}

export interface Credential extends CredentialBase {
  id: string;
  user_id: string;
  api_key_encrypted: string;
  api_key_display: string;
  is_active: string;
  created_at: string;
  updated_at: string;
}

export interface CredentialListResponse {
  credentials: Credential[];
  total: number;
}

export interface ModelTypesResponse {
  model_types: ModelTypeInfo[];
}

export interface KBModelConfigCreate {
  kb_id: string;
  credential_id: string;
  model_name: string;
  config_params?: Record<string, any>;
}

export interface KBModelConfigUpdate {
  credential_id: string;
  model_name?: string;
  config_params?: Record<string, any>;
}

export interface KBModelConfig {
  id: string;
  kb_id: string;
  model_type: ModelType;
  model_name: string;
  credential_id: string;
  config_params?: Record<string, any>;
  created_at: string;
  updated_at: string;
  credential?: Credential;
}

export interface KBModelConfigsResponse {
  kb_id: string;
  configs: KBModelConfig[];
}