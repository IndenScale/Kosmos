import React, { useState, useEffect } from 'react';
import { Card, Button, Tag, Typography, Image, Carousel, Spin, Empty } from 'antd';
import { FileTextOutlined, ExpandAltOutlined, DownloadOutlined, PictureOutlined, LeftOutlined, RightOutlined } from '@ant-design/icons';
import { SearchResultCardProps, ScreenshotInfo } from '../../types/search';
import { truncateContent } from '../../utils/searchUtils';
import { searchService } from '../../services/searchService';
import styles from './SearchResultCard.module.css';

const { Text, Paragraph } = Typography;

export const SearchResultCard: React.FC<SearchResultCardProps> = ({
  result,
  document,
  isHovered,
  onMouseEnter,
  onMouseLeave,
  onExpand,
  onDownload,
  onTagClick,
  getResultTagColor
}) => {
  const [screenshots, setScreenshots] = useState<ScreenshotInfo[]>([]);
  const [screenshotUrls, setScreenshotUrls] = useState<Map<string, string>>(new Map());
  const [loadingScreenshots, setLoadingScreenshots] = useState(false);
  const [showScreenshots, setShowScreenshots] = useState(false);
  const [screenshotRequested, setScreenshotRequested] = useState(false);
  const [expandCarousel, setExpandCarousel] = useState(true);
  const [activeIndex, setActiveIndex] = useState(0); // 当前激活的图片索引

  // 清理blob URLs以防内存泄漏
  useEffect(() => {
    return () => {
      screenshotUrls.forEach(url => {
        URL.revokeObjectURL(url);
      });
    };
  }, [screenshotUrls]);

  // 用户主动请求查看截图时的处理函数
  const handleViewScreenshots = async () => {
    if (!result.screenshot_ids || result.screenshot_ids.length === 0) {
      return;
    }

    if (!screenshotRequested) {
      setScreenshotRequested(true);
      setLoadingScreenshots(true);
      
      try {
        // 获取截图信息
        const screenshotInfos = await searchService.getScreenshotsBatch(result.screenshot_ids);
        const sortedScreenshots = screenshotInfos.sort((a, b) => a.page_number - b.page_number);
        setScreenshots(sortedScreenshots);

        // 获取截图图片的blob URLs
        const urlMap = new Map<string, string>();
        for (const screenshot of sortedScreenshots) {
          try {
            const blobUrl = await searchService.getScreenshotImageBlob(screenshot.id);
            urlMap.set(screenshot.id, blobUrl);
          } catch (error) {
            console.error(`获取截图 ${screenshot.id} 失败:`, error);
          }
        }
        setScreenshotUrls(urlMap);
        setShowScreenshots(true);
        setExpandCarousel(true);
        setActiveIndex(0); // 重置激活索引
      } catch (error) {
        console.error('加载截图信息失败:', error);
        setScreenshots([]);
      } finally {
        setLoadingScreenshots(false);
      }
    } else {
      // 如果已经加载过截图，则切换显示状态
      setShowScreenshots(!showScreenshots);
    }
  };

  // 处理图片切换
  const handlePrevious = () => {
    setActiveIndex((prev) => (prev > 0 ? prev - 1 : screenshots.length - 1));
  };

  const handleNext = () => {
    setActiveIndex((prev) => (prev < screenshots.length - 1 ? prev + 1 : 0));
  };

  const handleImageClick = (index: number) => {
    setActiveIndex(index);
  };

  const renderResultTags = (tags: string[]) => {
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

  const renderScreenshots = () => {
    if (loadingScreenshots) {
      return (
        <div className="flex justify-center items-center py-4">
          <Spin size="small" />
          <span className="ml-2 text-gray-500">加载截图中...</span>
        </div>
      );
    }

    if (screenshots.length === 0) {
      return null;
    }

    if (screenshots.length === 1) {
      const screenshot = screenshots[0];
      const imageUrl = screenshotUrls.get(screenshot.id);
      
      return (
        <div className={styles.screenshotContainer}>
          <div className={styles.screenshotHeader}>
            <div className="flex items-center">
              <PictureOutlined className="mr-2 text-blue-500" />
              <Text type="secondary" className="text-sm">
                页面截图
              </Text>
            </div>
            <span className={styles.screenshotBadge}>
              第{screenshot.page_number}页
            </span>
          </div>
          <div className={styles.singleScreenshot}>
            {imageUrl ? (
              <Image
                src={imageUrl}
                alt={`第${screenshot.page_number}页`}
                className={styles.screenshotImage}
                style={{ maxWidth: '100%', maxHeight: '200px' }}
                placeholder={
                  <div className="w-full h-32 bg-gray-100 flex items-center justify-center">
                    <Spin />
                  </div>
                }
                fallback="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAMIAAADDCAYAAADQvc6UAAABRWlDQ1BJQ0MgUHJvZmlsZQAAKJFjYGASSSwoyGFhYGDIzSspCnJ3UoiIjFJgf8LAwSDCIMogwMCcmFxc4BgQ4ANUwgCjUcG3awyMIPqyLsis7PPOq3QdDFcvjV3jOD1boQVTPQrgSkktTgbSf4A4LbmgqISBgTEFyLYuLykAsTuAbJEioKOA7DkgdjqEvQHEToKwj4DVhAQ5A9k3gGyB5IxEoBmML4BsnSQk8XQkNtReEOBxcfXxUQg1Mjc0dyHgXNJBSWpFCYh2zi+oLMpMzyhRcASGUqqCZ16yno6CkYGRAQMDKMwhqj/fAIcloxgHQqxAjIHBEugw5sUIsSQpBobtQPdLciLEVJYzMPBHMDBsayhILEqEO4DxG0txmrERhM29nYGBddr//5/DGRjYNRkY/l7////39v///y4Dmn+LgeHANwDrkl1AuO+pmgAAADhlWElmTU0AKgAAAAgAAYdpAAQAAAABAAAAGgAAAAAAAqACAAQAAAABAAAAwqADAAQAAAABAAAAwwAAAAD9b/HnAAAHlklEQVR4Ae3dP3Ik1RnG4W+FgYxN..."
              />
            ) : (
              <div className="w-full h-32 bg-gray-100 flex items-center justify-center">
                <Text type="secondary">图片加载失败</Text>
              </div>
            )}
          </div>
        </div>
      );
    }

    // 多张截图的情况 - 使用新的多图轮播模式
    return (
      <div className={styles.screenshotContainer}>
        <div className={styles.screenshotHeader}>
          <div className="flex items-center">
            <PictureOutlined className="mr-2 text-blue-500" />
            <Text type="secondary" className="text-sm">
              页面截图
            </Text>
            <span className={styles.screenshotBadge} style={{ marginLeft: '8px' }}>
              {screenshots.length}张
            </span>
          </div>
          <div className="flex items-center space-x-2">
            <Text type="secondary" className="text-xs">
              {activeIndex + 1} / {screenshots.length}
            </Text>
            <Button
              type="link"
              size="small"
              onClick={() => setExpandCarousel(!expandCarousel)}
              className="text-blue-500"
            >
              {expandCarousel ? '收起' : '展开'}
            </Button>
          </div>
        </div>

        {/* 使用新的多图轮播布局 */}
        {expandCarousel && (
          <div className={styles.multiImageCarousel}>
            <div className={styles.carouselContainer}>
              {/* 左箭头按钮 */}
              <Button
                type="text"
                size="small"
                icon={<LeftOutlined />}
                onClick={handlePrevious}
                className={styles.navButton}
                disabled={screenshots.length <= 1}
              />

              {/* 图片容器 */}
              <div className={styles.imagesContainer}>
                {screenshots.map((screenshot, index) => {
                  const imageUrl = screenshotUrls.get(screenshot.id);
                  const isActive = index === activeIndex;
                  const isPrev = index === (activeIndex - 1 + screenshots.length) % screenshots.length;
                  const isNext = index === (activeIndex + 1) % screenshots.length;
                  const isVisible = isActive || isPrev || isNext;

                  if (!isVisible && screenshots.length > 3) return null;

                  return (
                    <div
                      key={screenshot.id}
                      className={`${styles.imageWrapper} ${
                        isActive ? styles.activeImage : 
                        isPrev ? styles.prevImage : 
                        isNext ? styles.nextImage : styles.hiddenImage
                      }`}
                      onClick={() => handleImageClick(index)}
                    >
                      <div className={styles.imageContent}>
                        {isActive && (
                          <Text type="secondary" className={`${styles.pageLabel} text-xs mb-1 block`}>
                            第{screenshot.page_number}页
                          </Text>
                        )}
                        {imageUrl ? (
                          <Image
                            src={imageUrl}
                            alt={`第${screenshot.page_number}页`}
                            className={styles.screenshotImage}
                            style={{ 
                              maxWidth: '100%', 
                              maxHeight: isActive ? '300px' : '200px',
                              margin: '0 auto',
                              display: 'block',
                              transition: 'all 0.3s ease'
                            }}
                            placeholder={
                              <div className="w-full h-40 bg-gray-100 flex items-center justify-center">
                                <Spin />
                              </div>
                            }
                            preview={isActive} // 只有激活的图片才允许预览
                            fallback="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAMIAAADDCAYAAADQvc6UAAABRWlDQ1BJQ0MgUHJvZmlsZQAAKJFjYGASSSwoyGFhYGDIzSspCnJ3UoiIjFJgf8LAwSDCIMogwMCcmFxc4BgQ4ANUwgCjUcG3awyMIPqyLsis7PPOq3QdDFcvjV3jOD1boQVTPQrgSkktTgbSf4A4LbmgqISBgTEFyLYuLykAsTuAbJEioKOA7DkgdjqEvQHEToKwj4DVhAQ5A9k3gGyB5IxEoBmML4BsnSQk8XQkNtReEOBxcfXxUQg1Mjc0dyHgXNJBSWpFCYh2zi+oLMpMzyhRcASGUqqCZ16yno6CkYGRAQMDKMwhqj/fAIcloxgHQqxAjIHBEugw5sUIsSQpBobtQPdLciLEVJYzMPBHMDBsayhILEqEO4DxG0txmrERhM29nYGBddr//5/DGRjYNRkY/l7////39v///y4Dmn+LgeHANwDrkl1AuO+pmgAAADhlWElmTU0AKgAAAAgAAYdpAAQAAAABAAAAGgAAAAAAAqACAAQAAAABAAAAwqADAAQAAAABAAAAwwAAAAD9b/HnAAAHlklEQVR4Ae3dP3Ik1RnG4W+FgYxN..."
                          />
                        ) : (
                          <div className="w-full h-40 bg-gray-100 flex items-center justify-center">
                            <Text type="secondary">图片加载失败</Text>
                          </div>
                        )}
                        {!isActive && screenshots.length > 3 && (
                          <div className={styles.imageOverlay}>
                            <Text className="text-white text-xs">第{screenshot.page_number}页</Text>
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* 右箭头按钮 */}
              <Button
                type="text"
                size="small"
                icon={<RightOutlined />}
                onClick={handleNext}
                className={styles.navButton}
                disabled={screenshots.length <= 1}
              />
            </div>

            {/* 底部指示器 */}
            {screenshots.length > 1 && (
              <div className={styles.indicators}>
                {screenshots.map((_, index) => (
                  <button
                    key={index}
                    className={`${styles.indicator} ${index === activeIndex ? styles.activeIndicator : ''}`}
                    onClick={() => handleImageClick(index)}
                  />
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    );
  };

  return (
    <Card
      className="hover:shadow-lg transition-all duration-200 border-l-4 border-l-blue-500"
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
      bodyStyle={{ padding: '20px' }}
    >
      <div className="flex justify-between items-start mb-4">
        <div className="flex items-center text-sm text-gray-600">
          <FileTextOutlined className="mr-2 text-blue-500" />
          <span className="font-medium">
            {document?.document?.filename || result.document_id}
          </span>
        </div>
        <div className="flex items-center space-x-3">
          <Button
            type="text"
            size="small"
            icon={<ExpandAltOutlined />}
            onClick={() => onExpand(result.chunk_id)}
            className="hover:bg-blue-50 hover:text-blue-600"
          >
            展开
          </Button>
          {document && (
            <Button
              type="text"
              size="small"
              icon={<DownloadOutlined />}
              onClick={() => onDownload(result.document_id, document.document.filename)}
              className="hover:bg-green-50 hover:text-green-600"
            >
              下载
            </Button>
          )}
          {/* 查看截图按钮 - 只有当有截图ID时才显示 */}
          {result.screenshot_ids && result.screenshot_ids.length > 0 && (
            <Button
              type="text"
              size="small"
              icon={<PictureOutlined />}
              onClick={handleViewScreenshots}
              loading={loadingScreenshots}
              className="hover:bg-purple-50 hover:text-purple-600"
            >
              {screenshotRequested 
                ? (showScreenshots ? '隐藏截图' : '显示截图')
                : `查看截图(${result.screenshot_ids.length})`
              }
            </Button>
          )}
          <div className="text-sm text-gray-500 bg-gray-100 px-2 py-1 rounded">
            相似度: {(result.score * 100).toFixed(1)}%
          </div>
        </div>
      </div>

      <Paragraph className="mb-4 text-gray-700 leading-relaxed">
        {isHovered ? result.content : truncateContent(result.content, 5)}
      </Paragraph>

      {/* 只有用户请求查看截图时才显示截图内容 */}
      {screenshotRequested && showScreenshots && renderScreenshots()}

      {result.tags.length > 0 && (
        <div className="border-t pt-3">
          <Text type="secondary" className="mr-3 font-medium">标签：</Text>
          <div className="inline-flex flex-wrap gap-1">
            {renderResultTags(result.tags)}
          </div>
        </div>
      )}
    </Card>
  );
};