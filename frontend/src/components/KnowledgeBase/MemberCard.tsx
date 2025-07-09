import React from 'react';
import { Card, Tag, Space } from 'antd';
import { UserOutlined } from '@ant-design/icons';
import { KBMember } from '../../types/knowledgeBase';

interface MemberCardProps {
  members: KBMember[];
}

export const MemberCard: React.FC<MemberCardProps> = ({ members }) => {
  return (
    <Card
      title={
        <Space>
          <UserOutlined />
          成员信息
        </Space>
      }
    >
      <div className="space-y-3">
        {members?.map((member) => (
          <div key={member.user_id} className="flex justify-between items-center p-3 bg-gray-50 rounded-lg">
            <div className="flex-1">
              <div className="font-medium text-gray-900">{member.username}</div>
              <div className="text-sm text-gray-500">{member.email}</div>
            </div>
            <div>
              <Tag
                color={
                  member.role === 'owner' ? 'gold' :
                  member.role === 'admin' ? 'blue' : 'default'
                }
              >
                {member.role === 'owner' ? '所有者' :
                 member.role === 'admin' ? '管理员' : '成员'}
              </Tag>
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
};