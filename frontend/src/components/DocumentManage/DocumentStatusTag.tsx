import React from 'react';
import { Tag, Progress, Space } from 'antd';
import {
  LoadingOutlined,
  ExclamationCircleOutlined
} from '@ant-design/icons';
import { DocumentStatus } from '../../types/document';
import { DocumentProcessStatus, IndexStatus } from '../../types/index';

interface DocumentStatusTagProps {
  status: DocumentStatus;
  processStatus?: DocumentProcessStatus;
  progress?: number;
  chunkCount?: number;
  activeJob?: {
    status: string;
    progress?: number;
  };
}

export const DocumentStatusTag: React.FC<DocumentStatusTagProps> = ({
  status,
  processStatus,
  progress,
  chunkCount = 0,
  activeJob
}) => {
  // 如果有活跃任务，优先显示任务状态
  if (activeJob) {
    return (
      <div>
        <Tag icon={<LoadingOutlined />} color="processing">
          {activeJob.status === 'pending' ? '等待索引' : 
           activeJob.status === 'processing' ? '索引中' : 
           activeJob.status === 'completed' ? '索引完成' : 
           activeJob.status === 'failed' ? '索引失败' : '处理中'}
        </Tag>
        {activeJob.progress !== undefined && (
          <Progress
            percent={activeJob.progress}
            size="small"
            style={{ width: 100, marginTop: 4 }}
          />
        )}
      </div>
    );
  }

  switch (status) {
    case DocumentStatus.INGESTING:
      return (
        <div>
          <Tag icon={<LoadingOutlined />} color="processing">
            {processStatus?.parse_status === IndexStatus.PENDING ? '等待解析' : 
             processStatus?.index_status === IndexStatus.PENDING ? '等待索引' : '处理中'}
          </Tag>
          {progress !== undefined && (
            <Progress
              percent={progress}
              size="small"
              style={{ width: 100, marginTop: 4 }}
            />
          )}
          {processStatus?.error_message && (
            <div className="text-red-500 text-xs mt-1">
              {processStatus.error_message}
            </div>
          )}
        </div>
      );
    case DocumentStatus.INGESTED:
      return (
        <Tag color="success">
          已索引 ({chunkCount} 块)
        </Tag>
      );
    case DocumentStatus.OUTDATED:
      return (
        <Space>
          <Tag color="success">
            已索引 ({chunkCount} 块)
          </Tag>
          <Tag icon={<ExclamationCircleOutlined />} color="warning">
            需要重新索引
          </Tag>
        </Space>
      );
    default:
      return (
        <Tag color="default">
          未索引
        </Tag>
      );
  }
};