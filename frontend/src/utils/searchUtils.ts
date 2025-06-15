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

// 新的查询解析器类
export class QueryParser {
  /**
   * 解析查询字符串
   * 规则：当且仅当输入中带有标签标识符（+-~）同时前导为空格时会被视作标签分割记号
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
    let text = '';
    
    // 使用正则表达式匹配空格后跟标识符的模式
    // 匹配模式：空格 + 标识符(+/-/~) + 标签内容
    const tagPattern = /\s([+~-])(\S+)/g;
    let lastIndex = 0;
    let match;
    
    // 提取所有标签
    while ((match = tagPattern.exec(query)) !== null) {
      const [fullMatch, operator, tag] = match;
      const matchStart = match.index;
      
      // 如果这是第一个匹配，将之前的内容作为文本
      if (lastIndex === 0 && matchStart > 0) {
        text = query.substring(0, matchStart).trim();
      }
      
      // 根据操作符分类标签
      switch (operator) {
        case '+':
          must_tags.push(tag);
          break;
        case '-':
          must_not_tags.push(tag);
          break;
        case '~':
          like_tags.push(tag);
          break;
      }
      
      lastIndex = matchStart + fullMatch.length;
    }
    
    // 如果没有找到任何标签，整个查询都是文本
    if (lastIndex === 0) {
      text = query.trim();
    } else if (text === '') {
      // 如果文本为空但有标签，取第一个标签之前的内容作为文本
      const firstMatch = query.match(/\s[+~-]\S+/);
      if (firstMatch) {
        text = query.substring(0, firstMatch.index).trim();
      }
    }

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