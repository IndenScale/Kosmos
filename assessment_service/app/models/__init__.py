# In models/__init__.py
from .base import Base, UUIDChar

# Import all models so they are registered with the Base metadata
from .framework import AssessmentFramework, ControlItemDefinition
from .job import AssessmentJob, AssessmentFinding, Evidence, KnowledgeSpaceLink
from .session import AssessmentSession, ActionLog
from .queue import ExecutionQueue