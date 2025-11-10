"""
Cache Service - Redis-based caching with single-flight protection
"""
import json
import time
import asyncio
from typing import Any, Optional, Callable, Dict
import os
try:
    import redis.asyncio as redis
except ImportError:
    redis = None
from fastapi import HTTPException

# Redis connection
_redis_client = None

def get_redis_client():
    """Get or create Redis client"""
    global _redis_client
    if _redis_client is None:
        redis_url = os.getenv("REDIS_URL")
        if redis_url and redis:
            try:
                _redis_client = redis.from_url(redis_url, decode_responses=True)
            except Exception as e:
                print(f"Warning: Redis connection failed: {e}")
                _redis_client = None
    return _redis_client

async def get_cache(key: str) -> Optional[Any]:
    """Get cached value by key"""
    client = get_redis_client()
    if not client:
        return None
    
    try:
        value = await client.get(key)
        if value:
            return json.loads(value)
    except Exception as e:
        print(f"Cache get error: {e}")
    return None

async def set_cache(key: str, value: Any, ttl: int = 3600) -> bool:
    """Set cached value with TTL"""
    client = get_redis_client()
    if not client:
        return False
    
    try:
        serialized = json.dumps(value)
        await client.setex(key, ttl, serialized)
        return True
    except Exception as e:
        print(f"Cache set error: {e}")
        return False

async def with_singleflight(key: str, ttl_lock: int, fn: Callable) -> Any:
    """Execute function with single-flight protection"""
    client = get_redis_client()
    if not client:
        # No Redis, execute directly
        return await fn()
    
    lock_key = f"lock:{key}"
    cache_key = f"cache:{key}"
    
    # Try to get cached result first
    cached = await get_cache(cache_key)
    if cached is not None:
        return cached
    
    # Try to acquire lock
    lock_acquired = False
    try:
        # Try to set lock with expiration
        lock_acquired = await client.set(lock_key, "1", nx=True, ex=ttl_lock)
        
        if lock_acquired:
            # We got the lock, execute function
            result = await fn()
            # Cache the result
            await set_cache(cache_key, result, ttl=3600)
            return result
        else:
            # Someone else has the lock, wait and retry
            await asyncio.sleep(0.1)
            # Try to get cached result again
            cached = await get_cache(cache_key)
            if cached is not None:
                return cached
            # If still no cache, wait a bit more and try again
            await asyncio.sleep(0.5)
            cached = await get_cache(cache_key)
            if cached is not None:
                return cached
            # Last resort: execute function anyway
            return await fn()
    finally:
        if lock_acquired:
            try:
                await client.delete(lock_key)
            except Exception:
                pass

# Cache key generators
def insights_cache_key(variant_key: str, profile: str) -> str:
    """Generate cache key for insights"""
    return f"insights:{variant_key}:{profile}"

def efficacy_cache_key(variant_key: str, profile: str) -> str:
    """Generate cache key for efficacy"""
    return f"efficacy:{variant_key}:{profile}"

def datasets_cache_key(study_hash: str, profile: str) -> str:
    """Generate cache key for datasets"""
    return f"datasets:{study_hash}:{profile}"

def literature_cache_key(gene: str, hgvs_p: str, disease: str, max_results: int) -> str:
    """Generate cache key for literature searches"""
    key_parts = [gene or "", hgvs_p or "", disease or "", str(max_results)]
    return f"literature:{':'.join(key_parts)}"

# TTL constants
INSIGHTS_TTL = int(os.getenv("CACHE_TTL_INSIGHTS", "86400"))  # 24 hours
EFFICACY_TTL = int(os.getenv("CACHE_TTL_EFFICACY", "21600"))  # 6 hours
DATASETS_TTL = int(os.getenv("CACHE_TTL_DATASETS", "86400"))  # 24 hours
LITERATURE_TTL = int(os.getenv("CACHE_TTL_LITERATURE", "86400"))  # 24 hours

# Health check
async def cache_health() -> Dict[str, Any]:
    """Check cache service health"""
    client = get_redis_client()
    if not client:
        return {"status": "disabled", "redis_available": False}
    
    try:
        await client.ping()
        return {"status": "healthy", "redis_available": True}
    except Exception as e:
        return {"status": "unhealthy", "redis_available": False, "error": str(e)}
