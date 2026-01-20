"""
Admin Router
Endpoints for admin dashboard: user management, analytics, activity tracking.
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
import logging

from ..services.admin_service import AdminService
from ..middleware.admin_middleware import require_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])

# Initialize admin service
_admin_service: Optional[AdminService] = None

def get_admin_service() -> AdminService:
    """Get admin service singleton."""
    global _admin_service
    if _admin_service is None:
        _admin_service = AdminService()
    return _admin_service


# Pydantic models
class UserUpdateRequest(BaseModel):
    """User update request model."""
    full_name: Optional[str] = None
    institution: Optional[str] = None
    role: Optional[str] = None
    tier: Optional[str] = Field(None, pattern="^(free|pro|enterprise)$")
    variant_analyses_limit: Optional[int] = None
    drug_queries_limit: Optional[int] = None
    food_queries_limit: Optional[int] = None
    clinical_trials_limit: Optional[int] = None


# User Management Endpoints
@router.get("/users")
async def list_users(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    tier: Optional[str] = None,
    role: Optional[str] = None,
    status: Optional[str] = None,
    admin: Dict[str, Any] = Depends(require_admin)
):
    """
    List users with pagination and filters.
    Requires admin role.
    """
    try:
        service = get_admin_service()
        result = await service.get_users(
            page=page,
            limit=limit,
            search=search,
            tier=tier,
            role=role,
            status=status
        )
        return {
            "success": True,
            "data": result
        }
    except Exception as e:
        logger.error(f"Failed to list users: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list users: {str(e)}")


@router.get("/users/{user_id}")
async def get_user(
    user_id: str,
    admin: Dict[str, Any] = Depends(require_admin)
):
    """
    Get user details including usage stats.
    Requires admin role.
    """
    try:
        service = get_admin_service()
        user_details = await service.get_user_details(user_id)
        
        if not user_details:
            raise HTTPException(status_code=404, detail="User not found")
        
        return {
            "success": True,
            "data": user_details
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get user details: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get user details: {str(e)}")


@router.put("/users/{user_id}")
async def update_user(
    user_id: str,
    updates: UserUpdateRequest,
    admin: Dict[str, Any] = Depends(require_admin)
):
    """
    Update user profile, tier, role, or quotas.
    Requires admin role.
    """
    try:
        service = get_admin_service()
        
        # Get current user details for audit log
        current_user_details = await service.get_user_details(user_id)
        
        # Convert Pydantic model to dict
        update_dict = updates.dict(exclude_unset=True)
        
        success = await service.update_user(user_id, update_dict)
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update user")
        
        # Log admin action
        from ..audit.writer import get_audit_writer
        audit_writer = get_audit_writer()
        audit_writer.write(
            user_id=admin.get("user_id"),
            action="update_user",
            resource_type="user",
            resource_id=user_id,
            phi_accessed=False,
            additional_data={
                "admin_user_id": admin.get("user_id"),
                "changes": update_dict,
                "previous_values": current_user_details.get("profile", {}) if current_user_details else {}
            }
        )
        
        # Get updated user details
        user_details = await service.get_user_details(user_id)
        
        return {
            "success": True,
            "message": "User updated successfully",
            "data": user_details
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update user: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update user: {str(e)}")


@router.post("/users/{user_id}/suspend")
async def suspend_user(
    user_id: str,
    admin: Dict[str, Any] = Depends(require_admin)
):
    """Suspend a user account."""
    try:
        service = get_admin_service()
        success = await service.update_user(user_id, {"status": "suspended"})
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to suspend user")
        
        # Log admin action
        from ..audit.writer import get_audit_writer
        audit_writer = get_audit_writer()
        audit_writer.write(
            user_id=admin.get("user_id"),
            action="suspend_user",
            resource_type="user",
            resource_id=user_id,
            phi_accessed=False,
            additional_data={"admin_user_id": admin.get("user_id")}
        )
        
        return {
            "success": True,
            "message": "User suspended successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to suspend user: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to suspend user: {str(e)}")


@router.post("/users/{user_id}/activate")
async def activate_user(
    user_id: str,
    admin: Dict[str, Any] = Depends(require_admin)
):
    """Activate a suspended user account."""
    try:
        service = get_admin_service()
        success = await service.update_user(user_id, {"status": "active"})
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to activate user")
        
        # Log admin action
        from ..audit.writer import get_audit_writer
        audit_writer = get_audit_writer()
        audit_writer.write(
            user_id=admin.get("user_id"),
            action="activate_user",
            resource_type="user",
            resource_id=user_id,
            phi_accessed=False,
            additional_data={"admin_user_id": admin.get("user_id")}
        )
        
        return {
            "success": True,
            "message": "User activated successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to activate user: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to activate user: {str(e)}")


@router.post("/users/{user_id}/promote")
async def promote_to_admin(
    user_id: str,
    admin: Dict[str, Any] = Depends(require_admin)
):
    """
    Promote a user to admin role.
    Requires existing admin role.
    """
    try:
        service = get_admin_service()
        
        # Check if target user exists
        user_details = await service.get_user_details(user_id)
        if not user_details:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Update user role to admin
        success = await service.update_user(user_id, {"role": "admin"})
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to promote user")
        
        # Log admin action
        from ..audit.writer import get_audit_writer
        audit_writer = get_audit_writer()
        audit_writer.write(
            user_id=admin.get("user_id"),
            action="promote_to_admin",
            resource_type="user",
            resource_id=user_id,
            phi_accessed=False,
            additional_data={
                "admin_user_id": admin.get("user_id"),
                "previous_role": user_details.get("profile", {}).get("role", "researcher")
            }
        )
        
        return {
            "success": True,
            "message": "User promoted to admin successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to promote user: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to promote user: {str(e)}")


# Analytics Endpoints
@router.get("/analytics/overview")
async def get_analytics_overview(
    period: str = Query("7d", pattern="^(7d|30d|90d|all)$"),
    admin: Dict[str, Any] = Depends(require_admin)
):
    """
    Get dashboard overview analytics.
    Requires admin role.
    """
    try:
        service = get_admin_service()
        analytics = await service.get_analytics_overview(period=period)
        
        return {
            "success": True,
            "data": analytics
        }
    except Exception as e:
        logger.error(f"Failed to get analytics overview: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get analytics: {str(e)}")


@router.get("/analytics/usage")
async def get_usage_trends(
    period: str = Query("7d", pattern="^(7d|30d|90d|all)$"),
    admin: Dict[str, Any] = Depends(require_admin)
):
    """
    Get usage trends over time.
    Requires admin role.
    """
    try:
        service = get_admin_service()
        trends = await service.get_usage_trends(period=period)
        
        return {
            "success": True,
            "data": trends
        }
    except Exception as e:
        logger.error(f"Failed to get usage trends: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get usage trends: {str(e)}")


# Activity Endpoints
@router.get("/activity/logs")
async def get_usage_logs(
    user_id: Optional[str] = None,
    endpoint: Optional[str] = None,
    date_from: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000),
    admin: Dict[str, Any] = Depends(require_admin)
):
    """
    Get usage logs with filters.
    Requires admin role.
    """
    try:
        service = get_admin_service()
        logs = await service.get_usage_logs(
            user_id=user_id,
            endpoint=endpoint,
            date_from=date_from,
            limit=limit
        )
        
        return {
            "success": True,
            "data": logs,
            "count": len(logs)
        }
    except Exception as e:
        logger.error(f"Failed to get usage logs: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get usage logs: {str(e)}")


@router.get("/activity/sessions")
async def get_session_activity(
    user_id: Optional[str] = None,
    limit: int = Query(50, ge=1, le=500),
    admin: Dict[str, Any] = Depends(require_admin)
):
    """
    Get recent session activity.
    Requires admin role.
    """
    try:
        service = get_admin_service()
        sessions = await service.get_session_activity(user_id=user_id, limit=limit)
        
        return {
            "success": True,
            "data": sessions,
            "count": len(sessions)
        }
    except Exception as e:
        logger.error(f"Failed to get session activity: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get session activity: {str(e)}")


@router.get("/health")
async def admin_health(admin: Dict[str, Any] = Depends(require_admin)):
    """Health check for admin service."""
    return {
        "status": "healthy",
        "service": "admin",
        "admin_user": admin.get("user_id")[:8] + "..."
    }








