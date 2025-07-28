import React from 'react';
import { Alert, Button, Space } from 'antd';
import { DocumentRecord, DocumentStatus } from '../../types/document';

interface OutdatedDocumentsAlertProps {
  outdatedDocuments: DocumentRecord[];
  onBatchReIngest: (documentIds: string[]) => void;
  getDocumentStatus: (doc: DocumentRecord) => DocumentStatus;
  loading?: boolean;
}

export const OutdatedDocumentsAlert: React.FC<OutdatedDocumentsAlertProps> = ({
  outdatedDocuments,
  onBatchReIngest,
  getDocumentStatus,
  loading = false
}) => {
  if (outdatedDocuments.length === 0) {
    return null;
  }

  // 过滤过时文档
  const outdatedDocs = outdatedDocuments.filter(doc => 
    getDocumentStatus(doc) === DocumentStatus.OUTDATED
  );

  if (outdatedDocs.length === 0) {
    return null;
  }

  const handleBatchReIndex = () => {
    const outdatedIds = outdatedDocs.map(doc => doc.document_id);
    onBatchReIngest(outdatedIds);
  };

  const message = `检测到 ${outdatedDocs.length} 个文档的索引可能已过时`;
  const description = '标签字典已更新，建议重新索引这些文档以获得最佳搜索效果。';

  return (
    <Alert
      message={message}
      description={description}
      type="warning"
      showIcon
      className="mb-4"
      action={
        <Space>
          <Button
            size="small"
            type="primary"
            onClick={handleBatchReIndex}
            loading={loading}
          >
            批量重新索引 ({outdatedDocs.length})
          </Button>
        </Space>
      }
    />
  );
};