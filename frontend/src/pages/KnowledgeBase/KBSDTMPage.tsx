import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { 
  Card, 
  Statistic, 
  Button, 
  Progress, 
  Table, 
  Modal, 
  message, 
  Space, 
  Tag,
  Descriptions,
  Switch,
  InputNumber,
  Select,
  Alert
} from 'antd';
import { 
  BarChartOutlined, 
  BugOutlined, 
  SyncOutlined, 
  EyeOutlined,
  EditOutlined,
  TagOutlined
} from '@ant-design/icons';
import sdtmService, { SDTMStats, AbnormalDocument } from '../../services/sdtmService';

const { Option } = Select;

export const KBSDTMPage: React.FC = () => {
  const { kbId } = useParams<{ kbId: string }>();
  const [stats, setStats] = useState<SDTMStats | null>(null);
  const [loading, setLoading] = useState(false);
  const [optimizing, setOptimizing] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [abnormalDocs, setAbnormalDocs] = useState<AbnormalDocument[]>([]);
  const [processMode, setProcessMode] = useState<'edit' | 'annotate' | 'shadow'>('edit');
  const [batchSize, setBatchSize] = useState(10);
  const [autoApply, setAutoApply] = useState(true);
  
  // 批处理配置
  const [abnormalDocSlots, setAbnormalDocSlots] = useState(3);
  const [normalDocSlots, setNormalDocSlots] = useState(7);
  
  // 终止条件配置
  const [maxIterations, setMaxIterations] = useState(50);
  const [abnormalDocThreshold, setAbnormalDocThreshold] = useState(3);
  const [enableEarlyTermination, setEnableEarlyTermination] = useState(true);

  // 槽位自动计算
  const handleAbnormalDocSlotsChange = (value: number | null) => {
    if (value && value > 0 && value <= batchSize) {
      setAbnormalDocSlots(value);
      setNormalDocSlots(batchSize - value);
    }
  };

  const handleBatchSizeChange = (value: number | null) => {
    if (value && value > 0) {
      setBatchSize(value);
      // 重新计算槽位分配
      const newAbnormalSlots = Math.min(abnormalDocSlots, value);
      setAbnormalDocSlots(newAbnormalSlots);
      setNormalDocSlots(value - newAbnormalSlots);
    }
  };

  useEffect(() => {
    if (kbId) {
      loadStats();
    }
  }, [kbId]);

  const loadStats = async () => {
    if (!kbId) return;
    
    setLoading(true);
    try {
      const data = await sdtmService.getSDTMStats(kbId);
      setStats(data);
      setAbnormalDocs(data.abnormal_documents || []);
    } catch (error) {
      console.error('加载统计信息失败:', error);
      message.error('加载统计信息失败，可能知识库为空或未摄入文档');
      
      // 设置默认的空统计信息，避免页面崩溃
      const defaultStats = {
        kb_id: kbId,
        progress_metrics: {
          current_iteration: 0,
          total_iterations: 1,
          current_tags_dictionary_size: 0,
          max_tags_dictionary_size: 1000,
          progress_pct: 0,
          capacity_pct: 0
        },
        quality_metrics: {
          tags_document_distribution: {},
          documents_tag_distribution: {},
          under_annotated_docs_count: 0,
          over_annotated_docs_count: 0,
          under_used_tags_count: 0,
          over_used_tags_count: 0,
          indistinguishable_docs_count: 0
        },
        abnormal_documents: [],
        last_updated: new Date().toISOString()
      };
      setStats(defaultStats);
      setAbnormalDocs([]);
    } finally {
      setLoading(false);
    }
  };

  const handleOptimize = async () => {
    if (!kbId) return;

    setOptimizing(true);
    try {
      // 检查是否为冷启动情况
      const isColdStart = abnormalDocs.some(doc => doc.anomaly_type === 'cold_start');
      
      let result;
      if (isColdStart) {
        // 冷启动情况下，根据类型提供不同的建议
        const coldStartType = abnormalDocs.find(doc => doc.anomaly_type === 'cold_start')?.doc_id;
        
        if (coldStartType === 'cold_start_dict_init') {
          // 标签字典初始化 - 这是SDTM的核心功能
          result = await sdtmService.optimizeTagDictionary({
            kb_id: kbId,
            mode: processMode,
            batch_size: batchSize,
            auto_apply: autoApply,
            abnormal_doc_slots: abnormalDocSlots,
            normal_doc_slots: normalDocSlots,
            max_iterations: maxIterations,
            abnormal_doc_threshold: abnormalDocThreshold,
            enable_early_termination: enableEarlyTermination
          });
        } else {
          // 其他冷启动情况需要用户先完成摄入
          message.warning('请先完成文档摄入流程，然后使用SDTM进行智能标注');
          setOptimizing(false);
          return;
        }
      } else {
        // 使用标准的智能标注模式
        result = await sdtmService.optimizeTagDictionary({
          kb_id: kbId,
          mode: processMode,
          batch_size: batchSize,
          auto_apply: autoApply,
          abnormal_doc_slots: abnormalDocSlots,
          normal_doc_slots: normalDocSlots,
          max_iterations: maxIterations,
          abnormal_doc_threshold: abnormalDocThreshold,
          enable_early_termination: enableEarlyTermination
        });
      }

      if (result.success) {
        message.success(result.message);
        await loadStats(); // 重新加载统计信息
      } else {
        message.error(result.message);
      }
    } catch (error) {
      message.error('智能标注失败');
    } finally {
      setOptimizing(false);
    }
  };

  const handleRunShadowMode = async () => {
    if (!kbId) return;

    setLoading(true);
    try {
      const result = await sdtmService.runShadowMode(kbId, batchSize);
      
      if (result.success) {
        message.success('影子模式运行完成');
        Modal.info({
          title: '语义漂移检测结果',
          content: (
            <div>
              <p>检测到 {result.operations?.length || 0} 个潜在编辑操作</p>
              <p>漂移程度: {result.drift_metrics?.drift_percentage?.toFixed(2)}%</p>
              <p>推理结果: {result.reasoning}</p>
            </div>
          ),
          width: 600,
        });
      } else {
        message.error(result.message);
      }
    } catch (error) {
      message.error('运行影子模式失败');
    } finally {
      setLoading(false);
    }
  };

  const abnormalDocsColumns = [
    {
      title: '文档ID',
      dataIndex: 'doc_id',
      key: 'doc_id',
      width: 200,
      render: (text: string) => (
        <span className="font-mono text-sm">{text.substring(0, 12)}...</span>
      )
    },
    {
      title: '类型',
      dataIndex: 'anomaly_type',
      key: 'anomaly_type',
      width: 120,
      render: (type: string) => {
        const colorMap = {
          'under_annotated': 'orange',
          'over_annotated': 'red',
          'indistinguishable': 'purple',
          'cold_start': 'blue'
        };
        const labelMap = {
          'under_annotated': '标注不足',
          'over_annotated': '标注过度',
          'indistinguishable': '无法区分',
          'cold_start': '冷启动'
        };
        return <Tag color={colorMap[type as keyof typeof colorMap] || 'default'}>
          {labelMap[type as keyof typeof labelMap] || type}
        </Tag>;
      }
    },
    {
      title: '原因/建议',
      dataIndex: 'reason',
      key: 'reason',
      width: 200,
      render: (reason: string, record: any) => {
        if (record.anomaly_type === 'cold_start') {
          return <span className="text-blue-600">{reason}</span>;
        }
        return reason;
      }
    },
    {
      title: '当前标签',
      dataIndex: 'current_tags',
      key: 'current_tags',
      render: (tags: string[]) => (
        <div>
          {tags.map(tag => (
            <Tag key={tag}>{tag}</Tag>
          ))}
        </div>
      )
    },
    {
      title: '内容预览',
      dataIndex: 'content',
      key: 'content',
      render: (content: string) => (
        <div className="text-sm text-gray-600 truncate max-w-xs">
          {content}
        </div>
      )
    }
  ];

  if (!stats) {
    return <div className="p-6">加载中...</div>;
  }

  return (
    <div className="p-6">
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-2xl font-bold">SDTM 智能优化</h2>
        <Space>
          <Button
            icon={<EyeOutlined />}
            onClick={handleRunShadowMode}
            loading={loading}
          >
            运行影子模式
          </Button>
          
          <Button
            onClick={() => {
              // 重置配置到默认值
              setBatchSize(10);
              setAbnormalDocSlots(3);
              setNormalDocSlots(7);
              setMaxIterations(50);
              setAbnormalDocThreshold(3);
              setEnableEarlyTermination(true);
              setProcessMode('edit');
              setAutoApply(true);
              message.success('配置已重置为默认值');
            }}
          >
            重置配置
          </Button>
          
          {/* 显示智能标注按钮 */}
          {abnormalDocs.some(doc => doc.anomaly_type === 'cold_start') ? (
            <Button
              type="primary"
              icon={<SyncOutlined />}
              onClick={handleOptimize}
              loading={optimizing}
              className="bg-blue-500 hover:bg-blue-600"
            >
              SDTM 智能初始化
            </Button>
          ) : (
            <Button
              type="primary"
              icon={<SyncOutlined />}
              onClick={handleOptimize}
              loading={optimizing}
            >
              SDTM 智能标注
            </Button>
          )}
        </Space>
      </div>

      {/* 控制面板 */}
      <Card className="mb-6">
        <h3 className="text-lg font-semibold mb-4">控制面板</h3>
        
        {/* 冷启动提示 */}
        {abnormalDocs.some(doc => doc.anomaly_type === 'cold_start') && (
          <Alert
            message="SDTM智能初始化模式"
            description="SDTM检测到知识库需要智能初始化。如果文档已摄入但标签字典为空，SDTM可以分析已摄入的chunks内容，智能生成初始标签字典并为所有文档提供标注。"
            type="info"
            showIcon
            className="mb-4"
          />
        )}
        
        <div className="space-y-6">
          {/* 基本配置 */}
          <div>
            <h4 className="text-base font-medium mb-3 text-gray-700">基本配置</h4>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium mb-2">处理模式</label>
                <Select
                  value={processMode}
                  onChange={setProcessMode}
                  style={{ width: '100%' }}
                  disabled={abnormalDocs.some(doc => doc.anomaly_type === 'cold_start')}
                >
                  <Option value="edit">编辑模式</Option>
                  <Option value="annotate">标注模式</Option>
                  <Option value="shadow">影子模式</Option>
                </Select>
                {abnormalDocs.some(doc => doc.anomaly_type === 'cold_start') && (
                  <div className="text-xs text-gray-500 mt-1">智能初始化时自动使用编辑模式</div>
                )}
              </div>
              <div>
                <label className="block text-sm font-medium mb-2">自动应用</label>
                <Switch
                  checked={autoApply}
                  onChange={setAutoApply}
                  checkedChildren="开"
                  unCheckedChildren="关"
                />
                <div className="text-xs text-gray-500 mt-1">自动应用编辑操作到标签字典</div>
              </div>
            </div>
          </div>

          {/* 批处理配置 */}
          <div>
            <h4 className="text-base font-medium mb-3 text-gray-700">批处理配置</h4>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label className="block text-sm font-medium mb-2">批处理大小</label>
                <InputNumber
                  value={batchSize}
                  onChange={handleBatchSizeChange}
                  min={1}
                  max={100}
                  style={{ width: '100%' }}
                />
                <div className="text-xs text-gray-500 mt-1">每次处理的文档总数</div>
              </div>
              <div>
                <label className="block text-sm font-medium mb-2">异常文档槽位</label>
                <InputNumber
                  value={abnormalDocSlots}
                  onChange={handleAbnormalDocSlotsChange}
                  min={1}
                  max={batchSize}
                  style={{ width: '100%' }}
                />
                <div className="text-xs text-gray-500 mt-1">用于处理异常文档的槽位数</div>
              </div>
              <div>
                <label className="block text-sm font-medium mb-2">正常文档槽位</label>
                <InputNumber
                  value={normalDocSlots}
                  disabled
                  style={{ width: '100%' }}
                />
                <div className="text-xs text-gray-500 mt-1">自动计算：{batchSize} - {abnormalDocSlots} = {normalDocSlots}</div>
              </div>
            </div>
          </div>

          {/* 终止条件配置 */}
          <div>
            <h4 className="text-base font-medium mb-3 text-gray-700">终止条件配置</h4>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label className="block text-sm font-medium mb-2">最大迭代次数</label>
                <InputNumber
                  value={maxIterations}
                  onChange={(value) => setMaxIterations(value || 50)}
                  min={1}
                  max={1000}
                  style={{ width: '100%' }}
                />
                <div className="text-xs text-gray-500 mt-1">达到此次数时强制终止</div>
              </div>
              <div>
                <label className="block text-sm font-medium mb-2">异常文档阈值 (%)</label>
                <InputNumber
                  value={abnormalDocThreshold}
                  onChange={(value) => setAbnormalDocThreshold(value || 3)}
                  min={0}
                  max={100}
                  style={{ width: '100%' }}
                />
                <div className="text-xs text-gray-500 mt-1">异常文档占比低于此值时终止</div>
              </div>
              <div>
                <label className="block text-sm font-medium mb-2">启用提前终止</label>
                <Switch
                  checked={enableEarlyTermination}
                  onChange={setEnableEarlyTermination}
                  checkedChildren="开"
                  unCheckedChildren="关"
                />
                <div className="text-xs text-gray-500 mt-1">满足条件时提前终止优化</div>
              </div>
            </div>
          </div>
        </div>
      </Card>

      {/* 统计卡片 */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <Card>
          <Statistic
            title="进度"
            value={stats.progress_metrics?.progress_pct || 0}
            suffix="%"
            prefix={<BarChartOutlined />}
          />
          <Progress 
            percent={stats.progress_metrics?.progress_pct || 0} 
            size="small" 
            showInfo={false} 
          />
        </Card>
        
        <Card>
          <Statistic
            title="字典容量"
            value={stats.progress_metrics?.capacity_pct || 0}
            suffix="%"
            prefix={<TagOutlined />}
          />
          <Progress 
            percent={stats.progress_metrics?.capacity_pct || 0} 
            size="small" 
            showInfo={false}
            strokeColor={(stats.progress_metrics?.capacity_pct || 0) > 85 ? '#ff4d4f' : '#1890ff'}
          />
        </Card>
        
        <Card>
          <Statistic
            title="异常文档"
            value={stats.abnormal_documents?.length || 0}
            prefix={<BugOutlined />}
          />
        </Card>
        
        <Card>
          <Statistic
            title="标注不足"
            value={stats.quality_metrics?.under_annotated_docs_count || 0}
            prefix={<EditOutlined />}
          />
        </Card>
      </div>

      {/* 详细指标 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <Card title="进度指标">
          <Descriptions column={1} size="small">
            <Descriptions.Item label="当前迭代">
              {stats.progress_metrics?.current_iteration || 0} / {stats.progress_metrics?.total_iterations || 1}
            </Descriptions.Item>
            <Descriptions.Item label="标签字典大小">
              {stats.progress_metrics?.current_tags_dictionary_size || 0} / {stats.progress_metrics?.max_tags_dictionary_size || 1000}
            </Descriptions.Item>
          </Descriptions>
        </Card>

        <Card title="质量指标">
          <Descriptions column={1} size="small">
            <Descriptions.Item label="标注不足文档">
              {stats.quality_metrics?.under_annotated_docs_count || 0}
            </Descriptions.Item>
            <Descriptions.Item label="标注过度文档">
              {stats.quality_metrics?.over_annotated_docs_count || 0}
            </Descriptions.Item>
            <Descriptions.Item label="使用不足标签">
              {stats.quality_metrics?.under_used_tags_count || 0}
            </Descriptions.Item>
            <Descriptions.Item label="使用过度标签">
              {stats.quality_metrics?.over_used_tags_count || 0}
            </Descriptions.Item>
            <Descriptions.Item label="无法区分文档">
              {stats.quality_metrics?.indistinguishable_docs_count || 0}
            </Descriptions.Item>
          </Descriptions>
        </Card>
      </div>

      {/* 异常文档列表 */}
      {(abnormalDocs?.length || 0) > 0 ? (
        <Card title="异常文档与建议">
          {/* 检查是否有智能初始化建议 */}
          {abnormalDocs.some(doc => doc.anomaly_type === 'cold_start') ? (
            <Alert
              message="SDTM智能初始化建议"
              description="SDTM检测到知识库需要智能初始化。对于已摄入但缺少标签字典的知识库，SDTM可以分析chunks内容，智能生成标签字典并为所有文档提供标注。"
              type="info"
              showIcon
              className="mb-4"
              action={
                <Button
                  size="small"
                  type="primary"
                  onClick={handleOptimize}
                  loading={optimizing}
                >
                  启动SDTM智能标注
                </Button>
              }
            />
          ) : (
            <Alert
              message="发现需要处理的文档"
              description={`共发现 ${abnormalDocs.length} 个需要处理的文档，SDTM可以智能优化标签质量。`}
              type="warning"
              showIcon
              className="mb-4"
            />
          )}
          
          <Table
            columns={abnormalDocsColumns}
            dataSource={abnormalDocs}
            rowKey="doc_id"
            size="small"
            pagination={{
              pageSize: 10,
              showSizeChanger: true,
              showQuickJumper: true,
              showTotal: (total) => `共 ${total} 个问题/建议`
            }}
          />
        </Card>
      ) : (
        <Card title="异常文档">
          <Alert
            message="暂无异常文档"
            description="当前知识库没有检测到异常文档，或者知识库为空。您可以上传文档后进行摄入，然后再查看SDTM分析结果。"
            type="info"
            showIcon
          />
        </Card>
      )}
    </div>
  );
}; 