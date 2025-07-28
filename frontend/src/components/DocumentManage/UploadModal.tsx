import React from 'react';
import { Modal, Upload } from 'antd';
import { UploadOutlined } from '@ant-design/icons';
import type { UploadProps } from 'antd';
import { UploadConfig } from '../../config/uploadConfig';

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
  const supportedExtensions = UploadConfig.getSupportedExtensions();
  const extensionText = supportedExtensions.slice(0, 10).join(', ') + 
    (supportedExtensions.length > 10 ? ' 等' : '');

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
          支持单个或批量上传。支持的文件类型：{extensionText}<br/>
          文件大小限制：PDF/Office文件≤500MB，文本文件≤50MB，图片≤20MB，代码文件≤10MB
        </p>
      </Upload.Dragger>
    </Modal>
  );
};