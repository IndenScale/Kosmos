import React from 'react';
import { Typography } from 'antd';

const { Title } = Typography;

const Banner: React.FC = () => {
  return (
    <div style={{ display: 'flex', alignItems: 'center' }}>
      <Title level={3} style={{ margin: 0 }}>
        网络安全评估系统工作台
      </Title>
    </div>
  );
};

export default Banner;