import sys
import time
import argparse
import os
import re
from cli import utils
from cli.knowledge_base_client import KosmosClient


def register_subparser(subparsers, parent_parser):
    """为 'documents' 命令注册子解析器，默认操作是 list。"""
    # --- 通用过滤参数 ---
    filter_parser = argparse.ArgumentParser(add_help=False)
    filter_parser.add_argument("--ext", help="按文件扩展名过滤 (例如 'pdf', 'docx')。")
    filter_parser.add_argument("--status", help="按文档状态过滤 (例如 'completed', 'failed')。")
    filter_parser.add_argument("--filename", help="按文件名进行模糊匹配过滤。")
    filter_parser.add_argument("--doc-id", help="按文档ID过滤。", nargs='?')

    # --- 主 'documents' 命令解析器 ---
    p_docs = subparsers.add_parser(
        "documents", 
        help="对文档集合进行过滤、查询和批量操作。默认操作是列出文档。",
        parents=[parent_parser, filter_parser]
    )
    p_docs.add_argument("--all", action="store_true", help="获取所有符合条件的文档，而非仅第一页。")
    p_docs.add_argument("--concise", action="store_true", help="仅输出文档ID列表。")
    p_docs.set_defaults(func=run_list)
    
    # 添加别名 'doc'
    subparsers._name_parser_map["doc"] = p_docs

    # --- 为其他动作创建子解析器 ---
    docs_subparsers = p_docs.add_subparsers(dest="subcommand", help="可用操作")

    # --- documents delete ---
    p_delete = docs_subparsers.add_parser(
        "delete", 
        help="删除符合条件的文档。",
        parents=[parent_parser, filter_parser]
    )
    p_delete.add_argument("--force", action="store_true", help="强制删除，无需确认。")
    p_delete.set_defaults(func=run_delete)

    # --- documents verify ---
    p_verify = docs_subparsers.add_parser(
        "verify", 
        help="测试符合条件的文档解析是否成功。",
        parents=[parent_parser, filter_parser] # verify 仍然需要这些过滤器
    )
    p_verify.add_argument("--output-dir", help="将成功解析的文本内容保存到指定目录，以便人工检查。")
    p_verify.set_defaults(func=run_verify)


def _get_all_filtered_docs(client: KosmosClient, args, config):
    """辅助函数：获取所有符合过滤条件的文档，处理分页。"""
    # 如果指定了文档ID，直接获取该文档
    if hasattr(args, 'doc_id') and args.doc_id:
        try:
            doc = client.get_document(args.doc_id)
            return [doc] if doc else []
        except Exception:
            # 如果获取单个文档失败，返回空列表
            return []
    
    ks_id = config.require(args.ks_id, "KOSMOS_KS_ID", "知识空间ID")
    
    all_docs = []
    cursor = None
    page_num = 1
    
    while True:
        print(f"正在获取第 {page_num} 页文档...", file=sys.stderr)
        results = client.get_documents(
            ks_id, 
            status=args.status, 
            filename=args.filename, 
            extension=args.ext, 
            cursor=cursor,
            page_size=100
        )
        
        page_docs = results.get("items", [])
        if not page_docs:
            break
            
        all_docs.extend(page_docs)
        cursor = results.get("next_cursor")
        if not cursor:
            break
        page_num += 1
        
    return all_docs

def run_list(client: KosmosClient, args, config):
    """执行 'documents list' 命令。"""
    print(f"--- [DEBUG] Args received in documents.run_list ---", file=sys.stderr)
    print(vars(args), file=sys.stderr)
    print(f"-------------------------------------------------", file=sys.stderr)
    
    # 如果指定了文档ID，直接获取该文档
    if hasattr(args, 'doc_id') and args.doc_id:
        try:
            doc = client.get_document(args.doc_id)
            docs = [doc] if doc else []
        except Exception:
            docs = []
    else:
        ks_id = config.require(args.ks_id, "KOSMOS_KS_ID", "知识空间ID")

        if args.all or args.concise:
            docs = _get_all_filtered_docs(client, args, config)
        else:
            # 默认行为：只获取第一页
            print("正在获取第一页文档...", file=sys.stderr)
            results = client.get_documents(
                ks_id, 
                status=args.status, 
                filename=args.filename, 
                extension=args.ext,
                page_size=20 # 默认返回20个
            )
            docs = results.get("items", [])
            print(f"共找到 {results.get('total_count', 0)} 个文档。只显示前 {len(docs)} 个，使用 --all 获取全部。", file=sys.stderr)

    if not docs:
        print("未找到符合条件的文档。", file=sys.stderr)
        return

    if args.concise:
        for doc in docs:
            print(doc.get('id'))
    else:
        utils.print_json_response(docs)

