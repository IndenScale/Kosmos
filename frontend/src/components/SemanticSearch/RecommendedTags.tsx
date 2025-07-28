import React from 'react';
import { Card, Tag, Typography } from 'antd';
import { RecommendedTagsProps } from '../../types/search';

const { Text } = Typography;

export const RecommendedTags: React.FC<RecommendedTagsProps> = ({
  tags,
  onTagClick
}) => {
  if (tags.length === 0) return null;

  return (
    <Card
      title="推荐标签"
      className="sticky top-4 shadow-md"
      headStyle={{ backgroundColor: '#f8f9fa', borderBottom: '1px solid #e9ecef' }}
    >
      <div className="space-y-3">
        {tags.map(({ tag, count, relevance }) => (
          <div
            key={tag}
            className="flex items-center justify-between p-3 border border-gray-200 rounded-lg cursor-pointer hover:bg-blue-50 hover:border-blue-300 transition-all duration-200"
            onClick={() => onTagClick(tag)}
          >
            <div className="flex items-center flex-1">
              <Tag color="geekblue" className="mb-0 mr-3 font-medium">
                {tag}
              </Tag>
              <Text type="secondary" className="text-xs bg-gray-100 px-2 py-1 rounded">
                出现次数: {count}
              </Text>
            </div>
            <div className="flex items-center">
              <Text className="text-xs font-mono bg-green-100 px-2 py-1 rounded">
                相关度: {relevance.toFixed(2)}
              </Text>
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
};