import redis
from .config import settings

def get_redis_client() -> redis.Redis:
    """
    Returns a Redis client instance configured from application settings.
    """
    return redis.Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        db=settings.REDIS_DB,
        decode_responses=True
    )
