"""
事件中继服务 (Event Relay Service)

这是一个独立的、长期运行的后台进程，其唯一职责是：
1. 定期轮询 `domain_events` 数据库表，查找待处理的事件。
2. 将这些事件发布到相应的Redis消息总线频道。
3. 更新事件在数据库中的状态，以确保事件不会被重复发送。

这个服务是“事务性发件箱模式”的关键组成部分，它将核心业务逻辑
与消息传递基础设施完全解耦，并保证了事件传递的可靠性。
"""
import time
import json
import redis
from datetime import datetime, timezone
import os
import logging
from dotenv import load_dotenv

# 配置日志记录
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/event_relay.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# --- .env Configuration Loading ---
# Explicitly load the .env file from the project root to ensure this standalone
# process gets the correct configuration.
dotenv_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', '.env')
load_dotenv(dotenv_path=dotenv_path, override=True)
# --- End of .env Loading ---

from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.redis_client import get_redis_client
from backend.app.models.domain_events import DomainEvent, EventStatus

# --- 事件路由配置 ---
EVENT_ROUTING_CONFIG = {
    # 事件类型 (Pydantic模型的类名) -> Redis Channel 名称
    "DocumentRegisteredPayload": "kosmos:events:registration",
    "DocumentContentExtractedPayload": "kosmos:events:ingestion",
    "AssetAnalysisCompletedPayload": "kosmos:events:analysis",
    "DocumentChunkingCompletedPayload": "kosmos:events:chunking",
    # 未来新的事件类型可以继续添加到这里
}

def process_pending_events(db: Session, redis_client: redis.Redis):
    """
    处理一批待处理的领域事件。
    """
    # 1. 查询一批待处理的事件，按创建时间排序以保证顺序
    logger.info("Polling database for pending events...")
    events_to_process = (
        db.query(DomainEvent)
        .filter(DomainEvent.status == EventStatus.PENDING)
        .order_by(DomainEvent.created_at)
        .limit(settings.EVENT_RELAY_BATCH_SIZE)
        .with_for_update()  # 锁定行，防止多个中继实例处理相同的事件
        .all()
    )
    logger.info(f"Query finished. Found {len(events_to_process)} pending events.")

    if not events_to_process:
        return  # 没有待处理的事件

    logger.info(f"发现 {len(events_to_process)} 个待处理的事件，开始处理...")

    for event in events_to_process:
        try:
            # 2. 根据路由配置查找目标Channel
            channel = EVENT_ROUTING_CONFIG.get(event.event_type)

            if not channel:
                logger.warning(f"事件 {event.id} (类型: {event.event_type}) 没有配置路由，标记为失败。")
                event.status = EventStatus.FAILED
                event.error_message = "No route configured for this event type."
                continue

            # 3. 将事件的payload序列化为JSON并发布
            # 我们发布整个事件的payload，而不仅仅是原始payload，以便消费者获得更丰富的上下文
            # event.payload 现在是JSON字符串，需要先解析再重新序列化
            payload_dict = json.loads(event.payload)
            message = {
                "event_id": str(event.id),
                "correlation_id": str(event.correlation_id),
                "aggregate_id": event.aggregate_id,
                "event_type": event.event_type,
                "payload": payload_dict,
                "created_at": event.created_at.isoformat()
            }

            message_json = json.dumps(message, ensure_ascii=False)
            redis_client.publish(channel, message_json)

            # 4. 更新事件状态为已处理
            event.status = EventStatus.PROCESSED
            event.processed_at = datetime.now(timezone.utc)
            logger.info(f"事件 {event.id} (类型: {event.event_type}) 已发布到频道 '{channel}'")
            # [DEBUG] Print the full, pretty-printed JSON message
            pretty_message_json = json.dumps(message, indent=2, ensure_ascii=False)
            logger.debug(f"完整消息:\n{pretty_message_json}")

        except Exception as e:
            print(f"  - 错误: 发布事件 {event.id} 时失败: {e}")
            # 保持状态为PENDING，下一轮将重试
            # 也可以在这里增加重试计数器，并在达到阈值后标记为FAILED
            event.error_message = str(e)

    # 5. 统一提交所有状态变更
    db.commit()

    # 添加短暂延迟以确保事务完全提交
    time.sleep(0.1)

def run_relay_polling_loop():
    """
    启动事件中继的无限轮询循环。
    """
    # 引入 get_services_scope，因为它负责创建和管理数据库会话
    from backend.app.tasks.service_factory import get_services_scope

    logger.info("--- [事件中继服务] 启动 ---")
    # Log critical configuration settings for debugging
    from backend.app.core.config import settings
    logger.info(f"  - DATABASE_URL: {settings.DATABASE_URL}")
    logger.info(f"  - REDIS_HOST: {settings.REDIS_HOST}")
    logger.info(f"  - REDIS_PORT: {settings.REDIS_PORT}")
    logger.info(f"  - REDIS_DB: {settings.REDIS_DB}")
    logger.info(f"轮询间隔: {settings.EVENT_RELAY_POLLING_INTERVAL} 秒")
    logger.info(f"处理批次大小: {settings.EVENT_RELAY_BATCH_SIZE}")

    redis_client = get_redis_client()

    while True:
        try:
            # 每个循环都使用一个新的数据库会话，以确保会话状态是干净的
            with get_services_scope() as services:
                db_session = services["db"]
                process_pending_events(db_session, redis_client)

        except Exception as e:
            # 捕获顶层异常，防止整个服务因数据库连接等问题而崩溃
            logger.error(f"轮询循环中发生严重错误: {e}")
            # 在继续之前等待更长的时间
            time.sleep(settings.EVENT_RELAY_POLLING_INTERVAL * 3)

        # 等待下一个轮询周期
        time.sleep(settings.EVENT_RELAY_POLLING_INTERVAL)

if __name__ == "__main__":
    # 使此脚本可以直接运行
    run_relay_polling_loop()
