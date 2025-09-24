import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..core.db import get_db
from ..dependencies import get_current_user, require_role
from ..services.ontology_proposal_service import OntologyProposalService

router = APIRouter(
    # Only editors and owners can manage proposals
    dependencies=[Depends(require_role(["owner", "editor"]))],
)

def get_proposal_service(db: Session = Depends(get_db)) -> OntologyProposalService:
    return OntologyProposalService(db)

@router.get(
    "/knowledge-spaces/{knowledge_space_id}/ontology/proposals",
    response_model=List[schemas.OntologyChangeProposalRead],
    summary="List Pending Ontology Proposals"
)
def list_pending_proposals(
    knowledge_space_id: uuid.UUID,
    proposal_service: OntologyProposalService = Depends(get_proposal_service),
):
    """
    Lists all pending ontology change proposals for a specific knowledge space.
    Requires 'owner' or 'editor' role in the knowledge space.
    """
    # The require_role dependency already checks for membership and role.
    return proposal_service.get_pending_proposals(knowledge_space_id)

@router.post(
    "/ontology/proposals/{proposal_id}/approve",
    response_model=schemas.OntologyChangeProposalRead,
    summary="Approve an Ontology Proposal"
)
def approve_a_proposal(
    proposal_id: uuid.UUID,
    current_user: models.User = Depends(get_current_user),
    proposal_service: OntologyProposalService = Depends(get_proposal_service),
):
    """
    Approves a pending ontology change proposal, triggering its execution.
    Requires 'owner' or 'editor' role in the knowledge space.
    """
    # The service layer will handle fetching the proposal and checking its state.
    return proposal_service.approve_proposal(proposal_id, reviewer=current_user)

@router.post(
    "/ontology/proposals/{proposal_id}/reject",
    response_model=schemas.OntologyChangeProposalRead,
    summary="Reject an Ontology Proposal"
)
def reject_a_proposal(
    proposal_id: uuid.UUID,
    current_user: models.User = Depends(get_current_user),
    proposal_service: OntologyProposalService = Depends(get_proposal_service),
):
    """
    Rejects a pending ontology change proposal.
    Requires 'owner' or 'editor' role in the knowledge space.
    """
    return proposal_service.reject_proposal(proposal_id, reviewer=current_user)
