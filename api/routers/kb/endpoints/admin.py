"""
KB Admin Endpoints
Handles administrative functions like cache reload and stats
"""
from fastapi import APIRouter, HTTPException, Header, Depends
from fastapi.responses import JSONResponse
from typing import Optional
import uuid
import logging
import os

from ....services.kb_store import get_kb_store
from ..utils.rate_limiter import get_rate_limiter
from ..utils.client_extractor import get_client_ip

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["kb-admin"])

@router.get("/stats")
async def get_stats():
    """Get KB statistics"""
    
    # Generate run ID
    run_id = str(uuid.uuid4())
    
    try:
        kb_store = get_kb_store()
        stats = kb_store.get_stats()
        
        # Add rate limiter stats
        rate_limiter = get_rate_limiter()
        stats["rate_limiter"] = rate_limiter.get_stats()
        
        response = JSONResponse(
            content=stats,
            headers={
                "x-run-id": run_id,
                "cache-control": "public, max-age=60"
            }
        )
        
        logger.info(f"KB get_stats: run_id={run_id}")
        return response
        
    except Exception as e:
        logger.error(f"KB get_stats error: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.post("/reload")
async def reload_cache(
    x_api_key: Optional[str] = Header(None),
    client_ip: str = Depends(get_client_ip)
):
    """Reload KB cache (admin only)"""
    
    # Check admin key
    admin_key = os.getenv("KB_ADMIN_KEY")
    if not admin_key or x_api_key != admin_key:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    # Generate run ID
    run_id = str(uuid.uuid4())
    
    try:
        kb_store = get_kb_store()
        result = kb_store.reload_cache()
        
        response = JSONResponse(
            content=result,
            headers={
                "x-run-id": run_id,
                "cache-control": "no-store"
            }
        )
        
        logger.info(f"KB reload_cache: run_id={run_id}")
        return response
        
    except Exception as e:
        logger.error(f"KB reload_cache error: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
