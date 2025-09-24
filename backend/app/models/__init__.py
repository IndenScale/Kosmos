"""
This file serves as a central point for importing all SQLAlchemy models.

By importing all models here, we ensure that they are all registered with the
SQLAlchemy Base metadata before any part of the application tries to use them.
This helps prevent circular import errors and issues where relationships
cannot find their target class.
"""
from .base import Base
from .user import User
from .knowledge_space import KnowledgeSpace
from .membership import KnowledgeSpaceMember
from .original import Original
from .asset import Asset
from .document import Document, DocumentStatus
from .chunk import Chunk
from .canonical_content import CanonicalContent
from .document_asset_context import DocumentAssetContext
from .credential import ModelCredential, ModelFamily, CredentialType
from .credential_link import KnowledgeSpaceModelCredentialLink
from .job import Job, JobStatus, JobType
from .chunk_asset_link import ChunkAssetLink
from .ontology import Ontology
from .ontology_version import OntologyVersion
from .ontology_node import OntologyNode
from .ontology_version_node_link import OntologyVersionNodeLink
from .chunk_ontology_node_link import ChunkOntologyNodeLink
from .ontology_change_proposal import OntologyChangeProposal, ProposalType, ProposalStatus
from .bookmark import Bookmark
from .content_page_mapping import ContentPageMapping
from .refresh_token import RefreshToken
from .domain_events import DomainEvent


# This __all__ list is used for `from backend.app.models import *` statements.
__all__ = [
    "Base",
    "User",
    "KnowledgeSpace",
    "KnowledgeSpaceMember",
    "Original",
    "Asset",
    "Document",
    "DocumentStatus",
    "Chunk",
    "CanonicalContent",
    "DocumentAssetContext",
    "ModelCredential",
    "KnowledgeSpaceModelCredentialLink",
    "ModelFamily",
    "CredentialType",
    "Job",
    "JobStatus",
    "JobType",
    "ChunkAssetLink",
    "Ontology",
    "OntologyVersion",
    "OntologyNode",
    "OntologyVersionNodeLink",
    "ChunkOntologyNodeLink",
    "OntologyChangeProposal",
    "ProposalType",
    "ProposalStatus",
    "Bookmark",
    "ContentPageMapping",
    "RefreshToken",
    "DomainEvent",
]
