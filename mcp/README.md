# Kosmos MCP Server

这是一个模块化的MCP (Model Context Protocol) Server，为Kosmos知识库系统提供标准化的API接口。

## 架构概述

MCP Server采用模块化设计，主要组件包括：

- **core/kosmos_client.py**: Kosmos API客户端，处理认证和HTTP请求
- **core/tools.py**: MCP工具定义，封装Kosmos的核心功能
- **core/tool_handler.py**: 工具处理器，执行具体的API调用
- **core/response_formatter.py**: 响应格式化器，简化API响应
- **server.py**: MCP Server主文件，集成所有模块

## 主要功能

### 知识库管理
- `list_knowledge_bases`: 列出所有知识库
- `get_knowledge_base`: 获取知识库详情
- `create_knowledge_base`: 创建新知识库

### 文档管理
- `list_documents`: 列出知识库中的文档
- `get_document`: 获取文档详情

### 搜索功能
- `search_knowledge_base`: 语义搜索
- `get_fragment`: 获取文档片段详情

### 解析功能
- `parse_document`: 解析文档

### 任务管理
- `list_jobs`: 列出任务
- `get_job`: 获取任务详情

### 统计信息
- `get_kb_stats`: 获取知识库统计
- `get_fragment_types`: 获取片段类型

## 配置

1. 复制 `.env_example` 为 `.env`
2. 设置环境变量：
   ```
   KOSMOS_BASE_URL=http://localhost:8000
   KOSMOS_USERNAME=your_username
   KOSMOS_PASSWORD=your_password
   ```

3. 复制 `mcp_config_example.json` 为 `mcp_config.json`
4. 根据需要调整配置

## 运行

```bash
python run_server.py
```

## MCP Client配置

在MCP Client中添加以下配置：

```json
{
  "mcpServers": {
    "kosmos-knowledge-base": {
      "command": "python",
      "args": ["path/to/kosmos/mcp/run_server.py"],
      "env": {
        "KOSMOS_BASE_URL": "http://localhost:8000",
        "KOSMOS_USERNAME": "your_username",
        "KOSMOS_PASSWORD": "your_password"
      }
    }
  }
}
```

## 特性

- **模块化设计**: 清晰的代码组织和职责分离
- **简化响应**: 隐藏操作细节，保留核心语义
- **标准化接口**: 符合MCP协议规范
- **错误处理**: 完善的错误处理和用户友好的错误信息
- **认证支持**: 安全的Kosmos API认证