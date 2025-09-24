"""
Service layer for handling business logic related to Assessment Jobs.
"""
import jinja2
import base64
from sqlalchemy import func, Interval, or_
from sqlalchemy.orm import Session, selectinload
from typing import List, Optional
from datetime import datetime, timedelta
from uuid import UUID

from .. import models, schemas, kosmos_client
from ..fsm import initialize_fsm

def create_job(db: Session, job_create: schemas.JobCreate) -> (models.AssessmentJob, int):
    """
    Creates a new assessment job.
    Returns the job object and the number of findings created.
    """
    # 1. Validate framework exists
    framework = db.query(models.AssessmentFramework).filter(models.AssessmentFramework.id == job_create.framework_id).first()
    if not framework:
        raise ValueError(f"Framework with id {job_create.framework_id} not found.")

    # 2. Create the AssessmentJob
    db_job = models.AssessmentJob(
        framework_id=job_create.framework_id,
        name=job_create.name,
        status='PENDING'
    )
    db.add(db_job)
    db.flush()

    # 3. Link to knowledge spaces
    for ks_info in job_create.knowledge_spaces:
        link_object = models.KnowledgeSpaceLink(
            job_id=db_job.id,
            ks_id=ks_info.ks_id,
            role=ks_info.role
        )
        db.add(link_object)

    # 4. Create an empty finding for each control item definition
    findings_to_create = []
    if framework.control_item_definitions:
        findings_to_create = [
            models.AssessmentFinding(
                job_id=db_job.id,
                control_item_def_id=control_def.id
            ) for control_def in framework.control_item_definitions
        ]
        db.bulk_save_objects(findings_to_create)
    
    db.commit()
    db.refresh(db_job)
    
    return db_job, len(findings_to_create)

def get_jobs(db: Session, skip: int = 0, limit: int = 100) -> List[schemas.JobSummaryResponse]:
    """
    Retrieves a list of all assessment jobs with a summary of their findings.
    """
    jobs = db.query(models.AssessmentJob).options(
        selectinload(models.AssessmentJob.knowledge_spaces)
    ).order_by(models.AssessmentJob.id).offset(skip).limit(limit).all()
    if not jobs:
        return []

    job_ids = [job.id for job in jobs]

    summary_query = (
        db.query(
            models.AssessmentFinding.job_id,
            models.AssessmentFinding.judgement,
            func.count(models.AssessmentFinding.id).label("count"),
        )
        .filter(models.AssessmentFinding.job_id.in_(job_ids))
        .group_by(
            models.AssessmentFinding.job_id,
            models.AssessmentFinding.judgement,
        )
        .all()
    )

    summaries = {job_id: {} for job_id in job_ids}
    for job_id, judgement, count in summary_query:
        judgement_key = judgement if judgement else "PENDING"
        summaries[job_id][judgement_key] = count

    response_list = []
    for job in jobs:
        # 手动构建响应对象，避免from_orm的序列化问题
        job_summary = schemas.JobSummaryResponse(
            id=job.id,
            name=job.name,
            framework_id=job.framework_id,
            status=job.status,
            findings_summary=summaries.get(job.id, {}),
            knowledge_spaces=[
                schemas.KnowledgeSpaceLink(ks_id=ks.ks_id, role=ks.role)
                for ks in job.knowledge_spaces
            ]
        )
        response_list.append(job_summary)

    return response_list

def get_job_by_id(db: Session, job_id: UUID) -> Optional[models.AssessmentJob]:
    """
    Retrieves a single assessment job by its ID, including its findings.
    """
    return db.query(models.AssessmentJob).filter(models.AssessmentJob.id == job_id).first()

def recover_and_progress_stalled_sessions(db: Session, job_id: UUID):
    """
    Finds sessions that are stuck (timed out or over action limit),
    abandons them, fills their findings with a placeholder, submits them
    for review, and then triggers the scheduler to unblock the queue.
    """
    from . import execution_service # Avoid circular import

    now = datetime.utcnow()
    
    # Find sessions that are in progress but have stalled
    stalled_sessions = (
        db.query(models.AssessmentSession)
        .filter(
            models.AssessmentSession.job_id == job_id,
            models.AssessmentSession.status == 'ASSESSING_CONTROLS',
            or_(
                (models.AssessmentSession.created_at + func.cast(models.AssessmentSession.timeout_seconds, Interval)) < now,
                (models.AssessmentSession.action_count >= models.AssessmentSession.action_limit)
            )
        )
        .all()
    )
    
    if not stalled_sessions:
        return

    for session in stalled_sessions:
        reason = "timeout" if (now > session.created_at + timedelta(seconds=session.timeout_seconds)) else "action limit exceeded"
        
        fsm = initialize_fsm(session)
        if fsm.can('abandon_session'):
            session.abandon_session() # Move to ABANDONED state
            
            # Fill pending findings with a placeholder judgement and comment
            for finding in session.findings:
                if finding.judgement is None:
                    finding.judgement = schemas.JudgementEnum.NOT_APPLICABLE
                    finding.comment = f"由系统自动完成：会话因 {reason} 而被放弃。"
            
            # Force the session into the review state so it's not lost
            if fsm.can('submit_for_review'):
                session.submit_for_review()
                
                # Mark the corresponding queue item as COMPLETED to unblock the queue
                queue_item = db.query(models.ExecutionQueue).filter(models.ExecutionQueue.session_id == session.id).first()
                if queue_item:
                    queue_item.status = 'COMPLETED'

    # After handling all stalled sessions, try to schedule the next one
    if stalled_sessions:
        # The commit will be handled by the calling function.
        # We trigger the scheduler, which will also be handled in the caller's transaction.
        execution_service.schedule_next_session(db)


