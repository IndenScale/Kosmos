"""
Kosmos CLI commands for managing Assessment Findings.
"""
import sys
import json
from argparse import ArgumentParser, _SubParsersAction
from cli.utils import print_json_response
from cli.assessment_client import AssessmentClient
from cli.config import CliConfig

def register_subparser(subparsers: _SubParsersAction, parent_parser: ArgumentParser):
    """
    Registers the 'assessment-finding' command and its subcommands.
    """
    finding_parser = subparsers.add_parser(
        "assessment-finding",
        help="Manage assessment findings.",
        description="List and get assessment findings directly.",
        parents=[parent_parser],
        add_help=False
    )
    
    finding_parser.set_defaults(func=run_list_findings)
    finding_subparsers = finding_parser.add_subparsers(
        dest="assessment_finding_action", 
        help="Action to perform on assessment findings"
    )
    
    # --- kosmos assessment-finding list ---
    list_parser = finding_subparsers.add_parser(
        "list",
        help="List assessment findings with optional filtering.",
        parents=[parent_parser],
        add_help=False
    )
    list_parser.add_argument("--finding-id", action="append", dest="finding_ids", help="Filter by specific finding IDs (can be used multiple times).")
    list_parser.add_argument("--session-id", help="Filter by session ID.")
    list_parser.add_argument("--job-id", help="Filter by job ID.")
    list_parser.add_argument("--judgement", action="append", dest="judgements", help="Filter by judgement values (can be used multiple times).")
    list_parser.set_defaults(func=run_list_findings)
    
    # --- kosmos assessment-finding show ---
    show_parser = finding_subparsers.add_parser(
        "show",
        help="Show details for a specific finding.",
        parents=[parent_parser],
        add_help=False
    )
    show_parser.add_argument("id", help="The UUID of the finding to display.")
    show_parser.set_defaults(func=run_show_finding)

def run_list_findings(assessment_client: AssessmentClient, args: any, config: CliConfig, **kwargs):
    """Handles the 'assessment-finding list' command."""
    try:
        # Build query parameters
        params = {}
        
        # Add filtering parameters if provided
        if hasattr(args, 'finding_ids') and args.finding_ids:
            params['finding_ids'] = args.finding_ids
        if hasattr(args, 'session_id') and args.session_id:
            params['session_id'] = args.session_id
        if hasattr(args, 'job_id') and args.job_id:
            params['job_id'] = args.job_id
        if hasattr(args, 'judgements') and args.judgements:
            params['judgements'] = args.judgements
            
        result = assessment_client.list_findings(**params)
        print_json_response(result)
    except Exception as e:
        print(f"错误: 无法列出评估发现: {e}", file=sys.stderr)
        sys.exit(1)

def run_show_finding(assessment_client: AssessmentClient, args: any, config: CliConfig, **kwargs):
    """Handles the 'assessment-finding show' command."""
    try:
        result = assessment_client.get_finding(args.id)
        print_json_response(result)
    except Exception as e:
        print(f"错误: 无法获取评估发现详情: {e}", file=sys.stderr)
        sys.exit(1)