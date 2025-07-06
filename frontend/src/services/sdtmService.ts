import apiClient from './apiClient';

export interface QualityMetrics {
  tags_document_distribution: Record<string, number>;
  documents_tag_distribution: Record<string, number>;
  under_annotated_docs_count: number;
  over_annotated_docs_count: number;
  under_used_tags_count: number;
  over_used_tags_count: number;
  indistinguishable_docs_count: number;
}

export interface ProgressMetrics {
  current_iteration: number;
  total_iterations: number;
  current_tags_dictionary_size: number;
  max_tags_dictionary_size: number;
  progress_pct: number;
  capacity_pct: number;
}

export interface AbnormalDocument {
  doc_id: string;
  reason: string;
  content: string;
  current_tags: string[];
  anomaly_type: string;
}

export interface SDTMStats {
  kb_id: string;
  progress_metrics: ProgressMetrics;
  quality_metrics: QualityMetrics;
  abnormal_documents: AbnormalDocument[];
  last_updated: string;
}

export interface EditOperation {
  position: string;
  payload: Record<string, any>;
}

export interface DocumentAnnotation {
  doc_id: string;
  labels: string[];
  confidence: number;
}

export interface OptimizeRequest {
  kb_id: string;
  mode: 'edit' | 'annotate' | 'shadow';
  batch_size: number;
  auto_apply: boolean;
  abnormal_doc_slots?: number;
  normal_doc_slots?: number;
  max_iterations?: number;
  abnormal_doc_threshold?: number;
  enable_early_termination?: boolean;
}

export interface OptimizeResponse {
  success: boolean;
  message: string;
  operations: EditOperation[];
  preview_dictionary: Record<string, any>;
  stats?: SDTMStats;
}

export interface BatchAnnotateRequest {
  kb_id: string;
  document_ids: string[];
  mode: 'edit' | 'annotate' | 'shadow';
}

export interface BatchAnnotateResponse {
  success: boolean;
  message: string;
  annotations: DocumentAnnotation[];
  failed_documents: string[];
}

class SDTMService {
  /**
   * 获取知识库SDTM统计信息
   */
  async getSDTMStats(kbId: string): Promise<SDTMStats> {
    const response = await apiClient.get(`/api/v1/sdtm/${kbId}/stats`);
    return response.data;
  }

  /**
   * 优化标签字典
   */
  async optimizeTagDictionary(request: OptimizeRequest): Promise<OptimizeResponse> {
    const response = await apiClient.post(`/api/v1/sdtm/${request.kb_id}/optimize`, {
      mode: request.mode,
      batch_size: request.batch_size,
      auto_apply: request.auto_apply,
      abnormal_doc_slots: request.abnormal_doc_slots,
      normal_doc_slots: request.normal_doc_slots,
      max_iterations: request.max_iterations,
      abnormal_doc_threshold: request.abnormal_doc_threshold,
      enable_early_termination: request.enable_early_termination
    });
    return response.data;
  }

  /**
   * 批量标注文档
   */
  async batchAnnotateDocuments(request: BatchAnnotateRequest): Promise<BatchAnnotateResponse> {
    const response = await apiClient.post(`/api/v1/sdtm/${request.kb_id}/annotate`, {
      document_ids: request.document_ids,
      mode: request.mode
    });
    return response.data;
  }

  /**
   * 处理知识库（通用接口）
   */
  async processKnowledgeBase(
    kbId: string,
    mode: 'edit' | 'annotate' | 'shadow',
    batchSize: number = 10,
    autoApply: boolean = true
  ): Promise<any> {
    const response = await apiClient.post(`/api/v1/sdtm/${kbId}/process`, null, {
      params: {
        mode,
        batch_size: batchSize,
        auto_apply: autoApply
      }
    });
    return response.data;
  }

  /**
   * 获取异常文档列表
   */
  async getAbnormalDocuments(kbId: string): Promise<{ success: boolean; abnormal_documents: AbnormalDocument[]; total_count: number }> {
    const response = await apiClient.get(`/api/v1/sdtm/${kbId}/abnormal-documents`);
    return response.data;
  }

  /**
   * 运行影子模式
   */
  async runShadowMode(kbId: string, batchSize: number = 10): Promise<any> {
    const response = await apiClient.post(`/api/v1/sdtm/${kbId}/shadow-mode`, null, {
      params: {
        batch_size: batchSize
      }
    });
    return response.data;
  }

  /**
   * 运行冷启动模式
   */
  async runColdStart(kbId: string, batchSize: number = 10, autoApply: boolean = true): Promise<any> {
    const response = await apiClient.post(`/api/v1/sdtm/${kbId}/cold-start`, null, {
      params: {
        batch_size: batchSize,
        auto_apply: autoApply
      }
    });
    return response.data;
  }
}

export default new SDTMService(); 