"""
Quota Middleware
Enforces usage quotas for tier-based limits.
"""
from fastapi import HTTPException, Depends, Request
from typing import Dict, Any, Optional
import logging
from ..middleware.auth_middleware import get_current_user, get_optional_user
from ..services.quota_service import QuotaService

logger = logging.getLogger(__name__)

# Global quota service instance
_quota_service: Optional[QuotaService] = None


def get_quota_service() -> QuotaService:
    """Get quota service singleton."""
    global _quota_service
    if _quota_service is None:
        _quota_service = QuotaService()
    return _quota_service


def check_quota(quota_type: str):
    """
    Dependency to check and enforce usage quotas.
    
    Usage:
        @router.post("/api/variant-analysis", dependencies=[Depends(check_quota("variant_analyses"))])
    
    Args:
        quota_type: One of 'variant_analyses', 'drug_queries', 'food_queries', 'clinical_trials'
    
    Returns:
        User dict if quota available
    
    Raises:
        HTTPException 429 if quota exceeded
    """
    async def _check_quota(
        user: Optional[Dict[str, Any]] = Depends(get_optional_user)
    ) -> Dict[str, Any]:
        # Allow anonymous users (no quota check)
        if not user:
            return {}
        
        quota_service = get_quota_service()
        user_id = user.get("user_id")
        
        if not user_id:
            return user
        
        # Reset quotas if billing period ended
        await quota_service.reset_quotas_if_needed(user_id)
        
        # Check quota
        has_quota = await quota_service.check_quota(user_id, quota_type)
        
        if not has_quota:
            quotas = await quota_service.get_user_quotas(user_id)
            quota_info = quotas.get(quota_type, {})
            
            raise HTTPException(
                status_code=429,
                detail=f"Quota exceeded for {quota_type}. Upgrade your plan or wait for quota reset.",
                headers={
                    "X-Quota-Limit": str(quota_info.get("limit", 0)),
                    "X-Quota-Used": str(quota_info.get("used", 0)),
                    "X-Quota-Remaining": str(quota_info.get("remaining", 0)),
                    "X-Quota-Reset": quotas.get("period_end", "")
                }
            )
        
        # Increment usage (after successful check)
        await quota_service.increment_usage(user_id, quota_type)
        
        return user
    
    return _check_quota



































