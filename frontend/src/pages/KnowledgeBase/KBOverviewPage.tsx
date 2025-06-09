import React, { useState } from 'react';
import { Card, Button, Modal, Input, Tag, Space, message, Spin } from 'antd';
import { EditOutlined, PlusOutlined, DeleteOutlined, ExclamationCircleOutlined } from '@ant-design/icons';
import { useParams } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { KnowledgeBaseService } from '../../services/KnowledgeBase';

const { TextArea } = Input;
const { confirm } = Modal;

const cleanTagDictionary = (tagDict: Record<string, any>): Record<string, string[]> => {
  const cleaned: Record<string, string[]> = {};
  Object.entries(tagDict || {}).forEach(([category, tags]) => {
    if (Array.isArray(tags)) {
      cleaned[category] = tags;
    } else if (typeof tags === 'string') {
      // 如果是字符串，尝试解析为JSON数组
      try {
        const parsed = JSON.parse(tags);
        cleaned[category] = Array.isArray(parsed) ? parsed : [tags];
      } catch {
        cleaned[category] = [tags];
      }
    } else {
      // 其他情况转为字符串数组
      cleaned[category] = [String(tags)];
    }
  });
  return cleaned;
};

export const KBOverviewPage: React.FC = () => {
  const { kbId } = useParams<{ kbId: string }>();
  const queryClient = useQueryClient();
  const [isEditingTags, setIsEditingTags] = useState(false);
  const [tagInput, setTagInput] = useState('');
  const [editingTags, setEditingTags] = useState<Record<string, string[]>>({});

  // 获取知识库详情
  const { data: kbDetail, isLoading } = useQuery({
    queryKey: ['KnowledgeBase', kbId],
    queryFn: () => KnowledgeBaseService.getKBDetail(kbId!),
    enabled: !!kbId,
  });

  // 更新标签字典
  const updateTagsMutation = useMutation({
    mutationFn: (tags: Record<string, string[]>) =>
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

  const handleEditTags = () => {
    confirm({
      title: '编辑标签字典',
      icon: <ExclamationCircleOutlined />,
      content: '修改标签字典可能导致索引性能下降甚至失效，建议只进行扩充不进行删除。同时保证标签数量不超过250个。',
      onOk() {
        setEditingTags(cleanTagDictionary(kbDetail?.tag_dictionary || {}));
        setIsEditingTags(true);
      },
    });
  };

  const handleAddTag = (category: string) => {
    if (!tagInput.trim()) return;

    const newTags = { ...editingTags };
    if (!newTags[category]) {
      newTags[category] = [];
    }
    if (!newTags[category].includes(tagInput.trim())) {
      newTags[category].push(tagInput.trim());
      setEditingTags(newTags);
    }
    setTagInput('');
  };

  const handleRemoveTag = (category: string, tag: string) => {
    const newTags = { ...editingTags };
    newTags[category] = newTags[category].filter(t => t !== tag);
    if (newTags[category].length === 0) {
      delete newTags[category];
    }
    setEditingTags(newTags);
  };

  const handleAddCategory = () => {
    if (!tagInput.trim()) return;

    const newTags = { ...editingTags };
    if (!newTags[tagInput.trim()]) {
      newTags[tagInput.trim()] = [];
      setEditingTags(newTags);
    }
    setTagInput('');
  };

  const handleSaveTags = () => {
    // 检查标签总数
    const totalTags = Object.values(editingTags).flat().length;
    if (totalTags > 250) {
      message.error('标签总数不能超过250个');
      return;
    }
    updateTagsMutation.mutate(editingTags);
  };

  if (isLoading) {
    return <Spin size="large" className="flex justify-center mt-8" />;
  }

  const cleanedTagDict = cleanTagDictionary(kbDetail?.tag_dictionary || {});
  const displayTagDict = isEditingTags ? editingTags : cleanedTagDict;

  return (
    <div className="space-y-6">
      {/* 基本信息 */}
      <Card title="基本信息">
        <div className="space-y-4">
          <div>
            <span className="font-medium text-gray-700">名称：</span>
            <span>{kbDetail?.name}</span>
          </div>
          <div>
            <span className="font-medium text-gray-700">描述：</span>
            <span>{kbDetail?.description || '暂无描述'}</span>
          </div>
          <div>
            <span className="font-medium text-gray-700">创建者：</span>
            <span>{kbDetail?.owner_username}</span>
          </div>
          <div>
            <span className="font-medium text-gray-700">创建时间：</span>
            <span>{new Date(kbDetail?.created_at || '').toLocaleString()}</span>
          </div>
          <div>
            <span className="font-medium text-gray-700">公开状态：</span>
            <span>{kbDetail?.is_public ? '公开' : '私有'}</span>
          </div>
        </div>
      </Card>

      {/* 标签字典 */}
      <Card
        title="标签字典"
        extra={
          <Button
            icon={<EditOutlined />}
            onClick={handleEditTags}
            disabled={isEditingTags}
          >
            编辑
          </Button>
        }
      >
        <div className={`${!isEditingTags ? 'text-gray-400' : ''}`}>
          {Object.keys(displayTagDict).length === 0 ? (
            <p>暂无标签</p>
          ) : (
            Object.entries(displayTagDict).map(([category, tags]) => (
              <div key={category} className="mb-4">
                <div className="flex items-center mb-2">
                  <span className="font-medium text-gray-700 mr-2">{category}：</span>
                  {isEditingTags && (
                    <Button
                      size="small"
                      type="text"
                      danger
                      icon={<DeleteOutlined />}
                      onClick={() => {
                        const newTags = { ...editingTags };
                        delete newTags[category];
                        setEditingTags(newTags);
                      }}
                    />
                  )}
                </div>
                <div className="flex flex-wrap gap-2">
                  {Array.isArray(tags) && tags.map((tag: string) => (
                    <Tag
                      key={tag}
                      closable={isEditingTags}
                      onClose={() => handleRemoveTag(category, tag)}
                    >
                      {tag}
                    </Tag>
                  ))}
                  {isEditingTags && (
                    <div className="flex items-center gap-2">
                      <Input
                        size="small"
                        placeholder="添加标签"
                        value={tagInput}
                        onChange={(e) => setTagInput(e.target.value)}
                        onPressEnter={() => handleAddTag(category)}
                        style={{ width: 100 }}
                      />
                      <Button
                        size="small"
                        type="dashed"
                        icon={<PlusOutlined />}
                        onClick={() => handleAddTag(category)}
                      />
                    </div>
                  )}
                </div>
              </div>
            ))
          )}

          {isEditingTags && (
            <div className="mt-4 pt-4 border-t">
              <div className="flex items-center gap-2 mb-4">
                <Input
                  placeholder="添加新分类"
                  value={tagInput}
                  onChange={(e) => setTagInput(e.target.value)}
                  onPressEnter={handleAddCategory}
                  style={{ width: 200 }}
                />
                <Button
                  type="dashed"
                  icon={<PlusOutlined />}
                  onClick={handleAddCategory}
                >
                  添加分类
                </Button>
              </div>

              <Space>
                <Button
                  type="primary"
                  onClick={handleSaveTags}
                  loading={updateTagsMutation.isPending}
                >
                  保存
                </Button>
                <Button onClick={() => setIsEditingTags(false)}>
                  取消
                </Button>
              </Space>
            </div>
          )}
        </div>
      </Card>

      {/* 成员信息 */}
      <Card title="成员信息">
        <div className="space-y-2">
          {kbDetail?.members?.map((member: any) => (
            <div key={member.user_id} className="flex justify-between items-center">
              <div>
                <span className="font-medium">{member.username}</span>
                <span className="text-gray-500 ml-2">({member.email})</span>
              </div>
              <Tag color={member.role === 'owner' ? 'gold' : member.role === 'admin' ? 'blue' : 'default'}>
                {member.role === 'owner' ? '所有者' : member.role === 'admin' ? '管理员' : '成员'}
              </Tag>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
};