import React from 'react';
import { Card, Tag, Typography, Tooltip } from 'antd';
import { QuestionCircleOutlined } from '@ant-design/icons';
import { RecommendedTagsProps } from '../../types/search';
import { getEIGExplanation } from '../../utils/searchUtils';

const { Text } = Typography;

export const RecommendedTags: React.FC<RecommendedTagsProps> = ({
  tags,
  onTagClick,
  searchResultsLength
}) => {
  if (tags.length === 0) return null;

  return (
    <Card
      title="推荐标签"
      className="sticky top-4 shadow-md"
      headStyle={{ backgroundColor: '#f8f9fa', borderBottom: '1px solid #e9ecef' }}
    >
      <div className="space-y-3">
        {tags.map(({ tag, eig_score, freq }) => (
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
                hits: {freq || 0}
              </Text>
            </div>
            <div className="flex items-center">
              <Text className="text-xs mr-2 font-mono bg-yellow-100 px-2 py-1 rounded">
                {eig_score.toFixed(2)}
              </Text>
              <Tooltip
                title={getEIGExplanation(freq || 0, searchResultsLength)}
                placement="left"
              >
                <QuestionCircleOutlined className="text-gray-400 hover:text-blue-500 cursor-help" />
              </Tooltip>
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
};