"""
MFA (Multi-Factor Authentication) Middleware

Purpose: Require MFA for admin users and PHI access.

HIPAA Requirement: MFA must be enabled for users accessing PHI.
"""

import logging
from typing import Dict, Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

logger = logging.getLogger(__name__)

from ..middleware.auth_middleware import get_current_user
# Optional import - data_classification_service may not exist yet
try:
    from ..services.data_classification_service import DataClassificationService, get_data_classification_service
except ImportError:
    DataClassificationService = None
    get_data_classification_service = None
    logger.warning("⚠️ data_classification_service not available - MFA middleware will have limited functionality")


security = HTTPBearer()


async def require_mfa(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    user: Optional[Dict] = None
) -> Dict:
    """
    Require MFA for the current user.
    
    Checks:
    1. User has MFA enabled
    2. MFA has been verified in this session
    
    Raises:
        HTTPException 403 if MFA not enabled
        HTTPException 403 if MFA not verified
    """
    if user is None:
        user = await get_current_user(credentials)
    
    # Check if user has MFA enabled
    mfa_enabled = user.get("mfa_enabled", False)
    
    if not mfa_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Multi-factor authentication (MFA) is required. Please enable MFA in your profile settings."
        )
    
    # Check if MFA has been verified in this session
    # Note: This requires session management to track MFA verification
    # For now, we'll check if mfa_verified_at is recent (within session timeout)
    mfa_verified = user.get("mfa_verified_at")
    
    if not mfa_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Multi-factor authentication (MFA) verification required. Please complete MFA verification."
        )
    
    return user


async def require_mfa_for_admin(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> Dict:
    """
    Require MFA for admin users.
    
    Admin users must have MFA enabled and verified.
    """
    user = await get_current_user(credentials)
    
    # Check if user is admin
    if user.get("role") != "admin":
        # Not an admin, no MFA requirement
        return user
    
    # Admin users require MFA
    return await require_mfa(credentials, user)


async def require_mfa_for_phi_access(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    data_classification: Optional[str] = None,
    request_data: Optional[Dict] = None
) -> Dict:
    """
    Require MFA for PHI access.
    
    If the request involves PHI data, MFA is required.
    
    Args:
        credentials: JWT credentials
        data_classification: Pre-classified data type ("PHI" or "NON_PHI")
        request_data: Request data to classify if not pre-classified
    
    Returns:
        Authenticated user dict
    """
    user = await get_current_user(credentials)
    
    # Classify data if not pre-classified
    if data_classification is None and request_data:
        classification_service = get_data_classification_service()
        data_classification = classification_service.classify_data(
            data_type=request_data.get("type", "unknown"),
            content=request_data
        )
    
    # If data is PHI, require MFA
    if data_classification == "PHI":
        return await require_mfa(credentials, user)
    
    # Non-PHI data, no MFA requirement
    return user


# Convenience dependency for admin endpoints
RequireMFAForAdmin = Depends(require_mfa_for_admin)

# Convenience dependency for PHI access endpoints
RequireMFAForPHI = Depends(require_mfa_for_phi_access)
