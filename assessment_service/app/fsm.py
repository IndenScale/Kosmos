"""
Finite State Machine (FSM) for the Assessment Workflow.

This module defines the states, transitions, and validation logic for an
AssessmentBatch's lifecycle using the 'pytransitions' library.

The FSM is "hard-coded" here for the MVP to ensure rapid development and
reliability for the specific task of network security assessment. It is designed
to be attached to an SQLAlchemy AssessmentBatch object.
"""
from transitions import Machine, MachineError
from .models.session import AssessmentSession
from .models.job import AssessmentFinding

# --- 1. State Definitions ---
# Define the possible states for an assessment batch.
states = [
    'READY_FOR_ASSESSMENT', # Initial state after creation
    'ASSESSING_CONTROLS',   # Agent is actively working on the batch
    'SUBMITTED_FOR_REVIEW', # Agent has finished, pending human review
    'COMPLETED',            # Human has approved the batch
    'FAILED',               # Agent exceeded limits or a critical error occurred
    'ABANDONED'             # Session timed out and was abandoned
]

# --- 2. Validator Functions (Conditions) ---
# These functions are attached to transitions and must return True for the
# transition to be allowed. They receive the model object (the batch) as an argument.

def _is_within_action_limit(event) -> bool:
    """Check if the agent has not exceeded its action limit."""
    session = event.model
    return session.action_count < session.action_limit

def _validate_findings_on_submit(event) -> bool:
    """
    Check two conditions before allowing submission:
    1. Every finding must have a judgement.
    2. Any finding judged as '符合' or '部分符合' must have at least one piece of evidence.
    """
    session = event.model
    if not session.findings:
        return False  # Cannot submit an empty session

    for finding in session.findings:
        if finding.judgement is None:
            return False  # Condition 1 failed

        # Robustly handle both Enum objects and raw string values from the DB
        judgement_str = str(finding.judgement.value if hasattr(finding.judgement, 'value') else finding.judgement)
        
        if judgement_str in ["符合", "部分符合"] and not finding.evidences:
            return False  # Condition 2 failed
            
    return True

def _finding_has_evidence(finding: AssessmentFinding) -> bool:
    """Check if a specific finding has at least one piece of evidence."""
    return len(finding.evidences) > 0


# --- 3. Transition Definitions ---
# Define the edges of our state graph. Each transition has a 'trigger' name,
# a source state, and a destination state. Validators are added via 'conditions'.

transitions = [
    {
        'trigger': 'start_assessment',
        'source': 'READY_FOR_ASSESSMENT',
        'dest': 'ASSESSING_CONTROLS'
    },
    {
        'trigger': 'submit_for_review',
        'source': 'ASSESSING_CONTROLS',
        'dest': 'SUBMITTED_FOR_REVIEW',
        'conditions': [_validate_findings_on_submit]
    },
    {
        'trigger': 'force_fail',
        'source': '*', # Can fail from any state
        'dest': 'FAILED'
    },
    {
        'trigger': 'reject_submission',
        'source': 'SUBMITTED_FOR_REVIEW',
        'dest': 'ASSESSING_CONTROLS'
    },
    {
        'trigger': 'complete_review',
        'source': 'SUBMITTED_FOR_REVIEW',
        'dest': 'COMPLETED'
    },
    {
        'trigger': 'abandon_session',
        'source': 'ASSESSING_CONTROLS',
        'dest': 'ABANDONED'
    }
    # Note: Internal actions like 'add_evidence' do not trigger state changes,
    # but their own validators will be checked at the API level.
]

# --- 4. FSM Factory Function ---

def initialize_fsm(session: AssessmentSession) -> Machine:
    """
    Creates and attaches a configured state machine to an AssessmentSession object.

    Args:
        session: The SQLAlchemy AssessmentSession instance.

    Returns:
        The configured Machine instance, attached to the session object.
    """
    machine = Machine(
        model=session,
        states=states,
        transitions=transitions,
        initial=session.status,  # The machine starts in the object's current state
        model_attribute='status', # Explicitly tell the FSM which field to update
        auto_transitions=False, # We want to explicitly define all transitions
        send_event=True, # Allows methods to receive event data
    )
    return machine
