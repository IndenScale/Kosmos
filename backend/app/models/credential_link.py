import uuid
from sqlalchemy import Column, Integer, ForeignKey, PrimaryKeyConstraint
from sqlalchemy.orm import relationship
from ..models.base import Base, UUIDChar

class KnowledgeSpaceModelCredentialLink(Base):
    __tablename__ = "knowledge_space_model_credential_links"

    knowledge_space_id = Column(UUIDChar, ForeignKey("knowledge_spaces.id", ondelete="CASCADE"), nullable=False)
    credential_id = Column(UUIDChar, ForeignKey("model_credentials.id", ondelete="CASCADE"), nullable=False)
    
    # 路由逻辑第一层：等级。数字越大，优先级越高。
    priority_level = Column(Integer, default=0, nullable=False)
    
    # 路由逻辑第二层：权重。在同一等级内，权重越高的被选中的概率越大。
    weight = Column(Integer, default=1, nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint('knowledge_space_id', 'credential_id'),
    )

    # --- Relationships ---
    knowledge_space = relationship("KnowledgeSpace", back_populates="credential_links")
    credential = relationship("ModelCredential", back_populates="knowledge_space_links")
