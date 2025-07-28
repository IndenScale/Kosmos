import React, { useState, useMemo } from 'react';
import { Card, Button, Tag, Typography, Image, Spin, Empty, Modal, Space, Divider } from 'antd';
import { 
  FileTextOutlined, 
  ExpandAltOutlined, 
  DownloadOutlined, 
  PictureOutlined, 
  EyeOutlined,
  UpOutlined,
  DownOutlined
} from '@ant-design/icons';
import { SearchResult, TagType, ActiveTag } from '../../types/search';
import { DocumentRecord } from '../../types/document';
import { searchService } from '../../services/searchService';

const { Text, Paragraph } = Typography;

interface SearchResultListProps {
  results: SearchResult[];
  documents: Record<string, DocumentRecord>;
  activeTags: ActiveTag[];
  includeScreenshots: boolean;
  includeFigures: boolean;
  onTagClick: (tag: string) => void;
  onDownload: (documentId: string, filename: string) => void;
  getResultTagColor: (tag: string) => string;
}

interface SearchResultItemProps {
  result: SearchResult;
  document?: DocumentRecord;
  activeTags: ActiveTag[];
  includeScreenshots: boolean;
  includeFigures: boolean;
  onTagClick: (tag: string) => void;
  onDownload: (documentId: string, filename: string) => void;
  getResultTagColor: (tag: string) => string;
}

