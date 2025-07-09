import React from 'react';
import { Tag, Progress, Space } from 'antd';
import {
  LoadingOutlined,
  ExclamationCircleOutlined,
  TagOutlined,
  TagsOutlined
} from '@ant-design/icons';
import { DocumentStatus } from '../../types/document';
import { IngestionJobStatus } from '../../types/ingestion';
import { DocumentJobStatus } from '../../types/ingestion';

interface DocumentStatusTagProps {
  status: DocumentStatus;
  jobStatus?: DocumentJobStatus;
  progress?: number;
  chunkCount?: number;
}

export const DocumentStatusTag: React.FC<DocumentStatusTagProps> = ({
  status,
  jobStatus,
  progress,
  chunkCount = 0
}) => {
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
          已摄取 ({chunkCount} 块)
        </Tag>
      );
    case DocumentStatus.INGESTED_NOT_TAGGED:
      return (
        <Space>
          <Tag color="success">
            已摄取 ({chunkCount} 块)
          </Tag>
          <Tag icon={<TagOutlined />} color="orange">
            需要标注
          </Tag>
        </Space>
      );
    case DocumentStatus.TAGGING:
      return (
        <div>
          <Tag icon={<LoadingOutlined />} color="processing">
            标注中
          </Tag>
          {progress !== undefined && (
            <Progress
              percent={progress}
              size="small"
              style={{ width: 100, marginTop: 4 }}
            />
          )}
        </div>
      );
    case DocumentStatus.TAGGED:
      return (
        <Tag icon={<TagsOutlined />} color="green">
          已标注 ({chunkCount} 块)
        </Tag>
      );
    case DocumentStatus.TAGGING_OUTDATED:
      return (
        <Space>
          <Tag icon={<TagsOutlined />} color="green">
            已标注 ({chunkCount} 块)
          </Tag>
          <Tag icon={<ExclamationCircleOutlined />} color="gold">
            标注过时
          </Tag>
        </Space>
      );
    case DocumentStatus.OUTDATED:
      return (
        <Space>
          <Tag color="success">
            已摄取 ({chunkCount} 块)
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
};