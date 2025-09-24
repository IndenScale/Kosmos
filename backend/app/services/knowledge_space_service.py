import base64
import uuid
import json
import logging
from datetime import datetime
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc

from ..models.knowledge_space import KnowledgeSpace
from ..models.membership import KnowledgeSpaceMember
from ..models.user import User
from ..models.ontology import Ontology
from ..schemas.knowledge_space import (
    KnowledgeSpaceCreate, 
    KnowledgeSpaceUpdate, 
    KnowledgeSpaceListItem, 
    KnowledgeSpaceRead as KnowledgeSpaceSchema
)
from ..schemas.membership import MemberAdd
from .ontology_service import OntologyService

# Add a logger for this service
logger = logging.getLogger(__name__)

def create_knowledge_space(db: Session, ks_in: KnowledgeSpaceCreate, owner: User) -> KnowledgeSpaceSchema:
    """
    Creates a new knowledge space, adds the owner, and initializes its
    version-controlled ontology repository. If an initial ontology dictionary
    is provided, it will be committed as a new version.
    
    Returns a Pydantic schema object ready for API response.
    """
    db_ks = None
    try:
        # Step 1: Create the KnowledgeSpace record.
        db_ks = KnowledgeSpace(
            name=ks_in.name,
            owner_id=owner.id
        )
        db.add(db_ks)
        db.flush()  # Flush to get the generated knowledge_space_id

        # Step 2: Add the owner as the first member.
        owner_membership = KnowledgeSpaceMember(
            knowledge_space_id=db_ks.id,
            user_id=owner.id,
            role="owner"
        )
        db.add(owner_membership)

        # Step 3: Initialize the ontology repository, passing the initial tree
        # directly to create the first version atomically.
        ontology_service = OntologyService(db)
        ontology_service._create_ontology_for_knowledge_space(
            knowledge_space=db_ks,
            creator=owner,
            initial_tree=ks_in.ontology_dictionary
        )

        # Step 4: Commit the transaction.
        db.commit()
        
        # Step 5: Create the response with simplified ontology dictionary
        ontology_service = OntologyService(db)
        simple_ontology_dict = ontology_service.get_active_ontology_as_simple_dict(db_ks.id)
        
        # Step 6: Create Pydantic model instance and set the simplified ontology
        response = KnowledgeSpaceSchema.model_validate(db_ks)
        response.ontology_dictionary = simple_ontology_dict
        
        return response

    except Exception as e:
        logger.error(f"Error creating knowledge space: {e}")
        db.rollback()
        raise

def get_knowledge_space_by_id(db: Session, knowledge_space_id: uuid.UUID) -> KnowledgeSpace | None:
    """Gets a knowledge space by its ID."""
    return db.query(KnowledgeSpace).filter(KnowledgeSpace.id == knowledge_space_id).first()

def update_knowledge_space(db: Session, db_ks: KnowledgeSpace, ks_in: KnowledgeSpaceUpdate, current_user: User) -> KnowledgeSpaceSchema:
    """
    Updates a knowledge space's details. If an ontology_dictionary is provided,
    it intelligently commits it as a new version of the ontology.
    """
    update_data = ks_in.model_dump(exclude_unset=True)

    # --- Special Handling for Ontology ---
    if 'ontology_dictionary' in update_data:
        new_ontology_tree = update_data.pop('ontology_dictionary')
        
        # --- DEBUG LOGGING ---
        logger.info("--- KnowledgeSpaceService: Received Ontology Update ---")
        logger.info(f"Knowledge Space ID: {db_ks.id}")
        logger.info(f"Raw ontology_dictionary received:\n{json.dumps(new_ontology_tree, indent=2, ensure_ascii=False)}")
        # --- END DEBUG LOGGING ---

        if new_ontology_tree:
            ontology_service = OntologyService(db)
            ontology_service.commit_version_from_json_tree(
                knowledge_space_id=db_ks.id,
                author=current_user,
                commit_message="Updated ontology via PATCH request.",
                new_tree=new_ontology_tree
            )

    # --- Generic Handling for other fields ---
    for key, value in update_data.items():
        setattr(db_ks, key, value)
    
    db.commit()
    db.refresh(db_ks)
    
    # Create the response with simplified ontology dictionary
    ontology_service = OntologyService(db)
    simple_ontology_dict = ontology_service.get_active_ontology_as_simple_dict(db_ks.id)
    
    # Create Pydantic model instance and set the simplified ontology
    response = KnowledgeSpaceSchema.model_validate(db_ks)
    response.ontology_dictionary = simple_ontology_dict
    
    return response


