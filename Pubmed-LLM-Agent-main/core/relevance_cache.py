import os
import json
import hashlib
from typing import Dict, Any, Optional
import redis

class RelevanceCache:
    def __init__(self):
        url = os.getenv("REDIS_URL")
        self.redis = redis.from_url(url, decode_responses=True) if url else None

    def get_key(self, pmid: str, query: str) -> str:
        query_hash = hashlib.md5(query.encode()).hexdigest()[:8]
        return f"relevance:{pmid}:{query_hash}"

    def get(self, pmid: str, query: str) -> Optional[Dict[str, Any]]:
        if not self.redis:
            return None
        key = self.get_key(pmid, query)
        val = self.redis.get(key)
        return json.loads(val) if val else None

    def set(self, pmid: str, query: str, data: Dict[str, Any], ttl=604800):
        if not self.redis:
            return
        key = self.get_key(pmid, query)
        self.redis.setex(key, ttl, json.dumps(data))
