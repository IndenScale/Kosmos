import argparse
import os
import sys
import requests
from urllib.parse import urljoin
from cli import utils
from cli.knowledge_base_client import KosmosClient
from cli.config import CliConfig
from cli.commands.assessment import require_session

# --- Configuration for Assessment Service ---
ASSESSMENT_API_BASE_URL = os.getenv("ASSESSMENT_API_URL", "http://127.0.0.1:8015/api/v1/")

# --- API 调用函数 (agent actions) ---

def agent_action_api(token: str, session_id: str, action: str, payload: dict):
    """
    调用评估服务的代理动作接口 (search, read)。
    """
    url = urljoin(ASSESSMENT_API_BASE_URL, f"sessions/{session_id}/agent/{action}")
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        # Since this is not using the client's _request method, we need a way to handle errors.
        # For now, we'll print a simplified error. A better solution would be to
        # integrate this into the client's error handling.
        print(f"错误: 代理动作API请求失败 - {e}", file=sys.stderr)
        if e.response:
            print(f"响应 ({e.response.status_code}): {e.response.text}", file=sys.stderr)
        sys.exit(1)

def _get_agent_token(client: KosmosClient) -> str:
    """在AGENT模式下，使用环境变量中的用户名密码获取token"""
    if os.getenv("KOSMOS_MODE") == "AGENT":
        username = os.getenv("KOSMOS_USERNAME")
        password = os.getenv("KOSMOS_PASSWORD")
        if username and password:
            # 使用用户名密码登录获取token
            token_data = client.login(username, password)
            return token_data.get("access_token")
        else:
            print("错误: AGENT模式下未找到KOSMOS_USERNAME或KOSMOS_PASSWORD环境变量", file=sys.stderr)
            sys.exit(1)
    else:
        return client.get_raw_token()

# --- 命令注册与执行 ---

def register_subparser(subparsers, parent_parser):
    """为 'agent' 命令注册子解析器。"""
    p_agent = subparsers.add_parser(
        "agent", 
        help="执行绑定到当前评估会话的受控代理操作。",
        parents=[parent_parser]
    )
    
    # 为agent命令添加专属的session-id参数
    p_agent.add_argument("--session-id", help="评估会话ID (环境变量: KOSMOS_ASSESSMENT_SESSION_ID)。")
    
    # 创建一个包含session-id的agent父解析器，供子命令继承
    agent_parent_parser = argparse.ArgumentParser(add_help=False)
    agent_parent_parser.add_argument("--session-id", help="评估会话ID (环境变量: KOSMOS_ASSESSMENT_SESSION_ID)。")
    
    agent_sub = p_agent.add_subparsers(dest="subcommand", required=True, help="代理可执行的操作")

    # agent search
    p_search = agent_sub.add_parser("search", help="在当前会话的知识空间中执行搜索。", parents=[parent_parser, agent_parent_parser])
    p_search.add_argument("query", help="搜索查询语句。 সন")
    
    # --- Document Filtering (mirrored from search.py) ---
    g_doc = p_search.add_argument_group("Document Filters")
    g_doc.add_argument("--include-doc-id", action="append", dest="doc_ids_include", help="[+] 将搜索范围限定在指定的文档ID内 (可多次使用)。")
    g_doc.add_argument("--exclude-doc-id", action="append", dest="doc_ids_exclude", help="[-] 从搜索范围中排除指定的文档ID (可多次使用)。")
    g_doc.add_argument("--filename-contains", help="[+] 搜索文件名包含此字符串的文档。 সন")
    g_doc.add_argument("--filename-excludes", dest="filename_does_not_contain", help="[-] 排除文件名包含此字符串的文档。 সন")
    g_doc.add_argument("--ext-include", action="append", dest="extensions_include", help="[+] 只搜索指定扩展名的文件 (例如: --ext-include pdf)。")
    g_doc.add_argument("--ext-exclude", action="append", dest="extensions_exclude", help="[-] 排除指定扩展名的文件 (例如: --ext-exclude xlsx)。")

    # --- Content Filtering (mirrored from search.py) ---
    g_content = p_search.add_argument_group("Content Filters")
    g_content.add_argument("--contains-all", action="append", dest="keywords_include_all", help="[+] The content MUST contain ALL of these keywords (case-insensitive)。")
    g_content.add_argument("--excludes-any", action="append", dest="keywords_exclude_any", help="[-] The content must NOT contain ANY of these keywords (case-insensitive)。")

    # --- Result Tuning (mirrored from search.py) ---
    g_tune = p_search.add_argument_group("Result Tuning")
    g_tune.add_argument("--top-k", type=int, default=5, help="返回结果数量 (默认: 5)。")
    g_tune.add_argument("--boosters", nargs='+', help="用于影响排名的助推词列表。 সন")
    
    p_search.set_defaults(func=run_search)

    # agent read
    p_read = agent_sub.add_parser("read", help="在当前会话的知识空间中读取文档或书签。", parents=[parent_parser, agent_parent_parser])
    p_read.add_argument("doc_ref", help="要读取的文档ID或书签引用 (例如 @my_bookmark)。 সন")
    p_read.add_argument("--start", help="读取的起始位置 (行号或百分比)。")
    p_read.add_argument("--end", help="读取的结束位置 (行号或百分比)。")
    p_read.set_defaults(func=run_read)

    # agent grep
    p_grep = agent_sub.add_parser("grep", help="Perform a regex search across documents or a knowledge space in the current session.", parents=[parent_parser, agent_parent_parser])
    p_grep.add_argument("pattern", help="The regular expression pattern to search for. সন")
    
    scope_group = p_grep.add_mutually_exclusive_group()
    scope_group.add_argument("--doc", dest="document_ids", nargs='+', help="One or more document IDs to search within.")
    # 注意：--ks-id 是从父解析器继承的，映射到 args.ks_id

    p_grep.add_argument("--case-sensitive", action="store_true", help="Perform case-sensitive matching.")
    p_grep.add_argument("-m", "--max-matches-per-doc", type=int, help="Stop searching in a document after finding this many matches.")
    p_grep.add_argument("-B", "--before-context", type=int, default=0, dest="context_lines_before", help="Print NUM lines of leading context.")
    p_grep.add_argument("-A", "--after-context", type=int, default=0, dest="context_lines_after", help="Print NUM lines of trailing context.")
    p_grep.add_argument("-C", "--context", type=int, help="Print NUM lines of output context. Overrides -A and -B.")
    
    p_grep.add_argument("--json", action="store_true", dest="as_json", help="Output results in JSON format.")
    p_grep.add_argument("--max-output-chars", type=int, help="Maximum number of characters in output to prevent context overflow (default: 2500).")
    p_grep.set_defaults(func=run_grep)

