import React from 'react';
import { Card, Button, Tag, Typography } from 'antd';
import { FileTextOutlined, ExpandAltOutlined, DownloadOutlined } from '@ant-design/icons';
import { SearchResultCardProps } from '../../types/search';
import { truncateContent } from '../../utils/searchUtils';

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
          <div className="text-sm text-gray-500 bg-gray-100 px-2 py-1 rounded">
            相似度: {(result.score * 100).toFixed(1)}%
          </div>
        </div>
      </div>

      <Paragraph className="mb-4 text-gray-700 leading-relaxed">
        {isHovered ? result.content : truncateContent(result.content, 5)}
      </Paragraph>

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