def get_sessions_for_job(db: Session, job_id: UUID, status: Optional[str] = None) -> List[models.AssessmentSession]:
    """
    Retrieves all assessment sessions for a specific job, with an option to filter by status.
    """
    query = db.query(models.AssessmentSession).options(selectinload(models.AssessmentSession.findings)).filter(models.AssessmentSession.job_id == job_id)
    if status:
        query = query.filter(models.AssessmentSession.status == status)
    return query.order_by(models.AssessmentSession.id).all()

def export_findings_by_job_id(
    db: Session, 
    job_id: UUID, 
    judgements: Optional[List[str]] = None
) -> List[models.AssessmentFinding]:
    """
    Exports findings for a given job, with optional filtering by judgement.
    """
    query = db.query(models.AssessmentFinding).filter(models.AssessmentFinding.job_id == job_id)

    if judgements is None:
        query = query.filter(models.AssessmentFinding.judgement.isnot(None))
    elif judgements:
        query = query.filter(models.AssessmentFinding.judgement.in_(judgements))

    return query.all()

def delete_jobs_by_ids(db: Session, job_ids: List[UUID]) -> int:
    """
    Deletes one or more jobs by their IDs.
    """
    if not job_ids:
        return 0
    
    num_deleted = db.query(models.AssessmentJob).filter(models.AssessmentJob.id.in_(job_ids)).delete(synchronize_session=False)
    db.commit()
    return num_deleted

def delete_jobs_by_ids(db: Session, job_ids: List[UUID]) -> int:
    """
    Deletes one or more jobs by their IDs.
    """
    if not job_ids:
        return 0
    
    num_deleted = db.query(models.AssessmentJob).filter(models.AssessmentJob.id.in_(job_ids)).delete(synchronize_session=False)
    db.commit()
    return num_deleted

def _render_html_template(job_data: dict, findings_data: list) -> str:
    """Helper function to render the HTML template with prepared data."""
    template_loader = jinja2.FileSystemLoader(searchpath="./assessment_service/app/templates")
    template_env = jinja2.Environment(loader=template_loader)
    template = template_env.get_template("report_template.html")

    context = {
        "job": job_data,
        "findings": sorted(findings_data, key=lambda f: f['control_item_definition']['display_id']),
        "generation_time": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    }
    return template.render(context)

def generate_html_report(db: Session, job_id: UUID, token: str, judgements: Optional[List[str]] = None) -> str:
    """
    Generates an HTML report for a job, with filtering and evidence fetching.
    """
    job = get_job_by_id(db, job_id)
    if not job:
        return None

    job_data = { "id": job.id, "name": job.name, "framework_id": job.framework_id, "status": job.status }
    
    # Use the existing fine-grained filtering logic
    findings_to_process = export_findings_by_job_id(db, job_id, judgements=judgements)

    findings_with_evidence = []
    target_ks_id = UUID(job.knowledge_spaces[0].ks_id) if job.knowledge_spaces else None

    for finding in findings_to_process:
        control_def_dict = schemas.ControlItemDefinitionResponse.from_orm(finding.control_item_definition).dict()
        finding_data = {
            "judgement": finding.judgement, "comment": finding.comment, "supplement": finding.supplement,
            "control_item_definition": control_def_dict, "evidence_content": []
        }
        
        for evidence in finding.evidences:
            try:
                read_result = kosmos_client.read_from_kosmos(
                    doc_ref=evidence.doc_id, ks_id=target_ks_id,
                    start=evidence.start_line, end=evidence.end_line, token=token
                )
                # Reconstruct content from the 'lines' array
                content_str = "\n".join([line['content'] for line in read_result.get("lines", [])])
                if not content_str:
                    content_str = "Error: Could not fetch evidence content."

                evidence_data = {
                    "doc_id": evidence.doc_id, "start_line": evidence.start_line, "end_line": evidence.end_line,
                    "content": content_str,
                    "assets": read_result.get("assets", []),
                    "page_image_data_urls": []  # Changed to a list
                }

                # Fetch and embed all relevant page images
                page_numbers = read_result.get("relevant_page_numbers")
                if page_numbers:
                    for page_num in page_numbers:
                        try:
                            image_bytes = kosmos_client.get_page_image_from_kosmos(
                                doc_id=evidence.doc_id,
                                page_number=page_num,
                                token=token
                            )
                            encoded_image = base64.b64encode(image_bytes).decode('utf-8')
                            evidence_data["page_image_data_urls"].append(f"data:image/png;base64,{encoded_image}")
                        except Exception as img_e:
                            print(f"Could not fetch or embed page image for doc {evidence.doc_id}, page {page_num}: {img_e}")

                finding_data['evidence_content'].append(evidence_data)
            except Exception as e:
                 finding_data['evidence_content'].append({
                    "doc_id": evidence.doc_id, "start_line": evidence.start_line, "end_line": evidence.end_line,
                    "content": f"Error fetching evidence: {str(e)}", "assets": [],
                    "page_image_data_urls": []
                })
        findings_with_evidence.append(finding_data)

    return _render_html_template(job_data, findings_with_evidence)
