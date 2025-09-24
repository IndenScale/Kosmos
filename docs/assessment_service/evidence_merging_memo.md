# 证据合并功能备忘录

## 概述

本备忘录描述了评估服务中实现的证据合并功能。该功能旨在自动合并同一finding下的重叠、连续或距离较近的证据，以提高评估效率和证据管理质量。

## 功能描述

### 自动化合并
- 该功能在证据提交后自动执行，无需手动触发
- 仅在相同finding下的证据之间进行合并
- 合并条件包括：
  - 行范围重叠
  - 行范围连续
  - 行范围距离小于5行

### 实现位置
- **主实现文件**：`assessment_service/app/services/session_service.py`
- **调用位置**：`assessment_service/app/services/agent_service.py`

## 技术实现

### 合并算法
1. 获取session中的所有finding
2. 对每个finding，获取其所有证据
3. 按文档ID分组证据
4. 对每个文档中的证据，按起始行排序
5. 检查相邻证据的行范围：
   - 如果重叠或连续，则合并
   - 如果距离小于5行，则合并
6. 更新数据库中的证据记录

### 代码结构
```python
def merge_evidence_for_session(db: Session, session_id: UUID) -> None:
    # 实现合并逻辑
    pass
```

### 调用方式
在`add_evidence`函数中，每次添加证据后自动调用：
```python
from .session_service import merge_evidence_for_session
merge_evidence_for_session(db, session_id)
```

## 优势

1. **减少冗余**：合并重叠或连续的证据，减少数据库中的冗余数据
2. **提高效率**：使证据更清晰、更易于理解
3. **保持完整性**：确保合并后的证据仍然准确反映原始信息
4. **自动化**：无需人工干预，自动执行合并

## 注意事项

1. **性能考虑**：合并操作在每次证据提交时执行，需要确保性能影响在可接受范围内
2. **数据一致性**：合并过程中会删除旧证据并添加新证据，确保数据一致性
3. **合并条件**：仅在满足特定条件时才进行合并，避免误合并

## 测试验证

在测试环境中，已验证以下场景：
- 同一finding下的重叠证据合并
- 同一finding下的连续证据合并
- 同一finding下距离小于5行的证据合并
- 多个不同finding的证据独立处理