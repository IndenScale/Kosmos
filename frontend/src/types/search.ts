import { DocumentRecord } from "./document";
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

export interface SearchPageState {
  searchText: string;
  activeTags: ActiveTag[];
  searchQuery: string;
  expandedChunk: string | null;
  modalOpen: boolean;
  hoveredResult: string | null;
}

export interface SearchResultCardProps {
  result: SearchResult;
  document?: DocumentRecord;
  isHovered: boolean;
  onMouseEnter: () => void;
  onMouseLeave: () => void;
  onExpand: (chunkId: string) => void;
  onDownload: (documentId: string, filename: string) => void;
  onTagClick: (tag: string) => void;
  getResultTagColor: (tag: string) => string;
}

export interface RecommendedTagsProps {
  tags: RecommendedTag[];
  onTagClick: (tag: string) => void;
  searchResultsLength: number;
}

export interface ActiveTagsBarProps {
  activeTags: ActiveTag[];
  onTagClick: (tag: string, type?: TagType) => void;
  getTagColor: (type: TagType) => string;
}