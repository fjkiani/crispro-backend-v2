"""
Patient Router - Handles patient profile and data management

Author: Zo
Date: January 2025
Updated: January 2025 - Added auto tumor context generation for sporadic gates
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import logging

logger = logging.getLogger(__name__)

# Import services for auto-generating tumor context
try:
    from ..services.tumor_quick_intake import generate_level0_tumor_context
    from ..services.input_completeness import compute_input_completeness
    TUMOR_SERVICES_AVAILABLE = True
except ImportError:
    logger.warning("Tumor quick intake services not available - auto-generation disabled")
    TUMOR_SERVICES_AVAILABLE = False

router = APIRouter(prefix="/api/patient", tags=["patient"])


class PatientProfile(BaseModel):
    """Patient profile schema"""
    user_id: str
    disease: str = "ovarian_cancer_hgs"
    stage: Optional[str] = None
    treatment_line: int = 0
    germline_status: Optional[str] = None
    biomarkers: Optional[Dict[str, Any]] = None
    tumor_context: Optional[Dict[str, Any]] = None
    ca125_value: Optional[float] = None
    location_state: Optional[str] = None


class PatientProfileUpdate(BaseModel):
    """Patient profile update schema"""
    disease: Optional[str] = None
    stage: Optional[str] = None
    treatment_line: Optional[int] = None
    germline_status: Optional[str] = None
    biomarkers: Optional[Dict[str, Any]] = None
    tumor_context: Optional[Dict[str, Any]] = None
    ca125_value: Optional[float] = None
    location_state: Optional[str] = None
    location_city: Optional[str] = None
    full_name: Optional[str] = None
    # Optional biomarkers for Quick Intake (L0/L1 support)
    tmb: Optional[float] = None  # Tumor mutational burden
    msi_status: Optional[str] = None  # MSI-H / MSS
    hrd_score: Optional[float] = None  # HRD score (0-100)
    platinum_response: Optional[str] = None  # sensitive/resistant/refractory (for ovarian/breast)
    somatic_mutations: Optional[List[Dict[str, Any]]] = None  # Partial mutation list


# In-memory storage for demo (in production, use database)
_patient_profiles: Dict[str, PatientProfile] = {}


@router.get("/profile/{user_id}")
async def get_patient_profile(user_id: str):
    """Get patient profile by user ID"""
    if user_id not in _patient_profiles:
        # Return default profile for new users
        return PatientProfile(user_id=user_id)
    return _patient_profiles[user_id]


async def _auto_generate_tumor_context_if_needed(update_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Auto-generate tumor context if missing using Quick Intake (L0/L1 support).
    
    This implements the sporadic gates strategy: use disease priors when NGS not available.
    """
    # Only auto-generate if tumor_context is not provided
    if update_data.get("tumor_context") is not None:
        return update_data
    
    # Need at least disease type to generate context
    disease = update_data.get("disease") or "ovarian_cancer_hgs"
    
    if not TUMOR_SERVICES_AVAILABLE:
        logger.warning("Tumor services not available - skipping auto-generation")
        return update_data
    
    try:
        # Map disease format (onboarding uses "ovarian_cancer_hgs", quick intake expects "ovarian_hgs")
        cancer_type_map = {
            "ovarian_cancer_hgs": "ovarian_hgs",
            "ovarian_cancer_lgs": "ovarian_hgs",  # Fallback
            "breast_cancer": "breast_tnbc",
        }
        cancer_type = cancer_type_map.get(disease, "ovarian_hgs")
        
        # Extract optional biomarkers from update_data
        tmb = update_data.pop("tmb", None)
        msi_status = update_data.pop("msi_status", None)
        hrd_score = update_data.pop("hrd_score", None)
        platinum_response = update_data.pop("platinum_response", None)
        somatic_mutations = update_data.pop("somatic_mutations", None)
        
        # Convert somatic_mutations to SomaticMutation objects if needed
        from ..schemas.tumor_context import SomaticMutation
        mutations = None
        if somatic_mutations:
            mutations = [
                SomaticMutation(**m) if isinstance(m, dict) else m
                for m in somatic_mutations
            ]
        
        # Generate tumor context using Quick Intake
        tumor_context, provenance, confidence_cap, recommendations = await generate_level0_tumor_context(
            cancer_type=cancer_type,
            stage=update_data.get("stage"),
            line=update_data.get("treatment_line", 0),
            platinum_response=platinum_response,
            manual_tmb=tmb,
            manual_msi=msi_status,
            manual_hrd=hrd_score,
            manual_mutations=mutations
        )
        
        # Compute completeness (L0/L1/L2)
        completeness = compute_input_completeness(
            tumor_context=tumor_context.model_dump() if hasattr(tumor_context, 'model_dump') else tumor_context,
            ca125_history=[]  # No history yet during onboarding
        )
        
        # Convert tumor_context to dict
        if hasattr(tumor_context, 'model_dump'):
            tumor_context_dict = tumor_context.model_dump()
        else:
            tumor_context_dict = tumor_context
        
        # Add completeness info to tumor_context
        tumor_context_dict["intake_level"] = completeness.level
        tumor_context_dict["confidence_cap"] = completeness.confidence_cap
        tumor_context_dict["completeness_score"] = getattr(tumor_context, 'completeness_score', None)
        
        # Store generated tumor context
        update_data["tumor_context"] = tumor_context_dict
        update_data["intake_level"] = completeness.level
        update_data["confidence_cap"] = completeness.confidence_cap
        
        logger.info(f"✅ Auto-generated tumor context: {completeness.level} intake (completeness: {completeness.confidence_cap})")
        
        # Store recommendations for response (not in profile, but return to frontend)
        update_data["_onboarding_recommendations"] = recommendations
        update_data["_tumor_context_provenance"] = provenance
        
    except Exception as e:
        logger.error(f"Failed to auto-generate tumor context: {e}", exc_info=True)
        # Don't fail profile creation if tumor context generation fails
        # User will get L0 classification by default
    
    return update_data


