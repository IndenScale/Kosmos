import { TagType, ActiveTag, ParsedQuery } from '../types/search';

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

// 新的查询解析器类
export class QueryParser {
  /**
   * 解析查询字符串
   * 简化逻辑：只有明确的标签格式（空格+标识符+内容+空格）才被识别为标签
   */
  static parse(query: string): ParsedQuery {
    if (!query.trim()) {
      return {
        text: '',
        must_tags: [],
        must_not_tags: [],
        like_tags: []
      };
    }

    const must_tags: string[] = [];
    const must_not_tags: string[] = [];
    const like_tags: string[] = [];

    // 使用正则表达式匹配标签模式：空格+标识符+非空格内容
    const tagPattern = /\s([+\-~])(\S+)/g;
    let text = query;
    let match;

    // 提取所有标签
    while ((match = tagPattern.exec(query)) !== null) {
      const [fullMatch, operator, tagContent] = match;
      
      switch (operator) {
        case '+':
          must_tags.push(tagContent);
          break;
        case '-':
          must_not_tags.push(tagContent);
          break;
        case '~':
          like_tags.push(tagContent);
          break;
      }
      
      // 从文本中移除这个标签
      text = text.replace(fullMatch, ' ');
    }

    // 清理文本，移除多余的空格
    text = text.replace(/\s+/g, ' ').trim();

    return { text, must_tags, must_not_tags, like_tags };
  }

  /**
   * 构建查询字符串
   */
  static buildQuery(text: string, activeTags: ActiveTag[]): string {
    let query = text;

    activeTags.forEach(({ tag, type }) => {
      switch (type) {
        case TagType.LIKE:
          query += ` ~${tag}`;
          break;
        case TagType.MUST:
          query += ` +${tag}`;
          break;
        case TagType.MUST_NOT:
          query += ` -${tag}`;
          break;
      }
    });

    return query.trim();
  }

  /**
   * 从查询字符串中提取活动标签
   */
  static getActiveTagsFromQuery(query: string): ActiveTag[] {
    const parsed = this.parse(query);
    const activeTags: ActiveTag[] = [];

    parsed.like_tags.forEach(tag => {
      activeTags.push({ tag, type: TagType.LIKE });
    });

    parsed.must_tags.forEach(tag => {
      activeTags.push({ tag, type: TagType.MUST });
    });

    parsed.must_not_tags.forEach(tag => {
      activeTags.push({ tag, type: TagType.MUST_NOT });
    });

    return activeTags;
  }
}