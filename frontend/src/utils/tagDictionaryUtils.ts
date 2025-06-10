import { TagDictionary } from '../types/knowledgeBase';

// 递归清洗标签字典的工具函数
export const cleanTagDictionary = (tagDict: any): TagDictionary => {
  const cleaned: TagDictionary = {};

  const cleanNode = (node: any): TagDictionary | string[] => {
    if (Array.isArray(node)) {
      return node.filter(tag => typeof tag === 'string' && tag.trim() !== '').map(tag => tag.trim());
    } else if (typeof node === 'object' && node !== null) {
      const cleanedObj: TagDictionary = {};
      Object.entries(node).forEach(([key, value]) => {
        const cleanedValue = cleanNode(value);
        if (Array.isArray(cleanedValue) && cleanedValue.length > 0) {
          cleanedObj[key] = cleanedValue;
        } else if (typeof cleanedValue === 'object' && Object.keys(cleanedValue).length > 0) {
          cleanedObj[key] = cleanedValue;
        }
      });
      return cleanedObj;
    } else if (typeof node === 'string') {
      try {
        const parsed = JSON.parse(node);
        return cleanNode(parsed);
      } catch {
        return node.trim() ? [node.trim()] : [];
      }
    } else {
      const str = String(node).trim();
      return str ? [str] : [];
    }
  };

  Object.entries(tagDict || {}).forEach(([key, value]) => {
    const cleanedValue = cleanNode(value);
    if (Array.isArray(cleanedValue) && cleanedValue.length > 0) {
      cleaned[key] = cleanedValue;
    } else if (typeof cleanedValue === 'object' && Object.keys(cleanedValue).length > 0) {
      cleaned[key] = cleanedValue;
    }
  });

  return cleaned;
};

// 递归计算标签总数的辅助函数
export const countTags = (tagDict: TagDictionary): number => {
  let count = 0;
  Object.values(tagDict).forEach(value => {
    if (Array.isArray(value)) {
      count += value.length;
    } else {
      count += countTags(value);
    }
  });
  return count;
};

// 递归查找并移除标签的辅助函数
export const removeTagFromDict = (tagDict: TagDictionary, targetCategory: string, targetTag: string): TagDictionary => {
  const newDict: TagDictionary = {};

  Object.entries(tagDict).forEach(([key, value]) => {
    if (Array.isArray(value)) {
      if (key === targetCategory) {
        const filteredTags = value.filter(tag => tag !== targetTag);
        if (filteredTags.length > 0) {
          newDict[key] = filteredTags;
        }
      } else {
        newDict[key] = [...value];
      }
    } else {
      const nestedResult = removeTagFromDict(value, targetCategory, targetTag);
      if (Object.keys(nestedResult).length > 0) {
        newDict[key] = nestedResult;
      }
    }
  });

  return newDict;
};

// 递归添加标签的辅助函数
export const addTagToDict = (tagDict: TagDictionary, category: string, tag: string): TagDictionary => {
  const newDict = { ...tagDict };

  if (!newDict[category]) {
    newDict[category] = [];
  }

  if (Array.isArray(newDict[category])) {
    const currentTags = newDict[category] as string[];
    if (!currentTags.includes(tag)) {
      newDict[category] = [...currentTags, tag];
    }
  }

  return newDict;
};