def delete_knowledge_space(db: Session, knowledge_space_id: uuid.UUID, current_user: User) -> None:
    """
    删除知识空间及其相关的所有数据，包括本体、成员关系、文档、向量数据等。
    只有知识空间的所有者才能执行此操作。
    """
    try:
        # 获取知识空间
        db_ks = db.query(KnowledgeSpace).filter(KnowledgeSpace.id == knowledge_space_id).first()
        if not db_ks:
            raise ValueError(f"Knowledge space with ID {knowledge_space_id} not found")
        
        # 验证当前用户是否为所有者
        if db_ks.owner_id != current_user.id:
            raise PermissionError("Only the owner can delete a knowledge space")
        
        logger.info(f"Deleting knowledge space {knowledge_space_id} by user {current_user.id}")
        
        # 删除向量数据库中的分区数据
        try:
            from ..services.vector_db_service import VectorDBService
            vector_service = VectorDBService()
            vector_service.delete_partition(str(knowledge_space_id))
            logger.info(f"Deleted vector partition for knowledge space {knowledge_space_id}")
        except Exception as e:
            logger.warning(f"Failed to delete vector partition for knowledge space {knowledge_space_id}: {e}")
        
        # 删除相关的本体数据
        ontology_service = OntologyService(db)
        ontology_service.delete_ontology_for_knowledge_space(knowledge_space_id)
        
        # 删除成员关系（由于cascade设置，这一步可能不是必需的，但为了明确性保留）
        db.query(KnowledgeSpaceMember).filter(
            KnowledgeSpaceMember.knowledge_space_id == knowledge_space_id
        ).delete()
        
        # 删除知识空间本身（由于SQLAlchemy的cascade设置，相关的文档、chunks等会自动删除）
        db.delete(db_ks)
        db.commit()
        
        logger.info(f"Successfully deleted knowledge space {knowledge_space_id}")
        
    except Exception as e:
        logger.error(f"Error deleting knowledge space {knowledge_space_id}: {e}")
        db.rollback()
        raise


def add_member(db: Session, db_ks: KnowledgeSpace, member_in: MemberAdd) -> KnowledgeSpaceMember:
    """Adds a new member to a knowledge space."""
    # Check if user exists
    user_to_add = db.query(User).filter(User.id == member_in.id).first()
    if not user_to_add:
        return None # Or raise an exception

    # Check if membership already exists
    existing_member = db.query(KnowledgeSpaceMember).filter(
        KnowledgeSpaceMember.knowledge_space_id == db_ks.id,
        KnowledgeSpaceMember.user_id == member_in.id
    ).first()
    if existing_member:
        return existing_member # Or raise an exception indicating user is already a member

    new_member = KnowledgeSpaceMember(
        knowledge_space_id=db_ks.id,
        user_id=member_in.id,
        role=member_in.role
    )
    db.add(new_member)
    db.commit()
    db.refresh(new_member)
    return new_member

from ..models.ontology import Ontology
from ..models.ontology_version import OntologyVersion

