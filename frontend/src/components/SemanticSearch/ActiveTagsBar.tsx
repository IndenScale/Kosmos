import React from 'react';
import { Tag, Typography } from 'antd';
import { TagType } from '../../types/search';
import { ActiveTagsBarProps } from '../../types/search';

const { Text } = Typography;

export const ActiveTagsBar: React.FC<ActiveTagsBarProps> = ({
  activeTags,
  onTagClick,
  getTagColor
}) => {
  if (activeTags.length === 0) return null;

  return (
    <div className="mb-6 p-4 bg-gray-50 rounded-lg border">
      <Text strong className="mr-4 text-gray-700">激活标签：</Text>
      <div className="inline-flex flex-wrap gap-2">
        {[TagType.LIKE, TagType.MUST, TagType.MUST_NOT].map(type =>
          activeTags
            .filter(tag => tag.type === type)
            .map(({ tag, type }) => (
              <Tag
                key={`${tag}-${type}`}
                color={getTagColor(type)}
                closable
                onClose={() => onTagClick(tag, type)}
                onClick={() => onTagClick(tag, type)}
                className="cursor-pointer hover:opacity-80 transition-opacity"
              >
                {type === TagType.MUST && '+'}
                {type === TagType.MUST_NOT && '-'}
                {type === TagType.LIKE && '~'}
                {tag}
              </Tag>
            ))
        )}
      </div>
    </div>
  );
};