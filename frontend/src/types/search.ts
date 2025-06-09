export interface SearchQuery {
  query: string;
  top_k?: number;
}

export interface SearchResult {
  chunk_id: string;
  document_id: string;
  content: string;
  tags: string[];
  score: number;
}

export interface RecommendedTag {
  tag: string;
  freq: number;
  eig_score: number;
}

export interface SearchResponse {
  results: SearchResult[];
  recommended_tags: RecommendedTag[];
}

export interface ParsedQuery {
  text: string;
  must_tags: string[];
  must_not_tags: string[];
  like_tags: string[];
}

export enum TagType {
  LIKE = 'like',
  MUST = 'must',
  MUST_NOT = 'must_not',
  INACTIVE = 'inactive'
}

export interface ActiveTag {
  tag: string;
  type: TagType;
}