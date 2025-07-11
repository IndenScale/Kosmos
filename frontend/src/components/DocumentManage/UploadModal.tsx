import React from 'react';
import { Modal, Upload } from 'antd';
import { UploadOutlined } from '@ant-design/icons';
import type { UploadProps } from 'antd';

interface UploadModalProps {
  visible: boolean;
  onCancel: () => void;
  uploadProps: UploadProps;
}

export const UploadModal: React.FC<UploadModalProps> = ({
  visible,
  onCancel,
  uploadProps
}) => {
  return (
    <Modal
      title="上传文档"
      open={visible}
      onCancel={onCancel}
      footer={null}
    >
      <Upload.Dragger {...uploadProps}>
        <p className="ant-upload-drag-icon">
          <UploadOutlined />
        </p>
        <p className="ant-upload-text">点击或拖拽文件到此区域上传</p>
        <p className="ant-upload-hint">
          支持单个或批量上传。支持的文件类型：PDF、Word、PowerPoint、文本文件等。
        </p>
      </Upload.Dragger>
    </Modal>
  );
};