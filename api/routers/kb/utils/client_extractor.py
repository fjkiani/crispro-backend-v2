"""
Client IP Extraction Utility
"""
from fastapi import Header, Depends
from typing import Optional

def get_client_ip(x_forwarded_for: Optional[str] = Header(None)) -> str:
    """Extract client IP from headers"""
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return "127.0.0.1"



