print("--- [Broker Probe] broker.py loaded ---")
import redis
import dramatiq
from dramatiq.brokers.redis import RedisBroker
from dramatiq.middleware import Retries, Prometheus, AgeLimit, TimeLimit, Callbacks
import logging
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# --- [CRITICAL FIX] Ensure project root is in sys.path ---
# This guarantees that the 'backend' package can be found and imported
# regardless of how the dramatiq CLI is invoked.
project_root = Path(__file__).resolve().parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
    print(f"--- [Broker Probe] Project root '{project_root}' added to sys.path.")
# --- End of Fix ---

# --- .env Configuration Loading ---
# Explicitly load the .env file from the project root to ensure Dramatiq workers
# get the correct configuration when started from the command line.
# This is crucial for connecting to the correct Redis database.
dotenv_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', '.env')
load_dotenv(dotenv_path=dotenv_path, override=True)
# --- End of .env Loading ---

from backend.app.core.config import settings

logger = logging.getLogger(__name__)

# Log critical configuration settings for debugging Dramatiq workers
print("--- [Dramatiq Broker] 正在初始化 ---")
print(f"  - DATABASE_URL: {settings.DATABASE_URL}")
print(f"  - REDIS_HOST: {settings.REDIS_HOST}")
print(f"  - REDIS_PORT: {settings.REDIS_PORT}")
print(f"  - REDIS_DB: {settings.REDIS_DB}")
print("------------------------------------")

# --- Middleware Configuration ---
# By explicitly defining the middleware, we control what is loaded.
# This is necessary to conditionally disable Prometheus.
middleware = [
    AgeLimit(),
    TimeLimit(),
    Callbacks(),
    Retries()
]
if os.getenv("DRAMATIQ_SKIP_PROMETHEUS") != "1":
    print("  - Prometheus middleware ENABLED.")
    middleware.append(Prometheus())
else:
    print("  - Prometheus middleware DISABLED by environment variable.")
# --- End of Middleware Configuration ---


broker = RedisBroker(
    host=settings.REDIS_HOST, 
    port=settings.REDIS_PORT, 
    db=settings.REDIS_DB,
    middleware=middleware
)

dramatiq.set_broker(broker)

print(f"--- [Dramatiq Broker] Broker initialized. Declared queues: {broker.queues} ---")




def get_redis_client() -> redis.Redis:
    """
    获取Redis客户端连接
    
    Returns:
        redis.Redis: Redis客户端实例
    """
    return redis.Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        db=settings.REDIS_DB,
        decode_responses=True
    )

def clear_all_queues() -> int:
    """
    清理所有Dramatiq队列
    
    Returns:
        int: 清理的键数量
    """
    redis_client = get_redis_client()
    
    patterns = [
        "dramatiq:*", "dramatiq-rate-limits:*"
    ]
    
    all_keys = set()
    for pattern in patterns:
        keys = redis_client.keys(pattern)
        all_keys.update(keys)
    
    if not all_keys:
        logger.info("没有找到Dramatiq队列或限流器键，无需清理")
        return 0
    
    deleted_count = redis_client.delete(*list(all_keys))
    logger.info(f"成功清理了 {deleted_count} 个Dramatiq相关的键")
    
    return deleted_count
