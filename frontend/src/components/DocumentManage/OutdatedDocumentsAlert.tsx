import React from 'react';
import { Alert, Button, Space } from 'antd';
import { DocumentRecord, DocumentStatus } from '../../types/document';

interface OutdatedDocumentsAlertProps {
  outdatedDocuments: DocumentRecord[];
  onBatchReIngest: (documentIds: string[]) => void;
  onBatchReTag: (documentIds: string[]) => void;
  getDocumentStatus: (doc: DocumentRecord) => DocumentStatus;
  loading?: boolean;
  taggingLoading?: boolean;
}

export const OutdatedDocumentsAlert: React.FC<OutdatedDocumentsAlertProps> = ({
  outdatedDocuments,
  onBatchReIngest,
  onBatchReTag,
  getDocumentStatus,
  loading = false,
  taggingLoading = false
}) => {
  if (outdatedDocuments.length === 0) {
    return null;
  }

  // 分类过时文档
  const ingestOutdatedDocs = outdatedDocuments.filter(doc => 
    getDocumentStatus(doc) === DocumentStatus.OUTDATED
  );
  const tagOutdatedDocs = outdatedDocuments.filter(doc => 
    getDocumentStatus(doc) === DocumentStatus.TAGGING_OUTDATED
  );

  const handleBatchReIngest = () => {
    const outdatedIds = ingestOutdatedDocs.map(doc => doc.document_id);
    onBatchReIngest(outdatedIds);
  };

  const handleBatchReTag = () => {
    const outdatedIds = tagOutdatedDocs.map(doc => doc.document_id);
    onBatchReTag(outdatedIds);
  };

  // 构建消息文本
  let message = '';
  let description = '';
  
  if (ingestOutdatedDocs.length > 0 && tagOutdatedDocs.length > 0) {
    message = `检测到 ${ingestOutdatedDocs.length} 个文档摄取过时，${tagOutdatedDocs.length} 个文档标注过时`;
    description = '标签字典已更新，建议重新摄取或重新标注这些文档以获得最佳搜索效果。';
  } else if (ingestOutdatedDocs.length > 0) {
    message = `检测到 ${ingestOutdatedDocs.length} 个文档的摄取可能已过时`;
    description = '标签字典已更新，建议重新摄取这些文档以获得最佳搜索效果。';
  } else if (tagOutdatedDocs.length > 0) {
    message = `检测到 ${tagOutdatedDocs.length} 个文档的标注可能已过时`;
    description = '标签字典已更新，建议重新标注这些文档以获得最佳搜索效果。';
  }

  return (
    <Alert
      message={message}
      description={description}
      type="warning"
      showIcon
      className="mb-4"
      action={
        <Space>
          {ingestOutdatedDocs.length > 0 && (
            <Button
              size="small"
              type="primary"
              onClick={handleBatchReIngest}
              loading={loading}
            >
              批量重新摄取 ({ingestOutdatedDocs.length})
            </Button>
          )}
          {tagOutdatedDocs.length > 0 && (
            <Button
              size="small"
              onClick={handleBatchReTag}
              loading={taggingLoading}
            >
              批量重新标注 ({tagOutdatedDocs.length})
            </Button>
          )}
        </Space>
      }
    />
  );
};