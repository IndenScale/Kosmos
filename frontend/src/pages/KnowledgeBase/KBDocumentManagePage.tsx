import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { message, Modal, notification, Alert, Progress, Tag } from 'antd';
import { useParams } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import type { UploadProps } from 'antd';
import { ExclamationCircleOutlined } from '@ant-design/icons';

// 导入类型定义
import {
  DocumentRecord,
  SelectionState,
  DocumentStatus,
  BatchAction
} from '../../types/document';
import { DocumentProcessStatus, IndexStatus } from '../../types/index';
import { KBDetail } from '../../types/knowledgeBase';

// 导入服务
import { documentService } from '../../services/documentService';
import { indexService, JobResponse } from '../../services/indexService';
import { parserService } from '../../services/parserService';
import { KnowledgeBaseService } from '../../services/KnowledgeBase';

// 导入组件
import { DocumentToolbar } from '../../components/DocumentManage/DocumentToolbar';
import { OutdatedDocumentsAlert } from '../../components/DocumentManage/OutdatedDocumentsAlert';
import { DocumentTable } from '../../components/DocumentManage/DocumentTable';
import { UploadModal } from '../../components/DocumentManage/UploadModal';
import { DocumentPreviewModal } from '../../components/DocumentManage/DocumentPreviewModal';

// 导入工具函数
import { getDocumentStatus, isDocumentOutdated } from '../../utils/documentUtils';

interface IndexingJob {
  jobId: string;
  documentIds: string[];
  status: string;
  progress: number;
  startTime: Date;
  type: 'single' | 'batch';
}

