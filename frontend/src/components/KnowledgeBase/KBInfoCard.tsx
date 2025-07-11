import React from 'react';
import { Card, Space, Typography, Button, message } from 'antd';
import { IdcardOutlined, CopyOutlined } from '@ant-design/icons';

const { Text } = Typography;

interface KBInfoCardProps {
  kbId: string;
  kbName: string;
}

export const KBInfoCard: React.FC<KBInfoCardProps> = ({ kbId, kbName }) => {
  const handleCopyId = async () => {
    try {
      await navigator.clipboard.writeText(kbId);
      message.success('知识库ID已复制到剪贴板');
    } catch (error) {
      // 如果浏览器不支持clipboard API，使用传统方法
      const textArea = document.createElement('textarea');
      textArea.value = kbId;
      document.body.appendChild(textArea);
      textArea.select();
      document.execCommand('copy');
      document.body.removeChild(textArea);
      message.success('知识库ID已复制到剪贴板');
    }
  };

  return (
    <Card
      title={
        <Space>
          <IdcardOutlined />
          知识库信息
        </Space>
      }
      className="mb-6"
    >
      <div className="space-y-4">
        <div className="flex items-center">
          <Text strong className="w-20 text-gray-600">名称：</Text>
          <Text>{kbName}</Text>
        </div>
        <div className="flex items-center">
          <Text strong className="w-20 text-gray-600">ID：</Text>
          <div className="flex items-center space-x-2 flex-1">
            <Text 
              code 
              className="flex-1 bg-gray-50 px-2 py-1 rounded text-sm font-mono"
            >
              {kbId}
            </Text>
            <Button
              type="text"
              size="small"
              icon={<CopyOutlined />}
              onClick={handleCopyId}
              className="hover:bg-blue-50 hover:text-blue-600"
              title="复制知识库ID"
            >
              复制
            </Button>
          </div>
        </div>
        <div className="text-xs text-gray-500 bg-blue-50 p-3 rounded-lg">
          <Text>
            💡 此ID可用于外部系统集成时访问特定知识库，请妥善保管
          </Text>
        </div>
      </div>
    </Card>
  );
}; 