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

export interface KnowledgeBase {
  id: string;
  name: string;
  description?: string;
  owner_id: string;
  tag_dictionary: Record<string, any>;
  milvus_collection_id?: string;
  is_public: boolean;
  created_at: string;
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