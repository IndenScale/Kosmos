import sys
import json
from argparse import ArgumentParser, _SubParsersAction
from cli.utils import print_json_response
from cli.assessment_client import AssessmentClient
from cli.config import CliConfig

def register_subparser(subparsers: _SubParsersAction, parent_parser: ArgumentParser):
    """
    Registers the 'assessment-job' command and its subcommands.
    """
    job_parser = subparsers.add_parser(
        "assessment-job",
        help="Manage assessment jobs.",
        description="Create, list, show, and delete assessment jobs.",
        parents=[parent_parser],
        add_help=False
    )
    
    job_parser.set_defaults(func=run_list_jobs)
    job_subparsers = job_parser.add_subparsers(
        dest="assessment_job_action", 
        help="Action to perform on an assessment job"
    )
    
    # --- kosmos assessment-job list ---
    list_parser = job_subparsers.add_parser(
        "list",
        help="List all assessment jobs.",
        parents=[parent_parser],
        add_help=False
    )
    list_parser.set_defaults(func=run_list_jobs)
    
    # --- kosmos assessment-job create ---
    create_parser = job_subparsers.add_parser(
        "create",
        help="Create a new assessment job.",
        parents=[parent_parser],
        add_help=False
    )
    create_parser.add_argument("--name", required=True, help="A descriptive name for the job.")
    create_parser.add_argument("--framework-id", required=True, help="The UUID of the assessment framework to use.")
    # --ks-id is inherited from the parent parser.
    create_parser.set_defaults(func=run_create_job)
    
    # --- kosmos assessment-job show ---
    show_parser = job_subparsers.add_parser(
        "show",
        help="Show details for a specific assessment job.",
        parents=[parent_parser],
        add_help=False
    )
    show_parser.add_argument("id", help="The UUID of the job to display.")
    show_parser.set_defaults(func=run_show_job)

    # --- kosmos assessment-job delete ---
    delete_parser = job_subparsers.add_parser(
        "delete",
        help="Delete one or more assessment jobs.",
        parents=[parent_parser],
        add_help=False
    )
    delete_parser.add_argument("ids", nargs='+', help="One or more job UUIDs to delete.")
    delete_parser.set_defaults(func=run_delete_jobs)

    # --- kosmos assessment-job execute ---
    execute_parser = job_subparsers.add_parser(
        "execute",
        help="Execute an assessment job.",
        parents=[parent_parser],
        add_help=False
    )
    execute_parser.add_argument("id", help="The UUID of the job to execute.")
    # Add optional arguments for the payload fields
    execute_parser.add_argument("--agent", choices=["qwen", "gemini_cli", "claude"], default="qwen", help="The agent to dispatch for the assessment (default: qwen).")
    execute_parser.add_argument("--session-batch-size", type=int, default=5, help="The number of findings to process in each session (default: 5).")
    execute_parser.add_argument("--openai-base-url", help="OpenAI base URL for the agent.")
    execute_parser.add_argument("--openai-api-key", help="OpenAI API key for the agent.")
    execute_parser.add_argument("--openai-model", help="OpenAI model name for the agent.")
    execute_parser.add_argument("--kosmos-username", help="Kosmos system username for the agent.")
    execute_parser.add_argument("--kosmos-password", help="Kosmos system password for the agent.")
    execute_parser.add_argument("--agent-prompt", help="Custom agent prompt.")

    execute_parser.set_defaults(func=run_execute_job)
    
    # --- kosmos assessment-job requeue ---
    requeue_parser = job_subparsers.add_parser(
        "requeue",
        help="Requeue an assessment job.",
        parents=[parent_parser],
        add_help=False
    )
    requeue_parser.add_argument("id", help="The UUID of the job to requeue.")
    requeue_parser.add_argument("--payload", required=True, help="Path to the JSON file containing the execution payload.")
    requeue_parser.set_defaults(func=run_requeue_job)

def run_list_jobs(assessment_client: AssessmentClient, args: any, config: CliConfig, **kwargs):
    """Handles the 'assessment-job list' command."""
    try:
        result = assessment_client.list_jobs()
        print_json_response(result)
    except Exception as e:
        print(f"错误: 无法列出评估作业: {e}", file=sys.stderr)
        sys.exit(1)

def run_create_job(assessment_client: AssessmentClient, args: any, config: CliConfig, **kwargs):
    """Handles the 'assessment-job create' command."""
    try:
        ks_id = config.require(args.ks_id, "KOSMOS_KS_ID", "知识空间ID")
        
        result = assessment_client.create_job(
            name=args.name,
            framework_id=args.framework_id,
            ks_id=ks_id
        )
        print("评估作业创建成功。", file=sys.stderr)
        print_json_response(result)
    except Exception as e:
        print(f"错误: 无法创建评估作业: {e}", file=sys.stderr)
        sys.exit(1)

def run_show_job(assessment_client: AssessmentClient, args: any, config: CliConfig, **kwargs):
    """Handles the 'assessment-job show' command."""
    try:
        result = assessment_client.get_job(args.id)
        print_json_response(result)
    except Exception as e:
        print(f"错误: 无法获取评估作业详情: {e}", file=sys.stderr)
        sys.exit(1)

def run_delete_jobs(assessment_client: AssessmentClient, args: any, config: CliConfig, **kwargs):
    """Handles the 'assessment-job delete' command."""
    try:
        result = assessment_client.delete_jobs(args.ids)
        print(f"成功删除 {len(args.ids)} 个评估作业。", file=sys.stderr)
        if result:
            print_json_response(result)
    except Exception as e:
        print(f"错误: 无法删除评估作业: {e}", file=sys.stderr)
        sys.exit(1)

def run_execute_job(assessment_client: AssessmentClient, args: any, config: CliConfig, **kwargs):
    """Handles the 'assessment-job execute' command."""
    try:
        # Construct payload from args, allowing defaults to be used
        payload = {
            "agent": args.agent,
            "session_batch_size": args.session_batch_size,
            "openai_base_url": args.openai_base_url,
            "openai_api_key": args.openai_api_key,
            "openai_model": args.openai_model,
            "kosmos_username": args.kosmos_username,
            "kosmos_password": args.kosmos_password,
            "agent_prompt": args.agent_prompt
        }
        
        # Clean up None values so the backend's Pydantic model can apply its defaults
        payload = {k: v for k, v in payload.items() if v is not None}

        result = assessment_client.execute_job(args.id, payload)
        print(f"评估作业 '{args.id}' 已成功派发。", file=sys.stderr)
        print_json_response(result)
    except Exception as e:
        print(f"错误: 无法执行评估作业: {e}", file=sys.stderr)
        sys.exit(1)

def run_requeue_job(assessment_client: AssessmentClient, args: any, config: CliConfig, **kwargs):
    """Handles the 'assessment-job requeue' command."""
    try:
        with open(args.payload, 'r') as f:
            payload = json.load(f)
        
        result = assessment_client.requeue_job(args.id, payload)
        print(f"评估作业 '{args.id}' 已成功重新派发。", file=sys.stderr)
        print_json_response(result)
    except FileNotFoundError:
        print(f"错误: Payload 文件未找到 '{args.payload}'", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"错误: Payload 文件 '{args.payload}' 不是一个有效的JSON文件。", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"错误: 无法重新执行评估作业: {e}", file=sys.stderr)
        sys.exit(1)
