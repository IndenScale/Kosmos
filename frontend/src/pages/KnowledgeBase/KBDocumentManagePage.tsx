import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { message, Modal } from 'antd';
import { useParams } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import type { UploadProps } from 'antd';

// 导入类型定义
import {
  DocumentRecord,
  SelectionState,
  DocumentStatus,
  BatchAction
} from '../../types/document';
import { IngestionJobStatus, DocumentJobStatus } from '../../types/ingestion';
import { KBDetail } from '../../types/knowledgeBase';

// 导入服务
import { documentService } from '../../services/documentService';
import { ingestionService } from '../../services/ingestionService';
import { KnowledgeBaseService } from '../../services/KnowledgeBase';

// 导入组件
import { DocumentToolbar } from '../../components/DocumentManage/DocumentToolbar';
import { OutdatedDocumentsAlert } from '../../components/DocumentManage/OutdatedDocumentsAlert';
import { DocumentTable } from '../../components/DocumentManage/DocumentTable';
import { UploadModal } from '../../components/DocumentManage/UploadModal';

// 导入工具函数
import { getDocumentStatus, isDocumentOutdated } from '../../utils/documentUtils';

export const KBDocumentManagePage: React.FC = () => {
  const { kbId } = useParams<{ kbId: string }>();
  const queryClient = useQueryClient();

  // 状态管理
  const [uploadModalVisible, setUploadModalVisible] = useState(false);
  const [selectedRowKeys, setSelectedRowKeys] = useState<string[]>([]);
  const [documentJobStatuses, setDocumentJobStatuses] = useState<Map<string, DocumentJobStatus>>(new Map());

  // 获取知识库详情
  const { data: kbDetail } = useQuery({
    queryKey: ['knowledgeBase', kbId],
    queryFn: () => KnowledgeBaseService.getKBDetail(kbId!),
    enabled: !!kbId,
  });

  // 获取文档列表
  const { data: documentsData, isLoading } = useQuery({
    queryKey: ['documents', kbId],
    queryFn: () => documentService.getDocuments(kbId!),
    enabled: !!kbId,
  });

  // 获取文档任务状态
  const { data: jobStatuses } = useQuery({
    queryKey: ['documentJobStatuses', kbId],
    queryFn: () => ingestionService.getDocumentJobStatuses(kbId!),
    enabled: !!kbId,
    refetchInterval: 2000,
    refetchIntervalInBackground: true,
  });

  // 更新文档任务状态映射
  useEffect(() => {
    if (jobStatuses) {
      const statusMap = new Map<string, DocumentJobStatus>();
      jobStatuses.forEach(status => {
        statusMap.set(status.document_id, status);
      });
      setDocumentJobStatuses(statusMap);
    }
  }, [jobStatuses]);

  // 计算过时文档
  const outdatedDocuments = useMemo(() => {
    if (!documentsData?.documents || !kbDetail?.last_tag_directory_update_time) {
      return [];
    }
    return documentsData.documents.filter((doc: DocumentRecord) =>
      isDocumentOutdated(doc, kbDetail.last_tag_directory_update_time)
    );
  }, [documentsData, kbDetail]);

  // 计算选择状态
  const selectionState = useMemo(() => {
    if (!documentsData?.documents) return SelectionState.NONE;

    const allDocumentIds = documentsData.documents.map((doc: DocumentRecord) => doc.document_id);
    const currentPageIds = documentsData.documents.map((doc: DocumentRecord) => doc.document_id);

    if (selectedRowKeys.length === 0) {
      return SelectionState.NONE;
    } else if (selectedRowKeys.length === allDocumentIds.length && allDocumentIds.length > 0) {
      return SelectionState.ALL;
    } else if (
      currentPageIds.length > 0 &&
      currentPageIds.every((id: string) => selectedRowKeys.includes(id))
    ) {
      return SelectionState.PAGE;
    } else {
      return SelectionState.PARTIAL;
    }
  }, [selectedRowKeys, documentsData]);

  // Mutations
  const deleteMutation = useMutation({
    mutationFn: (documentId: string) => documentService.deleteDocument(kbId!, documentId),
    onSuccess: () => {
      message.success('文档删除成功');
      queryClient.invalidateQueries({ queryKey: ['documents', kbId] });
    },
    onError: (error: any) => {
      if (error.code === 'ECONNABORTED' && error.message.includes('timeout')) {
        message.warning('删除请求超时，请刷新页面确认删除结果');
        setTimeout(() => {
          queryClient.invalidateQueries({ queryKey: ['documents', kbId] });
        }, 2000);
      } else {
        message.error(`删除失败: ${error.message}`);
      }
    }
  });

  const ingestMutation = useMutation({
    mutationFn: ({ documentId, forceReingest }: { documentId: string, forceReingest?: boolean }) =>
      ingestionService.processDocument(kbId!, documentId, forceReingest),
    onSuccess: (data, { forceReingest }) => {
      const action = forceReingest ? '重摄取' : '摄取';
      message.success(`${action}任务已启动`);
      queryClient.invalidateQueries({ queryKey: ['documentJobStatuses', kbId] });
    },
    onError: (error: any) => {
      message.error(error.response?.data?.detail || '摄取启动失败');
    },
  });

  const batchDeleteMutation = useMutation({
    mutationFn: (documentIds: string[]) => documentService.deleteDocuments(kbId!, documentIds),
    onSuccess: (results) => {
      const successCount = results.filter(result => result.success).length;
      const failedCount = results.length - successCount;

      if (successCount > 0) {
        message.success(`成功删除 ${successCount} 个文档`);
      }
      if (failedCount > 0) {
        message.error(`${failedCount} 个文档删除失败`);
      }

      queryClient.invalidateQueries({ queryKey: ['documents', kbId] });
      setSelectedRowKeys([]);
    },
    onError: (error: any) => {
      message.error(error.response?.data?.detail || '批量删除失败');
    },
  });

  const batchProcessMutation = useMutation({
    mutationFn: ({ documentIds, forceReindex }: { documentIds: string[], forceReindex: boolean }) =>
      ingestionService.processBatchDocuments(kbId!, documentIds, forceReindex),
    onSuccess: (results, { forceReindex }) => {
      const action = forceReindex ? '重摄取' : '摄取';
      message.success(`已启动 ${results.success_count} 个文档的${action}任务`);
      if (results.failed_count > 0) {
        message.warning(`${results.failed_count} 个文档${action}启动失败`);
      }
      setSelectedRowKeys([]);
      queryClient.invalidateQueries({ queryKey: ['documentJobStatuses', kbId] });
    },
    onError: (error: any) => {
      message.error(error.response?.data?.detail || '批量处理启动失败');
    },
  });

  // 事件处理函数
  const handleSelectionChange = useCallback((newSelectedRowKeys: string[]) => {
    setSelectedRowKeys(newSelectedRowKeys);
  }, []);

  const handleSelectAll = useCallback(() => {
    if (documentsData?.documents) {
      const allIds = documentsData.documents.map((doc: DocumentRecord) => doc.document_id);
      setSelectedRowKeys(allIds);
    }
  }, [documentsData]);

  const handleSelectNone = useCallback(() => {
    setSelectedRowKeys([]);
  }, []);

  const handleBatchProcess = useCallback(() => {
    if (selectedRowKeys.length === 0) {
      message.warning('请选择要处理的文档');
      return;
    }

    const selectedDocs = documentsData?.documents?.filter(
      (doc: DocumentRecord) => selectedRowKeys.includes(doc.document_id)
    ) || [];

    const ingestableDocs = selectedDocs.filter((doc: DocumentRecord) => {
      const status = getDocumentStatus(doc, documentJobStatuses, kbDetail?.last_tag_directory_update_time);
      return status === DocumentStatus.NOT_INGESTED;
    });

    const reIndexableDocs = selectedDocs.filter((doc: DocumentRecord) => {
      const status = getDocumentStatus(doc, documentJobStatuses, kbDetail?.last_tag_directory_update_time);
      return status === DocumentStatus.INGESTED || status === DocumentStatus.OUTDATED;
    });

    if (ingestableDocs.length === 0 && reIndexableDocs.length === 0) {
      message.warning('选中的文档中没有可以处理的文档');
      return;
    }

    if (reIndexableDocs.length > 0) {
      Modal.confirm({
        title: '处理确认',
        content: `将处理 ${selectedRowKeys.length} 个文档，其中 ${ingestableDocs.length} 个新摄取，${reIndexableDocs.length} 个重摄取。是否继续？`,
        onOk: () => {
          if (ingestableDocs.length > 0) {
            batchProcessMutation.mutate({
              documentIds: ingestableDocs.map(doc => doc.document_id),
              forceReindex: false
            });
          }
          if (reIndexableDocs.length > 0) {
            batchProcessMutation.mutate({
              documentIds: reIndexableDocs.map(doc => doc.document_id),
              forceReindex: true
            });
          }
        }
      });
    } else {
      batchProcessMutation.mutate({
        documentIds: ingestableDocs.map(doc => doc.document_id),
        forceReindex: false
      });
    }
  }, [selectedRowKeys, documentsData, documentJobStatuses, kbDetail, batchProcessMutation]);

  const handleBatchDelete = useCallback(() => {
    if (selectedRowKeys.length === 0) {
      message.warning('请选择要删除的文档');
      return;
    }

    Modal.confirm({
      title: '确认批量删除',
      content: `确定要删除选中的 ${selectedRowKeys.length} 个文档吗？此操作不可撤销。`,
      okText: '确定删除',
      okType: 'danger',
      cancelText: '取消',
      onOk: () => {
        batchDeleteMutation.mutate(selectedRowKeys);
      },
    });
  }, [selectedRowKeys, batchDeleteMutation]);

  const handleBatchDownload = useCallback(async () => {
    if (selectedRowKeys.length === 0) {
      message.warning('请选择要下载的文档');
      return;
    }

    const selectedDocs = documentsData?.documents?.filter(
      (doc: DocumentRecord) => selectedRowKeys.includes(doc.document_id)
    ) || [];

    try {
      message.loading('正在准备下载...', 0);

      for (const doc of selectedDocs) {
        try {
          const blob = await documentService.downloadDocument(kbId!, doc.document_id);
          const url = window.URL.createObjectURL(blob);
          const a = document.createElement('a');
          a.href = url;
          a.download = doc.document.filename;
          document.body.appendChild(a);
          a.click();
          window.URL.revokeObjectURL(url);
          document.body.removeChild(a);

          await new Promise(resolve => setTimeout(resolve, 100));
        } catch (error) {
          console.error(`下载文档 ${doc.document.filename} 失败:`, error);
          message.error(`下载文档 ${doc.document.filename} 失败`);
        }
      }

      message.destroy();
      message.success(`已开始下载 ${selectedDocs.length} 个文档`);
    } catch (error) {
      message.destroy();
      message.error('批量下载失败');
    }
  }, [selectedRowKeys, documentsData, kbId]);

  const handleDownload = useCallback(async (documentId: string, filename: string) => {
    try {
      const blob = await documentService.downloadDocument(kbId!, documentId);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (error) {
      message.error('下载失败');
    }
  }, [kbId]);

  const handleCancelJob = useCallback(async (documentId: string) => {
    const jobStatus = documentJobStatuses.get(documentId);
    if (jobStatus?.job_id) {
      try {
        await ingestionService.cancelJob(jobStatus.job_id);
        message.success('任务已取消');
        queryClient.invalidateQueries({ queryKey: ['documentJobStatuses', kbId] });
      } catch (error: any) {
        message.error('取消任务失败');
      }
    }
  }, [documentJobStatuses, queryClient, kbId]);

  const handleBatchReIngest = useCallback((documentIds: string[]) => {
    setSelectedRowKeys(documentIds);
    batchProcessMutation.mutate({
      documentIds,
      forceReindex: true
    });
  }, [batchProcessMutation]);

  // 上传配置
  const uploadProps: UploadProps = {
    name: 'files',
    multiple: true,
    action: `/api/v1/kbs/${kbId}/documents/upload`,
    headers: {
      Authorization: `Bearer ${localStorage.getItem('access_token')}`,
    },
    onChange(info) {
      const { status } = info.file;
      if (status === 'done') {
        message.success(`${info.file.name} 文件上传成功`);
        queryClient.invalidateQueries({ queryKey: ['documents', kbId] });
      } else if (status === 'error') {
        message.error(`${info.file.name} 文件上传失败`);
      }
    },
    showUploadList: false,
  };

  return (
    <div>
      <DocumentToolbar
        selectedCount={selectedRowKeys.length}
        onBatchDownload={handleBatchDownload}
        onBatchProcess={handleBatchProcess}
        onBatchDelete={handleBatchDelete}
        uploadProps={uploadProps}
        batchProcessLoading={batchProcessMutation.isPending}
        batchDeleteLoading={batchDeleteMutation.isPending}
      />

      <OutdatedDocumentsAlert
        outdatedDocuments={outdatedDocuments}
        onBatchReIngest={handleBatchReIngest}
        loading={batchProcessMutation.isPending}
      />

      <DocumentTable
        documents={documentsData?.documents || []}
        total={documentsData?.total || 0}
        loading={isLoading}
        selectedRowKeys={selectedRowKeys}
        selectionState={selectionState}
        documentJobStatuses={documentJobStatuses}
        lastTagDirectoryUpdateTime={kbDetail?.last_tag_directory_update_time}
        onSelectionChange={handleSelectionChange}
        onSelectAll={handleSelectAll}
        onSelectNone={handleSelectNone}
        onPreview={(documentId) => message.info('预览功能待实现')}
        onDownload={handleDownload}
        onIngest={(documentId) => ingestMutation.mutate({ documentId })}
        onReIngest={(documentId) => ingestMutation.mutate({ documentId, forceReingest: true })}
        onCancel={handleCancelJob}
        onDelete={(documentId) => deleteMutation.mutate(documentId)}
        ingestLoading={ingestMutation.isPending}
      />

      <UploadModal
        visible={uploadModalVisible}
        onCancel={() => setUploadModalVisible(false)}
        uploadProps={uploadProps}
      />
    </div>
  );
};