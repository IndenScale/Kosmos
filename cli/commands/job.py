import argparse
import sys
from cli import utils
from cli.knowledge_base_client import KosmosClient

def register_subparser(subparsers, parent_parser):
    """为 'job' 命令注册子解析器，并设置默认的 list 行为。"""
    p_job = subparsers.add_parser(
        "job", 
        help="管理和监控后台作业。默认操作是列出作业。",
        parents=[parent_parser]
    )
    
    # --- 将所有过滤参数添加到主 'job' 解析器 ---
    p_job.add_argument("--job-id", help="按单个作业ID精确过滤。")
    p_job.add_argument("--doc-id", dest="document_id", help="按文档ID过滤作业。")
    p_job.add_argument("--job-type", help="按作业类型过滤。")
    p_job.add_argument("--status", help="按作业状态过滤。")
    p_job.add_argument("--limit", type=int, default=20, help="要返回的结果数量 (默认: 20)。")
    p_job.add_argument("--cursor", help="用于分页的光标。")
    
    # 设置默认函数为 run_list
    p_job.set_defaults(func=run_list)

    # --- 为动作类操作创建子解析器 ---
    job_subparsers = p_job.add_subparsers(dest="job_command", help="可用的作业操作")

    # --- job cancel ---
    p_cancel = job_subparsers.add_parser(
        "cancel",
        help="中止与特定文档关联的正在运行或待处理的作业。",
        parents=[parent_parser]
    )
    p_cancel.add_argument("document_id", help="要中止其作业的文档ID。")
    p_cancel.add_argument("--job-type", help="（可选）只中止特定类型的作业。")
    p_cancel.set_defaults(func=run_cancel)

    # --- job delete ---
    p_delete = job_subparsers.add_parser(
        "delete",
        help="按ID批量删除一个或多个作业。",
        parents=[parent_parser]
    )
    p_delete.add_argument("job_ids", nargs='+', help="要删除的一个或多个作业ID。")
    p_delete.add_argument("--force", action="store_true", help="强制删除，即使作业正在运行。")
    p_delete.set_defaults(func=run_delete)

def run_list(client: KosmosClient, args, config):
    """执行 'job list' (或默认的 'job') 命令。"""
    ks_id = args.ks_id
    
    # 如果提供了 job_id，则优先使用它进行精确查找
    if args.job_id:
        print(f"正在获取作业 {args.job_id} 的详细信息...", file=sys.stderr)
        params = {"job_id": args.job_id}
    else:
        print("正在查询作业列表...", file=sys.stderr)
        params = {
            "knowledge_space_id": ks_id,
            "document_id": args.document_id,
            "job_type": args.job_type,
            "status": args.status,
            "limit": args.limit,
            "cursor": args.cursor,
        }
    
    results = client.list_jobs(**params)
    
    if not results.get("items"):
        print("未找到符合条件的作业。")
        return
        
    utils.print_json_response(results)

def run_cancel(client: KosmosClient, args, config):
    """执行 'job cancel' 命令。"""
    print(f"正在为文档 {args.document_id} 中止作业...", file=sys.stderr)
    result = client.abort_jobs(
        document_ids=[args.document_id],
        job_type=args.job_type
    )
    print(f"成功中止了 {result.get('aborted_jobs_count', 0)} 个作业。")

def run_delete(client: KosmosClient, args, config):
    """执行 'job delete' 命令。"""
    job_count = len(args.job_ids)
    print(f"准备删除 {job_count} 个作业...", file=sys.stderr)
    
    # 为安全起见，可以增加一个确认步骤
    # if not args.force:
    #     confirm = input(f"您确定要删除这 {job_count} 个作业吗? [y/N]: ")
    #     if confirm.lower() != 'y':
    #         print("操作已取消。")
    #         return
            
    result = client.delete_jobs(
        job_ids=args.job_ids,
        force=args.force
    )
    print(result.get("detail", "操作已成功执行。"))