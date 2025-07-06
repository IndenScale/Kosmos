import React from 'react';
import { Button, Space, Upload } from 'antd';
import {
  UploadOutlined,
  DownloadOutlined,
  DeleteOutlined,
  PlayCircleOutlined,
  TagOutlined
} from '@ant-design/icons';
import type { UploadProps } from 'antd';

interface DocumentToolbarProps {
  selectedCount: number;
  onBatchDownload: () => void;
  onBatchProcess: () => void;
  onBatchTag: () => void;
  onBatchDelete: () => void;
  uploadProps: UploadProps;
  batchProcessLoading?: boolean;
  batchTagLoading?: boolean;
  batchDeleteLoading?: boolean;
}

export const DocumentToolbar: React.FC<DocumentToolbarProps> = ({
  selectedCount,
  onBatchDownload,
  onBatchProcess,
  onBatchTag,
  onBatchDelete,
  uploadProps,
  batchProcessLoading = false,
  batchTagLoading = false,
  batchDeleteLoading = false
}) => {
  return (
    <div className="mb-4 flex justify-between items-center">
      <h3 className="text-lg font-medium">文档管理</h3>
      <Space>
        <Button
          icon={<DownloadOutlined />}
          onClick={onBatchDownload}
          disabled={selectedCount === 0}
        >
          批量下载 ({selectedCount})
        </Button>
        <Button
          type="primary"
          icon={<PlayCircleOutlined />}
          onClick={onBatchProcess}
          disabled={selectedCount === 0 || batchProcessLoading}
          loading={batchProcessLoading}
        >
          批量摄取 ({selectedCount})
        </Button>
        <Button
          icon={<TagOutlined />}
          onClick={onBatchTag}
          disabled={selectedCount === 0 || batchTagLoading}
          loading={batchTagLoading}
        >
          批量标注 ({selectedCount})
        </Button>
        <Button
          danger
          icon={<DeleteOutlined />}
          onClick={onBatchDelete}
          disabled={selectedCount === 0 || batchDeleteLoading}
          loading={batchDeleteLoading}
        >
          批量删除 ({selectedCount})
        </Button>
        <Upload {...uploadProps}>
          <Button icon={<UploadOutlined />}>上传文档</Button>
        </Upload>
      </Space>
    </div>
  );
};