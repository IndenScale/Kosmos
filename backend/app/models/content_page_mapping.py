
import uuid
from sqlalchemy import Column, Integer, ForeignKey
from sqlalchemy.orm import relationship
from .base import Base, UUIDChar

class ContentPageMapping(Base):
    __tablename__ = 'content_page_mappings'

    id = Column(Integer, primary_key=True, index=True)
    canonical_content_id = Column(UUIDChar, ForeignKey('canonical_contents.id'), nullable=False, index=True)
    line_from = Column(Integer, nullable=False)
    line_to = Column(Integer, nullable=False)
    page_number = Column(Integer, nullable=False)

    canonical_content = relationship("CanonicalContent", back_populates="page_mappings")
