import os
import sys
import tempfile
from cli import utils
from cli.knowledge_base_client import KosmosClient

def register_subparser(subparsers, parent_parser):
    """为 'upload' 命令注册子解析器。"""
    p_upload = subparsers.add_parser(
        "upload", 
        help="上传一个新文档到知识空间，并启动事件驱动的摄入流程。",
        parents=[parent_parser]
    )
    p_upload.add_argument("file_path", help="要上传的文件的本地路径。")
    p_upload.add_argument(
        "--force",
        action="store_true",
        help="强制重新处理，即使内容之前已被处理过。"
    )
    p_upload.add_argument(
        "--content-extraction-strategy",
        choices=["reuse_any", "force_reextraction"],
        help="内容提取策略。"
    )
    p_upload.add_argument(
        "--asset-analysis-strategy",
        choices=["reuse_any", "reuse_within_document", "force_reanalysis"],
        help="资产分析策略。"
    )
    p_upload.add_argument(
        "--chunking-strategy-name",
        help="要使用的Chunking策略的名称。"
    )
    p_upload.add_argument(
        "--filename",
        help="上传文件在系统中的名称。如果未指定，则使用原始文件名。"
    )
    p_upload.set_defaults(func=run)

def run(client: KosmosClient, args, config):
    """执行 'upload' 命令。"""
    ks_id = config.require(args.ks_id, "KOSMOS_KS_ID", "知识空间ID")
    file_path = args.file_path

    if not os.path.exists(file_path) or not os.path.isfile(file_path):
        print(f"错误: 文件路径不存在或不是一个有效文件 '{file_path}'", file=sys.stderr)
        sys.exit(1)

    # 使用 --filename 参数指定的文件名，如果未指定则使用原始文件名
    file_name = args.filename if args.filename else os.path.basename(file_path)
    
    print(f"正在使用事件驱动流程上传 '{file_name}' 到知识空间 {ks_id}...", file=sys.stderr) 
    
    # 如果指定了文件名，创建一个临时文件并复制原始文件内容
    temp_file_path = None
    if args.filename:
        # 创建临时文件，使用我们想要的文件名
        temp_dir = tempfile.gettempdir()
        temp_file_path = os.path.join(temp_dir, file_name)
        
        # 复制原始文件内容到临时文件
        try:
            with open(file_path, 'rb') as src:
                with open(temp_file_path, 'wb') as dst:
                    dst.write(src.read())
        except Exception as e:
            print(f"错误: 无法创建临时文件: {e}", file=sys.stderr)
            sys.exit(1)
        
        # 使用临时文件路径进行上传
        file_path = temp_file_path
    
    # 收集所有策略参数
    params = {
        "force": args.force,
        "content_extraction_strategy": args.content_extraction_strategy,
        "asset_analysis_strategy": args.asset_analysis_strategy,
        "chunking_strategy_name": args.chunking_strategy_name,
        "filename": file_name  # 传递文件名参数给客户端
    }

    result = client.ingest_document(ks_id, file_path, **params)
    
    # 如果创建了临时文件，删除它
    if args.filename and temp_file_path and os.path.exists(temp_file_path):
        try:
            os.unlink(temp_file_path)
        except Exception as e:
            print(f"警告: 无法删除临时文件 {temp_file_path}: {e}", file=sys.stderr)
    
    print("上传成功。文档已注册，异步摄入流程已启动。", file=sys.stderr)
    print("\n--- 主文档元数据 ---")
    utils.print_json_response(result)