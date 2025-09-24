import sys
from cli import utils
from cli.knowledge_base_client import KosmosClient
from cli.config import CliConfig

def register_subparser(subparsers, parent_parser):
    """为 'bookmark' 命令注册子解析器。"""
    p_bookmark = subparsers.add_parser(
        "bookmark", 
        help="管理书签。",
        parents=[parent_parser]
    )
    bm_sub = p_bookmark.add_subparsers(dest="subcommand", required=True, help="书签操作")
    
    # list
    bm_list = bm_sub.add_parser("list", help="以树状结构列出书签。", parents=[parent_parser])
    bm_list.set_defaults(func=run_list)
    
    # add
    bm_add = bm_sub.add_parser("add", help="添加一个新书签。", parents=[parent_parser])
    bm_add.add_argument("name", help="书签的名称。")
    bm_add.add_argument("--doc-id", help="为书签关联一个可选的文档ID。")
    bm_add.add_argument("--lines", nargs=2, metavar=('START', 'END'), help="关联的行号范围。")
    bm_add.add_argument("--parent-name", help="父书签的名称。")
    bm_add.add_argument("--public", action="store_true", help="创建为公共书签 (默认: 私有)。")
    bm_add.set_defaults(func=run_add)

    # rm
    bm_rm = bm_sub.add_parser("rm", help="删除一个书签。", parents=[parent_parser])
    bm_rm.add_argument("name", help="要删除的书签名称。")
    bm_rm.set_defaults(func=run_rm)

def run_list(client: KosmosClient, args, config: CliConfig):
    """执行 'bookmark list'。"""
    ks_id = config.require(args.ks_id, "KOSMOS_KS_ID", "知识空间ID")
    bookmarks = client.list_bookmarks(ks_id)
    utils.print_bookmark_tree(bookmarks)

def run_add(client: KosmosClient, args, config: CliConfig):
    """执行 'bookmark add'。"""
    ks_id = config.require(args.ks_id, "KOSMOS_KS_ID", "知识空间ID")
    payload = {
        "name": args.name,
        "knowledge_space_id": ks_id,
        "visibility": "public" if args.public else "private"
    }
    
    # doc_id 现在只接受 --doc-id 标志，不再回退到环境变量
    doc_id = args.doc_id
    if doc_id:
        payload["document_id"] = doc_id
        
    if args.lines:
        payload["start_line"] = int(args.lines[0])
        payload["end_line"] = int(args.lines[1])
    
    if args.parent_name:
        all_bookmarks = client.list_bookmarks(ks_id)
        parent = next((b for b in all_bookmarks if b['name'] == args.parent_name), None)
        if not parent:
            print(f"错误: 未找到名为 '{args.parent_name}' 的父书签。", file=sys.stderr)
            sys.exit(1)
        payload["parent_id"] = parent["id"]

    client.create_bookmark(payload)
    print(f"书签 '{args.name}' 已成功添加。")

def run_rm(client: KosmosClient, args, config: CliConfig):
    """执行 'bookmark rm'。"""
    ks_id = config.require(args.ks_id, "KOSMOS_KS_ID", "知识空间ID")
    all_bookmarks = client.list_bookmarks(ks_id)
    bookmark_to_delete = next((b for b in all_bookmarks if b['name'] == args.name), None)
    if not bookmark_to_delete:
        print(f"错误: 未找到名为 '{args.name}' 的书签。", file=sys.stderr)
        sys.exit(1)
    
    client.delete_bookmark(bookmark_to_delete['id'])
    print(f"书签 '{args.name}' 已成功删除。")
