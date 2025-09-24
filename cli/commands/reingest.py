import sys
import argparse
from cli import utils
from cli.knowledge_base_client import KosmosClient

def register_subparser(subparsers, parent_parser):
    """为 're-ingest' 命令注册子解析器。"""
    p_reingest = subparsers.add_parser(
        "re-ingest", 
        help="为一个或多个现有文档触发重新摄入流程。",
        parents=[parent_parser]
    )
    
    scope_group = p_reingest.add_mutually_exclusive_group(required=True)
    scope_group.add_argument(
        "--doc-id",
        dest="document_ids",
        nargs='+',
        help="要重新摄入的一个或多个文档ID。"
    )
    scope_group.add_argument(
        "--all-in-ks",
        metavar="KS_ID",
        help="重新摄入指定知识空间ID下的所有文档。"
    )
    
    p_reingest.add_argument(
        "--no-force",
        dest="force",
        action="store_false",
        help="不要强制重新处理，允许复用旧的成功结果 (默认是强制处理)。"
    )
    p_reingest.add_argument(
        "--content-extraction-strategy",
        choices=["reuse_any", "force_reextraction"],
        help="内容提取策略。"
    )
    p_reingest.add_argument(
        "--asset-analysis-strategy",
        choices=["reuse_any", "reuse_within_document", "force_reanalysis"],
        help="资产分析策略。"
    )
    p_reingest.add_argument(
        "--chunking-strategy-name",
        help="要使用的Chunking策略的名称。"
    )
    p_reingest.set_defaults(func=run, force=True)

def run(client: KosmosClient, args, config):
    """执行 're-ingest' 命令。"""
    
    ks_id_for_reingest = args.all_in_ks
    
    if ks_id_for_reingest:
        print(f"准备为知识空间 {ks_id_for_reingest} 中的所有文档安排重新摄入...", file=sys.stderr)
    else:
        print(f"准备为 {len(args.document_ids)} 个文档安排重新摄入...", file=sys.stderr)

    params = {
        "force": args.force,
        "content_extraction_strategy": args.content_extraction_strategy,
        "asset_analysis_strategy": args.asset_analysis_strategy,
        "chunking_strategy_name": args.chunking_strategy_name,
    }

    result = client.reingest_documents(
        document_ids=args.document_ids,
        knowledge_space_id=ks_id_for_reingest,
        **params
    )
    
    print("重新摄入请求已成功提交。", file=sys.stderr)
    utils.print_json_response(result)
