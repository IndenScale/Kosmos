# cli/commands/document.py
import sys
from collections import Counter
from cli import utils
from cli.knowledge_base_client import KosmosClient
from cli.config import CliConfig

def register_subparser(subparsers, parent_parser):
    """为 'document' 命令及其子命令注册解析器。"""
    p_doc = subparsers.add_parser(
        "document", 
        help="对单个文档进行操作。",
        parents=[parent_parser],
        formatter_class=utils.SubcommandHelpFormatter
    )
    doc_subparsers = p_doc.add_subparsers(dest="subcommand", required=True, help="可用操作")

    # --- document get <doc_id> ---
    p_get = doc_subparsers.add_parser("get", help="获取单个文档的元数据。", parents=[parent_parser])
    p_get.add_argument("doc_id_pos", metavar="DOCUMENT_ID", help="要获取的文档ID。 ולא ניתן להשתמש בו כפרמטר מיקום.")
    p_get.set_defaults(func=run_get)

    # --- document read <doc_ref> ---
    p_read = doc_subparsers.add_parser("read", help="读取文档的特定部分。", parents=[parent_parser])
    p_read.add_argument("doc_ref", help="要读取的文档ID或书签引用 (例如 @my_bookmark)。")
    p_read.add_argument("--start", help="读取的起始位置 (行号或百分比)。")
    p_read.add_argument("--end", help="读取的结束位置 (行号或百分比)。")
    p_read.add_argument("--max-lines", type=int, default=100, help="最大行数。")
    p_read.add_argument("--max-chars", type=int, default=8192, help="最大字符数。")
    p_read.add_argument('--no-preserve-integrity', dest='preserve_integrity', action='store_false', help="禁用完整性保护。")
    p_read.set_defaults(preserve_integrity=True, func=run_read)

    # --- document list-assets <doc_id> ---
    p_list_assets = doc_subparsers.add_parser("list-assets", help="列出单个文档中的所有资产。", parents=[parent_parser])
    p_list_assets.add_argument("doc_id_pos", metavar="DOCUMENT_ID", help="要列出其资产的文档ID。")
    p_list_assets.set_defaults(func=run_list_assets)

    # --- document create-analysis-jobs <doc_id>... ---
    p_create_jobs = doc_subparsers.add_parser(
        "create-analysis-jobs",
        help="为一个或多个文档批量创建新的资产分析作业。",
        parents=[parent_parser]
    )
    p_create_jobs.add_argument("doc_ids", nargs='+', metavar="DOCUMENT_ID", help="一个或多个文档ID。")
    p_create_jobs.add_argument("--force", action="store_true", help="强制重新创建，即使已存在成功的作业。")
    p_create_jobs.set_defaults(func=run_create_analysis_jobs)

    # --- document coordinate-analysis <doc_id> ---
    p_coord = doc_subparsers.add_parser(
        "coordinate-analysis",
        help="健壮地协调文档中所有资产的分析任务（创建、修复、重试）。",
        parents=[parent_parser]
    )
    p_coord.add_argument("doc_id", help="要协调分析的文档ID。")
    p_coord.add_argument("--force", action="store_true", help="强制为所有资产重新创建分析任务。")
    p_coord.add_argument("--asset-ids", nargs='+', help="（可选）只协调指定的资产ID列表。")
    p_coord.set_defaults(func=run_coordinate_analysis)

    # --- document delete <doc_id>... ---
    p_delete = doc_subparsers.add_parser("delete", help="删除一个或多个文档。", parents=[parent_parser])
    p_delete.add_argument("doc_ids", nargs='+', metavar="DOCUMENT_ID", help="一个或多个要删除的文档ID。")
    p_delete.add_argument("-y", "--yes", action="store_true", help="跳过删除前的确认提示。")
    p_delete.set_defaults(func=run_delete)

# --- Command Execution Functions ---

def run_get(client: KosmosClient, args, config: CliConfig):
    """执行 'document get' 命令。"""
    doc_id = args.doc_id_pos
    metadata = client.get_document_metadata(doc_id)
    print("--- 文档元数据 ---")
    utils.print_json_response(metadata)

