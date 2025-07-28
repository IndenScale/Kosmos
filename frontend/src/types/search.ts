import { DocumentRecord } from "./document";

export enum FragmentType {
  TEXT = 'text',
  SCREENSHOT = 'screenshot',
  FIGURE = 'figure'
}

export interface SearchQuery {
  query: string;
  top_k?: number;
  fragment_types?: FragmentType[];
  must_tags?: string[];
  must_not_tags?: string[];
  like_tags?: string[];
  parse_query?: boolean;
  include_screenshots?: boolean;
  include_figures?: boolean;
}

export interface SearchResult {
  fragment_id: string;
  document_id: string;
  fragment_type: string;
  content: string;
  tags: string[];
  score: number;
  meta_info?: Record<string, any>;
  source_file_name?: string;
  figure_name?: string;
  related_screenshots?: Array<Record<string, any>>;
  related_figures?: Array<Record<string, any>>;
  page_range?: Record<string, number>;
  // 保持向后兼容
  chunk_id?: string;
  screenshot_ids?: string[];
}

export interface RecommendedTag {
  tag: string;
  count: number;
  relevance: number;
}

export interface ScreenshotInfo {
  id: string;
  document_id: string;
  page_number: number;
  width?: number;
  height?: number;
  created_at?: string;
  file_exists?: boolean;
}

export interface SearchResponse {
  results: SearchResult[];
  recommended_tags: RecommendedTag[];
  stats?: {
    original_count: number;
    deduplicated_count: number;
    final_count: number;
    search_time_ms?: number;
  };
  query_parse_result?: {
    text_query: string;
    must_tags: string[];
    must_not_tags: string[];
    like_tags: string[];
    original_query: string;
  };
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
  includeScreenshots: boolean;
  includeFigures: boolean;
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