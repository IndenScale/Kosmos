"""
Kosmos CLI commands for managing Assessment Sessions.
"""
import sys
import json
from argparse import ArgumentParser, _SubParsersAction
from cli.utils import print_json_response
from cli.assessment_client import AssessmentClient
from cli.config import CliConfig

def register_subparser(subparsers: _SubParsersAction, parent_parser: ArgumentParser):
    """
    Registers the 'assessment-session' command and its subcommands.
    """
    session_parser = subparsers.add_parser(
        "assessment-session",
        help="Manage assessment sessions.",
        description="List and manage assessment sessions.",
        parents=[parent_parser],
        add_help=False
    )
    
    # Add arguments for session-id and judgement
    session_parser.add_argument("--session-id", help="Filter sessions by a specific session UUID.")
    session_parser.add_argument("--judgement", help="Filter sessions by a specific judgement.")
    
    session_parser.set_defaults(func=run_list_sessions)
    session_subparsers = session_parser.add_subparsers(
        dest="assessment_session_action", 
        help="Action to perform on an assessment session"
    )
    
    # --- kosmos assessment-session list ---
    list_parser = session_subparsers.add_parser(
        "list",
        help="List assessment sessions.",
        parents=[parent_parser],
        add_help=False
    )
    list_parser.add_argument("--job-id", help="Filter sessions by a specific job UUID.")
    list_parser.add_argument("--status", help="Filter sessions by status (e.g., 'COMPLETED', 'ASSESSING_CONTROLS').")
    list_parser.add_argument("--session-id", help="Filter sessions by a specific session UUID.")
    list_parser.add_argument("--judgement", help="Filter sessions by a specific judgement.")
    list_parser.set_defaults(func=run_list_sessions)

    # --- kosmos assessment-session execute ---
    execute_parser = session_subparsers.add_parser(
        "execute",
        help="Execute a new assessment session for a job.",
        parents=[parent_parser],
        add_help=False
    )
    execute_parser.add_argument("--job-id", required=True, help="The UUID of the job to create a session for.")
    execute_parser.add_argument("--payload", required=True, help="Path to the JSON file containing the execution payload.")
    execute_parser.set_defaults(func=run_execute_session)


def run_list_sessions(assessment_client: AssessmentClient, args: any, config: CliConfig, **kwargs):
    """Handles the 'assessment-session list' command."""
    try:
        # Check if we have a session_id or job_id to filter by
        # If we have a session_id, we should only filter by that
        # If we have a job_id, we should only filter by that
        # If we have neither, we list all sessions
        params = {}
        
        # Only add parameters that exist and are not None
        if hasattr(args, 'job_id') and args.job_id is not None:
            params['job_id'] = args.job_id
        if hasattr(args, 'status') and args.status is not None:
            params['status'] = args.status
            
        # For session_id, we need to handle it differently since the API doesn't support it
        # We'll just use it to filter the results after fetching all sessions
        session_id_filter = getattr(args, 'session_id', None) if hasattr(args, 'session_id') else None
        judgement_filter = getattr(args, 'judgement', None) if hasattr(args, 'judgement') else None
        
        # If we have a session_id, we should make a direct call to get that session
        if session_id_filter:
            # Make a direct call to get the specific session
            result = assessment_client.get_session(session_id_filter)
            # Wrap in a list to maintain consistent response format
            result = [result] if result else []
        else:
            # Use the list sessions API
            result = assessment_client.list_sessions(**params)
        
        # Apply additional filtering if needed
        if judgement_filter and not session_id_filter:
            # Filter the results
            filtered_results = []
            # Check if result is a list or dict
            if isinstance(result, list):
                data = result
            elif isinstance(result, dict) and 'data' in result:
                data = result['data']
            else:
                data = result
            
            for session in data:
                if judgement_filter and session.get('judgement') != judgement_filter:
                    continue
                filtered_results.append(session)
            
            # Update the result with filtered data
            if isinstance(result, dict) and 'data' in result:
                result['data'] = filtered_results
                result['total'] = len(filtered_results)
            else:
                result = filtered_results
                
        print_json_response(result)
    except Exception as e:
        print(f"错误: 无法列出评估会话: {e}", file=sys.stderr)
        sys.exit(1)

def run_execute_session(assessment_client: AssessmentClient, args: any, config: CliConfig, **kwargs):
    """Handles the 'assessment-session execute' command."""
    try:
        with open(args.payload, 'r') as f:
            payload = json.load(f)
        
        # Add the job_id from the command line argument to the payload
        payload['job_id'] = args.job_id
        
        result = assessment_client.execute_session(payload)
        print(f"成功为作业 '{args.job_id}' 派发了一个新的评估会话。", file=sys.stderr)
        print_json_response(result)
    except FileNotFoundError:
        print(f"错误: Payload 文件未找到 '{args.payload}'", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"错误: Payload 文件 '{args.payload}' 不是一个有效的JSON文件。", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"错误: 无法执行评估会话: {e}", file=sys.stderr)
        sys.exit(1)
