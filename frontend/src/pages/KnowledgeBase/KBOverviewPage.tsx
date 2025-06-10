// frontend/src/pages/Knowledge/KBOverviewPage.tsx

import React, { useState, useEffect } from 'react';
import {
  Card,
  Button,
  Modal,
  Input,
  Tag,
  Space,
  message,
  Spin,
  Tabs,
  Form,
  Row,
  Col,
  Statistic,
  Typography,
  Breadcrumb,
  Tooltip
} from 'antd';
import {
  EditOutlined,
  PlusOutlined,
  DeleteOutlined,
  ExclamationCircleOutlined,
  SaveOutlined,
  CloseOutlined,
  InfoCircleOutlined,
  FileTextOutlined,
  TagsOutlined,
  UserOutlined,
  HomeOutlined,
  BookOutlined
} from '@ant-design/icons';
import { useParams, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { KnowledgeBaseService } from '../../services/KnowledgeBase';
import { TagDictionary } from '../../types/knowledgeBase';

import {BasicInfoCard} from '../../components/KnowledgeBase/BasicInfoCard';
import {MemberCard} from '../../components/KnowledgeBase/MemberCard';
import {StatsCard} from '../../components/KnowledgeBase/StatsCard';
import {TagDictionaryCard} from '../../components/KnowledgeBase/TagDictionaryCard';

import { countTags } from '../../utils/tagDictionaryUtils';
const { TextArea } = Input;
const { Text, Title } = Typography;
const { confirm } = Modal;

// 递归清洗标签字典的工具函数
const cleanTagDictionary = (tagDict: any): TagDictionary => {
  const cleaned: TagDictionary = {};

  const cleanNode = (node: any): TagDictionary | string[] => {
    if (Array.isArray(node)) {
      // 如果是数组，过滤并返回有效的字符串标签
      return node.filter(tag => typeof tag === 'string' && tag.trim() !== '').map(tag => tag.trim());
    } else if (typeof node === 'object' && node !== null) {
      // 如果是对象，递归处理每个属性
      const cleanedObj: TagDictionary = {};
      Object.entries(node).forEach(([key, value]) => {
        const cleanedValue = cleanNode(value);
        if (Array.isArray(cleanedValue) && cleanedValue.length > 0) {
          cleanedObj[key] = cleanedValue;
        } else if (typeof cleanedValue === 'object' && Object.keys(cleanedValue).length > 0) {
          cleanedObj[key] = cleanedValue;
        }
      });
      return cleanedObj;
    } else if (typeof node === 'string') {
      // 如果是字符串，尝试解析为JSON，否则作为单个标签
      try {
        const parsed = JSON.parse(node);
        return cleanNode(parsed);
      } catch {
        return node.trim() ? [node.trim()] : [];
      }
    } else {
      // 其他类型转换为字符串数组
      const str = String(node).trim();
      return str ? [str] : [];
    }
  };

  Object.entries(tagDict || {}).forEach(([key, value]) => {
    const cleanedValue = cleanNode(value);
    if (Array.isArray(cleanedValue) && cleanedValue.length > 0) {
      cleaned[key] = cleanedValue;
    } else if (typeof cleanedValue === 'object' && Object.keys(cleanedValue).length > 0) {
      cleaned[key] = cleanedValue;
    }
  });

  return cleaned;
};

export const KBOverviewPage: React.FC = () => {
  const { kbId } = useParams<{ kbId: string }>();
  const queryClient = useQueryClient();

  // 基本信息编辑状态
  const [isEditingBasic, setIsEditingBasic] = useState(false);
  const [basicForm] = Form.useForm();

  // 标签编辑状态
  const [isEditingTags, setIsEditingTags] = useState(false);

  // 获取知识库详情
  const { data: kbDetail, isLoading } = useQuery({
    queryKey: ['KnowledgeBase', kbId],
    queryFn: () => KnowledgeBaseService.getKBDetail(kbId!),
    enabled: !!kbId,
  });

  // 获取知识库统计信息
  const { data: kbStats } = useQuery({
    queryKey: ['KnowledgeBase', kbId, 'stats'],
    queryFn: () => KnowledgeBaseService.getKBStats(kbId!),
    enabled: !!kbId,
  });

  // 更新基本信息
  const updateBasicMutation = useMutation({
    mutationFn: (data: { name?: string; description?: string }) =>
      KnowledgeBaseService.updateKBBasicInfo(kbId!, data),
    onSuccess: () => {
      message.success('基本信息更新成功');
      setIsEditingBasic(false);
      queryClient.invalidateQueries({ queryKey: ['KnowledgeBase', kbId] });
    },
    onError: (error: any) => {
      message.error(error.response?.data?.detail || '更新失败');
    },
  });

  // 更新标签字典
  const updateTagsMutation = useMutation({
    mutationFn: (tags: TagDictionary) =>
      KnowledgeBaseService.updateTagDictionary(kbId!, tags),
    onSuccess: () => {
      message.success('标签字典更新成功');
      setIsEditingTags(false);
      queryClient.invalidateQueries({ queryKey: ['KnowledgeBase', kbId] });
    },
    onError: (error: any) => {
      message.error(error.response?.data?.detail || '更新失败');
    },
  });

  // 初始化编辑状态
  useEffect(() => {
    if (kbDetail && isEditingBasic) {
      basicForm.setFieldsValue({
        name: kbDetail.name,
        description: kbDetail.description || '',
      });
    }
  }, [kbDetail, isEditingBasic, basicForm]);

  // 基本信息编辑处理
  const handleEditBasic = () => setIsEditingBasic(true);
  const handleSaveBasic = () => {
    basicForm.validateFields().then(values => {
      updateBasicMutation.mutate(values);
    });
  };
  const handleCancelBasic = () => {
    setIsEditingBasic(false);
    basicForm.resetFields();
  };

  // 标签编辑处理
  const handleEditTags = () => setIsEditingTags(true);
  const handleSaveTags = (tags: TagDictionary) => {
    updateTagsMutation.mutate(tags);
  };
  const handleCancelTags = () => setIsEditingTags(false);

  if (isLoading) {
    return (
      <div className="flex justify-center items-center h-64">
        <Spin size="large" />
      </div>
    );
  }

  const cleanedTagDict = cleanTagDictionary(kbDetail?.tag_dictionary || {});
  const displayTagDict = isEditingTags ? cleanedTagDict : cleanedTagDict;
  const totalTags = countTags(displayTagDict);

  return (
    <div className="max-w-7xl mx-auto p-6 space-y-6">
      <Row gutter={[24, 24]}>
        {/* 左侧主要内容 */}
        <Col xs={24} lg={16}>
          <BasicInfoCard
            kbDetail={kbDetail}
            isEditing={isEditingBasic}
            form={basicForm}
            onEdit={handleEditBasic}
            onSave={handleSaveBasic}
            onCancel={handleCancelBasic}
            loading={updateBasicMutation.isPending}
          />

          <TagDictionaryCard
            tagDictionary={cleanedTagDict}
            lastUpdateTime={kbDetail?.last_tag_directory_update_time}
            isEditing={isEditingTags}
            onEdit={handleEditTags}
            onSave={handleSaveTags}
            onCancel={handleCancelTags}
            loading={updateTagsMutation.isPending}
          />
        </Col>

        {/* 右侧边栏 */}
        <Col xs={24} lg={8}>
          <StatsCard
            documentCount={kbStats?.document_count || 0}
            chunkCount={kbStats?.chunk_count || 0}
            tagCategoryCount={Object.keys(displayTagDict).length}
            totalTags={totalTags}
          />

          <MemberCard members={kbDetail?.members || []} />
        </Col>
      </Row>
    </div>
  );
};