def _sanitize_filename(name):
    """从原始文件名创建一个安全的文件系统路径组件。"""
    name = re.sub(r'[<>:"/\\|?*]', '_', name)
    return name[:200] # 限制文件名长度

def run_verify(client: KosmosClient, args, config):
    """执行 'documents verify' 命令。"""
    if args.output_dir:
        os.makedirs(args.output_dir, exist_ok=True)
        print(f"解析内容将被保存到: {os.path.abspath(args.output_dir)}")

    docs_to_test = _get_all_filtered_docs(client, args, config)

    if not docs_to_test:
        print("未找到符合条件的文档进行测试。", file=sys.stderr)
        return

    print(f"共找到 {len(docs_to_test)} 个文档，现在开始逐一测试解析...")
    
    successful_docs = []
    failed_docs = []
    
    for i, doc in enumerate(docs_to_test, 1):
        doc_id = doc.get('id')
        filename = doc.get('original_filename', 'NA')
        
        progress = f"({i}/{len(docs_to_test)})"
        print(f"{progress} 正在测试: {filename} (ID: {doc_id})... ", end="", flush=True) 
        
        try:
            # 如果指定了输出目录，则读取全部内容；否则只读一小部分以加快速度
            if args.output_dir:
                read_results = client.read(doc_id, start='1', end=None, max_lines=1000000, max_chars=10000000, preserve_integrity=False)
            else:
                # 维持原有的快速检查行为
                client.read(doc_id, start='1', end='1', max_lines=1, max_chars=128, preserve_integrity=False)
            
            print("✅ 成功")
            successful_docs.append(doc)

            # 如果需要，保存内容
            if args.output_dir:
                content = "\n".join(line['content'] for line in read_results.get("lines", []))
                safe_filename = f"{doc_id}_{_sanitize_filename(filename)}.txt"
                output_path = os.path.join(args.output_dir, safe_filename)
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(content)

        except SystemExit:
            print("❌ 失败")
            failed_docs.append(doc)
        except Exception as e:
            print(f"❌ 失败 (未知错误: {e})")
            failed_docs.append(doc)
        
        time.sleep(0.1)

    print("\n--- 解析测试总结 ---")
    print(f"总计: {len(docs_to_test)} | 成功: {len(successful_docs)} | 失败: {len(failed_docs)}")
    
    if failed_docs:
        print("\n失败的文档列表:")
        for doc in failed_docs:
            print(f"  - 文件名: {doc.get('original_filename', 'N/A')}")
            print(f"    ID: {doc.get('id')}")
            print(f"    状态: {doc.get('status')}")
    print("--- 测试完成 ---")

def run_delete(client: KosmosClient, args, config):
    """执行 'documents delete' 命令。"""
    ks_id = config.require(args.ks_id, "KOSMOS_KS_ID", "知识空间ID")
    
    # 获取所有符合条件的文档
    docs = _get_all_filtered_docs(client, args, config)
    
    if not docs:
        print("未找到符合条件的文档。", file=sys.stderr)
        return
    
    print(f"找到 {len(docs)} 个文档。")
    
    # 如果没有强制删除，需要用户确认
    if not args.force:
        print("你将要删除以下文档:")
        for doc in docs:
            print(f"  - {doc.get('original_filename', 'N/A')} (ID: {doc.get('id')})")
        
        confirm = input("确认删除? (y/N): ")
        if confirm.lower() not in ['y', 'yes']:
            print("操作已取消。")
            return
    
    # 删除文档
    deleted_count = 0
    for doc in docs:
        doc_id = doc.get('id')
        try:
            print(f"正在删除文档: {doc_id}...", file=sys.stderr)
            client.delete_document(doc_id)
            print(f"✅ 已删除: {doc_id}", file=sys.stderr)
            deleted_count += 1
        except Exception as e:
            print(f"❌ 删除失败 {doc_id}: {e}", file=sys.stderr)
    
    print(f"总共删除了 {deleted_count} 个文档。")
