import React, { useState, useEffect } from 'react';
import { Card, Button, Row, Col, Typography, Tag, Space, Modal, Form, Input, Switch, message, Spin, Dropdown, Popconfirm } from 'antd';
import { PlusOutlined, DatabaseOutlined, FileTextOutlined, TagsOutlined, SettingOutlined, DeleteOutlined, MoreOutlined } from '@ant-design/icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { KnowledgeBaseService } from '../../services/KnowledgeBase';
import { KnowledgeBase, KBCreate } from '../../types/knowledgeBase';

const { Title, Text, Paragraph } = Typography;

// 定义知识库统计数据类型
interface KBWithStats extends KnowledgeBase {
  stats?: {
    document_count: number;
    chunk_count: number;
  };
}

export const KnowledgeBaseListPage: React.FC = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [isCreateModalVisible, setIsCreateModalVisible] = useState(false);
  const [form] = Form.useForm();
  const [kbsWithStats, setKbsWithStats] = useState<KBWithStats[]>([]);

  // 获取知识库列表
  const { data: KnowledgeBases, isLoading } = useQuery({
    queryKey: ['KnowledgeBases'],
    queryFn: KnowledgeBaseService.getMyKBs
  });

  // 获取所有知识库的统计数据
  useEffect(() => {
    if (KnowledgeBases) {
      const fetchStatsForAllKBs = async () => {
        const kbsWithStatsPromises = KnowledgeBases.map(async (kb) => {
          try {
            const stats = await KnowledgeBaseService.getKBStats(kb.id);
            return {
              ...kb,
              stats: {
                document_count: stats.document_count,
                chunk_count: stats.chunk_count
              }
            };
          } catch (error) {
            console.error(`Failed to fetch stats for KB ${kb.id}:`, error);
            return {
              ...kb,
              stats: {
                document_count: 0,
                chunk_count: 0
              }
            };
          }
        });

        const results = await Promise.all(kbsWithStatsPromises);
        setKbsWithStats(results);
      };

      fetchStatsForAllKBs();
    }
  }, [KnowledgeBases]);

  // 创建知识库
  const createKBMutation = useMutation({
    mutationFn: KnowledgeBaseService.createKB,
    onSuccess: () => {
      message.success('知识库创建成功');
      setIsCreateModalVisible(false);
      form.resetFields();
      queryClient.invalidateQueries({ queryKey: ['KnowledgeBases'] });
    },
    onError: (error: any) => {
      message.error(error.response?.data?.detail || '创建失败');
    }
  });

  // 删除知识库
  const deleteKBMutation = useMutation({
    mutationFn: KnowledgeBaseService.deleteKB,
    onSuccess: () => {
      message.success('知识库删除成功');
      queryClient.invalidateQueries({ queryKey: ['KnowledgeBases'] });
    },
    onError: (error: any) => {
      message.error(error.response?.data?.detail || '删除失败');
    }
  });

  const handleCreateKB = (values: KBCreate) => {
    createKBMutation.mutate(values);
  };

  const handleKBClick = (kbId: string) => {
    navigate(`/dashboard/kb/${kbId}`);
  };

  const handleManageKB = (kbId: string) => {
    navigate(`/dashboard/kb/${kbId}`);
  };

  const handleDeleteKB = (kbId: string) => {
    deleteKBMutation.mutate(kbId);
  };

  const getTopLevelTags = (tagDictionary: Record<string, any>): string[] => {
    if (!tagDictionary || typeof tagDictionary !== 'object') return [];
    return Object.keys(tagDictionary).slice(0, 3); // 显示前3个顶级标签
  };

  if (isLoading) {
    return (
      <div className="flex justify-center items-center h-64">
        <Spin size="large" />
      </div>
    );
  }

  return (
    <div className="p-6">
      <div className="flex justify-between items-center mb-6">
        <div>
          <Title level={2} className="mb-2">知识库管理</Title>
          <Text type="secondary">管理您的知识库，查看文档和标签统计</Text>
        </div>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => setIsCreateModalVisible(true)}
          className="bg-gray-900 border-gray-900 hover:bg-gray-800"
        >
          创建知识库
        </Button>
      </div>

      <Row gutter={[16, 16]}>
        {kbsWithStats.map((kb) => {
          const topTags = getTopLevelTags(kb.tag_dictionary);

          return (
            <Col xs={24} sm={12} lg={8} xl={6} key={kb.id}>
              <Card
                hoverable
                className="h-full transition-all duration-200 hover:shadow-lg"
                onClick={() => handleKBClick(kb.id)}
                actions={[
                  <Dropdown
                    key="more"
                    menu={{
                      items: [
                        {
                          key: 'manage',
                          icon: <SettingOutlined />,
                          label: '管理',
                          onClick: ({ domEvent }) => {
                            domEvent.stopPropagation();
                            handleManageKB(kb.id);
                          },
                        },
                        {
                          key: 'delete',
                          icon: <DeleteOutlined />,
                          label: '删除',
                          danger: true,
                          onClick: ({ domEvent }) => {
                            domEvent.stopPropagation();
                            Modal.confirm({
                              title: '确认删除',
                              content: `确定要删除知识库"${kb.name}"吗？此操作不可恢复。`,
                              okText: '确认删除',
                              cancelText: '取消',
                              okButtonProps: { danger: true },
                              onOk: () => handleDeleteKB(kb.id),
                            });
                          },
                        },
                      ]
                    }}
                    trigger={['click']}
                  >
                    <MoreOutlined onClick={(e) => e.stopPropagation()} />
                  </Dropdown>
                ]}
              >
                <div className="mb-4">
                  <Title level={4} className="mb-2 truncate">{kb.name}</Title>
                  <Paragraph
                    type="secondary"
                    className="text-sm mb-3"
                    ellipsis={{ rows: 2 }}
                  >
                    {kb.description || '暂无描述'}
                  </Paragraph>
                </div>

                <Space direction="vertical" className="w-full" size="small">
                  <div className="flex items-center justify-between">
                    <Space>
                      <FileTextOutlined className="text-gray-500" />
                      <Text className="text-sm">文档: {kb.stats?.document_count || 0}</Text>
                    </Space>
                    <Space>
                      <DatabaseOutlined className="text-gray-500" />
                      <Text className="text-sm">片段: {kb.stats?.chunk_count || 0}</Text>
                    </Space>
                  </div>

                  {topTags.length > 0 && (
                    <div>
                      <div className="flex items-center mb-2">
                        <TagsOutlined className="text-gray-500 mr-1" />
                        <Text className="text-sm text-gray-600">主要标签:</Text>
                      </div>
                      <div className="flex flex-wrap gap-1">
                        {topTags.map((tag, index) => (
                          <Tag key={index} className="text-xs">
                            {tag}
                          </Tag>
                        ))}
                      </div>
                    </div>
                  )}

                  <div className="flex items-center justify-between pt-2 border-t border-gray-100">
                    <Text className="text-xs text-gray-500">
                      创建于 {new Date(kb.created_at).toLocaleDateString()}
                    </Text>
                    {kb.is_public && (
                      <Tag color="green">公开</Tag>
                    )}
                  </div>
                </Space>
              </Card>
            </Col>
          );
        })}
      </Row>

      {kbsWithStats.length === 0 && !isLoading && (
        <div className="text-center py-12">
          <DatabaseOutlined className="text-6xl text-gray-300 mb-4" />
          <Title level={3} type="secondary">还没有知识库</Title>
          <Text type="secondary">创建您的第一个知识库开始管理文档</Text>
          <br />
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => setIsCreateModalVisible(true)}
            className="mt-4 bg-gray-900 border-gray-900 hover:bg-gray-800"
          >
            创建知识库
          </Button>
        </div>
      )}

      {/* 创建知识库模态框 */}
      <Modal
        title="创建知识库"
        open={isCreateModalVisible}
        onCancel={() => {
          setIsCreateModalVisible(false);
          form.resetFields();
        }}
        footer={null}
        width={500}
      >
        <Form
          form={form}
          layout="vertical"
          onFinish={handleCreateKB}
          size="large"
        >
          <Form.Item
            name="name"
            label="知识库名称"
            rules={[
              { required: true, message: '请输入知识库名称' },
              { min: 2, message: '名称至少2个字符' },
              { max: 50, message: '名称不能超过50个字符' }
            ]}
          >
            <Input placeholder="请输入知识库名称" />
          </Form.Item>

          <Form.Item
            name="description"
            label="描述"
            rules={[
              { max: 200, message: '描述不能超过200个字符' }
            ]}
          >
            <Input.TextArea
              placeholder="请输入知识库描述（可选）"
              rows={3}
              showCount
              maxLength={200}
            />
          </Form.Item>

          <Form.Item
            name="is_public"
            label="公开设置"
            valuePropName="checked"
            initialValue={false}
          >
            <Switch
              checkedChildren="公开"
              unCheckedChildren="私有"
            />
          </Form.Item>

          <Form.Item className="mb-0">
            <Space className="w-full justify-end">
              <Button onClick={() => {
                setIsCreateModalVisible(false);
                form.resetFields();
              }}>
                取消
              </Button>
              <Button
                type="primary"
                htmlType="submit"
                loading={createKBMutation.isPending}
                className="bg-gray-900 border-gray-900 hover:bg-gray-800"
              >
                创建
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};