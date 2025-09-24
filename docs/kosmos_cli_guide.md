# Kosmos CLI 使用指南

本指南将帮助您快速了解如何使用 Kosmos CLI 工具来管理知识库和访问文档内容。

## 1. 注册与登录

### 注册
现在可以通过CLI注册新用户：

```bash
python -m cli.main user register --new-username <用户名> --email <邮箱> --display-name <显示名称> --new-password <密码>
```

### 登录
使用以下命令登录到 Kosmos 平台：

```bash
python -m cli.main login --username <用户名> --password <密码>
```

登录成功后，系统会保存会话凭证，后续命令将自动使用这些凭证。

## 2. 用户管理

### 查看用户列表
列出系统中的所有用户：

```bash
python -m cli.main user list
```

### 查看当前用户信息
查看当前登录用户的详细信息：

```bash
python -m cli.main user me
```

### 删除用户
删除指定用户账户（需要管理员权限）：

```bash
python -m cli.main user delete <用户ID> --force
```

## 2. 查看知识空间和文档元数据

### 查看知识空间
列出所有知识空间：

```bash
python -m cli.main knowledge-space list
```

### 查看文档元数据
列出指定知识空间中的所有文档：

```bash
python -m cli.main documents --ks-id <知识空间ID>
```

### 删除文档
删除符合条件的文档：

```bash
python -m cli.main documents delete --ks-id <知识空间ID> --filename <文件名>
```

使用 `--force` 参数可跳过确认提示：

```bash
python -m cli.main documents delete --ks-id <知识空间ID> --filename <文件名> --force
```

## 3. 内容访问方式

### 3.1 搜索 (Search)
在知识空间中进行全文搜索：

```bash
python -m cli.main search --ks-id <知识空间ID> "<搜索关键词>"
```

### 3.2 模式匹配 (Grep)
在知识空间中搜索特定模式：

```bash
python -m cli.main grep --ks-id <知识空间ID> "<搜索模式>"
```

### 3.3 读取文档内容 (Read)
读取特定文档的完整内容：

```bash
python -m cli.main read --ks-id <知识空间ID> --doc-id <文档ID>
```

## 4. 资产分析结果访问

### 4.1 查看文档资产信息
使用read命令时，会同时返回文档中所有资产的详细描述信息。

### 4.2 查看摄入状态
查看知识空间的摄入状态，包括文档处理进度：

```bash
python -m cli.main ingestion status --ks-id <知识空间ID>
```

## 5. 实用技巧

### 5.1 使用环境变量
可以通过设置环境变量来避免在每次命令中输入用户名和密码：

```bash
export KOSMOS_USERNAME=<用户名>
export KOSMOS_PASSWORD=<密码>
export KOSMOS_KS_ID=<知识空间ID>
```

### 5.2 限制输出长度
对于大型文档，可以使用 `--max-output-chars` 参数限制输出长度：

```bash
python -m cli.main read --ks-id <知识空间ID> --doc-id <文档ID> --max-output-chars 10000
```

## 6. 常见命令示例

### 列出知识空间中的所有文档并筛选有资产描述的文档
```bash
python -m cli.main documents --ks-id 8c2b40ef-8010-4ced-95ca-d7d0741aac6f | grep -A 10 -B 5 "described"
```

### 在知识空间中搜索包含特定关键词的文档
```bash
python -m cli.main search --ks-id 8c2b40ef-8010-4ced-95ca-d7d0741aac6f "删除集群"
```

### 在特定文档中搜索模式
```bash
python -m cli.main grep --ks-id 8c2b40ef-8010-4ced-95ca-d7d0741aac6f --doc-id 71b5ea38-2a9a-4105-bc23-57bd18703421 "删除集群"
```

### 读取文档并显示上下文
```bash
python -m cli.main grep --ks-id 8c2b40ef-8010-4ced-95ca-d7d0741aac6f -C 3 "删除集群"
```