"""
Admin Middleware for FastAPI
Enforces admin role requirement for admin endpoints.
"""
from fastapi import HTTPException, Depends
from typing import Dict, Any
import logging

from .auth_middleware import get_current_user

logger = logging.getLogger(__name__)


async def require_admin(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """
    Require authenticated user to have admin role.
    
    Usage:
        @router.get("/api/admin/users")
        async def list_users(admin: dict = Depends(require_admin)):
            # Only admins can access this endpoint
            ...
    
    Raises:
        HTTPException: If user is not authenticated or not an admin
    """
    user_id = user.get("user_id")
    user_role = user.get("role", "authenticated")
    
    # Check if user has admin role
    # Note: Role can come from JWT token or from user_profiles table
    if user_role != "admin":
        # Check user_profiles table for admin role
        from ..services.supabase_service import supabase
        if supabase.enabled:
            try:
                profiles = await supabase.select("user_profiles", {"id": user_id}, limit=1)
                if profiles and len(profiles) > 0:
                    profile_role = profiles[0].get("role", "researcher")
                    if profile_role != "admin":
                        logger.warning(f"Non-admin user {user_id[:8]}... attempted admin access")
                        raise HTTPException(
                            status_code=403,
                            detail="Admin access required. Contact administrator."
                        )
                else:
                    # Profile doesn't exist, default to non-admin
                    raise HTTPException(
                        status_code=403,
                        detail="Admin access required. Contact administrator."
                    )
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Failed to check admin role: {e}")
                raise HTTPException(
                    status_code=403,
                    detail="Admin access required. Contact administrator."
                )
        else:
            # Supabase not enabled, check JWT role only
            if user_role != "admin":
                raise HTTPException(
                    status_code=403,
                    detail="Admin access required. Contact administrator."
                )
    
    return user


async def require_admin_or_self(
    user_id: str,
    user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Require user to be admin OR the user themselves.
    
    Useful for endpoints where users can view their own data,
    but admins can view any user's data.
    
    Usage:
        @router.get("/api/admin/users/{user_id}")
        async def get_user(user_id: str, admin: dict = Depends(require_admin_or_self)):
            ...
    """
    current_user_id = user.get("user_id")
    
    # Allow if user is viewing their own data
    if current_user_id == user_id:
        return user
    
    # Otherwise require admin
    return await require_admin(user)

