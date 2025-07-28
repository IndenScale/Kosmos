/**
 * 解析服务
 * 文件: parserService.ts
 * 创建时间: 2025-07-26
 * 描述: 提供文档解析的前端接口
 */

import apiClient from './apiClient';
import { JobResponse } from './jobService';

// 解析请求类型
export interface DocumentParseRequest {
  document_id: string;
  force_reparse?: boolean;
}

export interface BatchParseRequest {
  document_ids: string[];
  force_reparse?: boolean;
  max_concurrent?: number;
}

// 解析响应类型
export interface ParseResponse {
  document_id: string;
  total_fragments: number;
  text_fragments: number;
  screenshot_fragments: number;
  figure_fragments: number;
  parse_duration_ms: number;
  success: boolean;
  error_message?: string;
}

export interface ParseStatusResponse {
  document_id: string;
  status: 'not_parsed' | 'parsing' | 'parsed' | 'failed' | 'unknown';
  last_parsed_at?: string;
  fragment_count: number;
  error_message?: string;
}

export interface ParseStatsResponse {
  kb_id: string;
  total_documents: number;
  parsed_documents: number;
  pending_documents: number;
  failed_documents: number;
  total_fragments: number;
  last_updated?: string;
}

export class ParserService {
  private readonly baseUrl = '/api/v1/parser';

  /**
   * 解析单个文档
   */
  async parseDocument(kbId: string, request: DocumentParseRequest): Promise<ParseResponse> {
    const response = await apiClient.post(`${this.baseUrl}/kb/${kbId}/parse`, request);
    return response.data;
  }

  /**
   * 批量解析文档（返回Job）
   */
  async batchParseDocuments(kbId: string, request: BatchParseRequest): Promise<JobResponse> {
    const response = await apiClient.post(`${this.baseUrl}/kb/${kbId}/batch-parse`, request);
    return response.data;
  }

  /**
   * 获取文档解析状态
   */
  async getParseStatus(documentId: string): Promise<ParseStatusResponse> {
    const response = await apiClient.get(`${this.baseUrl}/document/${documentId}/status`);
    return response.data;
  }

  /**
   * 获取知识库解析统计信息
   */
  async getParseStats(kbId: string): Promise<ParseStatsResponse> {
    const response = await apiClient.get(`${this.baseUrl}/kb/${kbId}/stats`);
    return response.data;
  }

  /**
   * 删除文档的所有Fragment
   */
  async deleteDocumentFragments(kbId: string, documentId: string): Promise<void> {
    await apiClient.delete(`${this.baseUrl}/kb/${kbId}/fragments/${documentId}`);
  }
}

// 导出单例实例
export const parserService = new ParserService();