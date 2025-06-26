import React, { useState, useEffect } from 'react';
import { Modal, Spin, message, Button, Space } from 'antd';
import { DownloadOutlined, CloseOutlined } from '@ant-design/icons';
import { documentService } from '../../services/documentService';
import { DocumentRecord } from '../../types/document';

interface DocumentPreviewModalProps {
  visible: boolean;
  document: DocumentRecord | null;
  kbId: string;
  onClose: () => void;
  onDownload: (documentId: string, filename: string) => void;
}

export const DocumentPreviewModal: React.FC<DocumentPreviewModalProps> = ({
  visible,
  document,
  kbId,
  onClose,
  onDownload
}) => {
  const [loading, setLoading] = useState(false);
  const [previewContent, setPreviewContent] = useState<string>('');
  const [previewType, setPreviewType] = useState<'image' | 'text' | 'pdf' | 'docx' | 'pptx' | 'unsupported'>('unsupported');

  useEffect(() => {
    if (visible && document) {
      loadPreview();
    } else {
      setPreviewContent('');
      setPreviewType('unsupported');
    }
  }, [visible, document, kbId]);

  // 在loadPreview方法中添加docx处理
  const loadPreview = async () => {
    if (!document) return;

    const { supported, type } = documentService.isSupportedForPreview(document.document.filename);
    setPreviewType(type);

    if (!supported) {
      message.warning('该文件类型不支持预览，请下载后查看');
      return;
    }

    setLoading(true);
    try {
      if (type === 'text') {
        const content = await documentService.getDocumentPreview(kbId, document.document_id);
        setPreviewContent(content);
      } else if (type === 'image' || type === 'pdf') {
        const url = documentService.getPreviewUrl(kbId, document.document_id);
        setPreviewContent(url);
      } else if (type === 'docx') {
        // 转换docx为PDF
        const pdfUrl = await documentService.convertDocxToPdf(kbId, document.document_id);
        setPreviewContent(pdfUrl);
        setPreviewType('pdf'); // 转换后按PDF处理
      }
      // 在loadPreview方法中添加pptx处理
      else if (type === 'pptx') {
        // 转换pptx为PDF
        const pdfUrl = await documentService.convertOfficeToPdf(kbId, document.document_id);
        setPreviewContent(pdfUrl);
        setPreviewType('pdf'); // 转换后按PDF处理
      }
    } catch (error) {
      console.error('预览加载失败:', error);
      message.error('预览加载失败');
    } finally {
      setLoading(false);
    }
  };

  const renderPreviewContent = () => {
    if (loading) {
      return (
        <div className="flex justify-center items-center h-96">
          <Spin size="large" />
        </div>
      );
    }

    switch (previewType) {
      case 'text':
        return (
          <div className="bg-gray-50 p-4 rounded border max-h-96 overflow-auto">
            <pre className="whitespace-pre-wrap text-sm font-mono">
              {previewContent}
            </pre>
          </div>
        );

      case 'image':
        return (
          <div className="flex justify-center">
            <img
              src={previewContent}
              alt={document?.document.filename}
              className="max-w-full max-h-96 object-contain"
              onError={() => message.error('图片加载失败')}
            />
          </div>
        );

      case 'pdf':
        return (
          <div className="h-96">
            <iframe
              src={previewContent}
              className="w-full h-full border-0"
              title={document?.document.filename}
            />
          </div>
        );

      case 'unsupported':
      default:
        return (
          <div className="flex flex-col items-center justify-center h-96 text-gray-500">
            <div className="text-lg mb-4">该文件类型不支持预览</div>
            <div className="text-sm mb-4">支持预览的文件类型：</div>
            <div className="text-sm text-center">
              <div>• 图片：PNG, JPG, JPEG, GIF, BMP, WEBP</div>
              <div>• 文本：TXT, MD, JS, TS, PY, JAVA, C, CPP, HTML, CSS, JSON, XML</div>
              <div>• PDF：PDF</div>
            </div>
            <Button
              type="primary"
              icon={<DownloadOutlined />}
              className="mt-4"
              onClick={() => document && onDownload(document.document_id, document.document.filename)}
            >
              下载文件
            </Button>
          </div>
        );
    }
  };

  return (
    <Modal
      title={
        <div className="flex justify-between items-center">
          <span>文件预览 - {document?.document.filename}</span>
          <Space>
            <Button
              icon={<DownloadOutlined />}
              onClick={() => document && onDownload(document.document_id, document.document.filename)}
            >
              下载
            </Button>
          </Space>
        </div>
      }
      open={visible}
      onCancel={onClose}
      footer={[
        <Button key="close" onClick={onClose}>
          关闭
        </Button>
      ]}
      width={800}
      centered
      destroyOnClose
    >
      {renderPreviewContent()}
    </Modal>
  );
};