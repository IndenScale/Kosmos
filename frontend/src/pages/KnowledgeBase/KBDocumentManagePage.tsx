import React, { useState, useMemo } from 'react';
import { Table, Button, Upload, Modal, message, Space, Tag, Popconfirm, Checkbox } from 'antd';
import { UploadOutlined, DownloadOutlined, DeleteOutlined, EyeOutlined, PlayCircleOutlined, LoadingOutlined } from '@ant-design/icons';
import { useParams } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { documentService } from '../../services/documentService';
import { ingestionService } from '../../services/ingestionService';
import type { UploadProps } from 'antd';

interface DocumentRecord {
  document_id: string;
  kb_id: string;
  uploaded_by: string;
  upload_at: string;
  chunk_count?: number;
  document: {
    id: string;
    filename: string;
    file_type: string;
    file_size: number;
    file_path: string;
    created_at: string;
  };
  // 添加用户名字段
  uploader_username?: string;
}

// 选择状态枚举
enum SelectionState {
  NONE = 'none',       // 未选择
  PARTIAL = 'partial', // 部分选择
  PAGE = 'page',       // 本页全选
  ALL = 'all'          // 全部选择
}

export const KBDocumentManagePage: React.FC = () => {
  const { kbId } = useParams<{ kbId: string }>();
  const queryClient = useQueryClient();
  const [uploadModalVisible, setUploadModalVisible] = useState(false);
  const [processingDocs, setProcessingDocs] = useState<Set<string>>(new Set());
  const [selectedRowKeys, setSelectedRowKeys] = useState<string[]>([]);

  // 移除 isDocumentSelectable 函数，所有文档都可以被选中
  // const isDocumentSelectable = (record: DocumentRecord) => {
  //   return (record.chunk_count === 0 || record.chunk_count === undefined) && !processingDocs.has(record.document_id);
  // };

  // 获取文档列表
  const { data: documentsData, isLoading } = useQuery({
    queryKey: ['documents', kbId],
    queryFn: () => documentService.getDocuments(kbId!),
    enabled: !!kbId,
  });

  // 计算当前选择状态
  const selectionState = useMemo(() => {
    if (!documentsData?.documents) return SelectionState.NONE;

    // 所有文档都可以被选中，不再过滤
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

  // 处理选择状态切换
  const handleSelectionChange = () => {
    if (!documentsData?.documents) return;

    // 所有文档都可以被选中
    const allDocumentIds = documentsData.documents.map((doc: DocumentRecord) => doc.document_id);
    const currentPageIds = documentsData.documents.map((doc: DocumentRecord) => doc.document_id);

    switch (selectionState) {
      case SelectionState.NONE:
        // 未选择 -> 本页全选
        setSelectedRowKeys(currentPageIds);
        break;
      case SelectionState.PARTIAL:
        // 部分选择 -> 本页全选
        setSelectedRowKeys([
          ...selectedRowKeys,
          ...currentPageIds.filter((id: string) => !selectedRowKeys.includes(id))
        ]);
        break;
      case SelectionState.PAGE:
        // 本页全选 -> 全部选择
        setSelectedRowKeys(allDocumentIds);
        break;
      case SelectionState.ALL:
        // 全部选择 -> 未选择
        setSelectedRowKeys([]);
        break;
    }
  };

  // 获取选择框的显示文本
  const getSelectionText = () => {
    switch (selectionState) {
      case SelectionState.NONE:
        return '选择';
      case SelectionState.PARTIAL:
        return '部分';
      case SelectionState.PAGE:
        return '本页';
      case SelectionState.ALL:
        return '全部';
    }
  };

  // 批量下载
  const handleBatchDownload = async () => {
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

          // 添加小延迟避免浏览器阻止多个下载
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
  };

  // 处理批量摄取 - 在这里进行摄取条件判断
  const handleBatchIngest = () => {
    if (selectedRowKeys.length === 0) {
      message.warning('请选择要摄取的文档');
      return;
    }

    // 过滤出可以摄取的文档（未摄取且未在处理中）
    const selectedDocs = documentsData?.documents?.filter(
      (doc: DocumentRecord) => selectedRowKeys.includes(doc.document_id)
    ) || [];

    const ingestableDocIds = selectedDocs
      .filter((doc: DocumentRecord) => {
        const isProcessing = processingDocs.has(doc.document_id);
        const isIngested = doc.chunk_count && doc.chunk_count > 0;
        return !isProcessing && !isIngested;
      })
      .map((doc: DocumentRecord) => doc.document_id);

    if (ingestableDocIds.length === 0) {
      message.warning('选中的文档中没有可以摄取的文档（未摄取且未在处理中）');
      return;
    }

    if (ingestableDocIds.length < selectedRowKeys.length) {
      const skippedCount = selectedRowKeys.length - ingestableDocIds.length;
      message.info(`将摄取 ${ingestableDocIds.length} 个文档，跳过 ${skippedCount} 个已摄取或正在处理的文档`);
    }

    batchIngestMutation.mutate(ingestableDocIds);
  };

  // // 获取文档列表
  // const { data: documentsData, isLoading } = useQuery({
  //   queryKey: ['documents', kbId],
  //   queryFn: () => documentService.getDocuments(kbId!),
  //   enabled: !!kbId,
  // });

  // 上传文档
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

  // 删除文档
  const deleteMutation = useMutation({
    mutationFn: (documentId: string) => documentService.deleteDocument(kbId!, documentId),
    onSuccess: (data, documentId) => {
      message.success('文档删除成功');
      queryClient.invalidateQueries({ queryKey: ['documents', kbId] });
      // 清理已删除文档的选择状态
      setSelectedRowKeys(prev => prev.filter(id => id !== documentId));
    },
    onError: (error: any) => {
      message.error(error.response?.data?.detail || '删除失败');
    },
  });

  // 摄取文档
  const ingestMutation = useMutation({
    mutationFn: (documentId: string) => ingestionService.startIngestion(kbId!, documentId),
    onSuccess: (data, documentId) => {
      message.success('摄取任务已启动');
      setProcessingDocs(prev => new Set([...prev, documentId]));
      // 可以启动轮询检查任务状态
      pollJobStatus(data.id, documentId);
    },
    onError: (error: any) => {
      message.error(error.response?.data?.detail || '摄取启动失败');
    },
  });

  // 轮询任务状态
  const pollJobStatus = (jobId: string, documentId: string) => {
    const interval = setInterval(async () => {
      try {
        const job = await ingestionService.getJobStatus(jobId);
        if (job.status === 'completed' || job.status === 'failed') {
          clearInterval(interval);
          setProcessingDocs(prev => {
            const newSet = new Set(prev);
            newSet.delete(documentId);
            return newSet;
          });
          if (job.status === 'completed') {
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
  };

  const handleDownload = (documentId: string, filename: string) => {
    documentService.downloadDocument(kbId!, documentId)
      .then(blob => {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
      })
      .catch(error => {
        message.error('下载失败');
      });
  };

  const uploadProps: UploadProps = {
    multiple: true,
    beforeUpload: (file) => {
      // 允许的 MIME 类型
      const allowedMimeTypes = [
        'application/pdf',
        'text/plain',
        'text/markdown',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document', // .docx
        'application/msword' // .doc
      ];

      // 允许的文件扩展名（用于补充 MIME 类型不准确的情况）
      const allowedExtensions = [
        'pdf',
        'txt',
        'md',
        'docx',
        'doc'
      ];

      // 获取文件扩展名
      const filename = file.name.toLowerCase();
      const fileExtension = filename.slice(((filename.lastIndexOf(".") - 1) >>> 0) + 2);

      // 检查文件类型（MIME 或 扩展名）
      const isValidType = allowedMimeTypes.includes(file.type) || allowedExtensions.includes(fileExtension);

      if (!isValidType) {
        message.error('只支持 PDF、TXT、MD、DOC、DOCX 格式的文件');
        return false;
      }

      const isLt10M = file.size / 1024 / 1024 < 10;
      if (!isLt10M) {
        message.error('文件大小不能超过 10MB');
        return false;
      }

      uploadMutation.mutate(file);
      return false; // 阻止 Ant Design 自动上传
    },
    showUploadList: false,
  };

  // 批量摄取
  const batchIngestMutation = useMutation({
    mutationFn: async (documentIds: string[]) => {
      const promises = documentIds.map(id => ingestionService.startIngestion(kbId!, id));
      return Promise.all(promises);
    },
    onSuccess: (results, documentIds) => {
      message.success(`已启动 ${documentIds.length} 个文档的摄取任务`);
      setProcessingDocs(prev => new Set([...prev, ...documentIds]));
      // 启动轮询检查任务状态
      results.forEach((result, index) => {
        pollJobStatus(result.id, documentIds[index]);
      });
      setSelectedRowKeys([]);
    },
    onError: (error: any) => {
      message.error(error.response?.data?.detail || '批量摄取启动失败');
    },
  });

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
          // 移除 disabled 属性，所有文档都可以被选中
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
      render: (size: number) => `${(size / 1024).toFixed(2)} KB`,
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
      title: '状态',
      key: 'status',
      render: (_: any, record: DocumentRecord) => {
        const isProcessing = processingDocs.has(record.document_id);
        const isIngested = record.chunk_count && record.chunk_count > 0;

        if (isProcessing) {
          return (
            <Tag icon={<LoadingOutlined />} color="processing">
              摄取中
            </Tag>
          );
        } else if (isIngested) {
          return (
            <Tag color="success">
              已摄取 ({record.chunk_count} 块)
            </Tag>
          );
        } else {
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
        const isProcessing = processingDocs.has(record.document_id);
        const isIngested = record.chunk_count && record.chunk_count > 0;

        return (
          <Space>
            <Button
              size="small"
              icon={<EyeOutlined />}
              onClick={() => {
                // 预览功能，可以后续实现
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
            <Button
              size="small"
              icon={isProcessing ? <LoadingOutlined /> : <PlayCircleOutlined />}
              onClick={() => ingestMutation.mutate(record.document_id)}
              disabled={isProcessing || ingestMutation.isPending || !!isIngested}
              className={isProcessing || isIngested ? 'text-gray-400' : ''}
            >
              摄取
            </Button>
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
                className={isProcessing ? 'text-gray-400' : ''}
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

      <Modal
        title="上传文档"
        open={uploadModalVisible}
        onCancel={() => setUploadModalVisible(false)}
        footer={null}
      >
        <Upload.Dragger {...uploadProps} className="mb-4">
          <p className="ant-upload-drag-icon">
            <UploadOutlined />
          </p>
          <p className="ant-upload-text">点击或拖拽文件到此区域上传</p>
          <p className="ant-upload-hint">
            支持 PDF、TXT、MD、DOC、DOCX 格式，文件大小不超过 10MB
          </p>
        </Upload.Dragger>
      </Modal>
    </div>
  );
};