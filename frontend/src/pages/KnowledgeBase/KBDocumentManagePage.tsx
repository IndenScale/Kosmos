import React, { useState, useMemo, useCallback, useEffect } from 'react';
import { Table, Button, Upload, Modal, message, Space, Tag, Popconfirm, Checkbox, Alert, Progress } from 'antd';
import {
  UploadOutlined,
  DownloadOutlined,
  DeleteOutlined,
  EyeOutlined,
  PlayCircleOutlined,
  LoadingOutlined,
  ExclamationCircleOutlined,
  ClockCircleOutlined,
  ReloadOutlined,
  StopOutlined
} from '@ant-design/icons';
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
    refetchInterval: 2000, // 每2秒刷新一次任务状态
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
      documentService.isDocumentOutdated(doc, kbDetail.last_tag_directory_update_time)
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

  // 获取文档状态（基于任务队列状态）
  const getDocumentStatus = useCallback((document: DocumentRecord): DocumentStatus => {
    const jobStatus = documentJobStatuses.get(document.document_id);

    // 如果有正在进行的任务，优先显示任务状态
    if (jobStatus) {
      switch (jobStatus.status) {
        case IngestionJobStatus.PENDING:
        case IngestionJobStatus.RUNNING:
          return DocumentStatus.INGESTING;
        case IngestionJobStatus.FAILED:
          return DocumentStatus.NOT_INGESTED; // 失败后回到未摄取状态
        case IngestionJobStatus.COMPLETED:
          // 任务完成，需要刷新文档数据
          queryClient.invalidateQueries({ queryKey: ['documents', kbId] });
          break;
      }
    }

    // 基于文档本身的状态判断
    const isIngested = document.chunk_count && document.chunk_count > 0;
    const isOutdated = documentService.isDocumentOutdated(
      document,
      kbDetail?.last_tag_directory_update_time
    );

    if (isIngested && isOutdated) return DocumentStatus.OUTDATED;
    if (isIngested) return DocumentStatus.INGESTED;
    return DocumentStatus.NOT_INGESTED;
  }, [documentJobStatuses, kbDetail, queryClient, kbId]);

  // 获取任务进度
  const getJobProgress = useCallback((documentId: string): number | undefined => {
    const jobStatus = documentJobStatuses.get(documentId);
    return jobStatus?.progress;
  }, [documentJobStatuses]);

  // 处理选择状态切换
  const handleSelectionChange = useCallback(() => {
    if (!documentsData?.documents) return;

    const allDocumentIds = documentsData.documents.map((doc: DocumentRecord) => doc.document_id);
    const currentPageIds = documentsData.documents.map((doc: DocumentRecord) => doc.document_id);

    switch (selectionState) {
      case SelectionState.NONE:
        setSelectedRowKeys(currentPageIds);
        break;
      case SelectionState.PARTIAL:
        setSelectedRowKeys([
          ...selectedRowKeys,
          ...currentPageIds.filter((id: string) => !selectedRowKeys.includes(id))
        ]);
        break;
      case SelectionState.PAGE:
        setSelectedRowKeys(allDocumentIds);
        break;
      case SelectionState.ALL:
        setSelectedRowKeys([]);
        break;
    }
  }, [selectionState, selectedRowKeys, documentsData]);

  // 获取选择框显示文本
  const getSelectionText = useCallback(() => {
    switch (selectionState) {
      case SelectionState.NONE: return '选择';
      case SelectionState.PARTIAL: return '部分';
      case SelectionState.PAGE: return '本页';
      case SelectionState.ALL: return '全部';
    }
  }, [selectionState]);

  // 文档上传
  const uploadMutation = useMutation({
    mutationFn: (file: File) => documentService.uploadDocument(kbId!, file),
    onSuccess: () => {
      message.success('文档上传成功');
      setUploadModalVisible(false);
      queryClient.invalidateQueries({ queryKey: ['documents', kbId] });
    },
    onError: (error: any) => {
      message.error(error.response?.data?.detail || '上传失败');
    },
  });

  // 文档删除
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

  // 文档摄取
  const ingestMutation = useMutation({
    mutationFn: ({ documentId, forceReingest }: { documentId: string, forceReingest?: boolean }) =>
      ingestionService.processDocument(kbId!, documentId, forceReingest),
    onSuccess: (data, { documentId, forceReingest }) => {
      // 根据请求参数判断操作类型，而不是依赖响应消息
      const action = forceReingest ? '重摄取' : '摄取';
      message.success(`${action}任务已启动`);
      // 立即刷新任务状态
      queryClient.invalidateQueries({ queryKey: ['documentJobStatuses', kbId] });
    },
    onError: (error: any) => {
      message.error(error.response?.data?.detail || '摄取启动失败');
    },
  });

  // 批量删除
  const batchDeleteMutation = useMutation({
    mutationFn: (documentIds: string[]) => documentService.deleteDocuments(kbId!, documentIds),
    onSuccess: (results, documentIds) => {
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

  // 合并的批量处理mutation
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
      // 立即刷新任务状态
      queryClient.invalidateQueries({ queryKey: ['documentJobStatuses', kbId] });
    },
    onError: (error: any) => {
      message.error(error.response?.data?.detail || '批量处理启动失败');
    },
  });

  // 智能批量处理函数
  const handleBatchProcess = useCallback(() => {
    if (selectedRowKeys.length === 0) {
      message.warning('请选择要处理的文档');
      return;
    }

    const selectedDocs = documentsData?.documents?.filter(
      (doc: DocumentRecord) => selectedRowKeys.includes(doc.document_id)
    ) || [];

    const ingestableDocs = selectedDocs.filter((doc: DocumentRecord) => {
      const status = getDocumentStatus(doc);
      return status === DocumentStatus.NOT_INGESTED;
    });

    const reIndexableDocs = selectedDocs.filter((doc: DocumentRecord) => {
      const status = getDocumentStatus(doc);
      return status === DocumentStatus.INGESTED || status === DocumentStatus.OUTDATED;
    });

    if (ingestableDocs.length === 0 && reIndexableDocs.length === 0) {
      message.warning('选中的文档中没有可以处理的文档');
      return;
    }

    // 如果有需要重索引的文档，询问用户
    if (reIndexableDocs.length > 0) {
      Modal.confirm({
        title: '处理确认',
        content: `将处理 ${selectedRowKeys.length} 个文档，其中 ${ingestableDocs.length} 个新摄取，${reIndexableDocs.length} 个重摄取。是否继续？`,
        onOk: () => {
          // 分别处理新摄取和重摄取
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
      // 只有新摄取的文档
      batchProcessMutation.mutate({
        documentIds: ingestableDocs.map(doc => doc.document_id),
        forceReindex: false
      });
    }
  }, [selectedRowKeys, documentsData, getDocumentStatus, batchProcessMutation]);

  // 批量删除处理
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

  // 取消任务
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

  // 批量下载
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

  // 单个文档下载
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

  // 上传配置
  const uploadProps: UploadProps = {
    multiple: true,
    beforeUpload: (file) => {
      // 验证文件类型
      const typeValidation = documentService.validateFileType(file);
      if (!typeValidation.isValid) {
        message.error(typeValidation.error);
        return false;
      }

      // 验证文件大小
      const sizeValidation = documentService.validateFileSize(file);
      if (!sizeValidation.isValid) {
        message.error(sizeValidation.error);
        return false;
      }

      uploadMutation.mutate(file);
      return false;
    },
    showUploadList: false,
  };

  // 表格列定义
  const columns = [
    {
      title: (
        <Checkbox
          indeterminate={selectionState === SelectionState.PARTIAL}
          checked={selectionState !== SelectionState.NONE}
          onChange={handleSelectionChange}
        >
          {getSelectionText()}
        </Checkbox>
      ),
      dataIndex: 'selection',
      key: 'selection',
      width: 100,
      render: (_: any, record: DocumentRecord) => (
        <Checkbox
          checked={selectedRowKeys.includes(record.document_id)}
          onChange={(e) => {
            if (e.target.checked) {
              setSelectedRowKeys([...selectedRowKeys, record.document_id]);
            } else {
              setSelectedRowKeys(selectedRowKeys.filter(key => key !== record.document_id));
            }
          }}
        />
      ),
    },
    {
      title: '文件名',
      dataIndex: ['document', 'filename'],
      key: 'filename',
      render: (filename: string, record: DocumentRecord) => {
        const status = getDocumentStatus(record);
        return (
          <div className="flex items-center">
            <span>{filename}</span>
            {status === DocumentStatus.OUTDATED && (
              <Tag icon={<ClockCircleOutlined />} color="orange" className="ml-2">
                标签过时
              </Tag>
            )}
          </div>
        );
      },
    },
    {
      title: '文件类型',
      dataIndex: ['document', 'file_type'],
      key: 'file_type',
    },
    {
      title: '文件大小',
      dataIndex: ['document', 'file_size'],
      key: 'file_size',
      render: (size: number) => documentService.formatFileSize(size),
    },
    {
      title: '上传者',
      dataIndex: 'uploader_username',
      key: 'uploader_username',
      render: (username: string, record: DocumentRecord) =>
        username || record.uploaded_by || '未知用户',
    },
    {
      title: '上传时间',
      dataIndex: 'upload_at',
      key: 'upload_at',
      render: (date: string) => new Date(date).toLocaleString(),
    },
    {
      title: '最后摄入时间',
      dataIndex: 'last_ingest_time',
      key: 'last_ingest_time',
      render: (date: string) => date ? new Date(date).toLocaleString() : '未摄入',
    },
    {
      title: '状态',
      key: 'status',
      render: (_: any, record: DocumentRecord) => {
        const status = getDocumentStatus(record);
        const jobStatus = documentJobStatuses.get(record.document_id);
        const progress = getJobProgress(record.document_id);

        switch (status) {
          case DocumentStatus.INGESTING:
            return (
              <div>
                <Tag icon={<LoadingOutlined />} color="processing">
                  {jobStatus?.status === IngestionJobStatus.PENDING ? '等待中' : '摄取中'}
                </Tag>
                {progress !== undefined && (
                  <Progress
                    percent={progress}
                    size="small"
                    style={{ width: 100, marginTop: 4 }}
                  />
                )}
                {jobStatus?.error_message && (
                  <div className="text-red-500 text-xs mt-1">
                    {jobStatus.error_message}
                  </div>
                )}
              </div>
            );
          case DocumentStatus.INGESTED:
            return (
              <Tag color="success">
                已摄取 ({record.chunk_count} 块)
              </Tag>
            );
          case DocumentStatus.OUTDATED:
            return (
              <Space>
                <Tag color="success">
                  已摄取 ({record.chunk_count} 块)
                </Tag>
                <Tag icon={<ExclamationCircleOutlined />} color="warning">
                  需要重新摄取
                </Tag>
              </Space>
            );
          default:
            return (
              <Tag color="default">
                未摄取
              </Tag>
            );
        }
      },
    },
    {
      title: '操作',
      key: 'actions',
      render: (_: any, record: DocumentRecord) => {
        const status = getDocumentStatus(record);
        const jobStatus = documentJobStatuses.get(record.document_id);
        const isProcessing = status === DocumentStatus.INGESTING;
        const canIngest = status === DocumentStatus.NOT_INGESTED;
        const canReIngest = status === DocumentStatus.OUTDATED;
        const canCancel = isProcessing && jobStatus?.job_id;

        return (
          <Space>
            <Button
              size="small"
              icon={<EyeOutlined />}
              onClick={() => {
                message.info('预览功能待实现');
              }}
            >
              预览
            </Button>
            <Button
              size="small"
              icon={<DownloadOutlined />}
              onClick={() => handleDownload(record.document_id, record.document.filename)}
            >
              下载
            </Button>
            {canIngest && (
              <Button
                size="small"
                icon={<PlayCircleOutlined />}
                onClick={() => ingestMutation.mutate({ documentId: record.document_id })}
                disabled={ingestMutation.isPending}
              >
                摄取
              </Button>
            )}
            {canReIngest && (
              <Button
                size="small"
                icon={<ReloadOutlined />}
                onClick={() => ingestMutation.mutate({ documentId: record.document_id, forceReingest: true })}
                disabled={ingestMutation.isPending}
              >
                重新摄取
              </Button>
            )}
            {canCancel && (
              <Button
                size="small"
                icon={<StopOutlined />}
                onClick={() => handleCancelJob(record.document_id)}
                danger
              >
                取消
              </Button>
            )}
            <Popconfirm
              title="确定要删除这个文档吗？"
              onConfirm={() => deleteMutation.mutate(record.document_id)}
              okText="确定"
              cancelText="取消"
            >
              <Button
                size="small"
                danger
                icon={<DeleteOutlined />}
                disabled={isProcessing}
              >
                删除
              </Button>
            </Popconfirm>
          </Space>
        );
      },
    },
  ];

  return (
    <div>
      <div className="mb-4 flex justify-between items-center">
        <h3 className="text-lg font-medium">文档管理</h3>
        <Space>
          <Button
            icon={<DownloadOutlined />}
            onClick={handleBatchDownload}
            disabled={selectedRowKeys.length === 0}
          >
            批量下载 ({selectedRowKeys.length})
          </Button>
          <Button
            type="primary"
            icon={<PlayCircleOutlined />}
            onClick={handleBatchProcess}
            disabled={selectedRowKeys.length === 0 || batchProcessMutation.isPending}
            loading={batchProcessMutation.isPending}
          >
            批量处理 ({selectedRowKeys.length})
          </Button>
          <Button
            danger
            icon={<DeleteOutlined />}
            onClick={handleBatchDelete}
            disabled={selectedRowKeys.length === 0 || batchDeleteMutation.isPending}
            loading={batchDeleteMutation.isPending}
          >
            批量删除 ({selectedRowKeys.length})
          </Button>
          <Upload {...uploadProps}>
            <Button icon={<UploadOutlined />}>上传文档</Button>
          </Upload>
        </Space>
      </div>

      {/* 过时文档提醒 */}
      {outdatedDocuments.length > 0 && (
        <Alert
          message={`检测到 ${outdatedDocuments.length} 个文档的索引可能已过时`}
          description="标签字典已更新，建议重新摄取这些文档以获得最佳搜索效果。"
          type="warning"
          showIcon
          className="mb-4"
          action={
            <Button
              size="small"
              type="primary"
              onClick={() => {
                const outdatedIds = outdatedDocuments.map(doc => doc.document_id);
                setSelectedRowKeys(outdatedIds);
                batchProcessMutation.mutate({
                  documentIds: outdatedIds,
                  forceReindex: true
                });
              }}
              loading={batchProcessMutation.isPending}
            >
              批量重新摄取
            </Button>
          }
        />
      )}

      <Table
        columns={columns}
        dataSource={documentsData?.documents || []}
        rowKey="document_id"
        loading={isLoading}
        pagination={{
          total: documentsData?.total || 0,
          pageSize: 20,
          showSizeChanger: true,
          showQuickJumper: true,
          showTotal: (total, range) => `第 ${range[0]}-${range[1]} 条，共 ${total} 条`,
        }}
      />

      {/* 上传模态框 */}
      <Modal
        title="上传文档"
        open={uploadModalVisible}
        onCancel={() => setUploadModalVisible(false)}
        footer={null}
      >
        <Upload.Dragger {...uploadProps}>
          <p className="ant-upload-drag-icon">
            <UploadOutlined />
          </p>
          <p className="ant-upload-text">点击或拖拽文件到此区域上传</p>
          <p className="ant-upload-hint">
            支持单个或批量上传。支持的文件类型：PDF、Word、PowerPoint、文本文件等。
          </p>
        </Upload.Dragger>
      </Modal>
    </div>
  );
};