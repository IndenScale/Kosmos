import sys
import argparse
from cli import utils
from cli.knowledge_base_client import KosmosClient

def register_subparser(subparsers, parent_parser):
    """为 'ingestion' 命令注册子解析器。"""
    p_ingestion = subparsers.add_parser(
        "ingestion", 
        help="管理文档摄入流程。",
        parents=[parent_parser]
    )
    ingestion_subparsers = p_ingestion.add_subparsers(dest="ingestion_command", required=True, help="摄入操作")

    # --- Status 命令 ---
    status_parser = ingestion_subparsers.add_parser("status", help="查看文档摄入状态。")
    status_group = status_parser.add_mutually_exclusive_group(required=True)
    status_group.add_argument("--ks-id", help="要查看摄入状态的知识空间ID。")
    status_group.add_argument("--doc-id", help="要查看摄入状态的文档ID。")
    status_parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="显示详细信息。"
    )
    status_parser.set_defaults(func=run_status)

    # --- Re-ingest 命令 ---
    reingest_parser = ingestion_subparsers.add_parser("reingest", help="为一个或多个现有文档触发重新摄入流程。")
    scope_group = reingest_parser.add_mutually_exclusive_group(required=True)
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
    
    reingest_parser.add_argument(
        "--no-force",
        dest="force",
        action="store_false",
        help="不要强制重新处理，允许复用旧的成功结果 (默认是强制处理)。"
    )
    reingest_parser.add_argument(
        "--content-extraction-strategy",
        choices=["reuse_any", "force_reextraction"],
        help="内容提取策略。"
    )
    reingest_parser.add_argument(
        "--asset-analysis-strategy",
        choices=["reuse_any", "reuse_within_document", "force_reanalysis"],
        help="资产分析策略。"
    )
    reingest_parser.add_argument(
        "--chunking-strategy-name",
        help="要使用的Chunking策略的名称。"
    )
    reingest_parser.set_defaults(func=run_reingest, force=True)

def run_status(client: KosmosClient, args, config):
    """执行 'ingestion status' 命令。"""
    if args.ks_id:
        ks_id = config.require(args.ks_id, "KOSMOS_KS_ID", "知识空间ID")
        result = client.get_document_ingestion_status(ks_id=ks_id)
        print(f"知识空间 {ks_id} 的摄入状态:", file=sys.stderr)
    elif args.doc_id:
        doc_id = args.doc_id
        result = client.get_document_ingestion_status(doc_id=doc_id)
        print(f"文档 {doc_id} 的摄入状态:", file=sys.stderr)
    
    # 如果没有 --verbose 参数，只显示摘要信息
    if not getattr(args, 'verbose', False):
        # 只显示关键摘要信息
        summary = {
            "knowledge_space_id": result.get("knowledge_space_id"),
            "total_documents": result.get("total_documents"),
            "documents_with_canonical_content": result.get("documents_with_canonical_content"),
            "documents_with_asset_analysis": result.get("documents_with_asset_analysis"),
            "canonical_content_rate": result.get("canonical_content_rate"),
            "asset_analysis_rate": result.get("asset_analysis_rate"),
            "total_assets_in_ks": result.get("total_assets_in_ks"),
            "total_completed_assets_in_ks": result.get("total_completed_assets_in_ks"),
            "overall_asset_analysis_rate": result.get("overall_asset_analysis_rate"),
        }
        utils.print_json_response(summary)
    else:
        # 显示完整结果
        utils.print_json_response(result)

def run_reingest(client: KosmosClient, args, config):
    """执行 'ingestion reingest' 命令。"""
    
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