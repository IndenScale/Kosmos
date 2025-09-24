import os
import json
import sys
import requests
from urllib.parse import urljoin
from cli import utils
from cli.knowledge_base_client import KosmosClient
from cli.config import CliConfig
import argparse

# --- Configuration for Assessment Service ---
ASSESSMENT_API_BASE_URL = os.getenv("ASSESSMENT_API_URL", "http://127.0.0.1:8015/api/v1/")

# --- 状态管理辅助函数 ---

STATE_FILE = ".kosmos_cli_state.json"

def save_current_session(session_id: str):
    """将当前活动的 session_id 保存到状态文件。"""
    with open(STATE_FILE, "w") as f:
        json.dump({"current_session_id": session_id}, f)

def get_current_session() -> str | None:
    """从状态文件读取当前活动的 session_id。"""
    if not os.path.exists(STATE_FILE):
        return None
    try:
        with open(STATE_FILE, "r") as f:
            data = json.load(f)
            return data.get("current_session_id")
    except (json.JSONDecodeError, IOError):
        return None

def require_session(session_id_arg: str | None, config: CliConfig) -> str:
    """
    使用集中的配置逻辑按优先级获取 session_id。
    """
    return config.require_session_id(session_id_arg)

# --- API 调用函数 (assessment_service) ---

def create_job_api(token: str, framework_id: str, ks_id: str, name: str | None):
    url = urljoin(ASSESSMENT_API_BASE_URL, "jobs/")
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {
        "framework_id": framework_id,
        "name": name,
        "knowledge_spaces": [{"ks_id": ks_id, "role": "target"}]
    }
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"错误: API请求失败 - {e}", file=sys.stderr)
        if hasattr(e, 'response') and e.response:
            print(f"响应 ({e.response.status_code}): {e.response.text}", file=sys.stderr)
        sys.exit(1)

def start_session_api(token: str, job_id: str):
    url = urljoin(ASSESSMENT_API_BASE_URL, f"jobs/{job_id}/sessions")
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {"batch_size": 5} # 默认值，未来可配置
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"错误: API请求失败 - {e}", file=sys.stderr)
        if hasattr(e, 'response') and e.response:
            print(f"响应 ({e.response.status_code}): {e.response.text}", file=sys.stderr)
        sys.exit(1)

