import uuid
from typing import List
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from .. import models
from .ontology_service import OntologyService

class OntologyProposalService:
    def __init__(self, db: Session):
        self.db = db
        self.ontology_service = OntologyService(db)

    def get_pending_proposals(self, knowledge_space_id: uuid.UUID) -> List[models.OntologyChangeProposal]:
        """Lists all pending proposals for a given knowledge space."""
        return self.db.query(models.OntologyChangeProposal).filter(
            models.OntologyChangeProposal.knowledge_space_id == knowledge_space_id,
            models.OntologyChangeProposal.status == models.ProposalStatus.PENDING
        ).all()

    def _get_proposal_or_404(self, proposal_id: uuid.UUID) -> models.OntologyChangeProposal:
        """Fetches a proposal by its ID, raising a 404 if not found."""
        proposal = self.db.query(models.OntologyChangeProposal).filter(models.OntologyChangeProposal.id == proposal_id).first()
        if not proposal:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proposal not found.")
        return proposal

    def approve_proposal(self, proposal_id: uuid.UUID, reviewer: models.User) -> models.OntologyChangeProposal:
        """
        Approves a proposal, which triggers the actual change in the ontology
        by calling the OntologyService.
        """
        proposal = self._get_proposal_or_404(proposal_id)
        if proposal.status != models.ProposalStatus.PENDING:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Proposal is already in '{proposal.status.value}' state.")

        details = proposal.proposal_details
        commit_message = f"Approved proposal {proposal.id} from job {proposal.source_job_id} (mode: {proposal.source_mode})."

        try:
            if proposal.proposal_type == models.ProposalType.ADD_NODE:
                self.ontology_service.add_node(
                    knowledge_space_id=proposal.knowledge_space_id,
                    author=reviewer,
                    parent_stable_id=details['parent_stable_id'], # Assuming stable_id is passed in future
                    node_data={'name': details['new_node_name'], 'node_metadata': {'description': details.get('new_node_description')}},
                    commit_message=commit_message
                )
            elif proposal.proposal_type == models.ProposalType.MODIFY_NODE:
                # This part needs more robust logic to differentiate between update and move
                # For now, we assume it's an update.
                self.ontology_service.update_node(
                    knowledge_space_id=proposal.knowledge_space_id,
                    author=reviewer,
                    stable_id=details['stable_id'], # Assuming stable_id is passed in future
                    new_node_data={'name': details.get('new_name'), 'node_metadata': {'description': details.get('new_description')}},
                    commit_message=commit_message
                )
            
            proposal.status = models.ProposalStatus.APPROVED
            proposal.reviewed_by_user_id = reviewer.id
            proposal.reviewed_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(proposal)
            return proposal

        except Exception as e:
            self.db.rollback()
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to apply ontology change: {e}")

    def reject_proposal(self, proposal_id: uuid.UUID, reviewer: models.User) -> models.OntologyChangeProposal:
        """Rejects a proposal."""
        proposal = self._get_proposal_or_404(proposal_id)
        if proposal.status != models.ProposalStatus.PENDING:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Proposal is already in '{proposal.status.value}' state.")

        proposal.status = models.ProposalStatus.REJECTED
        proposal.reviewed_by_user_id = reviewer.id
        proposal.reviewed_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(proposal)
        return proposal
