"""
General utility functions and response printers for the CLI.
"""
import json
import sys
import argparse
from typing import Union, List, Dict, Any

# --- General Helper Functions ---

def parse_location(loc_str: str | None) -> Union[int, float, None]:
    """Parses a string into an integer (line number) or a float (percentage)."""
    if loc_str is None:
        return None
    if '.' in loc_str:
        try:
            val = float(loc_str)
            if not 0.0 <= val <= 1.0:
                raise ValueError("百分比必须在 0.0 和 1.0 之间。")
            return val
        except ValueError as e:
            print(f"错误: 无效的百分比格式 '{loc_str}'. {e}", file=sys.stderr)
            sys.exit(1)
    else:
        try:
            val = int(loc_str)
            if val < 1:
                raise ValueError("行号必须是大于等于1的整数。")
            return val
        except ValueError as e:
            print(f"错误: 无效的行号格式 '{loc_str}'. {e}", file=sys.stderr)
            sys.exit(1)

# --- Response Printing Functions ---

def print_json_response(data: Any):
    """Prints an API response in a beautified JSON format."""
    print(json.dumps(data, indent=2, ensure_ascii=False))

def print_search_results(results_data):
    if not results_data or not results_data.get("results"):
        print("未找到结果。" )
        return
    print(f"找到 {len(results_data['results'])} 条结果:\n")
    for i, result in enumerate(results_data["results"], 1):
        print(f"--- 结果 {i} ---")
        print(f"  文档: {result.get('document_filename', 'N/A')} (ID: {result.get('document_id', 'N/A')})")
        print(f"  块ID: {result.get('chunk_id', 'N/A')}")
        print(f"  得分: {result.get('score', 0.0):.4f}")
        print(f"  行号: {result.get('start_line', 'N/A')} - {result.get('end_line', 'N/A')}")
        print("\n  内容:")
        content = result.get('content', '').strip()
        for line in content.split('\n'):
            print(f"    {line}")
        print("\n" + "="*40 + "\n")

def print_read_results(results_data):
    """Prints the results from the read_api, adapting to the new 'lines' structure."""
    lines_with_meta = results_data.get("lines", [])
    start_line = results_data.get("start_line", "N/A")
    end_line = results_data.get("end_line", "N/A")
    total_lines = results_data.get("total_lines", "N/A")
    assets = results_data.get("assets", [])
    
    # Reconstruct the content string from the lines array for printing
    content = "\n".join(line['content'] for line in lines_with_meta)

    print(f"--- 文档内容 (行 {start_line} - {end_line} / 共 {total_lines} 行) ---")
    print(content)
    print("--- 内容结束 ---")

    if assets:
        print("\n--- 关联资产信息 ---")
        # Use print_json_response for detailed, structured output
        print_json_response(assets)
        print("--- 资产信息结束 ---")


def print_asset_analysis_detail(result: Dict[str, Any], doc_id: str, asset_id: str):
    """Prints the detailed analysis result for an asset in a document context."""
    print("--- 资产分析详情 ---")
    print(f"文档 ID: {doc_id}")
    print(f"资产 ID: {asset_id}")
    print(f"分析状态: {result.get('analysis_status')}")
    
    # Use the description directly from the top-level of the response
    description = result.get('description')
    
    if description:
        print("\n--- 分析结果 ---")
        print(f"模型版本: {result.get('model_version', 'N/A')}")
        print("\n描述:")
        if isinstance(description, dict):
            print(json.dumps(description, indent=2, ensure_ascii=False))
        else:
            print(description)
    else:
        print("\n--- 分析结果 ---")
        print(f"尚未生成分析结果。({result.get('detail', 'No details provided')})")

    print("--- 详情结束 ---")


def print_asset_analysis(results_data, asset_id):
    status = results_data.get("analysis_status", "N/A")
    model = results_data.get("model_version", "N/A")
    description = results_data.get("description", "")

    detail = results_data.get("detail")

    print(f"--- 资产分析结果 (ID: {asset_id}) ---")
    print(f"状态: {status}")
    if status != "ANALYSIS_FAILED":
        print(f"模型: {model}")
        print("描述:")
        if description:
            for line in description.strip().split('\n'):
                print(f"  {line}")
    if detail:
        print(f"详细信息: {detail}")
    print("--- 分析结束 ---")

def print_bookmark_tree(bookmarks: List[Dict[str, Any]]):
    if not bookmarks:
        print("未找到书签。" )
        return

    nodes = {b['id']: b for b in bookmarks}
    children_map = {b['id']: [] for b in bookmarks}
    root_nodes = []

    for b_id, b in nodes.items():
        if b['parent_id'] and b['parent_id'] in nodes:
            children_map[b['parent_id']].append(b)
        else:
            root_nodes.append(b)

    def _print_node(node, prefix=""):
        doc_info = ""
        if node.get('document_id'):
            lines = f"{node.get('start_line', '?')}-{node.get('end_line', '?')}"
            doc_info = f" (doc: ...{node['document_id'][-4:]}, lines: {lines})"
        
        visibility = "🔒" if node.get('visibility', 'private') == 'private' else "🌐"
        print(f"{prefix}- {visibility} {node['name']}{doc_info}")

        children = sorted(children_map.get(node['id'], []), key=lambda x: x['name'])
        for i, child in enumerate(children):
            new_prefix = prefix + ("  " if i == len(children) - 1 else "│ ")
            _print_node(child, new_prefix)

    print("--- 书签列表 ---")
    for node in sorted(root_nodes, key=lambda x: x['name']):
        _print_node(node)
    print("--- 列表结束 ---")


class SubcommandHelpFormatter(argparse.RawDescriptionHelpFormatter):
    """
    一个自定义的帮助格式化程序，用于在显示子命令列表时提供更好的布局，
    并保留主命令和子命令描述中的原始换行格式。
    """
    def _format_action(self, action):
        # 调用父类的方法来获取大部分的格式化字符串
        parts = super()._format_action(action)
        # 如果动作是子解析器（即我们的子命令），则进行特殊处理
        if action.nargs == argparse.PARSER:
            # 将默认的 "{cmd1,cmd2,..." 替换为更清晰的格式
            parts = parts.replace('{', '').replace('}', '')
            # 移除自动生成的 "positional arguments:" 或类似标题
            # 因为我们已经在子解析器中定义了 "help"
            if "positional arguments:" in parts:
                 parts = "\n".join(parts.split("\n")[2:])
        return parts