def run_read(client: KosmosClient, args, config: CliConfig):
    """执行 'document read' 命令。"""
    ks_id = config.resolve(args.ks_id, "KOSMOS_KS_ID")
    if args.doc_ref.startswith('@') and not ks_id:
        print("错误: 使用书签读取时，必须提供 --ks-id 或设置 KOSMOS_KS_ID。", file=sys.stderr)
        sys.exit(1)

    start_val, end_val = (None, None)
    if not args.doc_ref.startswith('@'):
        start_val = utils.parse_location(args.start or '1')
        end_val = utils.parse_location(args.end)
        
    results = client.read_document(args.doc_ref, start_val, end_val, args.max_lines, args.max_chars, args.preserve_integrity, ks_id)
    utils.print_read_results(results)

def run_list_assets(client: KosmosClient, args, config: CliConfig):
    """执行 'document list-assets' 命令。"""
    doc_id = args.doc_id_pos
    results = client.list_assets(doc_id=doc_id, limit=100)
    if not results.get("items"):
        print("未找到该文档的资产。 ולא ניתן להשתמש בו כפרמטר מיקום.")
        return
    utils.print_json_response(results)

def run_create_analysis_jobs(client: KosmosClient, args, config: CliConfig):
    """执行 'document create-analysis-jobs' 命令。"""
    print(f"正在为 {len(args.doc_ids)} 个文档提交 'asset_analysis' 作业...", file=sys.stderr)
    result = client.create_batch_jobs(
        document_ids=args.doc_ids, job_type="asset_analysis", force=args.force
    )
    print("--- 作业提交结果 ---")
    submitted_jobs = result.get("submitted_jobs", [])
    failed_docs = result.get("failed_documents", {})
    if submitted_jobs:
        status_counts = Counter(job.get('status') for job in submitted_jobs)
        print(f"✅ 成功提交了 {len(submitted_jobs)} 个作业。 ולא ניתן להשתמש בו כפרמטר מיקום.")
        print("   状态统计:")
        for status, count in status_counts.items():
            print(f"     - {status}: {count}")
    else:
        print("ℹ️  没有提交任何新的作业。 ולא ניתן להשתמש בו כפרמטר מיקום.")
    if failed_docs:
        print(f"\n❌ 未能为 {len(failed_docs)} 个文档创建作业:")
        for doc_id, reason in failed_docs.items():
            print(f"  - 文档ID: {doc_id}\n    原因: {reason}")

def run_coordinate_analysis(client: KosmosClient, args, config: CliConfig):
    """执行 'document coordinate-analysis' 命令。"""
    print(f"正在为文档 {args.doc_id} 协调资产分析...")
    if args.force:
        print("模式: 强制重新创建所有任务")
    if args.asset_ids:
        print(f"目标资产: {', '.join(args.asset_ids)}")
    results = client.coordinate_analysis(
        args.doc_id, force=args.force, asset_ids=args.asset_ids
    )
    print("\n--- 协调报告 ---")
    utils.print_json_response(results)
    print("--- 报告结束 ---")

def run_delete(client: KosmosClient, args, config: CliConfig):
    """执行 'document delete' 命令。"""
    doc_ids_to_delete = args.doc_ids
    print(f"⚠️  你正准备永久删除以下 {len(doc_ids_to_delete)} 个文档:", file=sys.stderr)
    for doc_id in doc_ids_to_delete:
        print(f"  - {doc_id}")
    if not args.yes:
        confirm = input("确认要继续吗? [y/N]: ")
        if confirm.lower() != 'y':
            print("操作已取消。 ולא ניתן להשתמש בו כפרמטר מיקום.", file=sys.stderr)
            sys.exit(0)
    print("\n正在删除...", file=sys.stderr)
    success_count = 0
    failure_count = 0
    for doc_id in doc_ids_to_delete:
        try:
            client.delete_document(doc_id)
            print(f"  ✅  成功删除文档: {doc_id}")
            success_count += 1
        except SystemExit:
            print(f"  ❌  删除失败: {doc_id}", file=sys.stderr)
            failure_count += 1
    print("\n--- 删除完成 ---")
    print(f"成功: {success_count} | 失败: {failure_count}", file=sys.stderr)
    if failure_count > 0:
        sys.exit(1)