def _start_session_transition_api(token: str, session_id: str):
    """调用API以将会话状态从 'READY' 转换为 'ASSESSING'。"""
    url = urljoin(ASSESSMENT_API_BASE_URL, f"sessions/{session_id}/start")
    headers = {"Authorization": f"Bearer {token}"}
    try:
        response = requests.post(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        _handle_assessment_api_error(e)

def get_session_api(token: str, session_id: str):
    url = urljoin(ASSESSMENT_API_BASE_URL, f"sessions/{session_id}")
    headers = {"Authorization": f"Bearer {token}"}
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        handle_api_error(e)

def add_evidence_api(token: str, session_id: str, finding_id: str, doc_id: str, start: int, end: int):
    url = urljoin(ASSESSMENT_API_BASE_URL, f"sessions/{session_id}/agent/findings/{finding_id}/evidence")
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {"doc_id": doc_id, "start_line": start, "end_line": end}
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        handle_api_error(e)

def update_finding_api(token: str, session_id: str, finding_id: str, judgement: str, comment: str, supplement: str | None):
    url = urljoin(ASSESSMENT_API_BASE_URL, f"sessions/{session_id}/agent/findings/{finding_id}")
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {
        "judgement": judgement,
        "comment": comment,
        "supplement": supplement
    }
    # 移除 None 值
    payload = {k: v for k, v in payload.items() if v is not None}
    try:
        response = requests.patch(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        handle_api_error(e)

def session_action_api(token: str, session_id: str, action: str, reason: str | None = None):
    url = urljoin(ASSESSMENT_API_BASE_URL, f"sessions/{session_id}/{action}")
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {}
    if reason:
        payload["reason"] = reason
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        handle_api_error(e)

# --- 结果打印函数 ---

def print_session_status(session_data):
    print(f"--- 评估会话状态 ---")
    print(f"会话ID: {session_data.get('id')} (Job ID: {session_data.get('job_id')})")
    print(f"状态: {session_data.get('status')}")
    print(f"行动计数: {session_data.get('action_count')} / {session_data.get('action_limit')}")
    print("\n评估发现 (Findings):")
    
    findings = session_data.get('findings', [])
    if not findings:
        print("  (此会话没有评估发现)")
        return

    for f in findings:
        control_def = f.get('control_item_definition', {})
        cid = control_def.get('display_id', 'N/A')
        content = control_def.get('content', '错误：未提供控制项内容！')
        judgement = f.get('judgement') or "未评估"
        evidence_count = len(f.get('evidences', []))
        
        print(f"  - Finding ID: {f.get('id')}")
        print(f"    控制项ID: {cid}")
        print(f"    控制项内容: {content}")
        print(f"    结论: {judgement}")
        print(f"    证据数: {evidence_count}")

# --- 命令注册与执行 ---

def register_subparser(subparsers, parent_parser):
    p_assessment = subparsers.add_parser("assessment", help="管理评估工作流。", parents=[parent_parser])
    assessment_sub = p_assessment.add_subparsers(dest="subcommand", required=True, help="评估操作")

    # 全局评估参数
    assessment_parent_parser = argparse.ArgumentParser(add_help=False)
    assessment_parent_parser.add_argument("--session-id", type=str, help="手动指定会话ID，覆盖当前活动会话。" )

    # create-job
    p_create_job = assessment_sub.add_parser("create-job", help="创建一个新的评估任务。", parents=[parent_parser])
    p_create_job.add_argument("--framework-id", type=str, required=True, help="评估框架的ID。" )
    p_create_job.add_argument("--name", help="评估任务的可选名称。" )
    p_create_job.set_defaults(func=run_create_job)

    # start-session
    p_start = assessment_sub.add_parser("start-session", help="为任务启动一个新会话并设为活动状态。", parents=[parent_parser])
    p_start.add_argument("--job-id", type=str, required=True, help="要启动会话的任务ID。" )
    p_start.set_defaults(func=run_start_session)

    # status
    p_status = assessment_sub.add_parser("status", help="显示当前活动会话的状态。", parents=[parent_parser, assessment_parent_parser])
    p_status.set_defaults(func=run_status)

    # add-evidence
    p_add_ev = assessment_sub.add_parser("add-evidence", help="为评估发现添加证据。", parents=[parent_parser, assessment_parent_parser])
    p_add_ev.add_argument("finding_id", type=str, help="要添加证据的评估发现ID。" )
    p_add_ev.add_argument("doc_id", type=str, help="证据来源的文档ID。")
    p_add_ev.add_argument("--lines", nargs=2, metavar=("START", "END"), required=True, type=int, help="证据的起始和结束行号。" )
    p_add_ev.set_defaults(func=run_add_evidence)

    # update-finding
    p_update_f = assessment_sub.add_parser("update-finding", help="更新一个评估发现的结论。", parents=[parent_parser, assessment_parent_parser])
    p_update_f.add_argument("finding_id", type=str, help="要更新的评估发现ID。" )
    p_update_f.add_argument("--judgement", required=True, choices=["符合", "不符合", "部分符合", "不涉及", "无法确认"], help="评估结论。" )
    p_update_f.add_argument("--comment", required=True, help="评估评论。" )
    p_update_f.add_argument("--supplement", help="补充说明 (可选)。" )
    p_update_f.set_defaults(func=run_update_finding)

    # submit, reject, complete
    p_submit = assessment_sub.add_parser("submit", help="提交当前会话以供审核。", parents=[parent_parser, assessment_parent_parser])
    p_submit.set_defaults(func=run_submit)
    
    p_reject = assessment_sub.add_parser("reject", help="驳回已提交的会话。", parents=[parent_parser, assessment_parent_parser])
    p_reject.add_argument("--reason", required=True, help="驳回理由。" )
    p_reject.set_defaults(func=run_reject)

    p_complete = assessment_sub.add_parser("complete", help="完成对已提交会话的审核。", parents=[parent_parser, assessment_parent_parser])
    p_complete.set_defaults(func=run_complete)

def run_create_job(client: KosmosClient, args, config: CliConfig):
    ks_id = config.require(args.ks_id, "KOSMOS_KS_ID", "知识空间ID")
    token = client.get_raw_token()
    result = create_job_api(token, args.framework_id, ks_id, args.name)
    print("评估任务已成功创建。" )
    utils.print_json_response(result)

def run_start_session(client: KosmosClient, args, config: CliConfig):
    # Check if running in a non-interactive, server-dispatched mode.
    if os.getenv("KOSMOS_ASSESSMENT_SESSION_ID"):
        print("错误: 您正处于一个由服务器调度的非交互式会话中。", file=sys.stderr)
        print("评估会话已为您自动创建和启动。", file=sys.stderr)
        print("请勿尝试手动启动新会话，应使用 'assessment status' 命令来获取您的任务。", file=sys.stderr)
        sys.exit(1)

    # 1. 创建会话
    token = client.get_raw_token()
    created_session = start_session_api(token, args.job_id)
    session_id = created_session.get("id")
    
    if not session_id:
        print("错误：创建会话失败，未返回ID。", file=sys.stderr)
        utils.print_json_response(created_session)
        sys.exit(1)
        
    # 2. 启动会话（状态转换）
    started_session = _start_session_transition_api(token, session_id)
    
    # 3. 保存并打印最终状态
    save_current_session(session_id)
    print(f"会话 {session_id} 已启动并设为当前活动会话。")
    print_session_status(started_session)

def run_status(client: KosmosClient, args, config: CliConfig):
    session_id = require_session(args.session_id, config)
    token = client.get_raw_token()
    result = get_session_api(token, session_id)
    print_session_status(result)

def run_add_evidence(client: KosmosClient, args, config: CliConfig):
    session_id = require_session(args.session_id, config)
    # doc_id 现在直接从位置参数获取，不再依赖全局配置
    doc_id = args.doc_id
    token = client.get_raw_token()
    add_evidence_api(token, session_id, args.finding_id, doc_id, args.lines[0], args.lines[1])
    print(f"证据已成功添加到 Finding {args.finding_id}。" )

def run_update_finding(client: KosmosClient, args, config: CliConfig):
    session_id = require_session(args.session_id, config)
    token = client.get_raw_token()
    update_finding_api(token, session_id, args.finding_id, args.judgement, args.comment, args.supplement)
    print(f"Finding {args.finding_id} 已成功更新。" )

def run_submit(client: KosmosClient, args, config: CliConfig):
    session_id = require_session(args.session_id, config)
    token = client.get_raw_token()
    result = session_action_api(token, session_id, "submit")
    print(f"会话 {session_id} 已提交审核。" )
    print_session_status(result)

def run_reject(client: KosmosClient, args, config: CliConfig):
    session_id = require_session(args.session_id, config)
    token = client.get_raw_token()
    result = session_action_api(token, session_id, "reject", reason=args.reason)
    print(f"会话 {session_id} 已被驳回。" )
    print_session_status(result)

def run_complete(client: KosmosClient, args, config: CliConfig):
    session_id = require_session(args.session_id, config)
    token = client.get_raw_token()
    result = session_action_api(token, session_id, "complete")
    print(f"会话 {session_id} 已完成。" )
    print_session_status(result)