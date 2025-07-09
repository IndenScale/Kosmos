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
  message,
  Collapse
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
const { Panel } = Collapse;

interface TagDictionaryCardProps {
  tagDictionary: TagDictionary;
  lastUpdateTime?: string;
  isEditing: boolean;
  onEdit: () => void;
  onSave: (tags: TagDictionary) => void;
  onCancel: () => void;
  loading?: boolean;
}

// 递归渲染标签字典的组件
const TagDictionaryRenderer: React.FC<{ 
  tagDict: TagDictionary; 
  level?: number;
  parentPath?: string;
}> = ({ tagDict, level = 0, parentPath = '' }) => {
  const renderTagNode = (key: string, value: TagDictionary | string[], currentPath: string) => {
    if (Array.isArray(value)) {
      // 叶子节点：字符串数组
      return (
        <div key={currentPath} className={`mb-4 ${level > 0 ? 'ml-4' : ''}`}>
          <div className="flex items-center mb-2">
            <Text strong className={`text-${level === 0 ? 'lg' : 'base'} text-gray-700`}>
              {key}
            </Text>
            <Tag className="ml-2" color={level === 0 ? 'blue' : 'default'}>
              {value.length}
            </Tag>
          </div>
          <div className="flex flex-wrap gap-2 ml-2">
            {value.length > 0 ? (
              value.map((tag: string) => (
                <Tag key={`${currentPath}-${tag}`} className="mb-1">
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
      );
    } else {
      // 中间节点：嵌套对象
      const subTagCount = countTags({ [key]: value });
      return (
        <div key={currentPath} className={`mb-4 ${level > 0 ? 'ml-4' : ''}`}>
          <div className="flex items-center mb-3">
            <Text strong className={`text-${level === 0 ? 'lg' : 'base'} text-gray-700`}>
              {key}
            </Text>
            <Tag className="ml-2" color={level === 0 ? 'blue' : 'default'}>
              {subTagCount} 个标签
            </Tag>
          </div>
          <div className={`${level === 0 ? 'border-l-2 border-gray-200 pl-4' : ''}`}>
            <TagDictionaryRenderer 
              tagDict={value} 
              level={level + 1} 
              parentPath={currentPath}
            />
          </div>
        </div>
      );
    }
  };

  return (
    <div>
      {Object.entries(tagDict).map(([key, value]) => {
        const currentPath = parentPath ? `${parentPath}.${key}` : key;
        return renderTagNode(key, value, currentPath);
      })}
    </div>
  );
};

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

  // 初始化编辑状态
  React.useEffect(() => {
    if (isEditing) {
      setEditingTags(tagDictionary);
      setJsonInput(JSON.stringify(tagDictionary, null, 2));
    }
  }, [isEditing, tagDictionary]);

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
              <TagDictionaryRenderer tagDict={tagDictionary} />
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
              <div className="space-y-4">
                <div>
                  <Text strong>添加新分类：</Text>
                  <div className="flex gap-2 mt-2">
                    <Input
                      placeholder="输入分类名称"
                      value={tagInput}
                      onChange={(e) => setTagInput(e.target.value)}
                      onPressEnter={handleAddCategory}
                    />
                    <Button 
                      icon={<PlusOutlined />} 
                      onClick={handleAddCategory}
                      type="primary"
                    >
                      添加分类
                    </Button>
                  </div>
                </div>
                
                <div className="border-t pt-4">
                  <Text strong>当前标签结构：</Text>
                  <div className="mt-2 max-h-96 overflow-y-auto">
                    <TagDictionaryRenderer tagDict={editingTags} />
                  </div>
                </div>
              </div>
            </Tabs.TabPane>
            <Tabs.TabPane tab="JSON 编辑" key="json">
              <div className="space-y-4">
                <div>
                  <Text strong>JSON 格式编辑：</Text>
                  <TextArea
                    rows={12}
                    value={jsonInput}
                    onChange={(e) => handleJsonChange(e.target.value)}
                    placeholder="请输入有效的JSON格式标签字典"
                    className={jsonError ? 'border-red-500' : ''}
                  />
                  {jsonError && (
                    <Text type="danger" className="text-sm">
                      {jsonError}
                    </Text>
                  )}
                </div>
                
                <div className="text-sm text-gray-500">
                  <Text>格式说明：支持多层嵌套结构，叶子节点必须是字符串数组</Text>
                </div>
              </div>
            </Tabs.TabPane>
          </Tabs>
        </div>
      )}
    </Card>
  );
};