"""
Security Headers Middleware
Enforces security headers for HIPAA compliance and general security hardening.
"""
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import os
import logging

logger = logging.getLogger(__name__)

# Check if we're in production
IS_PRODUCTION = os.getenv("ENVIRONMENT", "development").lower() == "production"
HIPAA_MODE = os.getenv("HIPAA_MODE", "false").lower() == "true"


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add security headers to all responses.
    
    Headers added:
    - Strict-Transport-Security (HSTS): Enforce HTTPS in production
    - X-Content-Type-Options: Prevent MIME type sniffing
    - X-Frame-Options: Prevent clickjacking
    - Referrer-Policy: Control referrer information
    - Content-Security-Policy: XSS protection (basic)
    - Permissions-Policy: Control browser features
    """
    
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # HSTS: Only in production and when HIPAA_MODE is enabled
        if IS_PRODUCTION and HIPAA_MODE:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
        
        # X-Content-Type-Options: Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"
        
        # X-Frame-Options: Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"
        
        # Referrer-Policy: Limit referrer information
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # Content-Security-Policy: Basic XSS protection
        # Note: This is a basic CSP. Adjust based on your frontend needs.
        csp = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "  # Adjust for production
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self' data:; "
            "connect-src 'self' https:; "
            "frame-ancestors 'none';"
        )
        response.headers["Content-Security-Policy"] = csp
        
        # Permissions-Policy: Disable unnecessary browser features
        response.headers["Permissions-Policy"] = (
            "geolocation=(), "
            "microphone=(), "
            "camera=(), "
            "payment=(), "
            "usb=()"
        )
        
        # X-XSS-Protection: Legacy browser XSS protection (redundant with CSP but harmless)
        response.headers["X-XSS-Protection"] = "1; mode=block"
        
        return response



































