from cli import utils
from cli.knowledge_base_client import KosmosClient

def register_subparser(subparsers, parent_parser):
    """为 'search' 命令注册子解析器。"""
    p_search = subparsers.add_parser(
        "search", 
        help="在知识空间中执行搜索查询。",
        parents=[parent_parser]
    )
    p_search.add_argument("query", help="要执行的搜索查询语句。")
    
    # --- Document Filtering ---
    g_doc = p_search.add_argument_group("Document Filters")
    g_doc.add_argument(
        "--include-doc-id", 
        action="append",
        dest="doc_ids_include",
        help="[+] 将搜索范围限定在指定的文档ID内 (可多次使用)。"
    )
    g_doc.add_argument(
        "--exclude-doc-id",
        action="append",
        dest="doc_ids_exclude",
        help="[-] 从搜索范围中排除指定的文档ID (可多次使用)。"
    )
    g_doc.add_argument(
        "--filename-contains",
        help="[+] 搜索文件名包含此字符串的文档。"
    )
    g_doc.add_argument(
        "--filename-excludes",
        dest="filename_does_not_contain",
        help="[-] 排除文件名包含此字符串的文档。"
    )
    g_doc.add_argument(
        "--ext-include",
        action="append",
        dest="extensions_include",
        help="[+] 只搜索指定扩展名的文件 (例如: --ext-include pdf)。"
    )
    g_doc.add_argument(
        "--ext-exclude",
        action="append",
        dest="extensions_exclude",
        help="[-] 排除指定扩展名的文件 (例如: --ext-exclude xlsx)。"
    )


    # --- Content Filtering ---
    g_content = p_search.add_argument_group("Content Filters")
    g_content.add_argument(
        "--contains-all",
        action="append",
        dest="keywords_include_all",
        help="[+] The content MUST contain ALL of these keywords (case-insensitive)."
    )
    g_content.add_argument(
        "--excludes-any",
        action="append",
        dest="keywords_exclude_any",
        help="[-] The content must NOT contain ANY of these keywords (case-insensitive)."
    )

    # --- Result Tuning ---
    g_tune = p_search.add_argument_group("Result Tuning")
    g_tune.add_argument("--top-k", type=int, default=10, help="要返回的结果数量 (默认: 10)。")
    g_tune.add_argument("--boosters", nargs='+', help="用于影响排名的助推词列表。")
    
    p_search.set_defaults(func=run)

def run(client: KosmosClient, args, config):
    """执行 'search' 命令。"""
    ks_id = config.require(args.ks_id, "KOSMOS_KS_ID", "知识空间ID")
    
    # Combine all filter arguments into a single dictionary
    filters = {
        "doc_ids_include": args.doc_ids_include,
        "doc_ids_exclude": args.doc_ids_exclude,
        "filename_contains": args.filename_contains,
        "filename_does_not_contain": args.filename_does_not_contain,
        "extensions_include": args.extensions_include,
        "extensions_exclude": args.extensions_exclude,
        "keywords_include_all": args.keywords_include_all,
        "keywords_exclude_any": args.keywords_exclude_any,
        "boosters": args.boosters,
        "top_k": args.top_k,
    }
    


    results = client.search(ks_id, args.query, **filters)
    utils.print_search_results(results)
