import json
import hashlib
import logging
from typing import Dict, Any, Optional, List, Tuple, Callable
from datetime import datetime, timedelta
import os
import asyncio
import redis

# 使用Redis或内存缓存，取决于环境配置
USE_REDIS = os.getenv("USE_REDIS", "false").lower() == "true"
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CACHE_TTL = int(os.getenv("CACHE_TTL", "86400"))  # 默认缓存1天

# 内存缓存
memory_cache = {}
cache_expiry = {}

# Configure Redis client
redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)

# Cache expiration time (in seconds)
CACHE_EXPIRATION = 60 * 60 * 24  # 24 hours

async def get_redis_connection():
    """获取Redis连接"""
    if not hasattr(get_redis_connection, "redis"):
        get_redis_connection.redis = redis_client
    return get_redis_connection.redis

def generate_cache_key(prefix: str, params: Dict[str, Any]) -> str:
    """Generate a cache key from a prefix and parameters"""
    sorted_params = json.dumps(params, sort_keys=True)
    key_content = f"{prefix}:{sorted_params}"
    return hashlib.md5(key_content.encode()).hexdigest()

async def get_cached_data(key: str) -> Optional[Any]:
    """获取缓存数据"""
    if USE_REDIS:
        redis = await get_redis_connection()
        data = redis.get(key)
        if data:
            return json.loads(data)
    else:
        # 使用内存缓存
        if key in memory_cache:
            # 检查是否过期
            if key in cache_expiry and cache_expiry[key] > datetime.now():
                return memory_cache[key]
            else:
                # 过期则删除
                if key in memory_cache:
                    del memory_cache[key]
                if key in cache_expiry:
                    del cache_expiry[key]
    
    return None

async def set_cached_data(key: str, data: Any, ttl: int = CACHE_TTL) -> None:
    """设置缓存数据"""
    try:
        if USE_REDIS:
            redis = await get_redis_connection()
            redis.setex(key, ttl, json.dumps(data))
        else:
            # 使用内存缓存
            memory_cache[key] = data
            cache_expiry[key] = datetime.now() + timedelta(seconds=ttl)
    except Exception as e:
        logging.error(f"Error setting cache: {e}")

async def invalidate_cache(key: str) -> None:
    """使缓存失效"""
    if USE_REDIS:
        redis = await get_redis_connection()
        redis.delete(key)
    else:
        if key in memory_cache:
            del memory_cache[key]
        if key in cache_expiry:
            del cache_expiry[key]

async def get_or_create_cached_data(key: str, creator_func: Callable) -> Tuple[Any, bool]:
    """Get data from cache or create it using the provided function"""
    try:
        # Try to get from cache
        cached_data = redis_client.get(key)
        if cached_data:
            return json.loads(cached_data), True
        
        # Create new data
        data = await creator_func()
        
        # Store in cache
        redis_client.setex(key, CACHE_EXPIRATION, json.dumps(data))
        
        return data, False
    except redis.RedisError as e:
        logging.warning(f"Redis error: {e}. Falling back to direct function call.")
        # If Redis fails, just call the function directly
        return await creator_func(), False
    except Exception as e:
        logging.error(f"Unexpected error in cache: {e}")
        # For any other error, also fall back to direct function call
        return await creator_func(), False 

async def cleanup_expired_cache(max_age_hours: int = 24):
    """Clean up expired cache entries to prevent memory leaks"""
    if USE_REDIS:
        # Redis handles expiration automatically via TTL
        pass
    else:
        # Clean up expired memory cache entries
        current_time = datetime.now()
        for key in list(memory_cache.keys()):
            if key in cache_expiry and cache_expiry[key] < current_time:
                del memory_cache[key]
                del cache_expiry[key] 

async def periodic_cache_cleanup():
    while True:
        await cleanup_expired_cache()
        await asyncio.sleep(3600)  # Run every hour

# Start the cleanup task
# asyncio.create_task(periodic_cache_cleanup()) 