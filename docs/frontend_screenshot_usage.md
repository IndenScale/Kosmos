# 前端截图功能使用说明

## 功能概述

前端搜索界面现已支持显示搜索结果对应的文档页面截图，用户可以直观地查看文档内容的原始样式。

## 主要变更

### 1. 类型定义更新 (`frontend/src/types/search.ts`)

```typescript
export interface SearchResult {
  chunk_id: string;
  document_id: string;
  content: string;
  tags: string[];
  score: number;
  screenshot_ids?: string[];  // 新增：截图ID列表
}

export interface ScreenshotInfo {
  id: string;
  document_id: string;
  page_number: number;
  width?: number;
  height?: number;
  created_at?: string;
  file_exists?: boolean;
}
```

### 2. 搜索服务扩展 (`frontend/src/services/searchService.ts`)

新增截图相关服务方法：

```typescript
// 获取截图信息
getScreenshotInfo: async (screenshotId: string): Promise<ScreenshotInfo>

// 批量获取截图信息
getScreenshotsBatch: async (screenshotIds: string[]): Promise<ScreenshotInfo[]>

// 获取截图图片URL
getScreenshotImageUrl: (screenshotId: string): string

// 获取文档的所有截图
getDocumentScreenshots: async (documentId: string): Promise<ScreenshotInfo[]>
```

### 3. 搜索结果卡片组件更新 (`frontend/src/components/SemanticSearch/SearchResultCard.tsx`)

#### 新增功能：
- **自动加载截图**：当搜索结果包含`screenshot_ids`时，自动批量获取截图信息
- **智能显示**：
  - 单个截图：直接展示，显示页码标识
  - 多个截图：可展开/收起的轮播图形式
- **优雅的加载状态**：显示加载中和错误处理
- **响应式设计**：适配不同屏幕尺寸

#### 截图显示效果：
- **单个截图**：直接在卡片中显示，带页码标识
- **多个截图**：默认收起，点击"展开"按钮查看轮播图
- **交互体验**：图片hover效果、平滑过渡动画

## 使用场景

### 1. 文档搜索
当用户搜索文档内容时，如果匹配的chunk来自支持截图的文档（PDF、DOCX、PPTX等），搜索结果会自动显示对应页面的截图。

### 2. 截图查看
- **单页文档**：截图直接显示在搜索结果中
- **多页文档**：点击"展开"按钮查看轮播图，可以浏览所有相关页面
- **页码标识**：每个截图都标明对应的页码

### 3. 视觉对比
用户可以同时查看文本内容和原始页面截图，便于验证搜索结果的准确性和完整性。

## CSS样式说明

新增CSS模块 (`SearchResultCard.module.css`) 提供了：

- **截图容器样式**：统一的容器外观和间距
- **轮播图样式**：优雅的图片切换效果
- **响应式设计**：适配移动设备和桌面设备
- **交互效果**：hover动画和过渡效果

## 性能优化

### 1. 懒加载
- 截图信息只在需要时才加载
- 使用批量API减少请求次数

### 2. 缓存机制
- 图片自动缓存，避免重复加载
- 截图信息缓存，提升用户体验

### 3. 错误处理
- 优雅的加载失败提示
- 占位符图片防止布局跳动

## 后续扩展

- **缩略图预览**：在多个截图时显示缩略图网格
- **全屏查看**：点击截图放大查看
- **下载功能**：允许用户下载截图
- **标注功能**：在截图上高亮显示搜索匹配位置

## 注意事项

1. **网络依赖**：截图加载依赖网络连接，慢网络下可能影响体验
2. **存储空间**：截图文件较大，需要关注服务器存储空间
3. **浏览器兼容性**：使用了现代CSS特性，建议使用最新浏览器
4. **移动端适配**：在小屏设备上截图可能需要横向滚动查看 