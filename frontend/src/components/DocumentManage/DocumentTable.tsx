import React from 'react';
import { Table, Checkbox } from 'antd';
import type { ColumnsType, TableRowSelection, Key } from 'antd/es/table/interface';
import { DocumentRecord, DocumentStatus, SelectionState } from '../../types/document';
import { DocumentProcessStatus } from '../../types/index';
import { DocumentStatusTag } from './DocumentStatusTag';
import { DocumentActions } from './DocumentActions';
import { getDocumentStatus, getProcessProgress, formatFileSize } from '../../utils/documentUtils';

interface IndexingJob {
  jobId: string;
  documentIds: string[];
  status: string;
  progress: number;
  startTime: Date;
  type: 'single' | 'batch';
}

interface DocumentTableProps {
  documents: DocumentRecord[];
  total: number;
  loading: boolean;
  selectedRowKeys: string[];
  selectionState: SelectionState;
  documentProcessStatuses: Map<string, DocumentProcessStatus>;
  lastTagDirectoryUpdateTime?: string;
  indexStats?: {
    total_fragments: number;
    indexed_fragments: number;
    pending_fragments: number;
    vector_count: number;
    last_index_time?: string;
  };
  activeJobs?: Map<string, IndexingJob>;
  onSelectionChange: (selectedRowKeys: string[]) => void;
  onSelectAll: () => void;
  onSelectNone: () => void;
  onPreview: (documentId: string) => void;
  onDownload: (documentId: string, filename: string) => void;
  onIndex: (documentId: string) => void;
  onReIndex: (documentId: string) => void;
  onCancel: (documentId: string) => void;
  onDelete: (documentId: string) => void;
  indexLoading?: boolean;
}

export const DocumentTable: React.FC<DocumentTableProps> = ({
  documents,
  total,
  loading,
  selectedRowKeys,
  selectionState,
  documentProcessStatuses,
  lastTagDirectoryUpdateTime,
  indexStats,
  activeJobs = new Map(),
  onSelectionChange,
  onSelectAll,
  onSelectNone,
  onPreview,
  onDownload,
  onIndex,
  onReIndex,
  onCancel,
  onDelete,
  indexLoading = false
}) => {
  // 检查文档是否在活跃任务中
  const isDocumentInActiveJob = (documentId: string): IndexingJob | null => {
    for (const job of activeJobs.values()) {
      if (job.documentIds.includes(documentId)) {
        return job;
      }
    }
    return null;
  };

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
    getCheckboxProps: (record: DocumentRecord) => {
      // 如果文档正在索引中，禁用选择
      const activeJob = isDocumentInActiveJob(record.document_id);
      return {
        disabled: !!activeJob
      };
    }
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
      render: (date: string) => date ? new Date(date).toLocaleString() : '-',
    },
    {
      title: '最后索引时间',
      dataIndex: 'last_ingest_time',
      key: 'last_ingest_time',
      render: (date: string) => date ? new Date(date).toLocaleString() : '未索引',
    },
    {
      title: '状态',
      key: 'status',
      render: (_: any, record: DocumentRecord) => {
        const activeJob = isDocumentInActiveJob(record.document_id);
        
        // 如果文档在活跃任务中，显示任务状态
        if (activeJob) {
          const processStatus = documentProcessStatuses.get(record.document_id);
          return (
            <DocumentStatusTag
              status={DocumentStatus.INGESTING}
              processStatus={{
                document_id: record.document_id,
                parse_status: 'completed',
                index_status: 'processing' as any,
                fragment_count: processStatus?.fragment_count || 0,
                indexed_fragment_count: 0,
                last_updated: new Date().toISOString(),
                job_id: activeJob.jobId
              }}
              progress={activeJob.progress}
              chunkCount={processStatus?.indexed_fragment_count || 0}
            />
          );
        }

        // 否则显示正常状态
        const status = getDocumentStatus(record, documentProcessStatuses, lastTagDirectoryUpdateTime, indexStats);
        const processStatus = documentProcessStatuses.get(record.document_id);
        const progress = getProcessProgress(record.document_id, documentProcessStatuses);

        return (
          <DocumentStatusTag
            status={status}
            processStatus={processStatus}
            progress={progress}
            chunkCount={processStatus?.indexed_fragment_count || 0}
          />
        );
      },
    },
    {
      title: '操作',
      key: 'actions',
      render: (_: any, record: DocumentRecord) => {
        const activeJob = isDocumentInActiveJob(record.document_id);
        
        // 如果文档在活跃任务中，显示任务相关的操作
        if (activeJob) {
          return (
            <DocumentActions
              documentId={record.document_id}
              filename={record.document.filename}
              status={DocumentStatus.INGESTING}
              canCancel={true}
              onPreview={onPreview}
              onDownload={onDownload}
              onIndex={onIndex}
              onReIndex={onReIndex}
              onCancel={onCancel}
              onDelete={onDelete}
              indexLoading={true}
              isProcessing={true}
            />
          );
        }

        // 否则显示正常操作
        const status = getDocumentStatus(record, documentProcessStatuses, lastTagDirectoryUpdateTime, indexStats);
        const processStatus = documentProcessStatuses.get(record.document_id);
        const isProcessing = status === DocumentStatus.INGESTING;
        const canCancel = isProcessing && !!processStatus?.job_id;

        return (
          <DocumentActions
            documentId={record.document_id}
            filename={record.document.filename}
            status={status}
            canCancel={canCancel}
            onPreview={onPreview}
            onDownload={onDownload}
            onIndex={onIndex}
            onReIndex={onReIndex}
            onCancel={onCancel}
            onDelete={onDelete}
            indexLoading={indexLoading}
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
