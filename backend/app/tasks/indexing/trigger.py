print("--- [Trigger Probe] indexing/trigger.py loaded ---")
"""索引触发器 - 监听DocumentChunkingCompleted事件并触发索引作业"""
import sys
import os

# Ensure the project root is in the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import json
import uuid
import logging
# [FIX] Import the broker explicitly to ensure correct message dispatching
from backend.app.tasks import broker
from backend.app.core.redis_client import get_redis_client
from backend.app.tasks.service_factory import get_services_scope
from backend.app.services.job.creation import create_indexing_job
from backend.app.models import JobType, CredentialType
from backend.app.tasks import indexing_actor

logger = logging.getLogger(__name__)

def listen_for_chunking_completed_events():
    """
    连接到Redis并监听DocumentChunkingCompleted事件，
    触发索引作业的创建。
    """
    print("--- [Indexing Trigger] 启动 ---")
    # 记录关键配置设置用于调试
    from backend.app.core.config import settings
    print(f"  - DATABASE_URL: {settings.DATABASE_URL}")
    
    while True:
        try:
            redis_client = get_redis_client()
            pubsub = redis_client.pubsub(ignore_subscribe_messages=True)
            
            channel = "kosmos:events:chunking"
            pubsub.subscribe(channel)
            
            print(f"--- [Indexing Trigger] Subscribed to Redis channel: {channel} ---")

            for message in pubsub.listen():
                channel_name = message['channel']
                message_data = message['data']
                print(f"--- [Indexing Trigger] Received message from '{channel_name}' ---")
                print(f"    - 消息摘要: {message_data[:250]}...")
                
                event_data = json.loads(message_data)
                
                if event_data.get('event_type') != 'DocumentChunkingCompletedPayload':
                    print(f"  - Info: Skipping event of type '{event_data.get('event_type')}'.")
                    continue

                payload = event_data.get('payload', {})
                document_id_str = payload.get('document_id')
                knowledge_space_id_str = payload.get('knowledge_space_id')
                
                if not document_id_str or not knowledge_space_id_str:
                    print("  - Warning: Received event with missing document_id or knowledge_space_id. Skipping.")
                    continue
                
                try:
                    document_id = uuid.UUID(document_id_str)
                    knowledge_space_id = uuid.UUID(knowledge_space_id_str)
                except ValueError as e:
                    print(f"  - Warning: Invalid UUID format in event payload: {e}. Skipping.")
                    continue
                
                print(f"  - Processing DocumentChunkingCompleted event for document {document_id}")
                print(f"    - Knowledge Space: {knowledge_space_id}")
                print(f"    - Total chunks created: {payload.get('total_chunks_created', 'unknown')}")
                print(f"    - Chunking strategy used: {payload.get('chunking_strategy_used', 'unknown')}")
                
                # 使用数据库会话处理作业创建
                with get_services_scope() as services:
                    db_session = services["db"]
                    
                    try:
                        # 查找最近的处理作业以获取initiator_id
                        from backend.app.models import Job, Document
                        recent_job = (
                            db_session.query(Job)
                            .join(Document, Job.document_id == Document.id)
                            .filter(
                                Document.id == document_id,
                                Job.job_type.in_([JobType.DOCUMENT_PROCESSING, JobType.CHUNKING])
                            )
                            .order_by(Job.created_at.desc())
                            .first()
                        )
                        
                        if not recent_job:
                            print(f"  - Warning: No recent processing job found for document {document_id}. Skipping indexing.")
                            continue
                        
                        initiator_id = recent_job.initiator_id
                        
                        # 创建索引作业的上下文
                        job_context = {
                            "triggered_by_event": "DocumentChunkingCompleted",
                            "source_event_correlation_id": event_data.get('correlation_id'),
                            "chunking_job_id": payload.get('job_id')
                        }

                        try:
                            # 步骤1：在数据库中创建作业记录
                            job = create_indexing_job(
                                db=db_session,
                                document_id=document_id,
                                initiator_id=initiator_id,
                                force=False  # 如果已有索引则跳过
                            )
                            
                            # 将上下文信息添加到作业中
                            job.context = job_context
                            
                            db_session.commit()
                            print(f"  - Created indexing job {job.id} for document {document_id}")
                            
                            # [FIX] Call the actor's send() method directly.
                            indexing_actor.send(str(job.id))
                            print(f"  - Dispatched indexing job {job.id} to Dramatiq queue")
                            
                        except ValueError as ve:
                            if "already running or pending" in str(ve):
                                print(f"  - Info: Indexing job for document {document_id} already exists. Skipping.")
                            else:
                                print(f"  - Error creating indexing job: {ve}")
                        except Exception as e:
                            print(f"  - Error creating or dispatching indexing job: {e}")
                            db_session.rollback()
                            
                    except Exception as e:
                        print(f"  - Error processing chunking completed event: {e}")
                        db_session.rollback()
                        
        except KeyboardInterrupt:
            print("\n--- [Indexing Trigger] Received interrupt signal. Shutting down gracefully... ---")
            break
        except Exception as e:
            print(f"--- [Indexing Trigger] Error in main loop: {e} ---")
            import time
            time.sleep(5)  # 等待5秒后重试
            continue

if __name__ == "__main__":
    listen_for_chunking_completed_events()