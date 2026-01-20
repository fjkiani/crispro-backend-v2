"""
Doctor Router - Handles doctor/clinician profile and data management

Author: Zo
Date: January 2025
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

from ..schemas.doctor_profile import (
    DoctorProfileCreate,
    DoctorProfileUpdate,
    DoctorProfileResponse
)

# TODO: Import auth middleware when available
# from ..middleware.auth_middleware import get_current_user
# from ..middleware.doctor_middleware import require_doctor_role

router = APIRouter(prefix="/api/doctor", tags=["doctor"])


# In-memory storage for demo (in production, use database)
_doctor_profiles: Dict[str, DoctorProfileResponse] = {}


@router.get("/profile/{user_id}")
async def get_doctor_profile(user_id: str):
    """Get doctor profile by user ID"""
    if user_id not in _doctor_profiles:
        # Return empty profile for new doctors
        return DoctorProfileResponse(user_id=user_id)
    return _doctor_profiles[user_id]


@router.put("/profile")
async def update_doctor_profile(profile: DoctorProfileUpdate):
    """
    PUT endpoint for profile updates (used by frontend onboarding).
    Creates or updates doctor profile.
    """
    # For demo: extract user_id from default or auth token
    # In production, this would come from auth token via Depends(require_doctor_role)
    user_id = "demo_doctor"  # TODO: Get from auth token in production
    
    return await create_doctor_profile(user_id, profile)


@router.post("/profile/{user_id}")
async def create_doctor_profile(user_id: str, profile: DoctorProfileUpdate):
    """Create or update doctor profile"""
    existing = _doctor_profiles.get(user_id)
    
    # Update fields
    update_data = profile.model_dump(exclude_unset=True)
    
    if existing:
        # Update existing profile
        for key, value in update_data.items():
            if hasattr(existing, key):
                setattr(existing, key, value)
        existing.updated_at = "now"  # TODO: Use actual timestamp
    else:
        # Create new profile
        from datetime import datetime
        new_profile_data = {
            "user_id": user_id,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            **update_data
        }
        existing = DoctorProfileResponse(**new_profile_data)
    
    _doctor_profiles[user_id] = existing
    logger.info(f"✅ Updated doctor profile for {user_id}")
    
    return {
        "success": True,
        "profile": existing.model_dump() if hasattr(existing, 'model_dump') else existing.__dict__
    }


@router.delete("/profile/{user_id}")
async def delete_doctor_profile(user_id: str):
    """Delete doctor profile"""
    if user_id in _doctor_profiles:
        del _doctor_profiles[user_id]
        logger.info(f"🗑️ Deleted doctor profile for {user_id}")
        return {"success": True, "message": "Profile deleted"}
    return {"success": True, "message": "No profile found"}
