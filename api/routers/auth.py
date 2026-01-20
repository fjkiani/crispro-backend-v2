"""
Authentication Router
Endpoints for user signup, login, logout, and profile management.
"""
from fastapi import APIRouter, HTTPException, Depends, Body
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, Dict, Any
import logging

from api.services.auth_service import AuthService
from api.middleware.auth_middleware import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(tags=["auth"])

# Initialize auth service
_auth_service: Optional[AuthService] = None

def get_auth_service() -> AuthService:
    """Get auth service singleton."""
    global _auth_service
    if _auth_service is None:
        _auth_service = AuthService()
    return _auth_service


# Pydantic models
class SignupRequest(BaseModel):
    """Signup request model."""
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=8, description="User password (min 8 characters)")
    full_name: Optional[str] = Field(None, description="User full name")
    institution: Optional[str] = Field(None, description="User institution")
    role: Optional[str] = Field("researcher", description="User role (researcher/clinician/admin/patient)")


class LoginRequest(BaseModel):
    """Login request model."""
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., description="User password")


class ProfileUpdateRequest(BaseModel):
    """Profile update request model."""
    full_name: Optional[str] = None
    institution: Optional[str] = None
    role: Optional[str] = None
    bio: Optional[str] = None
    country: Optional[str] = None
    timezone: Optional[str] = None


