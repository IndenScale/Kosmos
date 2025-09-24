print("--- [Trigger Probe] asset_analysis/trigger.py loaded ---")
"""资产分析触发器 - 监听DocumentContentExtracted事件并触发资产分析作业"""
import json
import time
import redis

# [FIX] Import the broker explicitly to ensure correct message dispatching
from backend.app.tasks import broker
from backend.app.core.redis_client import get_redis_client
from backend.app.tasks import analyze_asset_actor

def listen_for_content_extracted_events():
    """
    连接到Redis并监听DocumentContentExtracted事件，
    触发资产分析作业的创建。
    """
    print("--- [Asset Analysis Trigger] 启动 ---")
    # 记录关键配置设置用于调试
    from backend.app.core.config import settings
    print(f"  - DATABASE_URL: {settings.DATABASE_URL}")
    
    while True:
        try:
            redis_client = get_redis_client()
            pubsub = redis_client.pubsub(ignore_subscribe_messages=True)
            
            channel = "kosmos:events:ingestion"
            pubsub.subscribe(channel)
            
            print(f"--- [Asset Analysis Trigger] Subscribed to Redis channel: {channel} ---")

            for message in pubsub.listen():
                channel_name = message['channel']
                message_data = message['data']
                print(f"--- [Asset Analysis Trigger] Received message from '{channel_name}' ---")
                print(f"    - 消息摘要: {message_data[:250]}...")
                
                event_data = json.loads(message_data)
                
                if event_data.get('event_type') != 'DocumentContentExtractedPayload':
                    print(f"  - Info: Skipping event of type '{event_data.get('event_type')}'.")
                    continue

                payload = event_data.get('payload', {})
                doc_id = payload.get('document_id')
                asset_ids = payload.get('extracted_asset_ids', [])
                ks_id = payload.get('knowledge_space_id')
                initiator_id = payload.get('initiator_id')
                correlation_id = event_data.get('correlation_id')
                
                if not doc_id or not ks_id or not initiator_id:
                    print("  - Warning: Received event with missing document_id, knowledge_space_id, or initiator_id. Skipping.")
                    continue
                
                print(f"  - Event 'DocumentContentExtracted' received for document_id: {doc_id}, found {len(asset_ids)} assets.")

                for asset_id in asset_ids:
                    # [DEBUG] Print the exact arguments being sent to the actor
                    print(f"    - Dispatching to actor with: asset_id='{asset_id}', doc_id='{doc_id}', ks_id='{ks_id}', initiator_id='{initiator_id}', correlation_id='{correlation_id}'")
                    # [FIX] Call the actor's send() method directly.
                    analyze_asset_actor.send(
                        asset_id,
                        doc_id,
                        ks_id,
                        initiator_id,
                        correlation_id
                    )

        except redis.exceptions.ConnectionError as e:
            print(f"!! [Asset Analysis Trigger] Redis connection error: {e}. Reconnecting in 15 seconds...")
            time.sleep(15)
        except Exception as e:
            print(f"!! [Asset Analysis Trigger] An unexpected error occurred: {e}")
            time.sleep(5)

if __name__ == "__main__":
    listen_for_content_extracted_events()