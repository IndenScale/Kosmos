import uuid
import enum
from datetime import datetime
from sqlalchemy import Column, String, JSON, ForeignKey, Enum as SQLAlchemyEnum, DateTime
from .base import Base, UUIDChar

class ProposalType(str, enum.Enum):
    ADD_NODE = "add_node"
    MODIFY_NODE = "modify_node"
    MOVE_NODE = "move_node"

class ProposalStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"

class OntologyChangeProposal(Base):
    __tablename__ = "ontology_change_proposals"

    id = Column(UUIDChar, primary_key=True, default=uuid.uuid4)
    knowledge_space_id = Column(UUIDChar, ForeignKey("knowledge_spaces.id"), nullable=False, index=True)
    
    # 提案来源信息
    source_job_id = Column(UUIDChar, ForeignKey("jobs.id"), nullable=False, index=True)
    source_chunk_id = Column(UUIDChar, ForeignKey("chunks.id"), nullable=False, index=True)
    source_mode = Column(String, nullable=False, index=True) # "evolution" or "shadow"

    # 提案内容
    proposal_type = Column(SQLAlchemyEnum(ProposalType), nullable=False)
    proposal_details = Column(JSON, nullable=False) # 存储工具调用的参数，如 {"new_name": "...", "parent_name": "..."}
    
    # 提案状态与审计
    status = Column(SQLAlchemyEnum(ProposalStatus), default=ProposalStatus.PENDING, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    reviewed_by_user_id = Column(UUIDChar, ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
