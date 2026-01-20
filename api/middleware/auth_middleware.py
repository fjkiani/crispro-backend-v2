"""
Authentication Middleware for FastAPI
Verifies JWT tokens from Supabase Auth and provides user context.
"""
import os
try:
    import jwt  # PyJWT package provides 'jwt' module
except ImportError:
    jwt = None  # Optional auth - graceful degradation
from fastapi import HTTPException, Depends, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, Dict, Any
import logging
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Security scheme for Bearer token
security = HTTPBearer()

# Get JWT secret from environment
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")
JWT_ALGORITHM = "HS256"

if not SUPABASE_JWT_SECRET:
    logger.warning("⚠️ SUPABASE_JWT_SECRET not set - JWT verification will fail")


async def verify_token(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> Dict[str, Any]:
    """
    Verify JWT token from Authorization header.
    
    Args:
        credentials: HTTPBearer credentials containing the token
        
    Returns:
        {
            "user_id": "uuid",
            "email": "user@example.com",
            "role": "authenticated",
            "exp": 1234567890
        }
        
    Raises:
        HTTPException: If token is invalid, expired, or missing
    """
    if not SUPABASE_JWT_SECRET:
        raise HTTPException(
            status_code=500,
            detail="Authentication service not configured (SUPABASE_JWT_SECRET missing)"
        )
    
    token = credentials.credentials
    
    try:
        # Decode JWT token using Supabase JWT secret
        payload = jwt.decode(
            token,
            SUPABASE_JWT_SECRET,
            algorithms=[JWT_ALGORITHM],
            audience="authenticated"
        )
        
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=401,
                detail="Invalid token: missing user_id (sub claim)"
            )
        
        return {
            "user_id": user_id,
            "email": payload.get("email"),
            "role": payload.get("role", "authenticated"),
            "exp": payload.get("exp"),
            "raw_payload": payload  # For debugging
        }
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=401,
            detail="Token expired. Please log in again."
        )
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid token: {str(e)}")
        raise HTTPException(
            status_code=401,
            detail=f"Invalid token: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Token verification error: {e}")
        raise HTTPException(
            status_code=401,
            detail=f"Token verification failed: {str(e)}"
        )


async def get_current_user(token_data: Dict[str, Any] = Depends(verify_token)) -> Dict[str, Any]:
    """
    Get current authenticated user from verified token.
    
    Usage:
        @router.post("/api/endpoint")
        async def my_endpoint(user: dict = Depends(get_current_user)):
            user_id = user["user_id"]
            ...
    """
    return token_data


async def get_optional_user(
    authorization: Optional[str] = Header(None)
) -> Optional[Dict[str, Any]]:
    """
    Get user if token is present, otherwise return None.
    Useful for endpoints that work with or without authentication.
    
    Usage:
        @router.post("/api/endpoint")
        async def my_endpoint(user: Optional[dict] = Depends(get_optional_user)):
            if user:
                user_id = user["user_id"]
            else:
                # Anonymous access
                ...
    """
    if not authorization or not authorization.startswith("Bearer "):
        return None
    
    try:
        token = authorization.replace("Bearer ", "")
        payload = jwt.decode(
            token,
            SUPABASE_JWT_SECRET,
            algorithms=[JWT_ALGORITHM],
            audience="authenticated"
        )
        
        return {
            "user_id": payload.get("sub"),
            "email": payload.get("email"),
            "role": payload.get("role", "authenticated"),
            "exp": payload.get("exp")
        }
    except Exception:
        # Invalid token, return None (anonymous access)
        return None





