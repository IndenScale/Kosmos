/**
 * 文件上传配置
 * 定义不同文件类型的大小限制和支持的MIME类型
 */

export enum FileCategory {
  PDF = 'pdf',
  OFFICE = 'office',
  TEXT = 'text',
  IMAGE = 'image',
  CODE = 'code',
}

export interface FileSizeLimits {
  [FileCategory.PDF]: number;
  [FileCategory.OFFICE]: number;
  [FileCategory.TEXT]: number;
  [FileCategory.IMAGE]: number;
  [FileCategory.CODE]: number;
}

export class UploadConfig {
  // 文件大小限制 (单位: MB)
  static readonly FILE_SIZE_LIMITS: FileSizeLimits = {
    [FileCategory.PDF]: 500,      // PDF文件限制500MB
    [FileCategory.OFFICE]: 500,   // Office文件限制500MB
    [FileCategory.TEXT]: 50,      // 文本文件限制50MB
    [FileCategory.IMAGE]: 20,     // 图片文件限制20MB
    [FileCategory.CODE]: 10,      // 代码文件限制10MB
  };

  // MIME类型到文件类别的映射
  static readonly MIME_TYPE_MAPPING: Record<string, FileCategory> = {
    // PDF文件
    'application/pdf': FileCategory.PDF,
    
    // Office文件
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': FileCategory.OFFICE, // .docx
    'application/msword': FileCategory.OFFICE, // .doc
    'application/vnd.openxmlformats-officedocument.presentationml.presentation': FileCategory.OFFICE, // .pptx
    'application/vnd.ms-powerpoint': FileCategory.OFFICE, // .ppt
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': FileCategory.OFFICE, // .xlsx
    'application/vnd.ms-excel': FileCategory.OFFICE, // .xls
    
    // 文本文件
    'text/plain': FileCategory.TEXT,
    'text/markdown': FileCategory.TEXT,
    'text/csv': FileCategory.TEXT,
    'application/json': FileCategory.TEXT,
    'application/xml': FileCategory.TEXT,
    'text/xml': FileCategory.TEXT,
    'application/yaml': FileCategory.TEXT,
    'text/yaml': FileCategory.TEXT,
    
    // 图片文件
    'image/png': FileCategory.IMAGE,
    'image/jpeg': FileCategory.IMAGE,
    'image/jpg': FileCategory.IMAGE,
    'image/gif': FileCategory.IMAGE,
    'image/bmp': FileCategory.IMAGE,
    'image/webp': FileCategory.IMAGE,
    'image/svg+xml': FileCategory.IMAGE,
    
    // 代码文件 (通过扩展名识别)
    'text/x-python': FileCategory.CODE,
    'application/javascript': FileCategory.CODE,
    'text/javascript': FileCategory.CODE,
    'application/typescript': FileCategory.CODE,
    'text/x-java-source': FileCategory.CODE,
    'text/x-c': FileCategory.CODE,
    'text/x-c++': FileCategory.CODE,
    'text/html': FileCategory.CODE,
    'text/css': FileCategory.CODE,
  };

  // 文件扩展名到文件类别的映射
  static readonly EXTENSION_MAPPING: Record<string, FileCategory> = {
    // PDF文件
    '.pdf': FileCategory.PDF,
    
    // Office文件
    '.docx': FileCategory.OFFICE,
    '.doc': FileCategory.OFFICE,
    '.pptx': FileCategory.OFFICE,
    '.ppt': FileCategory.OFFICE,
    '.xlsx': FileCategory.OFFICE,
    '.xls': FileCategory.OFFICE,
    
    // 文本文件
    '.txt': FileCategory.TEXT,
    '.md': FileCategory.TEXT,
    '.markdown': FileCategory.TEXT,
    '.csv': FileCategory.TEXT,
    '.json': FileCategory.TEXT,
    '.xml': FileCategory.TEXT,
    '.yaml': FileCategory.TEXT,
    '.yml': FileCategory.TEXT,
    '.log': FileCategory.TEXT,
    '.cfg': FileCategory.TEXT,
    '.conf': FileCategory.TEXT,
    '.ini': FileCategory.TEXT,
    
    // 图片文件
    '.png': FileCategory.IMAGE,
    '.jpg': FileCategory.IMAGE,
    '.jpeg': FileCategory.IMAGE,
    '.gif': FileCategory.IMAGE,
    '.bmp': FileCategory.IMAGE,
    '.webp': FileCategory.IMAGE,
    '.svg': FileCategory.IMAGE,
    
    // 代码文件
    '.py': FileCategory.CODE,
    '.js': FileCategory.CODE,
    '.ts': FileCategory.CODE,
    '.tsx': FileCategory.CODE,
    '.jsx': FileCategory.CODE,
    '.java': FileCategory.CODE,
    '.c': FileCategory.CODE,
    '.cpp': FileCategory.CODE,
    '.cc': FileCategory.CODE,
    '.cxx': FileCategory.CODE,
    '.h': FileCategory.CODE,
    '.hpp': FileCategory.CODE,
    '.cs': FileCategory.CODE,
    '.php': FileCategory.CODE,
    '.rb': FileCategory.CODE,
    '.go': FileCategory.CODE,
    '.rs': FileCategory.CODE,
    '.swift': FileCategory.CODE,
    '.kt': FileCategory.CODE,
    '.scala': FileCategory.CODE,
    '.html': FileCategory.CODE,
    '.htm': FileCategory.CODE,
    '.css': FileCategory.CODE,
    '.scss': FileCategory.CODE,
    '.sass': FileCategory.CODE,
    '.less': FileCategory.CODE,
    '.sql': FileCategory.CODE,
    '.sh': FileCategory.CODE,
    '.bash': FileCategory.CODE,
    '.zsh': FileCategory.CODE,
    '.fish': FileCategory.CODE,
    '.ps1': FileCategory.CODE,
    '.bat': FileCategory.CODE,
    '.cmd': FileCategory.CODE,
    '.dockerfile': FileCategory.CODE,
    '.makefile': FileCategory.CODE,
    '.r': FileCategory.CODE,
    '.m': FileCategory.CODE,
    '.pl': FileCategory.CODE,
    '.lua': FileCategory.CODE,
    '.vim': FileCategory.CODE,
    '.toml': FileCategory.CODE,
  };

