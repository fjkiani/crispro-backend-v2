"""
Data Subject Request (DSR) Router

Purpose: Handle GDPR Data Subject Requests (right to access, right to deletion).

Endpoints:
- POST /api/dsr/export - Export all user data
- POST /api/dsr/delete - Delete all user data
- GET /api/dsr/portable - Export data in machine-readable format
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse, FileResponse
from typing import Dict, Any, Optional
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# Optional import - dsr_service may not exist yet
try:
    from ..services.dsr_service import get_dsr_service, DSRType
except ImportError:
    get_dsr_service = None
    DSRType = None
    logger.warning("⚠️ dsr_service not available - DSR endpoints will return 501")
from ..middleware.auth_middleware import get_current_user
from ..middleware.mfa_middleware import require_mfa_for_phi_access
from fastapi.security import HTTPBearer

router = APIRouter(prefix="/api/dsr", tags=["dsr"])
security = HTTPBearer()


@router.post("/export")
async def export_user_data(
    format: str = "json",
    credentials: HTTPBearer = Depends(security)
) -> Dict[str, Any]:
    """
    Export all user data for GDPR access request.
    
    Requires: Authenticated user
    Returns: All user data organized by table
    """
    # Require MFA for PHI access
    user = await require_mfa_for_phi_access(credentials)
    user_id = user.get("user_id") or user.get("id")
    
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User ID not found in token"
        )
    
    # Export user data
    if not get_dsr_service:
        raise HTTPException(status_code=501, detail="DSR service not available")
    dsr_service = get_dsr_service()
    export_data = dsr_service.export_user_data(user_id, format=format)
    
    return export_data


@router.post("/delete")
async def delete_user_data(
    preserve_audit: bool = True,
    credentials: HTTPBearer = Depends(security)
) -> Dict[str, Any]:
    """
    Delete all user data for GDPR deletion request.
    
    Requires: Authenticated user, MFA verification
    Returns: Deletion statistics
    
    Note: This action is irreversible. Audit logs may be preserved.
    """
    # Require MFA for PHI access
    user = await require_mfa_for_phi_access(credentials)
    user_id = user.get("user_id") or user.get("id")
    
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User ID not found in token"
        )
    
    # Validate request
    if not get_dsr_service or not DSRType:
        raise HTTPException(status_code=501, detail="DSR service not available")
    dsr_service = get_dsr_service()
    validation = dsr_service.validate_dsr_request(user_id, DSRType.DELETION)
    
    if not validation["valid"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=validation["message"]
        )
    
    # Delete user data
    deletion_stats = dsr_service.delete_user_data(user_id, preserve_audit=preserve_audit)
    
    return deletion_stats


@router.get("/portable")
async def export_portable_data(
    credentials: HTTPBearer = Depends(security)
) -> JSONResponse:
    """
    Export user data in machine-readable format (JSON) for GDPR portability.
    
    Requires: Authenticated user, MFA verification
    Returns: JSON file with all user data
    """
    # Require MFA for PHI access
    user = await require_mfa_for_phi_access(credentials)
    user_id = user.get("user_id") or user.get("id")
    
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User ID not found in token"
        )
    
    # Export portable data
    if not get_dsr_service:
        raise HTTPException(status_code=501, detail="DSR service not available")
    dsr_service = get_dsr_service()
    json_data = dsr_service.export_portable_data(user_id)
    
    # Return as JSON response with download headers
    return JSONResponse(
        content=json.loads(json_data),
        headers={
            "Content-Disposition": f'attachment; filename="user_data_{user_id}_{datetime.now().strftime("%Y%m%d")}.json"'
        }
    )