const SearchResultItem: React.FC<SearchResultItemProps> = ({
  result,
  document,
  activeTags,
  includeScreenshots,
  includeFigures,
  onTagClick,
  onDownload,
  getResultTagColor
}) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const [showFullContent, setShowFullContent] = useState(false);
  const [loadingImages, setLoadingImages] = useState(false);
  const [imageUrls, setImageUrls] = useState<Map<string, string>>(new Map());
  const [showImages, setShowImages] = useState(false);

  // 检查内容是否需要展开按钮（简单检查内容长度）
  const needsExpansion = useMemo(() => {
    return result.content.length > 200 || result.content.split('\n').length > 3;
  }, [result.content]);

  // 处理下载确认
  const handleDownloadConfirm = () => {
    if (!document) return;
    
    Modal.confirm({
      title: '确认下载',
      content: `是否要下载原始完整文档：${document.document.filename}？`,
      okText: '确认下载',
      cancelText: '取消',
      onOk: () => {
        onDownload(result.document_id, document.document.filename);
      }
    });
  };

  // 处理预览截图
  const handlePreviewScreenshots = async () => {
    if (!result.related_screenshots?.length) return;

    if (!showImages) {
      setLoadingImages(true);
      try {
        const urlMap = new Map<string, string>();
        for (const screenshot of result.related_screenshots) {
          try {
            const blobUrl = await searchService.getFragmentImage(screenshot.fragment_id);
            urlMap.set(screenshot.fragment_id, blobUrl);
          } catch (error) {
            console.error(`获取截图 ${screenshot.fragment_id} 失败:`, error);
          }
        }
        setImageUrls(urlMap);
        setShowImages(true);
      } catch (error) {
        console.error('加载截图失败:', error);
      } finally {
        setLoadingImages(false);
      }
    } else {
      setShowImages(!showImages);
    }
  };

  // 处理预览插图
  const handlePreviewFigures = async () => {
    if (!result.related_figures?.length) return;

    if (!showImages) {
      setLoadingImages(true);
      try {
        const urlMap = new Map<string, string>();
        for (const figure of result.related_figures) {
          try {
            const blobUrl = await searchService.getFragmentImage(figure.fragment_id);
            urlMap.set(figure.fragment_id, blobUrl);
          } catch (error) {
            console.error(`获取插图 ${figure.fragment_id} 失败:`, error);
          }
        }
        setImageUrls(urlMap);
        setShowImages(true);
      } catch (error) {
        console.error('加载插图失败:', error);
      } finally {
        setLoadingImages(false);
      }
    } else {
      setShowImages(!showImages);
    }
  };

  // 渲染标签
  const renderTags = (tags: string[]) => {
    return tags.map(tag => (
      <Tag
        key={tag}
        color={getResultTagColor(tag)}
        style={{ margin: '2px', cursor: 'pointer' }}
        onClick={() => onTagClick(tag)}
      >
        {tag}
      </Tag>
    ));
  };

  // 渲染图片
  const renderImages = () => {
    if (loadingImages) {
      return (
        <div className="flex justify-center items-center py-4">
          <Spin size="small" />
          <span className="ml-2 text-gray-500">加载图片中...</span>
        </div>
      );
    }

    const screenshots = result.related_screenshots || [];
    const figures = result.related_figures || [];
    const allImages = [...screenshots, ...figures];

    if (allImages.length === 0) return null;

    return (
      <div className="mt-4 p-4 bg-gray-50 rounded-lg">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {allImages.map((item) => {
            const imageUrl = imageUrls.get(item.fragment_id);
            const isScreenshot = screenshots.includes(item);
            
            return (
              <div key={item.fragment_id} className="relative">
                <div className="mb-2 flex items-center justify-between">
                  <Text type="secondary" className="text-sm">
                    {isScreenshot ? '截图' : '插图'}: {item.figure_name}
                  </Text>
                  <Tag color={isScreenshot ? 'blue' : 'green'}>
                    {isScreenshot ? '截图' : '插图'}
                  </Tag>
                </div>
                {imageUrl ? (
                  <Image
                    src={imageUrl}
                    alt={item.figure_name}
                    className="w-full rounded"
                    style={{ maxHeight: '200px', objectFit: 'cover' }}
                    placeholder={
                      <div className="w-full h-32 bg-gray-100 flex items-center justify-center">
                        <Spin />
                      </div>
                    }
                  />
                ) : (
                  <div className="w-full h-32 bg-gray-100 flex items-center justify-center rounded">
                    <Text type="secondary">图片加载失败</Text>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    );
  };

  const hasScreenshots = (result.related_screenshots?.length || 0) > 0;
  const hasFigures = (result.related_figures?.length || 0) > 0;
  const shouldShowPreviewButtons = (includeScreenshots && hasScreenshots) || (includeFigures && hasFigures);

  return (
    <Card
      className="hover:shadow-lg transition-all duration-200 border-l-4 border-l-blue-500"
      bodyStyle={{ padding: '20px' }}
    >
      {/* 头部信息 */}
      <div className="flex justify-between items-start mb-4">
        <div className="flex items-center text-sm text-gray-600">
          <FileTextOutlined className="mr-2 text-blue-500" />
          <span className="font-medium">
            {document?.document?.filename || result.document_id}
          </span>
        </div>
        <div className="flex items-center space-x-2">
          <div className="text-sm text-gray-500 bg-gray-100 px-2 py-1 rounded">
            相似度: {(result.score * 100).toFixed(1)}%
          </div>
        </div>
      </div>

      {/* 内容区域 */}
      <div className="mb-4">
        <div 
          className={`text-gray-700 leading-relaxed mb-2 ${
            !isExpanded 
              ? 'line-clamp-3 overflow-hidden' 
              : ''
          }`}
          style={{
            display: '-webkit-box',
            WebkitLineClamp: !isExpanded ? 3 : 'none',
            WebkitBoxOrient: 'vertical',
            overflow: !isExpanded ? 'hidden' : 'visible'
          }}
        >
          <Paragraph className="mb-0 whitespace-pre-wrap">
            {result.content}
          </Paragraph>
        </div>
        
        {/* 折叠/展开按钮 */}
        {needsExpansion && (
          <Button
            type="link"
            size="small"
            icon={isExpanded ? <UpOutlined /> : <DownOutlined />}
            onClick={() => setIsExpanded(!isExpanded)}
            className="p-0 h-auto text-blue-500"
          >
            {isExpanded ? '收起' : '展开更多'}
          </Button>
        )}
      </div>

      {/* 图片预览区域 */}
      {showImages && renderImages()}

      {/* 操作按钮区域 */}
      <div className="flex justify-between items-center pt-3 border-t">
        <div className="flex items-center space-x-3">
          <Button
            type="text"
            size="small"
            icon={<EyeOutlined />}
            onClick={() => setShowFullContent(true)}
            className="hover:bg-blue-50 hover:text-blue-600"
          >
            查看原文
          </Button>
          
          {document && (
            <Button
              type="text"
              size="small"
              icon={<DownloadOutlined />}
              onClick={handleDownloadConfirm}
              className="hover:bg-green-50 hover:text-green-600"
            >
              源文档下载
            </Button>
          )}

          {/* 预览按钮 */}
          {shouldShowPreviewButtons && (
            <Space split={<Divider type="vertical" />}>
              {includeScreenshots && hasScreenshots && (
                <Button
                  type="text"
                  size="small"
                  icon={<PictureOutlined />}
                  onClick={handlePreviewScreenshots}
                  loading={loadingImages}
                  className="hover:bg-purple-50 hover:text-purple-600"
                >
                  预览截图({result.related_screenshots?.length || 0})
                </Button>
              )}
              
              {includeFigures && hasFigures && (
                <Button
                  type="text"
                  size="small"
                  icon={<PictureOutlined />}
                  onClick={handlePreviewFigures}
                  loading={loadingImages}
                  className="hover:bg-orange-50 hover:text-orange-600"
                >
                  预览插图({result.related_figures?.length || 0})
                </Button>
              )}
            </Space>
          )}
        </div>
      </div>

      {/* 标签区域 */}
      {result.tags.length > 0 && (
        <div className="border-t pt-3 mt-3">
          <Text type="secondary" className="mr-3 font-medium">标签：</Text>
          <div className="inline-flex flex-wrap gap-1">
            {renderTags(result.tags)}
          </div>
        </div>
      )}

      {/* 原文弹窗 */}
      <Modal
        title="原文内容"
        width={800}
        open={showFullContent}
        onCancel={() => setShowFullContent(false)}
        footer={null}
        className="top-8"
      >
        <div className="max-h-96 overflow-y-auto p-4 bg-gray-50 rounded">
          <Paragraph className="whitespace-pre-wrap">
            {result.content}
          </Paragraph>
        </div>
      </Modal>
    </Card>
  );
};

export const SearchResultList: React.FC<SearchResultListProps> = ({
  results,
  documents,
  activeTags,
  includeScreenshots,
  includeFigures,
  onTagClick,
  onDownload,
  getResultTagColor
}) => {
  if (results.length === 0) {
    return <Empty description="没有找到相关结果" className="py-12" />;
  }

  return (
    <div>
      <div className="mb-6">
        <Text type="secondary" className="text-lg">
          找到 <span className="font-semibold text-blue-600">{results.length}</span> 个相关结果
        </Text>
      </div>

      <div className="space-y-6">
        {results.map((result: SearchResult) => {
          const document = documents[result.document_id];
          const resultId = result.fragment_id || result.chunk_id || '';

          return (
            <SearchResultItem
              key={resultId}
              result={result}
              document={document}
              activeTags={activeTags}
              includeScreenshots={includeScreenshots}
              includeFigures={includeFigures}
              onTagClick={onTagClick}
              onDownload={onDownload}
              getResultTagColor={getResultTagColor}
            />
          );
        })}
      </div>
    </div>
  );
};