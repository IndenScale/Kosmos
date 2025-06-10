import { TagType, ActiveTag } from '../types/search';

// 获取标签颜色
export const getTagColor = (type: TagType): string => {
  switch (type) {
    case TagType.LIKE:
      return 'green';
    case TagType.MUST:
      return 'blue';
    case TagType.MUST_NOT:
      return 'red';
    default:
      return 'default';
  }
};

// 获取搜索结果标签的颜色
export const getResultTagColor = (tag: string, activeTags: ActiveTag[]): string => {
  const activeTag = activeTags.find(t => t.tag === tag);
  if (activeTag) {
    return getTagColor(activeTag.type);
  }
  return 'default';
};

// 限制内容显示行数
export const truncateContent = (content: string, maxLines: number = 5): string => {
  const lines = content.split('\n');
  if (lines.length <= maxLines) return content;
  return lines.slice(0, maxLines).join('\n') + '...';
};

// 计算EIG说明文本
export const getEIGExplanation = (hits: number, totalResults: number): string => {
  return `EIG分数计算方式：ABS(${hits} - ${totalResults} / 2) = ${Math.abs(hits - totalResults / 2).toFixed(2)}

EIG分数越低（越接近0），标签质量越高。`;
};

// 处理文件下载
export const handleFileDownload = async (
  kbId: string,
  documentId: string,
  filename: string,
  downloadFunction: (kbId: string, documentId: string) => Promise<Blob>
): Promise<void> => {
  try {
    const blob = await downloadFunction(kbId, documentId);
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
  } catch (error) {
    console.error('下载失败:', error);
  }
};