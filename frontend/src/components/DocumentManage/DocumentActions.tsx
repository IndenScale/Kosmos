import React from 'react';
import { Button, Space, Popconfirm } from 'antd';
import {
  EyeOutlined,
  DownloadOutlined,
  PlayCircleOutlined,
  ReloadOutlined,
  StopOutlined,
  DeleteOutlined,
  TagOutlined,
  TagsOutlined
} from '@ant-design/icons';
import { DocumentStatus } from '../../types/document';

interface DocumentActionsProps {
  documentId: string;
  filename: string;
  status: DocumentStatus;
  canCancel: boolean;
  onPreview: (documentId: string) => void;
  onDownload: (documentId: string, filename: string) => void;
  onIngest: (documentId: string) => void;
  onReIngest: (documentId: string) => void;
  onTag: (documentId: string) => void;
  onReTag: (documentId: string) => void;
  onCancel: (documentId: string) => void;
  onDelete: (documentId: string) => void;
  ingestLoading?: boolean;
  taggingLoading?: boolean;
  isProcessing?: boolean;
  isTagging?: boolean;
}

export const DocumentActions: React.FC<DocumentActionsProps> = ({
  documentId,
  filename,
  status,
  canCancel,
  onPreview,
  onDownload,
  onIngest,
  onReIngest,
  onTag,
  onReTag,
  onCancel,
  onDelete,
  ingestLoading = false,
  taggingLoading = false,
  isProcessing = false,
  isTagging = false
}) => {
  const canIngest = status === DocumentStatus.NOT_INGESTED;
  const canReIngest = status === DocumentStatus.OUTDATED;
  const canTag = status === DocumentStatus.INGESTED_NOT_TAGGED;
  const canReTag = status === DocumentStatus.TAGGING_OUTDATED || status === DocumentStatus.TAGGED;

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
      {canIngest && (
        <Button
          size="small"
          icon={<PlayCircleOutlined />}
          onClick={() => onIngest(documentId)}
          disabled={ingestLoading}
        >
          摄取
        </Button>
      )}
      {canReIngest && (
        <Button
          size="small"
          icon={<ReloadOutlined />}
          onClick={() => onReIngest(documentId)}
          disabled={ingestLoading}
        >
          重新摄取
        </Button>
      )}
      {canTag && (
        <Button
          size="small"
          icon={<TagOutlined />}
          onClick={() => onTag(documentId)}
          disabled={taggingLoading}
          type="default"
        >
          标注
        </Button>
      )}
      {canReTag && (
        <Button
          size="small"
          icon={<TagsOutlined />}
          onClick={() => onReTag(documentId)}
          disabled={taggingLoading}
        >
          重新标注
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
          disabled={isProcessing}
        >
          删除
        </Button>
      </Popconfirm>
    </Space>
  );
};