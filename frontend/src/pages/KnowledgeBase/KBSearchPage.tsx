import React, { useState, useMemo } from 'react';
import { useParams } from 'react-router-dom';
import { Input, Spin, Alert, Empty, Row, Col, Modal, Typography } from 'antd';
import { SearchOutlined } from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import { searchService } from '../../services/searchService';
import { documentService } from '../../services/documentService';
import { SearchResult, TagType, ActiveTag } from '../../types/search';
import { DocumentRecord } from '../../types/document';
import { QueryParser, getTagColor, getResultTagColor, handleFileDownload } from '../../utils/searchUtils';
import { SearchResultCard } from '../../components/SemanticSearch/SearchResultCard';
import { RecommendedTags } from '../../components/SemanticSearch/RecommendedTags';
import { ActiveTagsBar } from '../../components/SemanticSearch/ActiveTagsBar';
import { SearchPageState } from '../../types/search';

const { Search } = Input;
const { Text } = Typography;

export const KBSearchPage: React.FC = () => {
  const { kbId } = useParams<{ kbId: string }>();

  const [state, setState] = useState<SearchPageState>({
    searchText: '',
    activeTags: [],
    searchQuery: '',
    expandedChunk: null,
    modalOpen: false,
    hoveredResult: null
  });

  // 构建完整查询字符串
  const fullQuery = useMemo(() => {
    return QueryParser.buildQuery(state.searchText, state.activeTags);
  }, [state.searchText, state.activeTags]);

  // 执行搜索
  const { data: searchData, isLoading, error } = useQuery({
    queryKey: ['search', kbId, state.searchQuery],
    queryFn: () => searchService.searchKnowledgeBase(kbId!, { query: state.searchQuery, top_k: 10 }),
    enabled: !!kbId && !!state.searchQuery,
  });

  // 获取文档信息
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
        acc[doc.document_id] = doc;
        return acc;
      }, {} as Record<string, DocumentRecord>);
    },
    enabled: documentIds.length > 0,
  });

  // 处理搜索
  const handleSearch = (value: string) => {
    const trimmedValue = value.trim();
    if (trimmedValue) {
      const newActiveTags = QueryParser.getActiveTagsFromQuery(trimmedValue);
      const parsed = QueryParser.parse(trimmedValue);

      setState(prev => ({
        ...prev,
        searchQuery: trimmedValue,
        activeTags: newActiveTags,
        searchText: parsed.text
      }));
    }
  };

  // 处理输入框变化
  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const inputValue = e.target.value;
    const newActiveTags = QueryParser.getActiveTagsFromQuery(inputValue);
    const parsed = QueryParser.parse(inputValue);
    
    setState(prev => ({ 
      ...prev, 
      searchText: parsed.text,
      activeTags: newActiveTags
    }));
  };

  // 处理标签点击
  const handleTagClick = (tag: string, currentType?: TagType) => {
    const existingIndex = state.activeTags.findIndex(t => t.tag === tag);
    let newActiveTags = [...state.activeTags];

    if (existingIndex >= 0) {
      const current = newActiveTags[existingIndex];
      switch (current.type) {
        case TagType.LIKE:
          current.type = TagType.MUST;
          break;
        case TagType.MUST:
          current.type = TagType.MUST_NOT;
          break;
        case TagType.MUST_NOT:
          newActiveTags.splice(existingIndex, 1);
          break;
      }
    } else {
      newActiveTags.push({ tag, type: TagType.LIKE });
    }

    const newQuery = QueryParser.buildQuery(state.searchText, newActiveTags);
    setState(prev => ({
      ...prev,
      activeTags: newActiveTags,
      searchQuery: newQuery.trim() ? newQuery : prev.searchQuery
    }));
  };

  // 处理文件下载
  const handleDownload = async (documentId: string, filename: string) => {
    await handleFileDownload(kbId!, documentId, filename, documentService.downloadDocument);
  };

  // 展开查看原文
  const handleExpandChunk = (chunkId: string) => {
    setState(prev => ({
      ...prev,
      expandedChunk: chunkId,
      modalOpen: true
    }));
  };

  // 获取推荐标签
  const recommendedTags = useMemo(() => {
    if (!searchData?.recommended_tags) return [];
    const activeTagNames = new Set(state.activeTags.map(t => t.tag));
    return searchData.recommended_tags.filter(t => !activeTagNames.has(t.tag));
  }, [searchData?.recommended_tags, state.activeTags]);

  return (
    <div className="p-6 bg-gray-50 min-h-screen">
      {/* 搜索框 */}
      <div className="mb-6">
        <Search
          placeholder="输入查询语句，例如：AI未来发展 +技术 -历史 ~应用"
          size="large"
          value={fullQuery}
          onChange={handleInputChange}
          onSearch={handleSearch}
          enterButton={<SearchOutlined />}
          allowClear
          className="shadow-sm"
        />
      </div>

      {/* 激活标签栏 */}
      <ActiveTagsBar
        activeTags={state.activeTags}
        onTagClick={handleTagClick}
        getTagColor={getTagColor}
      />

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
          {isLoading && state.searchQuery && (
            <div className="text-center py-12">
              <Spin size="large" />
              <div className="mt-4 text-gray-500 text-lg">搜索中...</div>
            </div>
          )}

          {!isLoading && !error && searchData && (
            <div>
              <div className="mb-6">
                <Text type="secondary" className="text-lg">
                  找到 <span className="font-semibold text-blue-600">{searchData.results.length}</span> 个相关结果
                </Text>
              </div>

              {searchData.results.length === 0 ? (
                <Empty description="没有找到相关结果" className="py-12" />
              ) : (
                <div className="space-y-6">
                  {searchData.results.map((result: SearchResult) => {
                    const document = documentsData?.[result.document_id];
                    const isHovered = state.hoveredResult === result.chunk_id;

                    return (
                      <SearchResultCard
                        key={result.chunk_id}
                        result={result}
                        document={document}
                        isHovered={isHovered}
                        onMouseEnter={() => setState(prev => ({ ...prev, hoveredResult: result.chunk_id }))}
                        onMouseLeave={() => setState(prev => ({ ...prev, hoveredResult: null }))}
                        onExpand={handleExpandChunk}
                        onDownload={handleDownload}
                        onTagClick={handleTagClick}
                        getResultTagColor={(tag) => getResultTagColor(tag, state.activeTags)}
                      />
                    );
                  })}
                </div>
              )}
            </div>
          )}
        </Col>

        {/* 右侧推荐标签栏 */}
        <Col span={6}>
          <RecommendedTags
            tags={recommendedTags}
            onTagClick={handleTagClick}
            searchResultsLength={searchData?.results.length || 0}
          />
        </Col>
      </Row>

      {/* 原文弹窗 */}
      <Modal
        title="原文内容"
        width={800}
        open={state.modalOpen}
        onCancel={() => setState(prev => ({ ...prev, modalOpen: false }))}
        footer={null}
        className="top-8"
      >
        <div className="max-h-96 overflow-y-auto p-4 bg-gray-50 rounded">
          {state.expandedChunk && searchData?.results.find(r => r.chunk_id === state.expandedChunk)?.content}
        </div>
      </Modal>
    </div>
  );
};