export const KBDocumentManagePage: React.FC = () => {
  const { kbId } = useParams<{ kbId: string }>();
  const queryClient = useQueryClient();

  // 状态管理
  const [uploadModalVisible, setUploadModalVisible] = useState(false);
  const [selectedRowKeys, setSelectedRowKeys] = useState<string[]>([]);
  const [documentProcessStatuses, setDocumentProcessStatuses] = useState<Map<string, DocumentProcessStatus>>(new Map());
  const [previewModalVisible, setPreviewModalVisible] = useState(false);
  const [previewDocument, setPreviewDocument] = useState<DocumentRecord | null>(null);
  
  // 索引任务状态管理
  const [activeJobs, setActiveJobs] = useState<Map<string, IndexingJob>>(new Map());
  const [jobPollingIntervals, setJobPollingIntervals] = useState<Map<string, NodeJS.Timeout>>(new Map());
  const [notifiedJobs, setNotifiedJobs] = useState<Set<string>>(new Set()); // 跟踪已通知的任务

  // 获取知识库详情
  const { data: kbDetail } = useQuery({
    queryKey: ['knowledgeBase', kbId],
    queryFn: () => KnowledgeBaseService.getKBDetail(kbId!),
    enabled: !!kbId,
  });

  // 获取文档列表
  const { data: documentsData, isLoading } = useQuery({
    queryKey: ['documents', kbId],
    queryFn: () => documentService.getDocuments(kbId!),
    enabled: !!kbId,
  });

  // 获取文档处理状态
  const { data: processStatuses } = useQuery({
    queryKey: ['documentProcessStatuses', kbId],
    queryFn: () => indexService.getKBDocumentStatuses(kbId!),
    enabled: !!kbId,
    refetchInterval: 2000,
    refetchIntervalInBackground: true,
  });

  // 获取索引统计信息
  const { data: indexStats } = useQuery({
    queryKey: ['indexStats', kbId],
    queryFn: () => indexService.getIndexStats(kbId!),
    enabled: !!kbId,
    refetchInterval: 5000,
    refetchIntervalInBackground: true,
  });

  // 更新文档处理状态映射
  useEffect(() => {
    if (processStatuses) {
      const statusMap = new Map<string, DocumentProcessStatus>();
      processStatuses.forEach(status => {
        statusMap.set(status.document_id, status);
      });
      setDocumentProcessStatuses(statusMap);
    }
  }, [processStatuses]);

  // 清理轮询定时器
  const clearJobPolling = useCallback((jobId: string) => {
    const interval = jobPollingIntervals.get(jobId);
    if (interval) {
      clearInterval(interval);
      setJobPollingIntervals(prev => {
        const newMap = new Map(prev);
        newMap.delete(jobId);
        return newMap;
      });
    }
  }, [jobPollingIntervals]);

  // 开始轮询任务状态
  const startJobPolling = useCallback((job: IndexingJob) => {
    // 清除已存在的轮询
    clearJobPolling(job.jobId);
    
    const interval = setInterval(async () => {
      try {
        const jobStatus = await indexService.getJobStatus(job.jobId);
        
        // 更新任务状态
        setActiveJobs(prev => {
          const newMap = new Map(prev);
          const existingJob = newMap.get(job.jobId);
          if (existingJob) {
            newMap.set(job.jobId, {
              ...existingJob,
              status: jobStatus.status,
              progress: jobStatus.progress_percentage
            });
          }
          return newMap;
        });

        // 如果任务完成，停止轮询并刷新数据
        if (jobStatus.status === 'completed' || jobStatus.status === 'failed' || jobStatus.status === 'cancelled') {
          clearJobPolling(job.jobId);
          
          // 移除活跃任务
          setActiveJobs(prev => {
            const newMap = new Map(prev);
            newMap.delete(job.jobId);
            return newMap;
          });

          // 清理通知状态（延迟清理，避免重复通知）
          setTimeout(() => {
            setNotifiedJobs(prev => {
              const newSet = new Set(prev);
              newSet.delete(job.jobId);
              return newSet;
            });
          }, 10000); // 10秒后清理通知状态

          // 显示完成通知（只在首次完成时显示）
          if (jobStatus.status === 'completed' && !notifiedJobs.has(job.jobId)) {
            setNotifiedJobs(prev => new Set(prev).add(job.jobId));
            notification.success({
              message: '索引完成',
              description: job.type === 'single' 
                ? '文档索引已成功完成' 
                : `批量索引已完成，共处理 ${job.documentIds.length} 个文档`,
              duration: 4.5,
            });
          } else if (jobStatus.status === 'failed' && !notifiedJobs.has(job.jobId)) {
            setNotifiedJobs(prev => new Set(prev).add(job.jobId));
            notification.error({
              message: '索引失败',
              description: jobStatus.error_message || '索引过程中发生错误',
              duration: 4.5,
            });
          }

          // 刷新文档列表和统计
          queryClient.invalidateQueries({ queryKey: ['documents', kbId] });
          queryClient.invalidateQueries({ queryKey: ['documentProcessStatuses', kbId] });
        }
      } catch (error) {
          console.error('轮询任务状态失败:', error);
          clearJobPolling(job.jobId);
          setActiveJobs(prev => {
            const newMap = new Map(prev);
            newMap.delete(job.jobId);
            return newMap;
          });
          // 清理通知状态
          setNotifiedJobs(prev => {
            const newSet = new Set(prev);
            newSet.delete(job.jobId);
            return newSet;
          });
        }
    }, 5000); // 5秒轮询间隔

    setJobPollingIntervals(prev => {
      const newMap = new Map(prev);
      newMap.set(job.jobId, interval);
      return newMap;
    });
  }, [clearJobPolling, queryClient, kbId, notifiedJobs]);

  // 恢复正在运行任务的轮询
  useEffect(() => {
    const restoreRunningJobs = async () => {
      if (!kbId) return;
      
      try {
        const runningJobs = await indexService.getRunningJobs(kbId);
        
        for (const job of runningJobs) {
          // 确定任务类型和文档ID
          let documentIds: string[] = [];
          let jobType: 'single' | 'batch' = 'single';
          
          // 从任务配置中提取文档ID
          if (job.config?.document_ids) {
            documentIds = job.config.document_ids;
            jobType = documentIds.length > 1 ? 'batch' : 'single';
          } else if (job.config?.document_id) {
            documentIds = [job.config.document_id];
            jobType = 'single';
          }
          
          // 如果找到了文档ID，创建IndexingJob并开始轮询
            if (documentIds.length > 0) {
              const indexingJob: IndexingJob = {
                jobId: job.id,
                documentIds,
                status: job.status,
                progress: job.progress_percentage,
                startTime: new Date(job.started_at || job.created_at),
                type: jobType
              };
              
              setActiveJobs(prev => new Map(prev).set(job.id, indexingJob));
              
              // 如果任务已经完成，标记为已通知，避免重复通知
              if (job.status === 'completed' || job.status === 'failed') {
                setNotifiedJobs(prev => new Set(prev).add(job.id));
              }
              
              startJobPolling(indexingJob);
            }
        }
      } catch (error) {
        console.error('恢复正在运行任务失败:', error);
      }
    };
    
    restoreRunningJobs();
  }, [kbId, startJobPolling]);

  // 组件卸载时清理所有轮询
  useEffect(() => {
    return () => {
      jobPollingIntervals.forEach(interval => clearInterval(interval));
    };
  }, [jobPollingIntervals]);

  // 计算过时文档
  const outdatedDocuments = useMemo(() => {
    if (!documentsData?.documents || !kbDetail?.last_tag_directory_update_time) {
      return [];
    }
    return documentsData.documents.filter((doc: DocumentRecord) => {
      const status = getDocumentStatus(doc, documentProcessStatuses, kbDetail.last_tag_directory_update_time, indexStats);
      return status === DocumentStatus.OUTDATED;
    });
  }, [documentsData, kbDetail, documentProcessStatuses, indexStats]);

  // 计算选择状态
  const selectionState = useMemo(() => {
    if (!documentsData?.documents) return SelectionState.NONE;

    const allDocumentIds = documentsData.documents.map((doc: DocumentRecord) => doc.document_id);
    const currentPageIds = documentsData.documents.map((doc: DocumentRecord) => doc.document_id);

    if (selectedRowKeys.length === 0) {
      return SelectionState.NONE;
    } else if (selectedRowKeys.length === allDocumentIds.length && allDocumentIds.length > 0) {
      return SelectionState.ALL;
    } else if (
      currentPageIds.length > 0 &&
      currentPageIds.every((id: string) => selectedRowKeys.includes(id))
    ) {
      return SelectionState.PAGE;
    } else {
      return SelectionState.PARTIAL;
    }
  }, [selectedRowKeys, documentsData]);

  // Mutations
  const deleteMutation = useMutation({
    mutationFn: (documentId: string) => documentService.deleteDocument(kbId!, documentId),
    onSuccess: () => {
      message.success('文档删除成功');
      queryClient.invalidateQueries({ queryKey: ['documents', kbId] });
    },
    onError: (error: any) => {
      if (error.code === 'ECONNABORTED' && error.message.includes('timeout')) {
        message.warning('删除请求超时，请刷新页面确认删除结果');
        setTimeout(() => {
          queryClient.invalidateQueries({ queryKey: ['documents', kbId] });
        }, 2000);
      } else {
        message.error(`删除失败: ${error.message}`);
      }
    }
  });

  // 单文档索引
  const singleIndexMutation = useMutation({
    mutationFn: async ({ documentId, forceRegenerate }: { documentId: string; forceRegenerate?: boolean }) => {
      return await indexService.indexDocument(documentId, { force_regenerate: forceRegenerate });
    },
    onSuccess: (job: JobResponse, { documentId }) => {
      const indexingJob: IndexingJob = {
        jobId: job.id,
        documentIds: [documentId],
        status: job.status,
        progress: job.progress_percentage,
        startTime: new Date(),
        type: 'single'
      };
      
      setActiveJobs(prev => new Map(prev).set(job.id, indexingJob));
      startJobPolling(indexingJob);
      
      message.success('索引任务已启动');
    },
    onError: (error: any) => {
      message.error(`启动索引失败: ${error.message}`);
    }
  });

  // 批量索引
  const batchIndexMutation = useMutation({
    mutationFn: async ({ documentIds, forceRegenerate }: { documentIds: string[]; forceRegenerate?: boolean }) => {
      return await indexService.indexDocuments(documentIds, { force_regenerate: forceRegenerate });
    },
    onSuccess: (job: JobResponse, { documentIds }) => {
      const indexingJob: IndexingJob = {
        jobId: job.id,
        documentIds,
        status: job.status,
        progress: job.progress_percentage,
        startTime: new Date(),
        type: 'batch'
      };
      
      setActiveJobs(prev => new Map(prev).set(job.id, indexingJob));
      startJobPolling(indexingJob);
      
      message.success(`批量索引任务已启动，共 ${documentIds.length} 个文档`);
      setSelectedRowKeys([]);
    },
    onError: (error: any) => {
      message.error(`启动批量索引失败: ${error.message}`);
    }
  });

  // 批量解析
  const batchParseMutation = useMutation({
    mutationFn: async ({ documentIds, forceReparse }: { documentIds: string[]; forceReparse?: boolean }) => {
      return await parserService.batchParseDocuments(kbId!, { 
        document_ids: documentIds, 
        force_reparse: forceReparse 
      });
    },
    onSuccess: (job: JobResponse, { documentIds }) => {
      const parseJob: IndexingJob = {
        jobId: job.id,
        documentIds,
        status: job.status,
        progress: job.progress_percentage,
        startTime: new Date(),
        type: 'batch'
      };
      
      setActiveJobs(prev => new Map(prev).set(job.id, parseJob));
      startJobPolling(parseJob);
      
      message.success(`批量解析任务已启动，共 ${documentIds.length} 个文档`);
      setSelectedRowKeys([]);
    },
    onError: (error: any) => {
      message.error(`启动批量解析失败: ${error.message}`);
    }
  });

  const batchDeleteMutation = useMutation({
    mutationFn: (documentIds: string[]) => documentService.deleteDocuments(kbId!, documentIds),
    onSuccess: (results) => {
      const successCount = results.filter(result => result.success).length;
      const failedCount = results.length - successCount;

      if (successCount > 0) {
        message.success(`成功删除 ${successCount} 个文档`);
      }
      if (failedCount > 0) {
        message.error(`${failedCount} 个文档删除失败`);
      }

      queryClient.invalidateQueries({ queryKey: ['documents', kbId] });
      setSelectedRowKeys([]);
    },
    onError: (error: any) => {
      message.error(error.response?.data?.detail || '批量删除失败');
    },
  });

  // 事件处理函数
  const handleSelectionChange = useCallback((newSelectedRowKeys: string[]) => {
    setSelectedRowKeys(newSelectedRowKeys);
  }, []);

  const handleSelectAll = useCallback(() => {
    if (documentsData?.documents) {
      const allIds = documentsData.documents.map((doc: DocumentRecord) => doc.document_id);
      setSelectedRowKeys(allIds);
    }
  }, [documentsData]);

  const handleSelectNone = useCallback(() => {
    setSelectedRowKeys([]);
  }, []);

  // 检查并处理索引覆盖
  const handleIndexWithOverrideCheck = async (documentIds: string[], forceRegenerate: boolean = false) => {
    // 如果已经是强制重新索引，直接执行
    if (forceRegenerate) {
      if (documentIds.length === 1) {
        singleIndexMutation.mutate({ documentId: documentIds[0], forceRegenerate: true });
      } else {
        batchIndexMutation.mutate({ documentIds, forceRegenerate: true });
      }
      return;
    }

    // 无论什么情况，都询问用户是否覆盖现有索引
    const selectedDocs = documentsData?.documents?.filter(
      (doc: DocumentRecord) => documentIds.includes(doc.document_id)
    ) || [];

    Modal.confirm({
      title: '索引确认',
      icon: <ExclamationCircleOutlined />,
      content: (
        <div>
          <p>即将对以下 {documentIds.length} 个文档进行索引：</p>
          <ul style={{ maxHeight: '200px', overflowY: 'auto' }}>
            {selectedDocs.slice(0, 10).map(doc => (
              <li key={doc.document_id}>{doc.document?.filename || doc.document_id}</li>
            ))}
            {selectedDocs.length > 10 && <li>...还有 {selectedDocs.length - 10} 个文档</li>}
          </ul>
          <p><strong>请选择索引方式：</strong></p>
          <p>• <strong>覆盖现有索引</strong>：删除现有索引并重新创建（推荐）</p>
          <p>• <strong>跳过已索引</strong>：仅对没有索引的文档进行索引</p>
        </div>
      ),
      okText: '覆盖现有索引',
      cancelText: '跳过已索引',
      onOk: () => {
        // 覆盖现有索引 - 强制重新索引所有文档
        if (documentIds.length === 1) {
          singleIndexMutation.mutate({ documentId: documentIds[0], forceRegenerate: true });
        } else {
          batchIndexMutation.mutate({ documentIds, forceRegenerate: true });
        }
        message.info(`开始覆盖索引 ${documentIds.length} 个文档`);
      },
      onCancel: () => {
        // 跳过已索引 - 仅索引没有索引的文档
        if (documentIds.length === 1) {
          singleIndexMutation.mutate({ documentId: documentIds[0], forceRegenerate: false });
        } else {
          batchIndexMutation.mutate({ documentIds, forceRegenerate: false });
        }
        message.info(`开始索引 ${documentIds.length} 个文档（跳过已索引）`);
      }
    });
  };

  const handleBatchProcess = useCallback(() => {
    if (selectedRowKeys.length === 0) {
      message.warning('请选择要处理的文档');
      return;
    }
    // 批量索引时也检查是否需要强制重新索引
    handleIndexWithOverrideCheck(selectedRowKeys, false);
  }, [selectedRowKeys]);

  const handleBatchDelete = useCallback(() => {
    if (selectedRowKeys.length === 0) {
      message.warning('请选择要删除的文档');
      return;
    }

    Modal.confirm({
      title: '确认批量删除',
      content: `确定要删除选中的 ${selectedRowKeys.length} 个文档吗？此操作不可撤销。`,
      okText: '确定删除',
      okType: 'danger',
      cancelText: '取消',
      onOk: () => {
        batchDeleteMutation.mutate(selectedRowKeys);
      },
    });
  }, [selectedRowKeys, batchDeleteMutation]);

  const handleBatchDownload = useCallback(async () => {
    if (selectedRowKeys.length === 0) {
      message.warning('请选择要下载的文档');
      return;
    }

    const selectedDocs = documentsData?.documents?.filter(
      (doc: DocumentRecord) => selectedRowKeys.includes(doc.document_id)
    ) || [];

    try {
      message.loading('正在准备下载...', 0);

      for (const doc of selectedDocs) {
        try {
          const blob = await documentService.downloadDocument(kbId!, doc.document_id);
          const url = window.URL.createObjectURL(blob);
          const a = document.createElement('a');
          a.href = url;
          a.download = doc.document.filename;
          document.body.appendChild(a);
          a.click();
          window.URL.revokeObjectURL(url);
          document.body.removeChild(a);

          await new Promise(resolve => setTimeout(resolve, 100));
        } catch (error) {
          console.error(`下载文档 ${doc.document.filename} 失败:`, error);
          message.error(`下载文档 ${doc.document.filename} 失败`);
        }
      }

      message.destroy();
      message.success(`已开始下载 ${selectedDocs.length} 个文档`);
    } catch (error) {
      message.destroy();
      message.error('批量下载失败');
    }
  }, [selectedRowKeys, documentsData, kbId]);

  const handleBatchParse = useCallback(() => {
    if (selectedRowKeys.length === 0) {
      message.warning('请选择要解析的文档');
      return;
    }
    handleParseWithOverrideCheck(selectedRowKeys, false);
  }, [selectedRowKeys]);

  const handleParseWithOverrideCheck = useCallback((documentIds: string[], forceReparse = false) => {
    if (!forceReparse) {
      // 检查是否有已解析的文档
      const selectedDocs = documentsData?.documents?.filter(
        (doc: DocumentRecord) => documentIds.includes(doc.document_id)
      ) || [];
      
      const parsedDocs = selectedDocs.filter(doc => {
        const processStatus = documentProcessStatuses.get(doc.document_id);
        return processStatus && processStatus.fragment_count > 0;
      });
      
      if (parsedDocs.length > 0) {
        Modal.confirm({
          title: '检测到已解析文档',
          content: `选中的文档中有 ${parsedDocs.length} 个已经解析过，是否要重新解析？`,
          okText: '重新解析',
          cancelText: '跳过已解析',
          onOk: () => {
            batchParseMutation.mutate({ documentIds, forceReparse: true });
          },
          onCancel: () => {
            const unparsedDocIds = selectedDocs
              .filter(doc => {
                const processStatus = documentProcessStatuses.get(doc.document_id);
                return !processStatus || processStatus.fragment_count === 0;
              })
              .map(doc => doc.document_id);
            
            if (unparsedDocIds.length > 0) {
              batchParseMutation.mutate({ documentIds: unparsedDocIds, forceReparse: false });
            } else {
              message.info('所有选中文档都已解析，无需重复解析');
            }
          },
        });
        return;
      }
    }
    
    batchParseMutation.mutate({ documentIds, forceReparse });
  }, [documentsData, documentProcessStatuses, batchParseMutation]);

  const handlePreview = (documentId: string) => {
    const document = documentsData?.documents?.find(doc => doc.document_id === documentId);
    if (document) {
      setPreviewDocument(document);
      setPreviewModalVisible(true);
    } else {
      message.error('文档信息不存在');
    }
  };

  const handleDownload = useCallback(async (documentId: string, filename: string) => {
    try {
      const blob = await documentService.downloadDocument(kbId!, documentId);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (error) {
      message.error('下载失败');
    }
  }, [kbId]);

  const handleCancelJob = useCallback(async (documentId: string) => {
    // 在v2.0中，我们可能需要取消索引任务
    // 这里暂时保留接口，但实际实现可能需要调整
    message.info('任务取消功能正在开发中');
  }, []);

  const handleBatchReIndex = useCallback((documentIds: string[]) => {
    setSelectedRowKeys(documentIds);
    handleIndexWithOverrideCheck(documentIds, true);
  }, []);

  // 上传配置
  const uploadProps: UploadProps = {
    name: 'files',
    multiple: true,
    beforeUpload: (file) => {
      // 验证文件
      const validation = documentService.validateFile(file);
      if (!validation.isValid) {
        message.error(validation.error);
        return false;
      }
      return true;
    },
    customRequest: async ({ file, onSuccess, onError }) => {
      try {
        const result = await documentService.uploadDocument(kbId!, file as File);
        onSuccess?.(result);
        message.success(`${(file as File).name} 文件上传成功`);
        queryClient.invalidateQueries({ queryKey: ['documents', kbId] });
      } catch (error: any) {
        onError?.(error);
        message.error(`${(file as File).name} 文件上传失败`);
      }
    },
    showUploadList: false,
  };

  return (
    <div>
      <DocumentToolbar
        selectedCount={selectedRowKeys.length}
        onBatchDownload={handleBatchDownload}
        onBatchProcess={handleBatchProcess}
        onBatchParse={handleBatchParse}
        onBatchDelete={handleBatchDelete}
        uploadProps={uploadProps}
        batchProcessLoading={singleIndexMutation.isPending || batchIndexMutation.isPending}
        batchParseLoading={batchParseMutation.isPending}
        batchDeleteLoading={batchDeleteMutation.isPending}
      />

      {/* 索引任务状态 */}
      {activeJobs.size > 0 && (
        <Alert
          message="索引任务进行中"
          description={
            <div>
              {Array.from(activeJobs.values()).map(job => (
                <div key={job.jobId} style={{ marginBottom: 8 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span>
                      {job.type === 'single' ? '单文档索引' : `批量索引 (${job.documentIds.length} 个文档)`}
                    </span>
                    <Tag color={job.status === 'completed' ? 'green' : job.status === 'failed' ? 'red' : 'blue'}>
                      {job.status}
                    </Tag>
                  </div>
                  <Progress 
                    percent={Math.round(job.progress)} 
                    size="small" 
                    status={job.status === 'failed' ? 'exception' : 'active'}
                  />
                </div>
              ))}
            </div>
          }
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
        />
      )}

      <OutdatedDocumentsAlert
        outdatedDocuments={outdatedDocuments}
        onBatchReIngest={handleBatchReIndex}
        getDocumentStatus={(doc) => getDocumentStatus(doc, documentProcessStatuses, kbDetail?.last_tag_directory_update_time, indexStats)}
        loading={batchIndexMutation.isPending}
      />

      <DocumentTable
        documents={documentsData?.documents || []}
        total={documentsData?.total || 0}
        loading={isLoading}
        selectedRowKeys={selectedRowKeys}
        selectionState={selectionState}
        documentProcessStatuses={documentProcessStatuses}
        lastTagDirectoryUpdateTime={kbDetail?.last_tag_directory_update_time}
        indexStats={indexStats}
        onSelectionChange={handleSelectionChange}
        onSelectAll={handleSelectAll}
        onSelectNone={handleSelectNone}
        onPreview={handlePreview}
        onDownload={handleDownload}
        onIndex={(documentId) => handleIndexWithOverrideCheck([documentId])}
        onReIndex={(documentId) => handleIndexWithOverrideCheck([documentId], true)}
        onCancel={handleCancelJob}
        onDelete={(documentId) => deleteMutation.mutate(documentId)}
        indexLoading={singleIndexMutation.isPending}
        activeJobs={activeJobs}
      />

      <UploadModal
        visible={uploadModalVisible}
        onCancel={() => setUploadModalVisible(false)}
        uploadProps={uploadProps}
      />

      <DocumentPreviewModal
        visible={previewModalVisible}
        document={previewDocument}
        kbId={kbId!}
        onClose={() => {
          setPreviewModalVisible(false);
          setPreviewDocument(null);
        }}
        onDownload={handleDownload}
      />
    </div>
  );
};