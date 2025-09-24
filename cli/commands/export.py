import sys
import os
import json
import requests
from urllib.parse import urljoin
from typing import Optional
from cli import utils
from cli.knowledge_base_client.client import KosmosClient
from cli.config import CliConfig

# --- Configuration for Assessment Service ---
ASSESSMENT_API_BASE_URL = os.getenv("ASSESSMENT_API_URL", "http://127.0.0.1:8015/api/v1/")

def register_subparser(subparsers, parent_parser):
    """为 'export' 命令注册子解析器。"""
    p_export = subparsers.add_parser(
        "export", 
        help="将会话或任务的评估结果导出为人类可读的格式。",
        parents=[parent_parser]
    )
    p_export.add_argument("job_id", help="要导出的评估任务 (Job) 的ID。")
    p_export.add_argument(
        "--format", 
        default="html", 
        choices=["html"], 
        help="导出的文件格式 (目前仅支持 'html')。"
    )
    p_export.add_argument(
        "-o", "--output", 
        help="可选的输出文件路径。如果未提供，将自动保存在 'reports' 目录下。"
    )
    p_export.add_argument(
        "-j", "--judgement",
        action="append",
        help="按评估结论进行过滤 (可多次使用)。默认导出所有非空的结论。"
    )
    p_export.set_defaults(func=run)

def export_api(token: str, job_id: str, format: str, judgements: Optional[list]):
    """调用评估服务的导出API，并传递当前令牌和过滤条件。"""
    url = urljoin(ASSESSMENT_API_BASE_URL, f"jobs/{job_id}/export/{format}")
    headers = {"Authorization": f"Bearer {token}"}
    
    params = {}
    if judgements:
        params["judgements"] = judgements

    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException as e:
        if e.response and e.response.status_code == 404:
            print(f"错误: 找不到ID为 '{job_id}' 的评估任务。", file=sys.stderr)
            sys.exit(1)
        print(f"API错误: {e}", file=sys.stderr)
        sys.exit(1)

def run(client: KosmosClient, args, config: CliConfig):
    """执行 'export' 命令。"""
    print(f"正在为任务 {args.job_id} 生成 {args.format} 格式的报告...", file=sys.stderr)
    
    token = client.get_raw_token()
    report_content = export_api(token, args.job_id, args.format, args.judgement)
    
    output_path = args.output
    if not output_path:
        output_dir = "reports"
        os.makedirs(output_dir, exist_ok=True)
        filename = f"report-{args.job_id}.{args.format}"
        output_path = os.path.join(output_dir, filename)

    try:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(report_content)
        print(f"报告已成功保存到: {output_path}", file=sys.stderr)
    except IOError as e:
        print(f"错误: 无法写入文件 '{output_path}'. {e}", file=sys.stderr)
        sys.exit(1)
