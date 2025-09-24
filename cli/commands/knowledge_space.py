"""
Kosmos CLI的 `knowledge-space` (或 `ks`) 命令。

提供用于管理知识空间 (Knowledge Spaces) 的子命令。
"""
import sys
from argparse import ArgumentParser, _SubParsersAction
from ..knowledge_base_client import KosmosClient
from ..config import CliConfig
from .. import utils

def register_subparser(subparsers: _SubParsersAction, parent_parser: ArgumentParser):
    """为 `knowledge-space` 命令注册子解析器。"""
    ks_parser = subparsers.add_parser(
        "knowledge-space",
        help="管理知识空间。",
        aliases=['ks'],
        parents=[parent_parser],
        add_help=False
    )
    ks_parser.set_defaults(func=run_list)  # 设置默认动作为 list
    ks_subparsers = ks_parser.add_subparsers(dest="ks_command", help="知识空间操作") # 移除 required=True

    # --- List 命令 ---
    list_parser = ks_subparsers.add_parser("list", help="列出您是其成员的所有知识空间。")
    list_parser.set_defaults(func=run_list)

    # --- Create 命令 ---
    create_parser = ks_subparsers.add_parser("create", help="创建一个新的知识空间。")
    create_parser.add_argument("--name", required=True, help="新知识空间的名称。")
    create_parser.set_defaults(func=run_create)

    # --- Update 命令 ---
    update_parser = ks_subparsers.add_parser("update", help="更新一个知识空间的名称。")
    update_parser.add_argument("--ks-id", required=True, help="要更新的知识空间ID。")
    update_parser.add_argument("--name", required=True, help="知识空间的新名称。")
    update_parser.set_defaults(func=run_update)

    # --- Delete 命令 ---
    delete_parser = ks_subparsers.add_parser("delete", help="删除一个知识空间。")
    delete_parser.add_argument("--ks-id", nargs='?', default=None, help="要删除的知识空间ID (如果未提供，则使用配置中的默认值)。")
    delete_parser.add_argument("-y", "--yes", action="store_true", help="跳过删除确认提示。")
    delete_parser.set_defaults(func=run_delete)

# --- 命令执行函数 ---

def run_list(client: KosmosClient, args, config: CliConfig):
    """执行 `ks list` 命令。"""
    results = client.list_knowledge_spaces()
    utils.print_json_response(results)

def run_create(client: KosmosClient, args, config: CliConfig):
    """执行 `ks create` 命令。"""
    result = client.create_knowledge_space(name=args.name)
    utils.print_json_response(result)

def run_update(client: KosmosClient, args, config: CliConfig):
    """执行 `ks update` 命令。"""
    ks_id = config.require(args.ks_id, "KOSMOS_KS_ID", "知识空间ID")
    result = client.update_knowledge_space(ks_id=ks_id, new_name=args.name)
    utils.print_json_response(result)

def run_delete(client: KosmosClient, args, config: CliConfig):
    """执行 `ks delete` 命令。"""
    ks_id = config.require(getattr(args, 'ks_id'), "KOSMOS_KS_ID", "知识空间ID")
    
    # 增加一个危险操作的确认步骤
    if not args.yes:
        try:
            confirm = input(f"您确定要删除知识空间 '{ks_id}' 吗？此操作不可逆。[y/N]: ")
            if confirm.lower() != 'y':
                print("操作已取消。", file=sys.stderr)
                sys.exit(0)
        except (EOFError, KeyboardInterrupt):
            print("\n操作已取消。", file=sys.stderr)
            sys.exit(1)
            
    client.delete_knowledge_space(ks_id=ks_id)
    utils.print_json_response({"status": "deleted", "knowledge_space_id": ks_id})
