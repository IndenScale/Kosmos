import { DocumentRecord } from './document';

export enum KBRoleEnum {
  OWNER = 'owner',
  ADMIN = 'admin',
  MEMBER = 'member'
}

export interface KBCreate {
  name: string;
  description?: string;
  is_public?: boolean;
}

export interface KBUpdate {
  name?: string;
  description?: string;
  is_public?: boolean;
}

export interface KBMember {
  user_id: string;
  username: string;
  email: string;
  role: KBRoleEnum;
  created_at: string;
}

// 定义递归的标签字典类型
export type TagDictionary = {
  [key: string]: TagDictionary | string[];
};

export interface KnowledgeBase {
  id: string;
  name: string;
  description?: string;
  owner_id: string;
  tag_dictionary: TagDictionary;
  milvus_collection_id?: string;
  is_public: boolean;
  created_at: string;
  last_tag_directory_update_time?: string;
}

export interface KBDetail extends KnowledgeBase {
  members: KBMember[];
  owner_username: string;
}

export interface KBStats {
  document_count: number;
  chunk_count: number;
  tag_dictionary: TagDictionary;
}
