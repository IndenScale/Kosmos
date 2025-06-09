import React, { useState } from 'react';
import { Table, Button, Upload, Modal, message, Space, Tag, Popconfirm } from 'antd';
import { UploadOutlined, DownloadOutlined, DeleteOutlined, EyeOutlined, PlayCircleOutlined, LoadingOutlined } from '@ant-design/icons';
import { useParams } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { documentService } from '../../services/documentService';
import { ingestionService } from '../../services/ingestionService';
import type { UploadProps } from 'antd';

export const KBDocumentManagePage: React.FC = () => {
  const { kbId } = useParams<{ kbId: string }>();
  const queryClient = useQueryClient();
  const [uploadModalVisible, setUploadModalVisible] = useState(false);
  const [processingDocs, setProcessingDocs] = useState<Set<string>>(new Set());

  // 获取文档列表
  const { data: documentsData, isLoading } = useQuery({
    queryKey: ['documents', kbId],
    queryFn: () => documentService.getDocuments(kbId!),
    enabled: !!kbId,
  });

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
    onSuccess: () => {
      message.success('文档删除成功');
      queryClient.invalidateQueries({ queryKey: ['documents', kbId] });
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
      const fileExtension = filename.slice(((filename.lastIndexOf(".") - 1) >>> 0) + 2); // 从文件名中获取扩展名

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

  const columns = [
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
      dataIndex: 'uploaded_by',
      key: 'uploaded_by',
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
      render: (_: any, record: any) => {
        const isProcessing = processingDocs.has(record.document_id);
        return isProcessing ? (
          <Tag icon={<LoadingOutlined />} color="processing">
            摄取中
          </Tag>
        ) : (
          <Tag color="default">就绪</Tag>
        );
      },
    },
    {
      title: '操作',
      key: 'actions',
      render: (_: any, record: any) => {
        const isProcessing = processingDocs.has(record.document_id);
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
              disabled={isProcessing || ingestMutation.isPending}
              className={isProcessing ? 'text-gray-400' : ''}
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
        <Button
          type="primary"
          icon={<UploadOutlined />}
          onClick={() => setUploadModalVisible(true)}
        >
          上传文档
        </Button>
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