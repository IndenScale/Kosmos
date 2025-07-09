# 文档截图功能说明

## 功能概述

根据最新需求，系统已增加文档页面截图功能，在搜索文档时不仅返回chunk内容，还会返回对应的页面截图。

## 实现方案

### 1. 文档处理流程
- 对需要提供截图的文档（docx、pdf、ppt等），统一转化为PDF中间格式
- 对PDF的每一页进行渲染和截图，生成高清PNG图片
- 提取PDF中的嵌入图片，调用VLM进行理解和描述
- 将PDF转化为markdown，并将图片描述嵌入到文本中
- 进行chunking，根据chunk中包含的页码，将页面截图关联到chunk上

### 2. 数据库变更
- 添加了`page_screenshots`表，存储页面截图信息
- 扩展了`chunks`表，添加`page_screenshot_ids`字段存储关联的截图ID列表

### 3. API接口

#### 获取截图信息
```
GET /screenshots/{screenshot_id}/info
```
返回截图的元数据信息（不包含文件内容）

#### 获取截图图片
```
GET /screenshots/{screenshot_id}/image
```
返回截图图片文件（PNG格式）

#### 获取文档的所有截图
```
GET /screenshots/document/{document_id}
```
返回指定文档的所有页面截图信息

#### 批量获取截图信息
```
POST /screenshots/batch
```
批量获取多个截图的信息

### 4. 搜索结果变更
搜索结果中的chunk现在包含`screenshot_ids`字段，提供关联的页面截图ID列表。

## 安装依赖

运行安装脚本：
```bash
chmod +x install_screenshot_deps.sh
./install_screenshot_deps.sh
```

或手动安装：
```bash
# 激活uv虚拟环境
source .venv/bin/activate

# 安装Python依赖
uv pip install PyMuPDF>=1.23.0 pdf2image>=3.1.0 python-docx>=0.8.11 python-pptx>=0.6.21

# 安装系统依赖（Ubuntu/Debian）
sudo apt-get install poppler-utils libreoffice

# 安装系统依赖（CentOS/RHEL）
sudo yum install poppler-utils libreoffice

# 安装系统依赖（macOS）
brew install poppler
brew install --cask libreoffice
```

## 文件结构

### 新增文件
- `app/models/page_screenshot.py` - 页面截图数据模型
- `app/processors/pdf_processor.py` - PDF处理器，支持页面截图
- `app/services/screenshot_service.py` - 截图服务
- `app/routers/screenshots.py` - 截图API路由

### 修改文件
- `app/models/chunk.py` - 添加截图ID字段
- `app/services/ingestion_service.py` - 集成截图处理流程
- `app/services/search_service.py` - 搜索结果包含截图信息
- `app/processors/processor_factory.py` - 添加PDF处理器
- `app/main.py` - 注册截图路由
- `requirements.txt` - 添加新的依赖包

## 使用示例

### 1. 文档摄入
上传支持的文档格式（PDF、DOCX、PPTX等），系统会自动：
- 转换为PDF中间格式
- 生成页面截图
- 提取和理解嵌入图片
- 创建chunks并关联截图

### 2. 搜索文档
搜索结果现在包含截图信息：
```json
{
  "results": [
    {
      "chunk_id": "xxx",
      "document_id": "xxx",
      "content": "文档内容...",
      "tags": ["标签1", "标签2"],
      "score": 0.95,
      "screenshot_ids": ["screenshot_id_1", "screenshot_id_2"]
    }
  ]
}
```

### 3. 获取截图
使用screenshot_id从搜索结果中获取对应的页面截图：
```bash
# 获取截图信息
curl -H "Authorization: Bearer <token>" \
  http://localhost:8000/screenshots/screenshot_id_1/info

# 获取截图图片
curl -H "Authorization: Bearer <token>" \
  http://localhost:8000/screenshots/screenshot_id_1/image \
  -o page_screenshot.png
```

## 注意事项

1. **存储空间**: 页面截图会占用较多存储空间，建议定期清理不需要的截图
2. **性能**: PDF转换和截图生成是CPU密集型操作，大文档处理时间较长
3. **依赖**: 需要安装系统级依赖（poppler-utils、LibreOffice）
4. **格式支持**: 主要支持PDF、DOCX、PPTX格式，其他格式可能需要额外配置

## 故障排除

### 常见问题
1. **PDF处理失败**: 检查是否安装了PyMuPDF和poppler-utils
2. **文档转换失败**: 检查是否安装了LibreOffice
3. **截图生成失败**: 确认pdf2image和相关系统依赖已正确安装
4. **VLM图片理解失败**: 检查AI服务配置和网络连接

### 日志查看
查看应用日志了解详细错误信息：
```bash
tail -f backend.log
``` 