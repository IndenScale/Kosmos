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
  last_tag_directory_update_time?: string; // 新增：标签字典最后更新时间
}

export interface KBDetail extends KnowledgeBase {
  members: KBMember[];
  owner_username: string;
}

export interface KBStats {
  document_count: number;
  chunk_count: number;
  top_level_tags: string[];
}

// 新增：文档记录接口，包含摄入时间
export interface DocumentRecord {
  document_id: string;
  kb_id: string;
  uploaded_by: string;
  upload_at: string;
  last_ingest_time?: string; // 新增：最后摄入时间
  chunk_count?: number;
  document: {
    id: string;
    filename: string;
    file_type: string;
    file_size: number;
    file_path: string;
    created_at: string;
  };
  uploader_username?: string;
  is_outdated?: boolean; // 新增：是否过时标记
}