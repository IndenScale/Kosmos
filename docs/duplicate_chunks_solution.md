# 重复搜索结果问题解决方案

## 问题描述

在使用Kosmos系统时，可能会遇到重复搜索结果的问题，主要表现为：

1. **相同文档的不同页面内容相似**：如"第2页 图2 隐私政策2"和"第3页 图3 隐私政策3"
2. **同一文档被多次摄入**：同一个文档在不同时间被重复摄入，产生重复的chunks
3. **相似内容的语义重复**：不同文档中包含相似的内容片段

## 根本原因

1. **缺少文档摄入前的重复检查**：系统没有在摄入前检查同一文档是否已经存在
2. **去重机制不够完善**：虽然有去重功能，但主要针对搜索结果，而不是摄入时去重
3. **相似内容的语义去重阈值过低**：不同页面的相似内容没有被有效去重

## 解决方案

### 1. 摄入时去重（预防性措施）

#### 1.1 文档重复检查
- 在摄入前检查是否已存在相同文档
- 基于文件名和内容哈希进行检查
- 提供`force_reindex`选项强制重新索引

#### 1.2 Chunk去重
- 在文本分割后进行chunk去重
- 使用内容哈希进行精确去重
- 使用文本相似度算法进行语义去重
- 默认相似度阈值：0.95

### 2. 搜索时去重（保护性措施）

#### 2.1 更新去重配置
```python
# 新的去重配置
semantic_similarity_threshold: 0.85  # 提高语义相似度阈值
min_content_length: 30  # 提高最小内容长度
score_diff_threshold: 0.02  # 搜索结果分数差异阈值（2%）
content_similarity_threshold: 0.9  # 内容相似度阈值（90%）
```

#### 2.2 改进去重算法
- 基于搜索分数的相似度检查
- 字符级n-gram相似度计算
- 保留最相关的结果

### 3. 清理现有重复数据

#### 3.1 使用API清理
```bash
# 清理知识库中的重复chunks
POST /api/v1/kbs/{kb_id}/cleanup-duplicates
{
  "similarity_threshold": 0.95
}
```

#### 3.2 重新摄入文档
```bash
# 强制重新摄入文档
POST /api/v1/kbs/{kb_id}/documents/{document_id}/reingest
{
  "skip_tagging": true
}
```

## 使用指南

### 1. 预防重复摄入

```python
# 启动摄入时检查重复
await ingestion_service.start_ingestion_job(
    kb_id=kb_id,
    document_id=document_id,
    user_id=user_id,
    skip_tagging=False,
    force_reindex=False  # 默认不强制重新索引
)
```

### 2. 清理现有重复

```python
# 清理知识库中的重复chunks
result = await ingestion_service.cleanup_duplicate_chunks(
    kb_id=kb_id,
    similarity_threshold=0.95
)
```

### 3. 配置去重参数

通过环境变量配置去重参数：
```bash
# 去重配置
DEDUP_ENABLED=true
DEDUP_LITERAL_ENABLED=true
DEDUP_SEMANTIC_ENABLED=true
DEDUP_SEMANTIC_THRESHOLD=0.85
DEDUP_MIN_LENGTH=30
DEDUP_SCORE_DIFF_THRESHOLD=0.02
DEDUP_CONTENT_SIMILARITY_THRESHOLD=0.9
```

## 最佳实践

### 1. 摄入前检查
- 在摄入新文档前，先检查是否已存在相同文档
- 使用文件名和内容哈希进行检查
- 避免重复摄入相同内容

### 2. 定期清理
- 定期运行重复chunks清理任务
- 监控知识库的chunks数量和质量
- 及时处理发现的重复内容

### 3. 合理配置
- 根据业务需求调整相似度阈值
- 平衡去重效果和内容完整性
- 监控去重效果并及时调整

### 4. 监控和维护
- 定期检查搜索结果质量
- 监控重复率指标
- 及时处理用户反馈的重复问题

## 技术细节

### 1. 文本相似度计算
使用字符级n-gram的Jaccard相似度：
```python
def get_ngrams(text, n=3):
    return set(text[i:i+n] for i in range(len(text) - n + 1))

similarity = len(ngrams1 & ngrams2) / len(ngrams1 | ngrams2)
```

### 2. 内容哈希
使用MD5哈希进行精确去重：
```python
content_hash = hashlib.md5(content.encode('utf-8')).hexdigest()
```

### 3. 批量删除
从SQLite和Milvus中批量删除重复chunks：
```python
# SQLite删除
for chunk in chunks_to_remove:
    db.delete(chunk)

# Milvus删除
milvus_repo.delete_chunks_by_ids(collection_name, chunk_ids)
```

## 注意事项

1. **数据备份**：在执行清理操作前，建议备份重要数据
2. **性能影响**：大规模去重可能影响系统性能，建议在低峰时段执行
3. **阈值调整**：相似度阈值需要根据实际业务场景调整
4. **用户通知**：清理操作可能影响搜索结果，应提前通知用户

## 故障排除

### 1. 清理失败
- 检查数据库连接
- 确认Milvus服务正常
- 查看错误日志

### 2. 去重效果不佳
- 调整相似度阈值
- 检查文本预处理逻辑
- 验证n-gram算法参数

### 3. 性能问题
- 分批处理大量数据
- 优化数据库查询
- 考虑异步处理 