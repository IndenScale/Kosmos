import sys
import json
from cli import utils
from cli.knowledge_base_client import KosmosClient
from cli.config import CliConfig

def register_subparser(subparsers, parent_parser):
    """Registers the subparser for the 'grep' command."""
    # 不使用 parents 参数，手动添加需要的全局参数以允许覆盖
    p_grep = subparsers.add_parser(
        "grep",
        help="Perform a regex search across documents or a knowledge space."
    )
    
    # 手动添加全局参数，允许子命令覆盖
    p_grep.add_argument("--username", help="Kosmos用户名 (仅用于 'login' 命令)。")
    p_grep.add_argument("--password", help="Kosmos密码 (仅用于 'login' 命令)。")
    p_grep.add_argument("--asset-id", help="资产ID (环境变量: KOSMOS_ASSET_ID)。")
    
    p_grep.add_argument("pattern", help="The regular expression pattern to search for.")
    
    scope_group = p_grep.add_mutually_exclusive_group()
    scope_group.add_argument(
        "--doc-id",
        dest="document_ids",
        nargs='+',
        help="One or more document IDs to search within."
    )
    # 在子命令中重新定义 --ks-id，覆盖全局定义
    scope_group.add_argument(
        "--ks-id",
        dest="knowledge_space_id_scope", 
        help="A knowledge space ID to search within all its documents (overrides global --ks-id)."
    )

    p_grep.add_argument(
        "--case-sensitive",
        action="store_true",
        help="Perform case-sensitive matching (default is case-insensitive)."
    )
    p_grep.add_argument(
        "-m", "--max-matches-per-doc",
        type=int,
        help="Stop searching in a document after finding this many matches."
    )
    p_grep.add_argument(
        "-B", "--before-context",
        type=int,
        default=0,
        dest="context_lines_before",
        help="Print NUM lines of leading context before matching lines."
    )
    p_grep.add_argument(
        "-A", "--after-context",
        type=int,
        default=0,
        dest="context_lines_after",
        help="Print NUM lines of trailing context after matching lines."
    )
    p_grep.add_argument(
        "-C", "--context",
        type=int,
        help="Print NUM lines of output context. Overrides -A and -B."
    )

    p_grep.add_argument(
        "--doc-ext",
        dest="doc_ext",
        help="Filter search to only include documents with this file extension (e.g., .pdf, .xlsx)."
    )

    p_grep.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Output results in JSON format for programmatic use."
    )
    p_grep.add_argument(
        "--max-output-chars",
        type=int,
        help="Maximum number of characters in output to prevent context overflow (default: 200000)."
    )
    p_grep.set_defaults(func=run)

def run(client: KosmosClient, args, config: CliConfig):
    """Executes the 'grep' command."""
    
    # Determine the scope for the search
    ks_id = args.knowledge_space_id_scope
    doc_ids = args.document_ids

    # If no specific scope is provided via --ks or --doc, use the globally provided --ks-id
    # or fall back to the active knowledge space from the config.
    if not ks_id and not doc_ids:
        # The global --ks-id from parent_parser is available in args.ks_id
        ks_id = config.require(args.ks_id, "KOSMOS_KS_ID", "知识空间ID")

    # Handle context arguments: -C overrides -A and -B
    if args.context is not None:
        context_before = args.context
        context_after = args.context
    else:
        context_before = args.context_lines_before
        context_after = args.context_lines_after

    results = client.multi_document_grep(
        pattern=args.pattern,
        knowledge_space_id=ks_id,
        document_ids=doc_ids,
        doc_ext=args.doc_ext,
        case_sensitive=args.case_sensitive,
        max_matches_per_doc=args.max_matches_per_doc,
        context_lines_before=context_before,
        context_lines_after=context_after
    )

    if args.as_json:
        utils.print_json_response(results)
    else:
        print_grep_results(results, config.get_max_output_chars(args.max_output_chars))

def print_grep_results(data, max_output_chars=200000):
    """Prints grep results in a user-friendly format with output length limit."""
    results = data.get("results", [])
    summary = data.get("summary", {})
    
    output_lines = []
    current_chars = 0
    truncated = False

    if not results:
        print("No matches found.")
        return
    
    for i, doc_result in enumerate(results):
        if i > 0:
            separator = "\n" + "="*80 + "\n"
            if current_chars + len(separator) > max_output_chars:
                truncated = True
                break
            output_lines.append(separator)
            current_chars += len(separator)
        
        doc_name = doc_result.get('document_name', 'N/A')
        doc_id = doc_result.get('document_id')
        matches = doc_result.get('matches', [])
        doc_truncated = " (results truncated)" if doc_result.get('truncated') else ""
        
        header = f"--- Matches in: {doc_name} ({doc_id}){doc_truncated} ---"
        if current_chars + len(header) > max_output_chars:
            truncated = True
            break
        output_lines.append(header)
        current_chars += len(header)
        
        for j, match in enumerate(matches):
            if j > 0:
                separator = "--"
                if current_chars + len(separator) > max_output_chars:
                    truncated = True
                    break
                output_lines.append(separator)
                current_chars += len(separator)
            
            match_line = f"Match at line {match['match_line_number']}:"
            if current_chars + len(match_line) > max_output_chars:
                truncated = True
                break
            output_lines.append(match_line)
            current_chars += len(match_line)
            
            for line_content in match['lines']:
                formatted_line = f"  {line_content}"
                if current_chars + len(formatted_line) > max_output_chars:
                    truncated = True
                    break
                output_lines.append(formatted_line)
                current_chars += len(formatted_line)
            
            if truncated:
                break
        
        if truncated:
            break

    # Print all collected output
    for line in output_lines:
        print(line)
    
    if truncated:
        print(f"\n[OUTPUT TRUNCATED - Exceeded {max_output_chars} character limit]")

    # Print summary at the very end
    summary_text = f"""
{"="*80}
Grep Summary:
  Documents Searched: {summary.get('documents_searched', 0)}
  Documents with Matches: {summary.get('documents_with_matches', 0)}
  Total Matches Found: {summary.get('total_matches', 0)}"""
    
    if summary.get('results_truncated'):
        summary_text += "\n  Warning: Results for one or more documents were truncated."
    if truncated:
        summary_text += "\n  Warning: Output was truncated due to length limit."
    
    summary_text += f"\n{'='*80}"
    
    print(summary_text)