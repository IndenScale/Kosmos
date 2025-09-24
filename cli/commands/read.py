import sys
from cli import utils
from cli.knowledge_base_client import KosmosClient

def register_subparser(subparsers, parent_parser):
    """为 'read' 命令注册子解析器。"""
    p_read = subparsers.add_parser(
        "read", 
        help="读取文档的特定部分。",
        parents=[parent_parser]
    )
    
    # 支持两种方式：位置参数或 --doc-id 参数
    doc_group = p_read.add_mutually_exclusive_group(required=True)
    doc_group.add_argument("doc_ref", nargs='?', help="要读取的文档ID或书签引用 (例如 @my_bookmark)。")
    doc_group.add_argument("--doc-id", dest="doc_id", help="要读取的文档ID。")
    
    p_read.add_argument("--start", help="读取的起始位置 (行号或百分比)。如果使用书签，则此项被忽略。")
    p_read.add_argument("--end", help="读取的结束位置 (行号或百分比)。如果使用书签，则此项被忽略。")
    p_read.add_argument("--max-lines", type=int, default=100, help="要读取的最大行数 (默认: 100)。")
    p_read.add_argument("--max-chars", type=int, default=8192, help="要读取的最大字符数 (默认: 8192)。")
    p_read.add_argument('--no-preserve-integrity', dest='preserve_integrity', action='store_false', help="禁用完整性保护。")
    p_read.set_defaults(preserve_integrity=True, func=run)

def run(client: KosmosClient, args, config):
    """执行 'read' 命令。"""
    ks_id = config.resolve(args.ks_id, "KOSMOS_KS_ID")
    
    # 确定文档引用：优先使用 --doc-id，否则使用位置参数 doc_ref
    doc_ref = args.doc_id if args.doc_id else args.doc_ref
    
    if doc_ref.startswith('@') and not ks_id:
        print("错误: 使用书签读取时，必须提供 --ks-id 或设置 KOSMOS_KS_ID 环境变量。", file=sys.stderr)
        sys.exit(1)

    start_val, end_val = (None, None)
    if not doc_ref.startswith('@'):
        start_val = utils.parse_location(args.start or '1')
        end_val = utils.parse_location(args.end)
        
    results = client.read(
        doc_ref=doc_ref, 
        start=start_val, 
        end=end_val, 
        max_lines=args.max_lines, 
        max_chars=args.max_chars, 
        preserve_integrity=args.preserve_integrity, 
        ks_id=ks_id
    )
    utils.print_read_results(results)
