print("--- [Trigger Probe] chunking/trigger.py loaded ---")
"""分块触发器 - 监听DocumentContentExtracted事件并触发分块作业"""
import json
import uuid
import logging

# --- [FIX] Explicitly import the broker to ensure it's configured before any actors are imported. ---
from backend.app.tasks import broker
# --- End of Fix ---

from backend.app.core.redis_client import get_redis_client
from backend.app.tasks.service_factory import get_services_scope
from backend.app.services.job.creation import create_chunking_job
from backend.app.models import JobType, CredentialType
from backend.app.tasks import chunk_document_actor

logger = logging.getLogger(__name__)

def listen_for_content_extracted_events():
    """
    连接到Redis并监听DocumentContentExtracted事件，
    触发分块作业的创建。
    """
    print("--- [Chunking Trigger] 启动 ---")
    # 记录关键配置设置用于调试
    from backend.app.core.config import settings
    print(f"  - DATABASE_URL: {settings.DATABASE_URL}")
    
    while True:
        try:
            redis_client = get_redis_client()
            pubsub = redis_client.pubsub(ignore_subscribe_messages=True)
            
            channel = "kosmos:events:ingestion"
            pubsub.subscribe(channel)
            
            print(f"--- [Chunking Trigger] Subscribed to Redis channel: {channel} ---")

            for message in pubsub.listen():
                channel_name = message['channel']
                message_data = message['data']
                print(f"--- [Chunking Trigger] Received message from '{channel_name}' ---")
                print(f"    - 消息摘要: {message_data[:250]}...")
                
                event_data = json.loads(message_data)
                
                if event_data.get('event_type') != 'DocumentContentExtractedPayload':
                    print(f"  - Info: Skipping event of type '{event_data.get('event_type')}'.")
                    continue

                payload = event_data.get('payload', {})
                document_id_str = payload.get('document_id')
                knowledge_space_id_str = payload.get('knowledge_space_id')
                
                if not document_id_str or not knowledge_space_id_str:
                    print("  - Warning: Received event with missing document_id or knowledge_space_id. Skipping.")
                    continue
                
                document_id = uuid.UUID(document_id_str)
                knowledge_space_id = uuid.UUID(knowledge_space_id_str)

                print(f"  - Event 'DocumentContentExtracted' received for document_id: {document_id}")

                with get_services_scope() as services:
                    db_session = services["db"]
                    
                    # 获取文档信息以确定发起者
                    from backend.app.models import Document
                    document = db_session.query(Document).filter(Document.id == document_id).first()
                    if not document:
                        print(f"  - Warning: Document {document_id} not found. Skipping chunking.")
                        continue
                    
                    # 从文档的最近作业中获取发起者信息
                    from backend.app.models import Job
                    recent_job = db_session.query(Job).filter(
                        Job.document_id == document_id,
                        Job.job_type == JobType.CONTENT_EXTRACTION
                    ).order_by(Job.created_at.desc()).first()
                    
                    if not recent_job:
                        print(f"  - Warning: No recent processing job found for document {document_id}. Skipping chunking.")
                        continue
                    
                    initiator_id = recent_job.initiator_id
                    
                    # 创建分块作业的上下文
                    job_context = {
                        "chunking_params": {
                            "splitter": "rule_based"  # 默认使用基于规则的分割器
                        },
                        "triggered_by_event": "DocumentContentExtracted",
                        "source_event_correlation_id": event_data.get('correlation_id')
                    }

                    try:
                        # 步骤1：在数据库中创建作业记录
                        job = create_chunking_job(
                            db=db_session,
                            document_id=document_id,
                            initiator_id=initiator_id,
                            credential_type_preference=CredentialType.SLM,  # 默认使用小模型
                            context=job_context,
                            force=False  # 如果已有分块则跳过
                        )
                        
                        db_session.commit()
                        print(f"  - Created chunking job {job.id} for document {document_id}")
                        
                        # [FIX] Call the actor's send() method directly.
                        chunk_document_actor.send(str(job.id))
                        print(f"  - Dispatched chunking actor for job {job.id}")
                        
                    except ValueError as e:
                        # 作业已存在或其他业务逻辑错误
                        print(f"  - Info: {e}")
                        db_session.rollback()
                    except Exception as e:
                        print(f"  - Error: Failed to create chunking job for document {document_id}: {e}")
                        db_session.rollback()
                        
        except KeyboardInterrupt:
            print("--- [Chunking Trigger] Shutting down gracefully ---")
            break
        except Exception as e:
            print(f"--- [Chunking Trigger] Unexpected error: {e} ---")
            print("--- [Chunking Trigger] Restarting listener in 5 seconds ---")
            import time
            time.sleep(5)

if __name__ == "__main__":
    listen_for_content_extracted_events()