# Auth endpoints
@router.post("/api/auth/signup")
async def signup(request: SignupRequest):
    """
    Sign up a new user.
    
    Creates user account via Supabase Auth and user profile in database.
    Returns JWT token for immediate login.
    """
    try:
        auth_service = get_auth_service()
        
        metadata = {
            "full_name": request.full_name,
            "institution": request.institution,
            "role": request.role,
        }
        
        result = await auth_service.signup(
            email=request.email,
            password=request.password,
            metadata=metadata
        )
        
        # If role is "patient", create empty patient profile
        if request.role == "patient" and result.get("user_id"):
            try:
                from ..services.patient_service import get_patient_service
                patient_service = get_patient_service()
                await patient_service.create_patient_profile(
                    result["user_id"],
                    {
                        "disease": "ovarian_cancer_hgs",  # Default, can be updated in onboarding
                        "treatment_line": 0
                    }
                )
                logger.info(f"✅ Created patient profile for user {result['user_id']}")
            except Exception as e:
                logger.warning(f"Failed to create patient profile: {e}")
                # Don't fail signup if profile creation fails
        
        return {
            "success": True,
            "message": "Account created successfully. Please check your email for confirmation.",
            "data": {
                "user_id": result["user_id"],
                "email": result["email"],
                "session": result["session"],
                "email_confirmed": result["email_confirmed"]
            }
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Signup error: {e}")
        raise HTTPException(status_code=500, detail=f"Signup failed: {str(e)}")


@router.post("/api/auth/login")
async def login(request: LoginRequest):
    """
    Log in user.
    
    Authenticates user via Supabase Auth and returns JWT token.
    """
    try:
        auth_service = get_auth_service()
        
        result = await auth_service.login(
            email=request.email,
            password=request.password
        )
        
        return {
            "success": True,
            "message": "Login successful",
            "data": {
                "user_id": result["user_id"],
                "email": result["email"],
                "session": result["session"],
                "profile": result["profile"]
            }
        }
        
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(status_code=500, detail=f"Login failed: {str(e)}")


@router.post("/api/auth/logout")
async def logout(user: Dict[str, Any] = Depends(get_current_user)):
    """
    Log out user.
    
    Revokes current session. Requires authentication.
    """
    try:
        auth_service = get_auth_service()
        
        # Note: Frontend should handle token removal
        # Backend logout is handled by Supabase Auth client-side
        return {
            "success": True,
            "message": "Logout successful"
        }
        
    except Exception as e:
        logger.error(f"Logout error: {e}")
        raise HTTPException(status_code=500, detail=f"Logout failed: {str(e)}")


@router.get("/api/auth/profile")
async def get_profile(user: Dict[str, Any] = Depends(get_current_user)):
    """
    Get current user profile.
    
    Requires authentication.
    """
    try:
        auth_service = get_auth_service()
        user_id = user["user_id"]
        
        profile = await auth_service.get_user_profile(user_id)
        
        if not profile:
            # Profile might not exist yet (created by trigger)
            # Return basic info from token
            return {
                "success": True,
                "data": {
                    "user_id": user_id,
                    "email": user.get("email"),
                    "tier": "free",
                    "role": "researcher"
                }
            }
        
        return {
            "success": True,
            "data": profile
        }
        
    except Exception as e:
        logger.error(f"Get profile error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get profile: {str(e)}")


@router.put("/api/auth/profile")
async def update_profile(
    request: ProfileUpdateRequest,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Update user profile.
    
    Requires authentication.
    """
    try:
        auth_service = get_auth_service()
        user_id = user["user_id"]
        
        updates = request.dict(exclude_unset=True)
        
        success = await auth_service.update_user_profile(user_id, updates)
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update profile")
        
        # Get updated profile
        profile = await auth_service.get_user_profile(user_id)
        
        return {
            "success": True,
            "message": "Profile updated successfully",
            "data": profile
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update profile error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update profile: {str(e)}")


@router.post("/api/auth/refresh")
async def refresh_token(
    refresh_token: str = Body(..., embed=True),
    user: Optional[Dict[str, Any]] = Depends(get_current_user)
):
    """
    Refresh access token.
    
    Uses refresh token to get new access token.
    Note: Frontend typically handles this via Supabase client.
    """
    try:
        auth_service = get_auth_service()
        
        if not auth_service.supabase:
            raise HTTPException(status_code=500, detail="Auth service not configured")
        
        # Refresh session via Supabase
        response = auth_service.supabase.auth.refresh_session(refresh_token)
        
        return {
            "success": True,
            "data": {
                "access_token": response.session.access_token,
                "refresh_token": response.session.refresh_token,
                "expires_at": response.session.expires_at,
            }
        }
        
    except Exception as e:
        logger.error(f"Refresh token error: {e}")
        raise HTTPException(status_code=401, detail=f"Token refresh failed: {str(e)}")


@router.get("/api/auth/health")
async def auth_health():
    """Health check for auth service."""
    auth_service = get_auth_service()
    
    return {
        "status": "healthy" if auth_service.supabase else "degraded",
        "service": "auth",
        "supabase_configured": auth_service.supabase is not None
    }









# MFA endpoints
from ..services.mfa_service import get_mfa_service


class MFAVerifyRequest(BaseModel):
    """MFA verification request model."""
    code: str = Field(..., min_length=6, max_length=6, description="6-digit TOTP code")


class MFADisableRequest(BaseModel):
    """MFA disable request model."""
    code: Optional[str] = Field(None, description="MFA code to confirm disable (optional)")


@router.post("/api/auth/mfa/generate-secret")
async def generate_mfa_secret(user: Dict[str, Any] = Depends(get_current_user)):
    """
    Generate MFA secret and QR code for enrollment.
    
    Requires: Authenticated user
    Returns: Secret, QR code URL, and backup codes
    """
    try:
        mfa_service = get_mfa_service()
        user_id = user["user_id"]
        user_email = user.get("email", "")
        
        result = mfa_service.generate_mfa_secret(user_id, user_email)
        
        return {
            "success": True,
            "data": {
                "secret": result["secret"],
                "qr_code_url": result["qr_code_url"],
                "backup_codes": result["backup_codes"],
                "provisioning_uri": result["provisioning_uri"]
            }
        }
    except Exception as e:
        logger.error(f"Generate MFA secret error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate MFA secret: {str(e)}")


@router.post("/api/auth/mfa/verify-enrollment")
async def verify_mfa_enrollment(
    request: MFAVerifyRequest,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Verify MFA code during enrollment and enable MFA.
    
    Requires: Authenticated user
    Returns: Success status
    """
    try:
        mfa_service = get_mfa_service()
        user_id = user["user_id"]
        
        result = await mfa_service.enable_mfa(user_id, request.code)
        
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])
        
        return {
            "success": True,
            "message": result["message"]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Verify MFA enrollment error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to verify MFA enrollment: {str(e)}")


@router.post("/api/auth/mfa/verify")
async def verify_mfa_code(
    request: MFAVerifyRequest,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Verify MFA code for login or session verification.
    
    Requires: Authenticated user
    Returns: Success status
    """
    try:
        mfa_service = get_mfa_service()
        user_id = user["user_id"]
        
        is_valid = mfa_service.verify_mfa_code(user_id, request.code)
        
        if not is_valid:
            raise HTTPException(status_code=401, detail="Invalid MFA code")
        
        return {
            "success": True,
            "message": "MFA code verified successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Verify MFA code error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to verify MFA code: {str(e)}")


@router.post("/api/auth/mfa/disable")
async def disable_mfa(
    request: Optional[MFADisableRequest] = None,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Disable MFA for the current user.
    
    Requires: Authenticated user
    Optional: MFA code to confirm disable
    Returns: Success status
    """
    try:
        mfa_service = get_mfa_service()
        user_id = user["user_id"]
        
        # If code provided, verify it first
        if request and request.code:
            is_valid = mfa_service.verify_mfa_code(user_id, request.code)
            if not is_valid:
                raise HTTPException(status_code=401, detail="Invalid MFA code")
        
        result = await mfa_service.disable_mfa(user_id)
        
        if not result["success"]:
            raise HTTPException(status_code=500, detail=result["message"])
        
        return {
            "success": True,
            "message": result["message"]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Disable MFA error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to disable MFA: {str(e)}")


@router.get("/api/auth/mfa/status")
async def get_mfa_status(user: Dict[str, Any] = Depends(get_current_user)):
    """
    Get MFA status for the current user.
    
    Requires: Authenticated user
    Returns: MFA enabled status and verification recency
    """
    try:
        mfa_service = get_mfa_service()
        user_id = user["user_id"]
        
        mfa_enabled = mfa_service.is_mfa_enabled(user_id)
        mfa_verified_recently = mfa_service.is_mfa_verified_recently(user_id) if mfa_enabled else False
        
        return {
            "success": True,
            "data": {
                "mfa_enabled": mfa_enabled,
                "mfa_verified_recently": mfa_verified_recently
            }
        }
    except Exception as e:
        logger.error(f"Get MFA status error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get MFA status: {str(e)}")

# MFA endpoints
from ..services.mfa_service import get_mfa_service


class MFAVerifyRequest(BaseModel):
    """MFA verification request model."""
    code: str = Field(..., min_length=6, max_length=6, description="6-digit TOTP code")


class MFADisableRequest(BaseModel):
    """MFA disable request model."""
    code: Optional[str] = Field(None, description="MFA code to confirm disable (optional)")


@router.post("/api/auth/mfa/generate-secret")
async def generate_mfa_secret(user: Dict[str, Any] = Depends(get_current_user)):
    """
    Generate MFA secret and QR code for enrollment.
    
    Requires: Authenticated user
    Returns: Secret, QR code URL, and backup codes
    """
    try:
        mfa_service = get_mfa_service()
        user_id = user["user_id"]
        user_email = user.get("email", "")
        
        result = mfa_service.generate_mfa_secret(user_id, user_email)
        
        return {
            "success": True,
            "data": {
                "secret": result["secret"],
                "qr_code_url": result["qr_code_url"],
                "backup_codes": result["backup_codes"],
                "provisioning_uri": result["provisioning_uri"]
            }
        }
    except Exception as e:
        logger.error(f"Generate MFA secret error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate MFA secret: {str(e)}")


@router.post("/api/auth/mfa/verify-enrollment")
async def verify_mfa_enrollment(
    request: MFAVerifyRequest,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Verify MFA code during enrollment and enable MFA.
    
    Requires: Authenticated user
    Returns: Success status
    """
    try:
        mfa_service = get_mfa_service()
        user_id = user["user_id"]
        
        result = await mfa_service.enable_mfa(user_id, request.code)
        
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])
        
        return {
            "success": True,
            "message": result["message"]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Verify MFA enrollment error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to verify MFA enrollment: {str(e)}")


@router.post("/api/auth/mfa/verify")
async def verify_mfa_code(
    request: MFAVerifyRequest,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Verify MFA code for login or session verification.
    
    Requires: Authenticated user
    Returns: Success status
    """
    try:
        mfa_service = get_mfa_service()
        user_id = user["user_id"]
        
        is_valid = mfa_service.verify_mfa_code(user_id, request.code)
        
        if not is_valid:
            raise HTTPException(status_code=401, detail="Invalid MFA code")
        
        return {
            "success": True,
            "message": "MFA code verified successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Verify MFA code error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to verify MFA code: {str(e)}")


@router.post("/api/auth/mfa/disable")
async def disable_mfa(
    request: Optional[MFADisableRequest] = None,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Disable MFA for the current user.
    
    Requires: Authenticated user
    Optional: MFA code to confirm disable
    Returns: Success status
    """
    try:
        mfa_service = get_mfa_service()
        user_id = user["user_id"]
        
        # If code provided, verify it first
        if request and request.code:
            is_valid = mfa_service.verify_mfa_code(user_id, request.code)
            if not is_valid:
                raise HTTPException(status_code=401, detail="Invalid MFA code")
        
        result = await mfa_service.disable_mfa(user_id)
        
        if not result["success"]:
            raise HTTPException(status_code=500, detail=result["message"])
        
        return {
            "success": True,
            "message": result["message"]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Disable MFA error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to disable MFA: {str(e)}")


@router.get("/api/auth/mfa/status")
async def get_mfa_status(user: Dict[str, Any] = Depends(get_current_user)):
    """
    Get MFA status for the current user.
    
    Requires: Authenticated user
    Returns: MFA enabled status and verification recency
    """
    try:
        mfa_service = get_mfa_service()
        user_id = user["user_id"]
        
        mfa_enabled = mfa_service.is_mfa_enabled(user_id)
        mfa_verified_recently = mfa_service.is_mfa_verified_recently(user_id) if mfa_enabled else False
        
        return {
            "success": True,
            "data": {
                "mfa_enabled": mfa_enabled,
                "mfa_verified_recently": mfa_verified_recently
            }
        }
    except Exception as e:
        logger.error(f"Get MFA status error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get MFA status: {str(e)}")
