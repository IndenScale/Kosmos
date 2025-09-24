#!/usr/bin/env python3
"""
Test script to verify OpenAI credential dispatch from database.
Reads credentials from execution_queue and starts a non-interactive session.
"""
import json
import subprocess
import os
import sqlite3
from pathlib import Path
from datetime import datetime

def get_execution_config(session_id: str) -> dict:
    """Read execution_config from database for given session_id."""
    conn = sqlite3.connect('/home/hxdi/Kosmos/assessment.db')
    cursor = conn.cursor()
    cursor.execute(
        "SELECT execution_config FROM execution_queue WHERE session_id = ?",
        (session_id,)
    )
    result = cursor.fetchone()
    conn.close()

    if result and result[0]:
        return json.loads(result[0])
    return {}

def test_credential_dispatch():
    """Test credential dispatch by starting a qwen process with database credentials."""
    session_id = "844d516a-c8ad-42e9-98f7-bbc3955b1887"

    print(f"[{datetime.now()}] Testing credential dispatch for session: {session_id}")

    # Get credentials from database
    config = get_execution_config(session_id)
    if not config:
        print(f"[{datetime.now()}] ERROR: No execution_config found for session {session_id}")
        return False

    print(f"[{datetime.now()}] Retrieved config from database:")
    for key, value in config.items():
        if 'api_key' in key:
            print(f"  {key}: {value[:10]}..." if value else f"  {key}: None")
        else:
            print(f"  {key}: {value}")

    # Prepare environment variables
    env = os.environ.copy()
    env["KOSMOS_ASSESSMENT_SESSION_ID"] = session_id

    if config.get('agent') == 'qwen':
        if config.get('openai_base_url'):
            env["OPENAI_BASE_URL"] = config['openai_base_url']
            print(config.get('openai_base_url'))
        if config.get('openai_api_key'):
            env["OPENAI_API_KEY"] = config['openai_api_key']
            print(config.get('openai_api_key'))
        if config.get('openai_model'):
            env["OPENAI_MODEL"] = config['openai_model']
            print(config.get('openai_model'))

    print(f"[{datetime.now()}] Environment variables set:")
    for key in ['OPENAI_BASE_URL', 'OPENAI_API_KEY', 'OPENAI_MODEL']:
        if key in env:
            if 'API_KEY' in key:
                print(f"  {key}: {env[key][:10]}..." if env[key] else f"  {key}: None")
            else:
                print(f"  {key}: {env[key]}")

    # Create test prompt that asks for current time
    test_prompt = f"""
# 测试任务简报
**核心指令：请务必使用中文进行思考、推理和决策。你所有的内心独白和输出都必须是中文，以便于审计。**
你是一个自动化测试代理。你的任务是验证凭证传递是否正常工作。
## 关键信息
- **知识空间 ID**: `e97ca4dd-432d-4d3e-a9b5-41d5d479a7b2`
- **评估任务 ID**: `d7e9ac34-b93d-4ad2-a2e2-422b77a609af`
- **当前会话 ID**: `{session_id}` (此ID也已通过 KOSMOS_ASSESSMENT_SESSION_ID 环境变量提供)

## 你的任务
你**必须**严格遵循以下步骤：

### 步骤 1: 验证环境
首先，你需要验证是否可以正常调用bash命令。请执行以下命令：
```bash
date
```

### 步骤 2: 报告结果
将命令执行的结果返回，并说明凭证传递是否正常工作。

现在开始测试。
"""

    # Prepare log file
    log_dir = Path("logs/agent_sessions")
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file_path = log_dir / f"{session_id}_test.log"

    print(f"[{datetime.now()}] Starting qwen process with test prompt...")
    print(f"[{datetime.now()}] Log file: {log_file_path}")

    # Start the process
    command = ["qwen", "-p", test_prompt, "--approval-mode=yolo"]

    try:
        with open(log_file_path, "w", encoding="utf-8") as log_file:
            process = subprocess.Popen(
                command, env=env, start_new_session=True,
                stdout=log_file, stderr=subprocess.STDOUT
            )

        print(f"[{datetime.now()}] Process started with PID: {process.pid}")
        print(f"[{datetime.now()}] Waiting 30 seconds for process to complete...")

        # Wait for a reasonable time
        try:
            process.wait(timeout=30)
            print(f"[{datetime.now()}] Process completed with return code: {process.returncode}")
        except subprocess.TimeoutExpired:
            print(f"[{datetime.now()}] Process timed out after 30 seconds, terminating...")
            process.terminate()
            process.wait(timeout=5)
            if process.poll() is None:
                print(f"[{datetime.now()}] Process still running, force killing...")
                process.kill()
                process.wait()

        # Check log file
        print(f"[{datetime.now()}] Checking log file contents...")
        if log_file_path.exists():
            with open(log_file_path, "r", encoding="utf-8") as f:
                log_content = f.read()
                print(f"[{datetime.now()}] Log file content ({len(log_content)} bytes):")
                if log_content:
                    print("=" * 50)
                    print(log_content)
                    print("=" * 50)
                else:
                    print("Log file is empty!")
        else:
            print(f"[{datetime.now()}] ERROR: Log file not found!")

        return True

    except Exception as e:
        print(f"[{datetime.now()}] ERROR: Failed to start process: {e}")
        return False

if __name__ == "__main__":
    print(f"[{datetime.now()}] === Starting Credential Dispatch Test ===")
    success = test_credential_dispatch()
    print(f"[{datetime.now()}] Test {'PASSED' if success else 'FAILED'}")