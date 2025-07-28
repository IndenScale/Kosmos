import React from 'react';
import { Button, Space, Upload } from 'antd';
import {
  UploadOutlined,
  DownloadOutlined,
  DeleteOutlined,
  PlayCircleOutlined,
  FileTextOutlined
} from '@ant-design/icons';
import type { UploadProps } from 'antd';

interface DocumentToolbarProps {
  selectedCount: number;
  onBatchDownload: () => void;
  onBatchProcess: () => void;
  onBatchParse: () => void;
  onBatchDelete: () => void;
  uploadProps: UploadProps;
  batchProcessLoading?: boolean;
  batchParseLoading?: boolean;
  batchDeleteLoading?: boolean;
}

export const DocumentToolbar: React.FC<DocumentToolbarProps> = ({
  selectedCount,
  onBatchDownload,
  onBatchProcess,
  onBatchParse,
  onBatchDelete,
  uploadProps,
  batchProcessLoading = false,
  batchParseLoading = false,
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
          icon={<FileTextOutlined />}
          onClick={onBatchParse}
          disabled={selectedCount === 0 || batchParseLoading}
          loading={batchParseLoading}
        >
          批量解析 ({selectedCount})
        </Button>
        <Button
          type="primary"
          icon={<PlayCircleOutlined />}
          onClick={onBatchProcess}
          disabled={selectedCount === 0 || batchProcessLoading}
          loading={batchProcessLoading}
        >
          批量索引 ({selectedCount})
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