def get_user_knowledge_spaces_paginated(
    db: Session, 
    user: User, 
    cursor: str | None, 
    page_size: int,
    knowledge_space_id: uuid.UUID | None = None,
    name: str | None = None
):
    """
    Gets all knowledge spaces a user is a member of, with a simplified ontology,
    using cursor pagination and optional filters. Returns the total count of matching spaces.
    """
    query = (
        db.query(KnowledgeSpace)
        .join(KnowledgeSpaceMember)
        .filter(KnowledgeSpaceMember.user_id == user.id)
    )
    
    # Apply filters
    if knowledge_space_id:
        query = query.filter(KnowledgeSpace.id == knowledge_space_id)
    
    if name:
        query = query.filter(KnowledgeSpace.name.ilike(f"%{name}%"))

    # Get the total count *before* pagination is applied
    total_count = query.count()

    if cursor:
        try:
            cursor_time_str = base64.urlsafe_b64decode(cursor).decode()
            cursor_time = datetime.fromisoformat(cursor_time_str)
            query = query.filter(KnowledgeSpace.created_at < cursor_time)
        except (ValueError, TypeError):
            pass

    spaces = query.order_by(desc(KnowledgeSpace.created_at)).limit(page_size + 1).all()

    next_cursor = None
    if len(spaces) > page_size:
        next_item = spaces[page_size]
        next_cursor = base64.urlsafe_b64encode(next_item.created_at.isoformat().encode()).decode()
        spaces = spaces[:page_size]

    # Post-process to create Pydantic models with the simplified ontology
    ontology_service = OntologyService(db)
    result_items = []
    for space in spaces:
        list_item = KnowledgeSpaceListItem.model_validate(space)
        list_item.ontology_simple_dict = ontology_service.get_active_ontology_as_simple_dict(space.id)
        result_items.append(list_item)

    return {"items": result_items, "total_count": total_count, "next_cursor": next_cursor}

def get_knowledge_space_members_paginated(db: Session, knowledge_space_id: uuid.UUID, cursor: str | None, page_size: int):
    """Gets all members of a knowledge space, with cursor pagination."""
    query = db.query(KnowledgeSpaceMember).filter(KnowledgeSpaceMember.knowledge_space_id == knowledge_space_id).options(joinedload(KnowledgeSpaceMember.user))

    if cursor:
        try:
            cursor_time_str = base64.urlsafe_b64decode(cursor).decode()
            cursor_time = datetime.fromisoformat(cursor_time_str)
            query = query.filter(KnowledgeSpaceMember.joined_at < cursor_time)
        except (ValueError, TypeError):
            pass

    members = query.order_by(desc(KnowledgeSpaceMember.joined_at)).limit(page_size + 1).all()

    next_cursor = None
    if len(members) > page_size:
        next_item = members[page_size]
        next_cursor = base64.urlsafe_b64encode(next_item.joined_at.isoformat().encode()).decode()
        members = members[:page_size]

    return {"items": members, "next_cursor": next_cursor}


# --- AI Configuration Service Functions ---

from ..schemas.knowledge_space import AIConfigurationUpdate
import copy

def get_ai_configuration(db_ks: KnowledgeSpace) -> dict:
    """
    Retrieves the AI configuration for a given knowledge space.
    """
    return db_ks.ai_configuration

def _deep_update(source: dict, overrides: dict) -> dict:
    """
    Recursively update a dictionary.
    Sub-dictionaries are updated instead of being replaced.
    """
    updated = copy.deepcopy(source)
    for key, value in overrides.items():
        if isinstance(value, dict) and key in updated and isinstance(updated[key], dict):
            updated[key] = _deep_update(updated[key], value)
        else:
            updated[key] = value
    return updated

def update_ai_configuration(db: Session, db_ks: KnowledgeSpace, config_in: AIConfigurationUpdate) -> dict:
    """
    Partially updates the AI configuration for a knowledge space.
    Only the fields provided in the request will be updated.
    """
    # Convert Pydantic model to dict, excluding unset values
    update_data = config_in.model_dump(exclude_unset=True)
    
    if not update_data:
        # If there's nothing to update, just return the current config
        return db_ks.ai_configuration

    # Perform a deep update of the configuration
    new_config = _deep_update(db_ks.ai_configuration, update_data)
    
    # Set the updated configuration back to the model
    db_ks.ai_configuration = new_config
    
    db.commit()
    db.refresh(db_ks)
    
    return db_ks.ai_configuration
