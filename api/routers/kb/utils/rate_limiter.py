"""
Rate Limiting Utility for KB API
"""
import time
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)

class RateLimiter:
    """Simple in-memory rate limiter for KB API"""
    
    def __init__(self, window_seconds: int = 60, max_requests: int = 60):
        self.window_seconds = window_seconds
        self.max_requests = max_requests
        self._rate_limits: Dict[str, List[float]] = {}
    
    def check_rate_limit(self, client_ip: str) -> bool:
        """Check if client is within rate limits"""
        now = time.time()
        
        # Initialize client if not exists
        if client_ip not in self._rate_limits:
            self._rate_limits[client_ip] = []
        
        # Clean old requests
        self._rate_limits[client_ip] = [
            req_time for req_time in self._rate_limits[client_ip] 
            if now - req_time < self.window_seconds
        ]
        
        # Check limit
        if len(self._rate_limits[client_ip]) >= self.max_requests:
            logger.warning(f"Rate limit exceeded for client: {client_ip}")
            return False
        
        # Add current request
        self._rate_limits[client_ip].append(now)
        return True
    
    def get_remaining_requests(self, client_ip: str) -> int:
        """Get remaining requests for client"""
        if client_ip not in self._rate_limits:
            return self.max_requests
        
        now = time.time()
        # Clean old requests
        self._rate_limits[client_ip] = [
            req_time for req_time in self._rate_limits[client_ip] 
            if now - req_time < self.window_seconds
        ]
        
        return max(0, self.max_requests - len(self._rate_limits[client_ip]))
    
    def get_stats(self) -> Dict[str, any]:
        """Get rate limiter statistics"""
        now = time.time()
        active_clients = 0
        total_requests = 0
        
        for client_ip, requests in self._rate_limits.items():
            # Clean old requests
            active_requests = [
                req_time for req_time in requests 
                if now - req_time < self.window_seconds
            ]
            self._rate_limits[client_ip] = active_requests
            
            if active_requests:
                active_clients += 1
                total_requests += len(active_requests)
        
        return {
            "active_clients": active_clients,
            "total_requests": total_requests,
            "window_seconds": self.window_seconds,
            "max_requests_per_window": self.max_requests
        }

# Global rate limiter instance
_rate_limiter: RateLimiter = None

def get_rate_limiter() -> RateLimiter:
    """Get the global rate limiter instance"""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter



