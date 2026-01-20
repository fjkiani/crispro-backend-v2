"""
Feature Flag Middleware
Enforces tier-based feature access.
"""
from fastapi import HTTPException, Depends
from typing import Dict, Any, Optional
import logging
from ..middleware.auth_middleware import get_current_user, get_optional_user
from ..services.feature_flag_service import FeatureFlagService

logger = logging.getLogger(__name__)

# Global feature flag service instance
_feature_flag_service: Optional[FeatureFlagService] = None


def get_feature_flag_service() -> FeatureFlagService:
    """Get feature flag service singleton."""
    global _feature_flag_service
    if _feature_flag_service is None:
        _feature_flag_service = FeatureFlagService()
    return _feature_flag_service


def require_feature(feature_name: str):
    """
    Dependency to require a specific feature flag.
    
    Usage:
        @router.post("/api/premium-endpoint", dependencies=[Depends(require_feature("sae_features"))])
    
    Args:
        feature_name: Feature name to require (e.g., "sae_features", "cohort_lab")
    
    Returns:
        User dict if feature available
    
    Raises:
        HTTPException 403 if feature not available
    """
    async def _require_feature(
        user: Optional[Dict[str, Any]] = Depends(get_optional_user)
    ) -> Dict[str, Any]:
        # Allow anonymous users (no feature check)
        if not user:
            return {}
        
        feature_service = get_feature_flag_service()
        user_id = user.get("user_id")
        
        if not user_id:
            return user
        
        has_feature = await feature_service.has_feature(user_id, feature_name)
        
        if not has_feature:
            # Get user tier for better error message
            from ..services.supabase_service import supabase
            if supabase.enabled:
                try:
                    profiles = await supabase.select("user_profiles", {"id": user_id}, limit=1)
                    tier = profiles[0].get("tier", "free") if profiles else "free"
                except Exception:
                    tier = "free"
            else:
                tier = "free"
            
            raise HTTPException(
                status_code=403,
                detail=f"Feature '{feature_name}' not available on your tier ({tier}). Upgrade to access this feature."
            )
        
        return user
    
    return _require_feature



































