import React, { useState, useMemo, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { Input, Card, Tag, Typography, Spin, Alert, Empty, Divider, Row, Col, Button, Modal } from 'antd';
import { SearchOutlined, FileTextOutlined, ExpandAltOutlined, DownloadOutlined } from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import { searchService } from '../../services/searchService';
import { documentService } from '../../services/documentService';
import { SearchResult, RecommendedTag, TagType, ActiveTag } from '../../types/search';
import { QueryParser } from '../../utils/queryParser';

const { Search } = Input;
const { Text, Paragraph } = Typography;

export const KBSearchPage: React.FC = () => {
  const { kbId } = useParams<{ kbId: string }>();
  const [searchText, setSearchText] = useState('');
  const [activeTags, setActiveTags] = useState<ActiveTag[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [expandedChunk, setExpandedChunk] = useState<string | null>(null);
  const [modalVisible, setModalVisible] = useState(false);

  // 构建完整查询字符串
  const fullQuery = useMemo(() => {
    return QueryParser.buildQuery(searchText, activeTags);
  }, [searchText, activeTags]);

  // 执行搜索 - 只在有搜索查询时执行
  const { data: searchData, isLoading, error } = useQuery({
    queryKey: ['search', kbId, searchQuery],
    queryFn: () => searchService.searchKnowledgeBase(kbId!, { query: searchQuery, top_k: 10 }),
    enabled: !!kbId && !!searchQuery,
  });

  // 获取文档信息的查询
  const documentIds = useMemo(() => {
    if (!searchData?.results) return [];
    return [...new Set(searchData.results.map(r => r.document_id))];
  }, [searchData]);

  const { data: documentsData } = useQuery({
    queryKey: ['documents', kbId, documentIds],
    queryFn: async () => {
      const docs = await Promise.all(
        documentIds.map(id => documentService.getDocument(kbId!, id))
      );
      return docs.reduce((acc, doc) => {
        acc[doc.id] = doc;
        return acc;
      }, {} as Record<string, any>);
    },
    enabled: documentIds.length > 0,
  });

  // 处理搜索 - 只在用户主动触发时执行
  const handleSearch = (value: string) => {
    const trimmedValue = value.trim();
    if (trimmedValue) {
      setSearchQuery(trimmedValue);
      // 解析查询并更新激活标签
      const newActiveTags = QueryParser.getActiveTagsFromQuery(trimmedValue);
      setActiveTags(newActiveTags);
      // 提取纯文本部分
      const parsed = QueryParser.parse(trimmedValue);
      setSearchText(parsed.text);
    }
  };

  // 处理标签点击
  const handleTagClick = (tag: string, currentType?: TagType) => {
    const existingIndex = activeTags.findIndex(t => t.tag === tag);

    if (existingIndex >= 0) {
      // 标签已存在，切换状态
      const newActiveTags = [...activeTags];
      const current = newActiveTags[existingIndex];

      switch (current.type) {
        case TagType.LIKE:
          current.type = TagType.MUST;
          break;
        case TagType.MUST:
          current.type = TagType.MUST_NOT;
          break;
        case TagType.MUST_NOT:
          // 移除标签
          newActiveTags.splice(existingIndex, 1);
          break;
      }

      setActiveTags(newActiveTags);
    } else {
      // 新标签，默认为LIKE类型
      setActiveTags([...activeTags, { tag, type: TagType.LIKE }]);
    }

    // 更新搜索查询
    const newQuery = QueryParser.buildQuery(searchText, activeTags);
    if (newQuery.trim()) {
      setSearchQuery(newQuery);
    }
  };

  // 处理搜索结果中的标签点击
  const handleResultTagClick = (tag: string) => {
    handleTagClick(tag);
  };

  // 获取标签颜色
  const getTagColor = (type: TagType) => {
    switch (type) {
      case TagType.LIKE:
        return 'green';
      case TagType.MUST:
        return 'blue';
      case TagType.MUST_NOT:
        return 'red';
      default:
        return 'default';
    }
  };

  // 获取搜索结果标签的颜色
  const getResultTagColor = (tag: string) => {
    const activeTag = activeTags.find(t => t.tag === tag);
    if (activeTag) {
      switch (activeTag.type) {
        case TagType.LIKE:
          return 'green';
        case TagType.MUST:
          return 'blue';
        case TagType.MUST_NOT:
          return 'red';
        default:
          return 'default';
      }
    }
    return 'default';
  };


  // 获取推荐标签（排除已激活的）
  const recommendedTags = useMemo(() => {
    if (!searchData?.recommended_tags) return [];
    const activeTagNames = new Set(activeTags.map(t => t.tag));
    return searchData.recommended_tags.filter(t => !activeTagNames.has(t.tag));
  }, [searchData?.recommended_tags, activeTags]);

  // 渲染搜索结果标签
  const renderResultTags = (tags: string[]) => {
    return tags.map(tag => (
      <Tag
        key={tag}
        color={getResultTagColor(tag)}
        style={{ margin: '2px', cursor: 'pointer' }}
        onClick={() => handleResultTagClick(tag)}
      >
        {tag}
      </Tag>
    ));
  };

  // 限制内容显示行数（增加到3行）
  const truncateContent = (content: string, maxLines: number = 3) => {
    const lines = content.split('\n');
    if (lines.length <= maxLines) return content;
    return lines.slice(0, maxLines).join('\n') + '...';
  };

  // 处理文件下载
  const handleDownload = async (documentId: string, filename: string) => {
    try {
      const blob = await documentService.downloadDocument(kbId!, documentId);
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (error) {
      console.error('下载失败:', error);
    }
  };

  // 展开查看原文
  const handleExpandChunk = (chunkId: string) => {
    setExpandedChunk(chunkId);
    setModalVisible(true);
  };

  return (
    <div className="p-6">
      {/* 搜索框 */}
      <div className="mb-6">
        <Search
          placeholder="输入查询语句，例如：AI未来发展 +技术 -历史 ~应用"
          size="large"
          value={fullQuery}
          onChange={(e) => {
            const value = e.target.value;
            // 只更新输入框显示，不触发搜索
            const parsed = QueryParser.parse(value);
            setSearchText(parsed.text);
            const newActiveTags = QueryParser.getActiveTagsFromQuery(value);
            setActiveTags(newActiveTags);
          }}
          onSearch={handleSearch}
          enterButton={<SearchOutlined />}
          allowClear
        />
      </div>

      {/* 激活标签栏 */}
      {activeTags.length > 0 && (
        <div className="mb-6">
          <Text strong className="mr-3">激活标签：</Text>
          {[TagType.LIKE, TagType.MUST, TagType.MUST_NOT].map(type =>
            activeTags
              .filter(tag => tag.type === type)
              .map(({ tag, type }) => (
                <Tag
                  key={`${tag}-${type}`}
                  color={getTagColor(type)}
                  closable
                  onClose={() => handleTagClick(tag, type)}
                  onClick={() => handleTagClick(tag, type)}
                  style={{ cursor: 'pointer', margin: '2px 4px' }}
                >
                  {type === TagType.MUST && '+'}
                  {type === TagType.MUST_NOT && '-'}
                  {type === TagType.LIKE && '~'}
                  {tag}
                </Tag>
              ))
          )}
        </div>
      )}

      <Row gutter={24}>
        {/* 主体搜索结果 */}
        <Col span={18}>
        <>
          {error && (
            <Alert
              message="搜索失败"
              description={String(error)}
              type="error"
              className="mb-4"
            />
          )}
        </>
          {isLoading && searchQuery && (
            <div className="text-center py-8">
              <Spin size="large" />
              <div className="mt-2 text-gray-500">搜索中...</div>
            </div>
          )}

          {!isLoading && !error && searchData && (
            <div>
              <div className="mb-4">
                <Text type="secondary">
                  找到 {searchData.results.length} 个相关结果
                </Text>
              </div>

              {searchData.results.length === 0 ? (
                <Empty description="没有找到相关结果" />
              ) : (
                <div className="space-y-4">
                  {searchData.results.map((result: SearchResult) => {
                    const document = documentsData?.[result.document_id];
                    return (
                      <Card key={result.chunk_id} className="hover:shadow-md transition-shadow">
                        <div className="flex justify-between items-start mb-3">
                          <div className="flex items-center text-sm text-gray-500">
                            <FileTextOutlined className="mr-1" />
                            <span>{document?.filename || result.document_id}</span>
                          </div>
                          <div className="flex items-center space-x-2">
                            <Button
                              type="text"
                              size="small"
                              icon={<ExpandAltOutlined />}
                              onClick={() => handleExpandChunk(result.chunk_id)}
                            >
                              展开
                            </Button>
                            {document && (
                              <Button
                                type="text"
                                size="small"
                                icon={<DownloadOutlined />}
                                onClick={() => handleDownload(result.document_id, document.filename)}
                              >
                                下载
                              </Button>
                            )}
                            <div className="text-sm text-gray-400">
                              相似度: {(result.score * 100).toFixed(1)}%
                            </div>
                          </div>
                        </div>

                        <Paragraph className="mb-3">
                          {truncateContent(result.content, 3)}
                        </Paragraph>

                        {result.tags.length > 0 && (
                          <div>
                            <Text type="secondary" className="mr-2">标签：</Text>
                            {renderResultTags(result.tags)}
                          </div>
                        )}
                      </Card>
                    );
                  })}
                </div>
              )}
            </div>
          )}
        </Col>

        {/* 右侧推荐标签栏 */}
        <Col span={6}>
          {recommendedTags.length > 0 && (
            <Card title="推荐标签" className="sticky top-4">
              <div className="flex flex-wrap">
                {recommendedTags.map(({ tag, eig_score }) => (
                  <Tag
                    key={tag}
                    color="geekblue"
                    style={{ margin: '2px', cursor: 'pointer' }}
                    onClick={() => handleTagClick(tag)}
                  >
                    {tag} ({eig_score.toFixed(2)})
                  </Tag>
                ))}
              </div>
            </Card>
          )}
        </Col>
      </Row>

      {/* 原文弹窗 */}
      <Modal
        title="原文内容"
        width={800}
        visible={modalVisible}
        onCancel={() => setModalVisible(false)}
        footer={null}
      >
        {expandedChunk && searchData?.results.find(r => r.chunk_id === expandedChunk)?.content}
      </Modal>
    </div>
  );
};
