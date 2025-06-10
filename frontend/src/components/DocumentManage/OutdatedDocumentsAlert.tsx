import React from 'react';
import { Alert, Button } from 'antd';
import { DocumentRecord } from '../../types/document';

interface OutdatedDocumentsAlertProps {
  outdatedDocuments: DocumentRecord[];
  onBatchReIngest: (documentIds: string[]) => void;
  loading?: boolean;
}

export const OutdatedDocumentsAlert: React.FC<OutdatedDocumentsAlertProps> = ({
  outdatedDocuments,
  onBatchReIngest,
  loading = false
}) => {
  if (outdatedDocuments.length === 0) {
    return null;
  }

  const handleBatchReIngest = () => {
    const outdatedIds = outdatedDocuments.map(doc => doc.document_id);
    onBatchReIngest(outdatedIds);
  };

  return (
    <Alert
      message={`检测到 ${outdatedDocuments.length} 个文档的索引可能已过时`}
      description="标签字典已更新，建议重新摄取这些文档以获得最佳搜索效果。"
      type="warning"
      showIcon
      className="mb-4"
      action={
        <Button
          size="small"
          type="primary"
          onClick={handleBatchReIngest}
          loading={loading}
        >
          批量重新摄取
        </Button>
      }
    />
  );
};