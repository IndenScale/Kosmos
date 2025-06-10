import React from 'react';
import { Table, Checkbox } from 'antd';
import type { ColumnsType, TableRowSelection, Key } from 'antd/es/table/interface';
import { DocumentRecord, DocumentStatus, SelectionState } from '../../types/document';
import { DocumentJobStatus } from '../../types/ingestion';
import { DocumentStatusTag } from './DocumentStatusTag';
import { DocumentActions } from './DocumentActions';
import { getDocumentStatus, getJobProgress, formatFileSize } from '../../utils/documentUtils';

interface DocumentTableProps {
  documents: DocumentRecord[];
  total: number;
  loading: boolean;
  selectedRowKeys: string[];
  selectionState: SelectionState;
  documentJobStatuses: Map<string, DocumentJobStatus>;
  lastTagDirectoryUpdateTime?: string;
  onSelectionChange: (selectedRowKeys: string[]) => void;
  onSelectAll: () => void;
  onSelectNone: () => void;
  onPreview: (documentId: string) => void;
  onDownload: (documentId: string, filename: string) => void;
  onIngest: (documentId: string) => void;
  onReIngest: (documentId: string) => void;
  onCancel: (documentId: string) => void;
  onDelete: (documentId: string) => void;
  ingestLoading?: boolean;
}

export const DocumentTable: React.FC<DocumentTableProps> = ({
  documents,
  total,
  loading,
  selectedRowKeys,
  selectionState,
  documentJobStatuses,
  lastTagDirectoryUpdateTime,
  onSelectionChange,
  onSelectAll,
  onSelectNone,
  onPreview,
  onDownload,
  onIngest,
  onReIngest,
  onCancel,
  onDelete,
  ingestLoading = false
}) => {
  const rowSelection: TableRowSelection<DocumentRecord> = {
    selectedRowKeys,
    onChange: (selectedRowKeys: Key[]) => {
      // 转换 Key[] 为 string[]
      onSelectionChange(selectedRowKeys.map(key => String(key)));
    },
    columnTitle: (
      <Checkbox
        indeterminate={selectionState === SelectionState.PARTIAL}
        checked={selectionState === SelectionState.ALL}
        onChange={(e) => {
          if (e.target.checked) {
            onSelectAll();
          } else {
            onSelectNone();
          }
        }}
      />
    ),
  };

  const columns: ColumnsType<DocumentRecord> = [
    {
      title: '文件名',
      dataIndex: ['document', 'filename'],
      key: 'filename',
      ellipsis: true,
    },
    {
      title: '文件大小',
      dataIndex: ['document', 'file_size'],
      key: 'file_size',
      render: (size: number) => formatFileSize(size),
    },
    {
      title: '上传者',
      dataIndex: 'uploader_username',
      key: 'uploader_username',
      render: (username: string, record: DocumentRecord) =>
        username || record.uploaded_by || '未知用户',
    },
    {
      title: '上传时间',
      dataIndex: 'upload_at',
      key: 'upload_at',
      render: (date: string) => new Date(date).toLocaleString(),
    },
    {
      title: '最后摄入时间',
      dataIndex: 'last_ingest_time',
      key: 'last_ingest_time',
      render: (date: string) => date ? new Date(date).toLocaleString() : '未摄入',
    },
    {
      title: '状态',
      key: 'status',
      render: (_: any, record: DocumentRecord) => {
        const status = getDocumentStatus(record, documentJobStatuses, lastTagDirectoryUpdateTime);
        const jobStatus = documentJobStatuses.get(record.document_id);
        const progress = getJobProgress(record.document_id, documentJobStatuses);

        return (
          <DocumentStatusTag
            status={status}
            jobStatus={jobStatus}
            progress={progress}
            chunkCount={record.chunk_count}
          />
        );
      },
    },
    {
      title: '操作',
      key: 'actions',
      render: (_: any, record: DocumentRecord) => {
        const status = getDocumentStatus(record, documentJobStatuses, lastTagDirectoryUpdateTime);
        const jobStatus = documentJobStatuses.get(record.document_id);
        const isProcessing = status === DocumentStatus.INGESTING;
        const canCancel = isProcessing && !!jobStatus?.job_id;

        return (
          <DocumentActions
            documentId={record.document_id}
            filename={record.document.filename}
            status={status}
            canCancel={canCancel}
            onPreview={onPreview}
            onDownload={onDownload}
            onIngest={onIngest}
            onReIngest={onReIngest}
            onCancel={onCancel}
            onDelete={onDelete}
            ingestLoading={ingestLoading}
            isProcessing={isProcessing}
          />
        );
      },
    },
  ];

  return (
    <Table
      columns={columns}
      dataSource={documents}
      rowKey="document_id"
      loading={loading}
      rowSelection={rowSelection}
      pagination={{
        total,
        pageSize: 20,
        showSizeChanger: true,
        showQuickJumper: true,
        showTotal: (total, range) => `第 ${range[0]}-${range[1]} 条，共 ${total} 条`,
      }}
    />
  );
};
