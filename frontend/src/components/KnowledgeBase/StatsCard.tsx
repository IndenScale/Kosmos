import React from 'react';
import { Card, Row, Col, Statistic, Space } from 'antd';
import { FileTextOutlined } from '@ant-design/icons';

interface StatsCardProps {
  documentCount: number;
  chunkCount: number;
  tagCategoryCount: number;
  totalTags: number;
}

export const StatsCard: React.FC<StatsCardProps> = ({
  documentCount,
  chunkCount,
  tagCategoryCount,
  totalTags
}) => {
  return (
    <Card
      title={
        <Space>
          <FileTextOutlined />
          统计信息
        </Space>
      }
      className="mb-6"
    >
      <Row gutter={16}>
        <Col span={12}>
          <Statistic
            title="文档数量"
            value={documentCount}
            valueStyle={{ color: '#1890ff' }}
          />
        </Col>
        <Col span={12}>
          <Statistic
            title="文档块数"
            value={chunkCount}
            valueStyle={{ color: '#52c41a' }}
          />
        </Col>
      </Row>
      <Row gutter={16} className="mt-4">
        <Col span={12}>
          <Statistic
            title="标签分类"
            value={tagCategoryCount}
            valueStyle={{ color: '#722ed1' }}
          />
        </Col>
        <Col span={12}>
          <Statistic
            title="标签总数"
            value={totalTags}
            valueStyle={{ color: '#fa8c16' }}
          />
        </Col>
      </Row>
    </Card>
  );
};