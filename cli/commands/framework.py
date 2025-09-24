"""
Kosmos CLI commands for managing Assessment Frameworks.
"""
import sys
import re
from argparse import ArgumentParser, _SubParsersAction
from cli.utils import print_json_response
from cli.knowledge_base_client import KosmosClient
from cli.assessment_client import AssessmentClient
from cli.config import CliConfig

def register_subparser(subparsers: _SubParsersAction, parent_parser: ArgumentParser):
    """
    Registers the 'framework' command and its subcommands.
    """
    framework_parser = subparsers.add_parser(
        "framework",
        help="Manage assessment frameworks.",
        description="Create, list, update, delete, and manage assessment frameworks.",
        parents=[parent_parser],
        add_help=False
    )
    
    framework_parser.set_defaults(func=run_list_frameworks)
    framework_subparsers = framework_parser.add_subparsers(
        dest="framework_action", 
        help="Action to perform on a framework"
    )
    
    # --- kosmos framework list ---
    list_parser = framework_subparsers.add_parser(
        "list",
        help="List all assessment frameworks.",
        parents=[parent_parser],
        add_help=False
    )
    list_parser.set_defaults(func=run_list_frameworks)
    
    # --- kosmos framework create ---
    create_parser = framework_subparsers.add_parser(
        "create",
        help="Create a new assessment framework.",
        parents=[parent_parser],
        add_help=False
    )
    create_parser.add_argument("--name", required=True, help="The name of the framework.")
    create_parser.add_argument("--version", required=True, help="The version of the framework (e.g., '1.0.0').")
    create_parser.add_argument("--description", help="An optional description for the framework.")
    create_parser.add_argument("--source", help="An optional source URL or reference document.")
    create_parser.set_defaults(func=run_create_framework)
    
    # --- kosmos framework show ---
    show_parser = framework_subparsers.add_parser(
        "show",
        help="Show details for a specific framework.",
        parents=[parent_parser],
        add_help=False
    )
    show_parser.add_argument("id", help="The UUID of the framework to display.")
    show_parser.set_defaults(func=run_show_framework)

    # --- kosmos framework delete ---
    delete_parser = framework_subparsers.add_parser(
        "delete",
        help="Delete a framework.",
        parents=[parent_parser],
        add_help=False
    )
    delete_parser.add_argument("id", help="The UUID of the framework to delete.")
    delete_parser.set_defaults(func=run_delete_framework)

    # --- kosmos framework import-controls ---
    import_parser = framework_subparsers.add_parser(
        "import-controls",
        help="Bulk import control items from a JSONL file into a framework.",
        parents=[parent_parser],
        add_help=False
    )
    import_parser.add_argument("--framework-id", required=True, help="The UUID of the framework to import into.")
    import_parser.add_argument("--file", required=True, help="The local path to the .jsonl file.")
    import_parser.set_defaults(func=run_import_controls)

# Note: The 'kb_client' is passed to provide the token for the 'assessment_client'.
# The 'run_*' functions themselves will primarily use the 'assessment_client'.

def run_list_frameworks(kb_client: KosmosClient, assessment_client: AssessmentClient, args: any, config: CliConfig):
    """Handles the 'framework list' command."""
    try:
        frameworks = assessment_client.list_frameworks()
        
        # Process the list to summarize control items
        summarized_frameworks = []
        for framework in frameworks:
            summary = framework.copy() # Start with a copy of all metadata
            if 'control_item_definitions' in summary and isinstance(summary['control_item_definitions'], list):
                summary['control_item_definitions_count'] = len(summary['control_item_definitions'])
                del summary['control_item_definitions'] # Remove the large list
            summarized_frameworks.append(summary)
            
        print_json_response(summarized_frameworks)
    except Exception as e:
        print(f"错误: 无法列出框架: {e}", file=sys.stderr)
        sys.exit(1)

def run_create_framework(kb_client: KosmosClient, assessment_client: AssessmentClient, args: any, config: CliConfig):
    """Handles the 'framework create' command."""
    try:
        result = assessment_client.create_framework(
            name=args.name,
            version=args.version,
            description=args.description,
            source=args.source
        )
        print("框架创建成功。", file=sys.stderr)
        print_json_response(result)
    except Exception as e:
        print(f"错误: 无法创建框架: {e}", file=sys.stderr)
        sys.exit(1)

def run_show_framework(kb_client: KosmosClient, assessment_client: AssessmentClient, args: any, config: CliConfig):
    """Handles the 'framework show' command."""
    try:
        result = assessment_client.get_framework(args.id)
        print_json_response(result)
    except Exception as e:
        print(f"错误: 无法获取框架详情: {e}", file=sys.stderr)
        sys.exit(1)

def run_delete_framework(kb_client: KosmosClient, assessment_client: AssessmentClient, args: any, config: CliConfig):
    """Handles the 'framework delete' command."""
    try:
        assessment_client.delete_framework(args.id)
        print(f"框架 '{args.id}' 删除成功。", file=sys.stderr)
    except Exception as e:
        print(f"错误: 无法删除框架: {e}", file=sys.stderr)
        sys.exit(1)

def run_import_controls(kb_client: KosmosClient, assessment_client: AssessmentClient, args: any, config: CliConfig):
    """Handles the 'framework import-controls' command."""
    try:
        result = assessment_client.import_control_items(
            framework_id=args.framework_id,
            file_path=args.file
        )
        
        count = 0
        message = result.get("message", "")
        match = re.search(r'\d+', message)
        if match:
            count = int(match.group(0))
        
        print(f"成功向框架 '{args.framework_id}' 导入 {count} 个控制项。", file=sys.stderr)
        print_json_response(result)
    except Exception as e:
        print(f"错误: 无法导入控制项: {e}", file=sys.stderr)
        sys.exit(1)
