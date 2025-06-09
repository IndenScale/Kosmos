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
import { TagDictionary } from '../../types/KnowledgeBase';
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
  const [tagEditMode, setTagEditMode] = useState<'manual' | 'json'>('manual');
  const [tagInput, setTagInput] = useState('');
  const [editingTags, setEditingTags] = useState<TagDictionary>({});
  const [jsonInput, setJsonInput] = useState('');
  const [jsonError, setJsonError] = useState<string>('');

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
  // Remove the duplicate functions (lines 311-339)
  // Keep only the first implementations (lines 207-235)

  // Add selectedCategory state
  const [selectedCategory, setSelectedCategory] = useState<string>('');

  // Fix the type issue in updateTagsMutation
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

  useEffect(() => {
    if (kbDetail && isEditingTags) {
      const cleaned = cleanTagDictionary(kbDetail.tag_dictionary || {});
      setEditingTags(cleaned);
      setJsonInput(JSON.stringify(cleaned, null, 2));
    }
  }, [kbDetail, isEditingTags]);

  // 基本信息编辑处理
  const handleEditBasic = () => {
    setIsEditingBasic(true);
  };

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
  const handleEditTags = () => {
    confirm({
      title: '编辑标签字典',
      icon: <ExclamationCircleOutlined />,
      content: '修改标签字典可能导致索引性能下降甚至失效，建议只进行扩充不进行删除。同时保证标签数量不超过250个。',
      onOk() {
        setIsEditingTags(true);
      },
    });
  };

  // 手动编辑模式处理
  const handleAddTag = (category: string) => {
    if (!tagInput.trim()) return;

    const newTags = { ...editingTags };
    if (!newTags[category]) {
      newTags[category] = [];
    }
    // 修改includes调用方式
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

  // 在cleanTagDictionary函数后添加辅助函数

  // 递归计算标签总数的辅助函数
  const countTags = (tagDict: TagDictionary): number => {
    let count = 0;
    Object.values(tagDict).forEach(value => {
      if (Array.isArray(value)) {
        count += value.length;
      } else {
        count += countTags(value);
      }
    });
    return count;
  };

  // 递归查找并移除标签的辅助函数
  const removeTagFromDict = (tagDict: TagDictionary, targetCategory: string, targetTag: string): TagDictionary => {
    const newDict: TagDictionary = {};

    Object.entries(tagDict).forEach(([key, value]) => {
      if (Array.isArray(value)) {
        if (key === targetCategory) {
          const filteredTags = value.filter(tag => tag !== targetTag);
          if (filteredTags.length > 0) {
            newDict[key] = filteredTags;
          }
        } else {
          newDict[key] = [...value];
        }
      } else {
        const nestedResult = removeTagFromDict(value, targetCategory, targetTag);
        if (Object.keys(nestedResult).length > 0) {
          newDict[key] = nestedResult;
        }
      }
    });

    return newDict;
  };

  // 递归添加标签的辅助函数
  const addTagToDict = (tagDict: TagDictionary, category: string, tag: string): TagDictionary => {
    const newDict = { ...tagDict };

    if (!newDict[category]) {
      newDict[category] = [];
    }

    if (Array.isArray(newDict[category])) {
      const currentTags = newDict[category] as string[];
      if (!currentTags.includes(tag)) {
        newDict[category] = [...currentTags, tag];
      }
    }

    return newDict;
  };

  // const handleAddTag = () => {
  //   if (!tagInput.trim() || !selectedCategory) return;

  //   const newTags = addTagToDict(editingTags, selectedCategory, tagInput.trim());
  //   setEditingTags(newTags);
  //   setJsonInput(JSON.stringify(newTags, null, 2));
  //   setTagInput('');
  // };

  // const handleRemoveTag = (category: string, tag: string) => {
  //   const newTags = removeTagFromDict(editingTags, category, tag);
  //   setEditingTags(newTags);
  //   setJsonInput(JSON.stringify(newTags, null, 2));
  // };

  // const handleAddCategory = () => {
  //   if (!tagInput.trim()) return;

  //   const newTags = { ...editingTags };
  //   if (!newTags[tagInput.trim()]) {
  //     newTags[tagInput.trim()] = [];
  //     setEditingTags(newTags);
  //     setJsonInput(JSON.stringify(newTags, null, 2));
  //   }
  //   setTagInput('');
  // };

  // JSON编辑模式处理
  // const handleJsonChange = (value: string) => {
  //   setJsonInput(value);
  //   setJsonError('');

  //   if (!value.trim()) {
  //     setEditingTags({});
  //     return;
  //   }

  //   const validation = KnowledgeBaseService.validateTagDictionary(value);
  //   if (validation.isValid && validation.data) {
  //     setEditingTags(validation.data);
  //     setJsonError('');
  //   } else {
  //     setJsonError(validation.error || '格式错误');
  //   }
  // };

  const handleSaveTags = () => {
    const totalTags = countTags(editingTags);
    if (totalTags > 250) {
      message.error('标签总数不能超过250个');
      return;
    }

    if (tagEditMode === 'json' && jsonError) {
      message.error('请修复JSON格式错误');
      return;
    }

    updateTagsMutation.mutate(editingTags);
  };

  const handleCancelTags = () => {
    setIsEditingTags(false);
    setJsonError('');
    setTagEditMode('manual');
  };

  if (isLoading) {
    return (
      <div className="flex justify-center items-center h-64">
        <Spin size="large" />
      </div>
    );
  }

  const cleanedTagDict = cleanTagDictionary(kbDetail?.tag_dictionary || {});
  const displayTagDict = isEditingTags ? editingTags : cleanedTagDict;
  const totalTags = Object.values(displayTagDict).flat().length;

  return (
    <div className="max-w-7xl mx-auto p-6 space-y-6">
     {/* /*面包屑导航
      <Breadcrumb className="mb-4">
        <Breadcrumb.Item>
          <Link to="/">
            <HomeOutlined /> 首页
          </Link>
        </Breadcrumb.Item>
        <Breadcrumb.Item>
          <Link to="/knowledge">
            <BookOutlined /> 知识库
          </Link>
        </Breadcrumb.Item>
        <Breadcrumb.Item>
          <Text strong>{kbDetail?.name}</Text>
        </Breadcrumb.Item>
      </Breadcrumb>
      */}

      {/* 页面标题
      <div className="mb-6">
        <Title level={2} className="mb-2">
          {kbDetail?.name}
        </Title>
        <Text type="secondary">{kbDetail?.description || '暂无描述'}</Text>
      </div> */}

      <Row gutter={[24, 24]}>
        {/* 左侧主要内容 */}
        <Col xs={24} lg={16}>
          {/* 基本信息卡片 */}
          <Card
            title={
              <Space>
                <InfoCircleOutlined />
                基本信息
              </Space>
            }
            extra={
              !isEditingBasic ? (
                <Button
                  icon={<EditOutlined />}
                  onClick={handleEditBasic}
                  type="text"
                >
                  编辑
                </Button>
              ) : (
                <Space>
                  <Button
                    icon={<SaveOutlined />}
                    type="primary"
                    size="small"
                    onClick={handleSaveBasic}
                    loading={updateBasicMutation.isPending}
                  >
                    保存
                  </Button>
                  <Button
                    icon={<CloseOutlined />}
                    size="small"
                    onClick={handleCancelBasic}
                  >
                    取消
                  </Button>
                </Space>
              )
            }
            className="mb-6"
          >
            {!isEditingBasic ? (
              <div className="space-y-4">
                <div className="flex items-center">
                  <Text strong className="w-20 text-gray-600">名称：</Text>
                  <Text>{kbDetail?.name}</Text>
                </div>
                <div className="flex items-start">
                  <Text strong className="w-20 text-gray-600">描述：</Text>
                  <Text>{kbDetail?.description || '暂无描述'}</Text>
                </div>
                <div className="flex items-center">
                  <Text strong className="w-20 text-gray-600">创建者：</Text>
                  <Text>{kbDetail?.owner_username}</Text>
                </div>
                <div className="flex items-center">
                  <Text strong className="w-20 text-gray-600">创建时间：</Text>
                  <Text>{new Date(kbDetail?.created_at || '').toLocaleString()}</Text>
                </div>
                <div className="flex items-center">
                  <Text strong className="w-20 text-gray-600">状态：</Text>
                  <Tag color={kbDetail?.is_public ? 'green' : 'blue'}>
                    {kbDetail?.is_public ? '公开' : '私有'}
                  </Tag>
                </div>
              </div>
            ) : (
              <Form form={basicForm} layout="vertical">
                <Form.Item
                  name="name"
                  label="知识库名称"
                  rules={[
                    { required: true, message: '请输入知识库名称' },
                    { max: 100, message: '名称长度不能超过100个字符' }
                  ]}
                >
                  <Input placeholder="请输入知识库名称" />
                </Form.Item>
                <Form.Item
                  name="description"
                  label="描述"
                  rules={[
                    { max: 500, message: '描述长度不能超过500个字符' }
                  ]}
                >
                  <TextArea
                    rows={3}
                    placeholder="请输入知识库描述"
                    showCount
                    maxLength={500}
                  />
                </Form.Item>
              </Form>
            )}
          </Card>

          {/* 标签字典卡片 */}
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
              !isEditingTags ? (
                <Button
                  icon={<EditOutlined />}
                  onClick={handleEditTags}
                  type="text"
                >
                  编辑
                </Button>
              ) : (
                <Space>
                  <Button
                    icon={<SaveOutlined />}
                    type="primary"
                    onClick={handleSaveTags}
                    loading={updateTagsMutation.isPending}
                  >
                    保存
                  </Button>
                  <Button
                    icon={<CloseOutlined />}
                    onClick={handleCancelTags}
                  >
                    取消
                  </Button>
                </Space>
              )
            }
          >
            {!isEditingTags ? (
              <div>
                {Object.keys(displayTagDict).length === 0 ? (
                  <div className="text-center py-8 text-gray-400">
                    <TagsOutlined className="text-4xl mb-4" />
                    <p>暂无标签，点击编辑按钮添加标签</p>
                  </div>
                ) : (
                  <>
                    <div className="mb-4 text-sm text-gray-500">
                      共 {Object.keys(displayTagDict).length} 个分类，{totalTags} 个标签
                    </div>
                    {Object.entries(displayTagDict).map(([category, tags]) => (
                      <div key={category} className="mb-6 last:mb-0">
                        <div className="flex items-center mb-3">
                          <Text strong className="text-lg text-gray-700">{category}</Text>
                          <Tag className="ml-2">{Array.isArray(tags) ? tags.length : 0}</Tag>
                        </div>
                        <div className="flex flex-wrap gap-2">
                          {Array.isArray(tags) && tags.map((tag: string) => (
                            <Tag key={tag} className="mb-2">
                              {tag}
                            </Tag>
                          ))}
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
                    <div className="space-y-6">
                      {Object.keys(editingTags).length === 0 ? (
                        <div className="text-center py-4 text-gray-400">
                          <p>暂无标签分类</p>
                        </div>
                      ) : (
                        Object.entries(editingTags).map(([category, tags]) => (
                          <div key={category} className="border rounded-lg p-4">
                            <div className="flex items-center justify-between mb-3">
                              <Text strong className="text-lg">{category}</Text>
                              <Button
                                size="small"
                                type="text"
                                danger
                                icon={<DeleteOutlined />}
                                onClick={() => {
                                  const newTags = { ...editingTags };
                                  delete newTags[category];
                                  setEditingTags(newTags);
                                  setJsonInput(JSON.stringify(newTags, null, 2));
                                }}
                              >
                                删除分类
                              </Button>
                            </div>
                            <div className="flex flex-wrap gap-2 mb-3">
                              {Array.isArray(tags) && tags.map((tag: string) => (
                                <Tag
                                  key={tag}
                                  closable
                                  onClose={() => handleRemoveTag(category, tag)}
                                  className="mb-2"
                                >
                                  {tag}
                                </Tag>
                              ))}
                            </div>
                            <div className="flex items-center gap-2">
                              <Input
                                size="small"
                                placeholder="添加标签"
                                value={tagInput}
                                onChange={(e) => setTagInput(e.target.value)}
                                onPressEnter={() => handleAddTag(category)}
                                style={{ width: 150 }}
                              />
                              <Button
                                size="small"
                                type="dashed"
                                icon={<PlusOutlined />}
                                onClick={() => handleAddTag(category)}
                              >
                                添加
                              </Button>
                            </div>
                          </div>
                        ))
                      )}

                      <div className="border-t pt-4">
                        <div className="flex items-center gap-2">
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
                      </div>
                    </div>
                  </Tabs.TabPane>

                  <Tabs.TabPane tab="JSON 编辑" key="json">
                    <div className="space-y-4">
                      <div className="text-sm text-gray-600 bg-gray-50 p-3 rounded">
                        <p><strong>格式说明：</strong></p>
                        <p>请输入有效的 JSON 格式，例如：</p>
                        <pre className="mt-2 text-xs">
{`{
  "技术": ["Python", "JavaScript", "React"],
  "业务": ["产品设计", "用户体验"]
}`}
                        </pre>
                      </div>

                      <TextArea
                        value={jsonInput}
                        onChange={(e) => handleJsonChange(e.target.value)}
                        placeholder="请输入 JSON 格式的标签字典"
                        rows={12}
                        className={jsonError ? 'border-red-300' : ''}
                      />

                      {jsonError && (
                        <div className="text-red-500 text-sm bg-red-50 p-2 rounded">
                          <ExclamationCircleOutlined className="mr-1" />
                          {jsonError}
                        </div>
                      )}

                      {!jsonError && Object.keys(editingTags).length > 0 && (
                        <div className="text-green-600 text-sm bg-green-50 p-2 rounded">
                          <InfoCircleOutlined className="mr-1" />
                          格式正确，共 {Object.keys(editingTags).length} 个分类，
                          {Object.values(editingTags).flat().length} 个标签
                        </div>
                      )}
                    </div>
                  </Tabs.TabPane>
                </Tabs>
              </div>
            )}
          </Card>
        </Col>

        {/* 右侧边栏 */}
        <Col xs={24} lg={8}>
          {/* 统计信息卡片 */}
          <Card
            title={
              <Space>
                <FileTextOutlined />
                统计信息
              </Space>
            }
            className="mb-6"
          >
            <Row gutter={16}>
              <Col span={12}>
                <Statistic
                  title="文档数量"
                  value={kbStats?.document_count || 0}
                  valueStyle={{ color: '#1890ff' }}
                />
              </Col>
              <Col span={12}>
                <Statistic
                  title="文档块数"
                  value={kbStats?.chunk_count || 0}
                  valueStyle={{ color: '#52c41a' }}
                />
              </Col>
            </Row>
            <Row gutter={16} className="mt-4">
              <Col span={12}>
                <Statistic
                  title="标签分类"
                  value={Object.keys(cleanedTagDict).length}
                  valueStyle={{ color: '#722ed1' }}
                />
              </Col>
              <Col span={12}>
                <Statistic
                  title="标签总数"
                  value={totalTags}
                  valueStyle={{ color: '#fa8c16' }}
                />
              </Col>
            </Row>
          </Card>

          {/* 成员信息卡片 */}
          <Card
            title={
              <Space>
                <UserOutlined />
                成员信息
              </Space>
            }
          >
            <div className="space-y-3">
              {kbDetail?.members?.map((member: any) => (
                <div key={member.user_id} className="flex justify-between items-center p-3 bg-gray-50 rounded-lg">
                  <div className="flex-1">
                    <div className="font-medium text-gray-900">{member.username}</div>
                    <div className="text-sm text-gray-500">{member.email}</div>
                  </div>
                  <div>
                    <Tag
                      color={
                        member.role === 'owner' ? 'gold' :
                        member.role === 'admin' ? 'blue' : 'default'
                      }
                    >
                      {member.role === 'owner' ? '所有者' :
                       member.role === 'admin' ? '管理员' : '成员'}
                    </Tag>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </Col>
      </Row>
    </div>
  );
};