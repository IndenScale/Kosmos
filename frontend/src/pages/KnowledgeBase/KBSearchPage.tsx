import React, { useState, useMemo } from 'react';
import { useParams } from 'react-router-dom';
import { Input, Button, Switch, Space, Row, Col, Spin, Alert, Empty, Typography } from 'antd';
import { SearchOutlined } from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import { SearchResult, TagType, ActiveTag } from '../../types/search';
import { DocumentRecord } from '../../types/document';
import { QueryParser } from '../../utils/searchUtils';
import { handleFileDownload, getTagColor, getResultTagColor } from '../../utils/searchUtils';
import { documentService } from '../../services/documentService';
import { searchService } from '../../services/searchService';
import { ActiveTagsBar } from '../../components/SemanticSearch/ActiveTagsBar';
import { RecommendedTagsCard, SearchResultList } from '../../components/search';
import { SearchPageState } from '../../types/search';

const { Search } = Input;
const { Text } = Typography;

export const KBSearchPage: React.FC = () => {
  const { kbId } = useParams<{ kbId: string }>();

  const [state, setState] = useState<SearchPageState>({
    searchText: '',
    activeTags: [],
    searchQuery: '',
    includeScreenshots: false,
    includeFigures: false
  });

  // 构建完整查询字符串 - 直接使用用户输入的文本
  const fullQuery = useMemo(() => {
    return state.searchText;
  }, [state.searchText]);

  // 执行搜索
  const { data: searchData, isLoading, error } = useQuery({
    queryKey: ['search', kbId, state.searchQuery, state.includeScreenshots, state.includeFigures],
    queryFn: () => searchService.searchKnowledgeBase(kbId!, { 
      query: state.searchQuery, 
      top_k: 10,
      include_screenshots: state.includeScreenshots,
      include_figures: state.includeFigures
    }),
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
      // 解析查询字符串，提取标签和文本
      const newActiveTags = QueryParser.getActiveTagsFromQuery(trimmedValue);
      const parsed = QueryParser.parse(trimmedValue);

      setState(prev => ({
        ...prev,
        searchQuery: trimmedValue,
        activeTags: newActiveTags,
        // 保持原始输入文本不变，不更新searchText
      }));
    }
  };

  // 处理输入框变化
  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const inputValue = e.target.value;
    
    // 直接更新搜索文本，不进行解析和trim
    setState(prev => ({ 
      ...prev, 
      searchText: inputValue
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

    // 解析当前输入文本，获取纯文本部分
    const parsed = QueryParser.parse(state.searchText);
    const newQuery = QueryParser.buildQuery(parsed.text, newActiveTags);
    
    setState(prev => ({
      ...prev,
      activeTags: newActiveTags,
      searchText: newQuery, // 更新输入框内容
      searchQuery: newQuery.trim() ? newQuery : prev.searchQuery
    }));
  };

  // 处理文件下载
  const handleDownload = async (documentId: string, filename: string) => {
    await handleFileDownload(kbId!, documentId, filename, documentService.downloadDocument);
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
        
        {/* 搜索选项 */}
        <div className="mt-3">
          <Space size="large">
            <Space>
              <Switch
                checked={state.includeScreenshots}
                onChange={(checked) => setState(prev => ({ ...prev, includeScreenshots: checked }))}
                size="small"
              />
              <span className="text-gray-600">包含截图</span>
            </Space>
            <Space>
              <Switch
                checked={state.includeFigures}
                onChange={(checked) => setState(prev => ({ ...prev, includeFigures: checked }))}
                size="small"
              />
              <span className="text-gray-600">包含插图</span>
            </Space>
          </Space>
        </div>
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
            <SearchResultList
              results={searchData.results}
              documents={documentsData || {}}
              activeTags={state.activeTags}
              includeScreenshots={state.includeScreenshots}
              includeFigures={state.includeFigures}
              onTagClick={handleTagClick}
              onDownload={handleDownload}
              getResultTagColor={(tag) => getResultTagColor(tag, state.activeTags)}
            />
          )}
        </Col>

        {/* 右侧推荐标签栏 */}
        <Col span={6}>
          <RecommendedTagsCard
            tags={recommendedTags}
            onTagClick={handleTagClick}
            searchResultsLength={searchData?.results.length || 0}
          />
        </Col>
      </Row>
    </div>
  );
};