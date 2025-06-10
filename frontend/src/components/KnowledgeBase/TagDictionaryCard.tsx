import React, { useState } from 'react';
import {
  Card,
  Tag,
  Typography,
  Space,
  Tooltip,
  Button,
  Tabs,
  Input,
  message
} from 'antd';
import {
  TagsOutlined,
  InfoCircleOutlined,
  EditOutlined,
  SaveOutlined,
  CloseOutlined,
  PlusOutlined,
  DeleteOutlined,
  ExclamationCircleOutlined
} from '@ant-design/icons';
import { TagDictionary } from '../../types/knowledgeBase';
import { KnowledgeBaseService } from '../../services/KnowledgeBase';
import { countTags } from '../../utils/tagDictionaryUtils';

const { Text } = Typography;
const { TextArea } = Input;

interface TagDictionaryCardProps {
  tagDictionary: TagDictionary;
  lastUpdateTime?: string;
  isEditing: boolean;
  onEdit: () => void;
  onSave: (tags: TagDictionary) => void;
  onCancel: () => void;
  loading?: boolean;
}

export const TagDictionaryCard: React.FC<TagDictionaryCardProps> = ({
  tagDictionary,
  lastUpdateTime,
  isEditing,
  onEdit,
  onSave,
  onCancel,
  loading = false
}) => {
  const [tagEditMode, setTagEditMode] = useState<'manual' | 'json'>('manual');
  const [tagInput, setTagInput] = useState('');
  const [editingTags, setEditingTags] = useState<TagDictionary>(tagDictionary);
  const [jsonInput, setJsonInput] = useState('');
  const [jsonError, setJsonError] = useState<string>('');

  const totalTags = countTags(tagDictionary);

  // 手动编辑模式处理
  const handleAddTag = (category: string) => {
    if (!tagInput.trim()) return;

    const newTags = { ...editingTags };
    if (!newTags[category]) {
      newTags[category] = [];
    }
    if (Array.isArray(newTags[category])) {
      const tagArray = newTags[category] as string[];
      if (!tagArray.includes(tagInput.trim())) {
        tagArray.push(tagInput.trim());
        setEditingTags(newTags);
        setJsonInput(JSON.stringify(newTags, null, 2));
      }
    }
    setTagInput('');
  };

  const handleRemoveTag = (category: string, tag: string) => {
    const newTags = { ...editingTags };
    if (Array.isArray(newTags[category])) {
      newTags[category] = (newTags[category] as string[]).filter(t => t !== tag);
      if (newTags[category].length === 0) {
        delete newTags[category];
      }
      setEditingTags(newTags);
      setJsonInput(JSON.stringify(newTags, null, 2));
    }
  };

  const handleAddCategory = () => {
    if (!tagInput.trim()) return;

    const newTags = { ...editingTags };
    if (!newTags[tagInput.trim()]) {
      newTags[tagInput.trim()] = [];
      setEditingTags(newTags);
      setJsonInput(JSON.stringify(newTags, null, 2));
    }
    setTagInput('');
  };

  // JSON编辑模式处理
  const handleJsonChange = (value: string) => {
    setJsonInput(value);
    setJsonError('');

    if (!value.trim()) {
      setEditingTags({});
      return;
    }

    const validation = KnowledgeBaseService.validateTagDictionary(value);
    if (validation.isValid && validation.data) {
      setEditingTags(validation.data);
      setJsonError('');
    } else {
      setJsonError(validation.error || '格式错误');
    }
  };

  const handleSave = () => {
    const totalTags = countTags(editingTags);
    if (totalTags > 250) {
      message.error('标签总数不能超过250个');
      return;
    }

    if (tagEditMode === 'json' && jsonError) {
      message.error('请修复JSON格式错误');
      return;
    }

    onSave(editingTags);
  };

  return (
    <Card
      title={
        <Space>
          <TagsOutlined />
          标签字典
          <Tooltip title="标签字典用于对文档进行分类和标记，便于后续的检索和管理">
            <InfoCircleOutlined className="text-gray-400" />
          </Tooltip>
        </Space>
      }
      extra={
        !isEditing ? (
          <Button icon={<EditOutlined />} onClick={onEdit} type="text">
            编辑
          </Button>
        ) : (
          <Space>
            <Button
              icon={<SaveOutlined />}
              type="primary"
              onClick={handleSave}
              loading={loading}
            >
              保存
            </Button>
            <Button
              icon={<CloseOutlined />}
              onClick={onCancel}
            >
              取消
            </Button>
          </Space>
        )
      }
    >
      {!isEditing ? (
        <div>
          {lastUpdateTime && (
            <div className="mb-4 p-3 bg-blue-50 rounded-lg">
              <div className="flex items-center text-sm text-blue-600">
                <InfoCircleOutlined className="mr-2" />
                <span>
                  标签字典最后更新时间：
                  {new Date(lastUpdateTime).toLocaleString()}
                </span>
              </div>
            </div>
          )}

          {Object.keys(tagDictionary).length === 0 ? (
            <div className="text-center py-8 text-gray-400">
              <TagsOutlined className="text-4xl mb-4" />
              <p>暂无标签，点击编辑按钮添加标签</p>
            </div>
          ) : (
            <>
              <div className="mb-4 text-sm text-gray-500">
                共 {Object.keys(tagDictionary).length} 个分类，{totalTags} 个标签
                {totalTags === 0 && (
                  <span className="text-orange-500 ml-2">
                    （各分类下暂无具体标签）
                  </span>
                )}
              </div>
              {Object.entries(tagDictionary).map(([category, tags]) => (
                <div key={category} className="mb-6 last:mb-0">
                  <div className="flex items-center mb-3">
                    <Text strong className="text-lg text-gray-700">{category}</Text>
                    <Tag className="ml-2">{Array.isArray(tags) ? tags.length : 0}</Tag>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {Array.isArray(tags) && tags.length > 0 ? (
                      tags.map((tag: string) => (
                        <Tag key={tag} className="mb-2">
                          {tag}
                        </Tag>
                      ))
                    ) : (
                      <Text type="secondary" className="italic">
                        该分类下暂无标签，点击编辑添加标签
                      </Text>
                    )}
                  </div>
                </div>
              ))}
            </>
          )}
        </div>
      ) : (
        <div>
          <Tabs
            activeKey={tagEditMode}
            onChange={(key) => setTagEditMode(key as 'manual' | 'json')}
            className="mb-4"
          >
            <Tabs.TabPane tab="手动编辑" key="manual">
              {/* 手动编辑内容 */}
            </Tabs.TabPane>
            <Tabs.TabPane tab="JSON 编辑" key="json">
              {/* JSON编辑内容 */}
            </Tabs.TabPane>
          </Tabs>
        </div>
      )}
    </Card>
  );
};