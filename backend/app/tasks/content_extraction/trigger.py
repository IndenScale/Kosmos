print("--- [Trigger Probe] content_extraction/trigger.py loaded ---")
import json
import redis
import time
import uuid
import os
from typing import Dict, Any, Optional, Tuple
from dotenv import load_dotenv

# --- .env Configuration Loading ---
def load_environment_config():
    """加载环境配置"""
    dotenv_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', '.env')
    load_dotenv(dotenv_path=dotenv_path, override=True)

load_environment_config()
# --- End of .env Loading ---

from backend.app.core.redis_client import get_redis_client
from backend.app.tasks.service_factory import get_services_scope
from backend.app.models.job import JobType
from backend.app.services.job.creation import create_content_extraction_job
from backend.app.tasks import broker, content_extraction_actor


def print_startup_info():
    """打印启动信息"""
    print("--- [Content Extraction Trigger] 启动 ---")
    from backend.app.core.config import settings
    print(f"  - DATABASE_URL: {settings.DATABASE_URL}")


def validate_event_data(event_data: Dict[str, Any]) -> Optional[Tuple[uuid.UUID, uuid.UUID, Dict[str, Any]]]:
    """
    验证事件数据并提取必要信息
    
    Returns:
        Tuple[document_id, initiator_id, job_context] 如果验证成功
        None 如果验证失败
    """
    if event_data.get('event_type') != 'DocumentRegisteredPayload':
        print(f"  - Info: Skipping event of type '{event_data.get('event_type')}'.")
        return None

    payload = event_data.get('payload', {})
    document_id_str = payload.get('document_id')
    initiator_id_str = payload.get('initiator_id')

    if not document_id_str or not initiator_id_str:
        print("  - Warning: Received event with missing document_id or initiator_id. Skipping.")
        return None

    try:
        document_id = uuid.UUID(document_id_str)
        initiator_id = uuid.UUID(initiator_id_str)
    except ValueError as e:
        print(f"  - Warning: Invalid UUID format: {e}. Skipping.")
        return None

    job_context = {
        "force": payload.get('force', False),
        "content_extraction_strategy": payload.get('content_extraction_strategy'),
        "asset_analysis_strategy": payload.get('asset_analysis_strategy'),
        "chunking_strategy_name": payload.get('chunking_strategy_name'),
    }

    return document_id, initiator_id, job_context


def create_job_with_retry(document_id: uuid.UUID, initiator_id: uuid.UUID, job_context: Dict[str, Any]) -> bool:
    """
    使用重试机制创建内容提取作业
    
    Returns:
        bool: 作业是否成功创建
    """
    for attempt in range(3):
        try:
            with get_services_scope() as services:
                db_session = services["db"]
                job = create_content_extraction_job(
                    db=db_session,
                    document_id=document_id,
                    initiator_id=initiator_id,
                    force=job_context.get('force', False),
                    context=job_context
                )
                db_session.commit()
                # 在会话关闭前保存job_id，避免会话绑定问题
                job_id = job.id

            content_extraction_actor.send(str(job_id))
            print(f"  - Successfully created job {job_id} and enqueued it to 'content_extraction' queue. (Attempt {attempt + 1})")
            return True
            
        except ValueError as e:
            if "not found during job creation" in str(e):
                print(f"  - Attempt {attempt + 1}/3: Document {document_id} not found, retrying in 0.5s...")
                time.sleep(0.5)
                continue
            else:
                print(f"  - ERROR during job creation for doc {document_id}: {e}")
                break
        except Exception as e:
            print(f"  - ERROR during job creation for doc {document_id}: {e}")
            break
    
    return False


def process_message(message: Dict[str, Any]) -> None:
    """处理单个Redis消息"""
    channel_name = message['channel']
    message_data = message['data']
    print(f"--- [Content Extraction Trigger] Received message from '{channel_name}' ---")
    print(f"    - 消息摘要: {message_data[:250]}...")

    try:
        event_data = json.loads(message_data)
    except json.JSONDecodeError as e:
        print(f"  - ERROR: Failed to parse JSON message: {e}")
        return

    validation_result = validate_event_data(event_data)
    if validation_result is None:
        return

    document_id, initiator_id, job_context = validation_result
    print(f"  - Event 'DocumentRegistered' received for document_id: {document_id}")

    job_created = create_job_with_retry(document_id, initiator_id, job_context)
    if not job_created:
        print(f"  - CRITICAL: Failed to create job for document {document_id} after multiple retries.")


def handle_redis_connection_error(e: redis.exceptions.ConnectionError) -> None:
    """处理Redis连接错误"""
    print(f"!! [Content Extraction Trigger] Redis connection error: {e}. Reconnecting in 15 seconds...")
    time.sleep(15)


def handle_general_error(e: Exception) -> None:
    """处理通用错误"""
    print(f"!! [Content Extraction Trigger] An unexpected error occurred: {e}")
    time.sleep(5)


def listen_for_registration_events():
    """
    Connects to Redis and listens for DocumentRegistered events,
    triggering the creation of content extraction jobs.
    """
    print_startup_info()

    while True:
        try:
            redis_client = get_redis_client()
            pubsub = redis_client.pubsub(ignore_subscribe_messages=True)

            channel = "kosmos:events:registration"
            pubsub.subscribe(channel)

            print(f"--- [Content Extraction Trigger] Subscribed to Redis channel: {channel} ---")

            for message in pubsub.listen():
                process_message(message)

        except redis.exceptions.ConnectionError as e:
            handle_redis_connection_error(e)
        except Exception as e:
            handle_general_error(e)


if __name__ == "__main__":
    listen_for_registration_events()