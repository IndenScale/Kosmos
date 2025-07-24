# app/models/index.py

import json
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.ext.hybrid import hybrid_property
from app.db.database import Base

class Index(Base):
    """
    索引条目模型 (能指层的表达)。
    
    此模型专注于在 Milvus 向量数据库中表示 Fragment 的可检索形式。
    它包含了用于搜索和召回的关键信息。
    
    注意：此模型主要用于定义 Milvus Collection 的结构和 ORM 映射。
          实际的数据库操作 (CRUD) 将主要通过 Milvus SDK 进行。
          SQL 中可能只存储最基本的关联信息 (如 fragment_id, kb_id) 作为后备。
    """
    __tablename__ = "index_entries"  # 可以根据实际存储方式调整表名
    # 如果需要在 SQL 中存储备份信息，可以启用以下约束和字段
    # __table_args__ = (
    #     UniqueConstraint('kb_id', 'fragment_id', name='uq_index_kb_fragment'),
    #     {'extend_existing': True}
    # )

    # 注意：Milvus 是主存储，这里的 ORM 映射主要用于 Schema 定义和可能的辅助查询
    # 如果完全不使用 SQL 存储 Index 条目，这部分可以简化或仅用于类型提示和 Schema 管理

    id = Column(String, primary_key=True) # UUID, 与 Fragment.id 对应
    
    # 关联到 Knowledge Base
    kb_id = Column(String, ForeignKey("knowledge_bases.id"), nullable=False)
    
    # 关联到 Fragment (稳固的能指)
    fragment_id = Column(String, ForeignKey("fragments.id"), nullable=False)

    # LLM生成的标签 (JSON数组格式)
    # 存储在 Milvus 中，用于基于标签的过滤和召回
    tags = Column(Text, nullable=True) 

    # 内容预览/摘要 (为减少数据库查询次数而冗余存储)
    # TextFragment: 存储原始文本内容
    # Image/VideoFragment: 存储 AI 生成的描述
    content = Column(Text, nullable=False) 

    # 创建时间
    created_at = Column(DateTime, default=func.now())
    
    # 更新时间 (例如，tags 被 SDTM 更新时)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


    # --- 以下字段主要用于 Milvus，不一定直接映射为 SQL 字段 ---
    
    # 向量嵌入 (存储在 Milvus 中)
    # 在 ORM 对象中可以存在，但在 SQL 映射中通常忽略或作为占位符
    # embedding = Column(...) # Milvus specific, type and mapping handled by Milvus SDK


    @hybrid_property
    def tags_list(self):
        """
        将 tags (JSON 字符串) 转换为 Python 列表的便捷属性。
        """
        if self.tags:
            try:
                return json.loads(self.tags)
            except (json.JSONDecodeError, TypeError):
                return []
        return []

    @tags_list.setter
    def tags_list(self, value):
        """
        将 Python 列表设置为 tags (JSON 字符串)。
        """
        if value is not None:
            self.tags = json.dumps(value, ensure_ascii=False)
        else:
            self.tags = None
