import argparse
from cli import utils
from cli.knowledge_base_client import KosmosClient
from cli.config import CliConfig

def register_subparser(subparsers, parent_parser):
    """为 'asset' 命令注册子解析器。"""
    p_asset = subparsers.add_parser(
        "asset", 
        help="管理和查询文档中的资产（图片、表格等）。",
        parents=[parent_parser]
    )
    asset_subparsers = p_asset.add_subparsers(dest="subcommand", required=True, help="可用的资产操作")

    # --- asset list ---
    p_list = asset_subparsers.add_parser(
        "list", 
        help="列出并过滤资产。",
        parents=[parent_parser]
    )
    p_list.add_argument("--doc-id", help="按文档ID过滤。")
    p_list.add_argument("--asset-type", choices=['figure', 'table'], help="按资产类型过滤 (figure 或 table)。")
    p_list.add_argument("--status", help="按分析状态过滤 (例如, not_analyzed, completed)。")
    p_list.add_argument("--limit", type=int, default=20, help="要返回的结果数量 (默认: 20)。")
    p_list.set_defaults(func=run_list)

    # --- asset get-analysis ---
    p_get_analysis = asset_subparsers.add_parser(
        "get-analysis",
        help="获取资产在特定文档上下文中的分析结果。",
        parents=[parent_parser]
    )
    p_get_analysis.add_argument("asset_id_pos", metavar="ASSET_ID", help="要查询的资产ID。")
    p_get_analysis.add_argument("--doc-id", required=True, help="资产所在的文档ID。")
    p_get_analysis.set_defaults(func=run_get_analysis)

def run_get_analysis(client: KosmosClient, args, config: CliConfig):
    """执行 'asset get-analysis' 命令。"""
    doc_id = args.doc_id
    asset_id = args.asset_id_pos # 从位置参数获取
    
    result = client.get_asset_analysis_in_doc_context(
        doc_id=doc_id,
        asset_id=asset_id
    )
    utils.print_asset_analysis_detail(result, doc_id=doc_id, asset_id=asset_id)

def run_list(client: KosmosClient, args, config: CliConfig):
    """执行 'asset list' 命令。"""
    results = client.list_assets(
        ks_id=args.ks_id,
        doc_id=args.doc_id,
        asset_type=args.asset_type,
        status=args.status,
        limit=args.limit
    )
    
    if not results.get("items"):
        print("未找到符合条件的资产。")
        return
        
    utils.print_json_response(results)