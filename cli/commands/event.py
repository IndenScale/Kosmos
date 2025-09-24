import sys
from cli import utils
from cli.knowledge_base_client import KosmosClient

def register_subparser(subparsers, parent_parser):
    """为 'event' 命令注册子解析器。"""
    p_event = subparsers.add_parser(
        "event",
        help="查询和监控领域事件。",
        parents=[parent_parser]
    )
    
    event_subparsers = p_event.add_subparsers(dest="event_command", required=True)
    
    # --- 'event list' 子命令 ---
    p_list = event_subparsers.add_parser(
        "list",
        help="列出并过滤领域事件。",
        parents=[parent_parser]
    )
    p_list.add_argument("--event-type", help="按事件类型过滤 (例如, 'DocumentRegisteredPayload')。")
    p_list.add_argument("--status", choices=["pending", "processed", "failed", "aborted"], help="按事件状态过滤。")
    p_list.add_argument("--aggregate-id", help="按聚合ID过滤 (例如, 文档ID)。")
    p_list.add_argument("--page-size", type=int, default=20, help="每页返回的事件数量。")
    p_list.add_argument("--cursor", help="用于分页的光标。")
    p_list.set_defaults(func=run_list)

def run_list(client: KosmosClient, args, config):
    """执行 'event list' 命令。"""
    print("正在查询领域事件...", file=sys.stderr)
    
    params = {
        "event_type": args.event_type,
        "status": args.status,
        "aggregate_id": args.aggregate_id,
        "page_size": args.page_size,
        "cursor": args.cursor,
    }
    
    result = client.list_events(**params)
    
    utils.print_json_response(result)
