import { ParsedQuery, TagType, ActiveTag } from '../types/search';

export class QueryParser {
  static parse(query: string): ParsedQuery {
    const parts = query.trim().split(/\s+/);
    
    if (!parts.length) {
      return {
        text: '',
        must_tags: [],
        must_not_tags: [],
        like_tags: []
      };
    }

    // 第一个部分作为文本查询
    const text = parts[0];
    
    const must_tags: string[] = [];
    const must_not_tags: string[] = [];
    const like_tags: string[] = [];

    // 解析剩余部分的标签
    for (let i = 1; i < parts.length; i++) {
      const part = parts[i];
      if (part.startsWith('+')) {
        must_tags.push(part.slice(1));
      } else if (part.startsWith('-')) {
        must_not_tags.push(part.slice(1));
      } else if (part.startsWith('~')) {
        like_tags.push(part.slice(1));
      } else {
        // 无前缀默认为like_tags
        like_tags.push(part);
      }
    }

    return { text, must_tags, must_not_tags, like_tags };
  }

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