  /**
   * 根据文件名和MIME类型确定文件类别
   */
  static getFileCategory(filename: string, mimeType?: string): FileCategory {
    // 首先尝试通过MIME类型判断
    if (mimeType && this.MIME_TYPE_MAPPING[mimeType]) {
      return this.MIME_TYPE_MAPPING[mimeType];
    }

    // 然后通过文件扩展名判断
    const fileExtension = this.getFileExtension(filename);
    if (this.EXTENSION_MAPPING[fileExtension]) {
      return this.EXTENSION_MAPPING[fileExtension];
    }

    // 默认按文本文件处理
    return FileCategory.TEXT;
  }

  /**
   * 获取文件扩展名
   */
  static getFileExtension(filename: string): string {
    const lastDotIndex = filename.lastIndexOf('.');
    if (lastDotIndex === -1) return '';
    return filename.slice(lastDotIndex).toLowerCase();
  }

  /**
   * 获取文件的最大允许大小（字节）
   */
  static getMaxFileSize(filename: string, mimeType?: string): number {
    const category = this.getFileCategory(filename, mimeType);
    const maxSizeMB = this.FILE_SIZE_LIMITS[category];
    return maxSizeMB * 1024 * 1024; // 转换为字节
  }

  /**
   * 验证文件大小是否符合限制
   */
  static validateFileSize(filename: string, fileSize: number, mimeType?: string): { isValid: boolean; error?: string } {
    const category = this.getFileCategory(filename, mimeType);
    const maxSize = this.getMaxFileSize(filename, mimeType);
    const maxSizeMB = this.FILE_SIZE_LIMITS[category];

    if (fileSize > maxSize) {
      const currentSizeMB = (fileSize / 1024 / 1024).toFixed(1);
      return {
        isValid: false,
        error: `文件大小超出限制。${this.getCategoryDisplayName(category)}文件最大允许${maxSizeMB}MB，当前文件大小为${currentSizeMB}MB`
      };
    }

    return { isValid: true };
  }

  /**
   * 获取文件类别的显示名称
   */
  static getCategoryDisplayName(category: FileCategory): string {
    const displayNames = {
      [FileCategory.PDF]: 'PDF',
      [FileCategory.OFFICE]: 'Office',
      [FileCategory.TEXT]: '文本',
      [FileCategory.IMAGE]: '图片',
      [FileCategory.CODE]: '代码',
    };
    return displayNames[category];
  }

  /**
   * 获取所有支持的文件扩展名
   */
  static getSupportedExtensions(): string[] {
    return Object.keys(this.EXTENSION_MAPPING);
  }

  /**
   * 获取所有支持的MIME类型
   */
  static getSupportedMimeTypes(): string[] {
    return Object.keys(this.MIME_TYPE_MAPPING);
  }

  /**
   * 检查文件是否被支持
   */
  static isSupportedFile(filename: string, mimeType?: string): boolean {
    // 检查MIME类型
    if (mimeType && this.MIME_TYPE_MAPPING[mimeType]) {
      return true;
    }

    // 检查文件扩展名
    const fileExtension = this.getFileExtension(filename);
    return !!this.EXTENSION_MAPPING[fileExtension];
  }

  /**
   * 验证文件类型和大小
   */
  static validateFile(file: File): { isValid: boolean; error?: string } {
    // 验证文件类型
    if (!this.isSupportedFile(file.name, file.type)) {
      const supportedExtensions = this.getSupportedExtensions().join(', ');
      return {
        isValid: false,
        error: `不支持的文件类型。支持的格式：${supportedExtensions}`
      };
    }

    // 验证文件大小
    return this.validateFileSize(file.name, file.size, file.type);
  }

  /**
   * 获取文件类别的大小限制信息
   */
  static getFileSizeLimitInfo(): Array<{ category: FileCategory; displayName: string; limitMB: number }> {
    return Object.entries(this.FILE_SIZE_LIMITS).map(([category, limitMB]) => ({
      category: category as FileCategory,
      displayName: this.getCategoryDisplayName(category as FileCategory),
      limitMB,
    }));
  }
}