@router.put("/profile")
async def update_patient_profile_put(profile: PatientProfileUpdate):
    """
    PUT endpoint for profile updates (used by frontend onboarding).
    Creates or updates profile with auto tumor context generation.
    """
    # For demo: extract user_id from profile if available, or use default
    # In production, this would come from auth token via Depends(require_patient_role)
    user_id = "demo_user"  # TODO: Get from auth token in production
    
    return await create_patient_profile(user_id, profile)


@router.post("/profile/{user_id}")
async def create_patient_profile(user_id: str, profile: PatientProfileUpdate):
    """Create or update patient profile with auto tumor context generation"""
    existing = _patient_profiles.get(user_id, PatientProfile(user_id=user_id))
    
    # Update fields
    update_data = profile.model_dump(exclude_unset=True)
    
    # Auto-generate tumor context if missing (sporadic gates L0/L1 support)
    update_data = await _auto_generate_tumor_context_if_needed(update_data)
    
    # Extract metadata (not stored in profile model, but returned in response)
    recommendations = update_data.pop("_onboarding_recommendations", [])
    provenance = update_data.pop("_tumor_context_provenance", None)
    intake_level = update_data.pop("intake_level", None)
    confidence_cap = update_data.pop("confidence_cap", None)
    
    # Update profile fields (only fields that exist in PatientProfile model)
    valid_profile_fields = set(PatientProfile.model_fields.keys())
    for key, value in update_data.items():
        if key in valid_profile_fields and key not in ["_onboarding_recommendations", "_tumor_context_provenance"]:
            setattr(existing, key, value)
    
    _patient_profiles[user_id] = existing
    logger.info(f"✅ Updated patient profile for {user_id}")
    
    # Return response with intake level and recommendations
    response = {
        "success": True,
        "profile": existing.model_dump() if hasattr(existing, 'model_dump') else existing.__dict__,
        "intake_level": intake_level,
        "confidence_cap": confidence_cap,
        "recommendations": recommendations
    }
    
    return response


@router.delete("/profile/{user_id}")
async def delete_patient_profile(user_id: str):
    """Delete patient profile (GDPR compliance)"""
    if user_id in _patient_profiles:
        del _patient_profiles[user_id]
        logger.info(f"🗑️ Deleted patient profile for {user_id}")
        return {"success": True, "message": "Profile deleted"}
    return {"success": True, "message": "No profile found"}


@router.get("/ca125/history/{user_id}")
async def get_ca125_history(user_id: str):
    """Get CA-125 history for a patient"""
    # In production, fetch from database
    return {
        "user_id": user_id,
        "history": [],
        "message": "No CA-125 history available"
    }


@router.post("/ca125/record/{user_id}")
async def record_ca125(user_id: str, value: float, date: Optional[str] = None):
    """Record a new CA-125 measurement"""
    # In production, store in database
    logger.info(f"📊 Recorded CA-125 {value} for {user_id}")
    return {
        "success": True,
        "value": value,
        "date": date or "now"
    }

