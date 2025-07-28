import React from 'react';
import { Button, Space, Popconfirm } from 'antd';
import {
  EyeOutlined,
  DownloadOutlined,
  PlayCircleOutlined,
  ReloadOutlined,
  StopOutlined,
  DeleteOutlined
} from '@ant-design/icons';
import { DocumentStatus } from '../../types/document';

interface DocumentActionsProps {
  documentId: string;
  filename: string;
  status: DocumentStatus;
  canCancel: boolean;
  onPreview: (documentId: string) => void;
  onDownload: (documentId: string, filename: string) => void;
  onIndex: (documentId: string) => void;
  onReIndex: (documentId: string) => void;
  onCancel: (documentId: string) => void;
  onDelete: (documentId: string) => void;
  indexLoading?: boolean;
  isProcessing?: boolean;
  hasActiveJob?: boolean; // 是否有活跃的索引任务
}

export const DocumentActions: React.FC<DocumentActionsProps> = ({
  documentId,
  filename,
  status,
  canCancel,
  onPreview,
  onDownload,
  onIndex,
  onReIndex,
  onCancel,
  onDelete,
  indexLoading = false,
  isProcessing = false,
  hasActiveJob = false
}) => {
  const canIndex = status === DocumentStatus.NOT_INGESTED;
  const canReIndex = status === DocumentStatus.OUTDATED;

  return (
    <Space>
      <Button
        size="small"
        icon={<EyeOutlined />}
        onClick={() => onPreview(documentId)}
      >
        预览
      </Button>
      <Button
        size="small"
        icon={<DownloadOutlined />}
        onClick={() => onDownload(documentId, filename)}
      >
        下载
      </Button>
      {canIndex && (
        <Button
          size="small"
          icon={<PlayCircleOutlined />}
          onClick={() => onIndex(documentId)}
          disabled={indexLoading || hasActiveJob}
        >
          索引
        </Button>
      )}
      {canReIndex && (
        <Button
          size="small"
          icon={<ReloadOutlined />}
          onClick={() => onReIndex(documentId)}
          disabled={indexLoading || hasActiveJob}
        >
          重新索引
        </Button>
      )}
      {canCancel && (
        <Button
          size="small"
          icon={<StopOutlined />}
          onClick={() => onCancel(documentId)}
          danger
        >
          取消
        </Button>
      )}
      <Popconfirm
        title="确定要删除这个文档吗？"
        onConfirm={() => onDelete(documentId)}
        okText="确定"
        cancelText="取消"
      >
        <Button
          size="small"
          danger
          icon={<DeleteOutlined />}
          disabled={isProcessing || hasActiveJob}
        >
          删除
        </Button>
      </Popconfirm>
    </Space>
  );
};