def run_search(client: KosmosClient, args, config: CliConfig):
    """执行 'agent search' 命令。"""
    session_id = require_session(getattr(args, 'session_id', None), config) # Agent命令强制使用活动会话
    token = _get_agent_token(client)
    
    payload = {
        "query": args.query,
        "top_k": args.top_k,
        "doc_ids_include": args.doc_ids_include,
        "doc_ids_exclude": args.doc_ids_exclude,
        "filename_contains": args.filename_contains,
        "filename_does_not_contain": args.filename_does_not_contain,
        "extensions_include": args.extensions_include,
        "extensions_exclude": args.extensions_exclude,
        "keywords_include_all": args.keywords_include_all,
        "keywords_exclude_any": args.keywords_exclude_any,
        "boosters": args.boosters
    }
    payload = {k: v for k, v in payload.items() if v is not None}
    
    results = agent_action_api(token, session_id, "search", payload)
    
    print(f"--- 在会话 {session_id} 上下文中执行搜索 ---")
    utils.print_search_results(results)

def run_read(client: KosmosClient, args, config: CliConfig):
    """执行 'agent read' 命令。"""
    session_id = require_session(getattr(args, 'session_id', None), config)
    token = _get_agent_token(client)
    start_val = utils.parse_location(args.start) if args.start else None
    end_val = utils.parse_location(args.end) if args.end else None
    payload = {
        "doc_ref": args.doc_ref,
        "start": start_val,
        "end": end_val
    }
    payload = {k: v for k, v in payload.items() if v is not None}
    results = agent_action_api(token, session_id, "read", payload)

    print(f"--- 在会话 {session_id} 上下文中读取文档 ---")
    utils.print_read_results(results)

def run_grep(client: KosmosClient, args, config: CliConfig):
    """Executes the 'agent grep' command."""
    session_id = require_session(getattr(args, 'session_id', None), config)
    token = _get_agent_token(client)
    
    scope = {
        "knowledge_space_id": args.ks_id,  # 使用父解析器中的ks_id变量
        "document_ids": args.document_ids
    }

    if args.context is not None:
        context_before = args.context
        context_after = args.context
    else:
        context_before = args.context_lines_before
        context_after = args.context_lines_after

    payload = {
        "pattern": args.pattern,
        "scope": scope,
        "case_sensitive": args.case_sensitive,
        "max_matches_per_doc": args.max_matches_per_doc,
        "context_lines_before": context_before,
        "context_lines_after": context_after,
    }
    
    if payload.get("max_matches_per_doc") is None:
        del payload["max_matches_per_doc"]
    if scope.get("knowledge_space_id") is None:
        del scope["knowledge_space_id"]
    if scope.get("document_ids") is None:
        del scope["document_ids"]

    results = agent_action_api(token, session_id, "grep", payload)

    print(f"--- Grep results in session {session_id} ---")
    if args.as_json:
        utils.print_json_response(results)
    else:
        print_agent_grep_results(results, config.get_max_output_chars(args.max_output_chars))

def print_agent_grep_results(results, max_output_chars=2500):
    """Prints agent grep results with output length limit."""
    summary = results.get("summary", {})
    doc_results = results.get("results", [])
    
    output_lines = []
    current_chars = 0
    truncated = False
    
    if not doc_results:
        print("No matches found.")
        return
    
    for i, doc_result in enumerate(doc_results):
        if i > 0:
            separator = "\n" + "="*80 + "\n"
            if current_chars + len(separator) > max_output_chars:
                truncated = True
                break
            output_lines.append(separator)
            current_chars += len(separator)
            
        doc_name = doc_result.get('document_name', 'N/A')
        doc_id = doc_result.get('document_id')
        doc_truncated = " (results truncated)" if doc_result.get('truncated') else ""
        
        header = f"--- Matches in: {doc_name} ({doc_id}){doc_truncated} ---"
        if current_chars + len(header) > max_output_chars:
            truncated = True
            break
        output_lines.append(header)
        current_chars += len(header)
        
        for j, match in enumerate(doc_result.get('matches', [])):
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
            
            for line in match['lines']:
                formatted_line = f"  {line}"
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

    # Print summary
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
