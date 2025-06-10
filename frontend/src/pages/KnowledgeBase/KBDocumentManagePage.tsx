import React, { useState, useMemo, useCallback } from 'react';
import { Table, Button, Upload, Modal, message, Space, Tag, Popconfirm, Checkbox, Alert } from 'antd';
import {
  UploadOutlined,
  DownloadOutlined,
  DeleteOutlined,
  EyeOutlined,
  PlayCircleOutlined,
  LoadingOutlined,
  ExclamationCircleOutlined,
  ClockCircleOutlined,
  ReloadOutlined
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
import { IngestionJobStatus } from '../../types/ingestion';
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
  const [processingDocs, setProcessingDocs] = useState<Set<string>>(new Set());
  const [selectedRowKeys, setSelectedRowKeys] = useState<string[]>([]);

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

  // 获取文档状态
  const getDocumentStatus = useCallback((document: DocumentRecord): DocumentStatus => {
    const isProcessing = processingDocs.has(document.document_id);
    const isIngested = document.chunk_count && document.chunk_count > 0;
    const isOutdated = documentService.isDocumentOutdated(
      document,
      kbDetail?.last_tag_directory_update_time
    );

    if (isProcessing) return DocumentStatus.INGESTING;
    if (isIngested && isOutdated) return DocumentStatus.OUTDATED;
    if (isIngested) return DocumentStatus.INGESTED;
    return DocumentStatus.NOT_INGESTED;
  }, [processingDocs, kbDetail]);

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
    onSuccess: (data, documentId) => {
      message.success('文档删除成功');
      queryClient.invalidateQueries({ queryKey: ['documents', kbId] });
      setSelectedRowKeys(prev => prev.filter(id => id !== documentId));
    },
    onError: (error: any) => {
      message.error(error.response?.data?.detail || '删除失败');
    },
  });

  // 文档摄取
  const ingestMutation = useMutation({
    mutationFn: (documentId: string) => ingestionService.startIngestion(kbId!, documentId),
    onSuccess: (data, documentId) => {
      message.success('摄取任务已启动');
      setProcessingDocs(prev => new Set([...prev, documentId]));
      pollJobStatus(data.id, documentId);
    },
    onError: (error: any) => {
      message.error(error.response?.data?.detail || '摄取启动失败');
    },
  });

  // 批量摄取
  const batchIngestMutation = useMutation({
    mutationFn: (documentIds: string[]) => ingestionService.startBatchIngestion(kbId!, documentIds),
    onSuccess: (results, documentIds) => {
      message.success(`已启动 ${results.success_count} 个文档的摄取任务`);
      if (results.failed_count > 0) {
        message.warning(`${results.failed_count} 个文档摄取启动失败`);
      }
      setProcessingDocs(prev => new Set([...prev, ...documentIds]));
      results.jobs.forEach((job, index) => {
        pollJobStatus(job.id, documentIds[index]);
      });
      setSelectedRowKeys([]);
    },
    onError: (error: any) => {
      message.error(error.response?.data?.detail || '批量摄取启动失败');
    },
  });

  // 轮询任务状态
  const pollJobStatus = useCallback((jobId: string, documentId: string) => {
    const interval = setInterval(async () => {
      try {
        const job = await ingestionService.getJobStatus(jobId);
        if (job.status === IngestionJobStatus.COMPLETED || job.status === IngestionJobStatus.FAILED) {
          clearInterval(interval);
          setProcessingDocs(prev => {
            const newSet = new Set(prev);
            newSet.delete(documentId);
            return newSet;
          });
          if (job.status === IngestionJobStatus.COMPLETED) {
            message.success('文档摄取完成');
            queryClient.invalidateQueries({ queryKey: ['documents', kbId] });
          } else {
            message.error('文档摄取失败');
          }
        }
      } catch (error) {
        clearInterval(interval);
        setProcessingDocs(prev => {
          const newSet = new Set(prev);
          newSet.delete(documentId);
          return newSet;
        });
      }
    }, 2000);
  }, [queryClient, kbId]);

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

  // 批量摄取处理
  const handleBatchIngest = useCallback(() => {
    if (selectedRowKeys.length === 0) {
      message.warning('请选择要摄取的文档');
      return;
    }

    const selectedDocs = documentsData?.documents?.filter(
      (doc: DocumentRecord) => selectedRowKeys.includes(doc.document_id)
    ) || [];

    const ingestableDocIds = selectedDocs
      .filter((doc: DocumentRecord) => {
        const status = getDocumentStatus(doc);
        return status === DocumentStatus.NOT_INGESTED;
      })
      .map((doc: DocumentRecord) => doc.document_id);

    if (ingestableDocIds.length === 0) {
      message.warning('选中的文档中没有可以摄取的文档');
      return;
    }

    if (ingestableDocIds.length < selectedRowKeys.length) {
      const skippedCount = selectedRowKeys.length - ingestableDocIds.length;
      message.info(`将摄取 ${ingestableDocIds.length} 个文档，跳过 ${skippedCount} 个已摄取或正在处理的文档`);
    }

    batchIngestMutation.mutate(ingestableDocIds);
  }, [selectedRowKeys, documentsData, getDocumentStatus, batchIngestMutation]);

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

        switch (status) {
          case DocumentStatus.INGESTING:
            return (
              <Tag icon={<LoadingOutlined />} color="processing">
                摄取中
              </Tag>
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
        const isProcessing = status === DocumentStatus.INGESTING;
        const canIngest = status === DocumentStatus.NOT_INGESTED;
        const canReIngest = status === DocumentStatus.OUTDATED;

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
                onClick={() => ingestMutation.mutate(record.document_id)}
                disabled={ingestMutation.isPending}
              >
                摄取
              </Button>
            )}
            {canReIngest && (
              <Button
                size="small"
                icon={<ReloadOutlined />}
                onClick={() => {
                  // 这里可以调用重新摄取的API
                  ingestMutation.mutate(record.document_id);
                }}
                disabled={ingestMutation.isPending}
              >
                重新摄取
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
            onClick={handleBatchIngest}
            disabled={selectedRowKeys.length === 0 || batchIngestMutation.isPending}
            loading={batchIngestMutation.isPending}
          >
            批量摄取 ({selectedRowKeys.length})
          </Button>
          <Button
            type="primary"
            icon={<UploadOutlined />}
            onClick={() => setUploadModalVisible(true)}
          >
            上传文档
          </Button>
        </Space>
      </div>

      {/* 过时文档提醒 */}
      {outdatedDocuments.length > 0 && (
        <Alert
          message="发现过时文档"
          description={`有 ${outdatedDocuments.length} 个文档的标签可能已过时，建议重新摄取以获得最新的标签信息。`}
          type="warning"
          showIcon
          icon={<ClockCircleOutlined />}
          className="mb-4"
          action={
            <Button
              size="small"
              type="primary"
              onClick={() => {
                const outdatedIds = outdatedDocuments.map((doc: DocumentRecord) => doc.document_id);
                setSelectedRowKeys(outdatedIds);
                message.info(`已选择 ${outdatedIds.length} 个过时文档`);
              }}
            >
              选择过时文档
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
          showSizeChanger: true,
          showQuickJumper: true,
          showTotal: (total) => `共 ${total} 个文档`,
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
            支持单个或批量上传。支持的文件格式：PDF、TXT、MD、DOC、DOCX、PPTX、图片(PNG/JPG)及代码文件
          </p>
        </Upload.Dragger>
      </Modal>
    </div>
  );
};