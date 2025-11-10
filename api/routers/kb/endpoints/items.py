"""
KB Items Endpoints
Handles listing and retrieving individual KB items
"""
from fastapi import APIRouter, HTTPException, Query, Header, Depends
from fastapi.responses import JSONResponse
from typing import Optional
import uuid
import logging

from ....services.kb_store import get_kb_store
from ..utils.rate_limiter import get_rate_limiter
from ..utils.client_extractor import get_client_ip

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/items", tags=["kb-items"])

@router.get("")
async def list_items(
    type: str = Query(..., description="Item type (gene, variant, pathway, drug, disease, evidence, policy, cohort)"),
    limit: int = Query(50, ge=1, le=100, description="Number of items to return"),
    offset: int = Query(0, ge=0, description="Number of items to skip"),
    client_ip: str = Depends(get_client_ip)
):
    """List items of a specific type with pagination"""
    
    # Rate limiting
    rate_limiter = get_rate_limiter()
    if not rate_limiter.check_rate_limit(client_ip):
        raise HTTPException(
            status_code=429, 
            detail="Rate limit exceeded",
            headers={"Retry-After": "60"}
        )
    
    # Generate run ID
    run_id = str(uuid.uuid4())
    
    try:
        kb_store = get_kb_store()
        items = kb_store.list_items(type, limit, offset)
        
        response = JSONResponse(
            content=items,
            headers={
                "x-run-id": run_id,
                "cache-control": "public, max-age=300",
                "x-rate-remaining": str(rate_limiter.get_remaining_requests(client_ip))
            }
        )
        
        logger.info(f"KB list_items: type={type}, limit={limit}, offset={offset}, count={len(items)}, run_id={run_id}")
        return response
        
    except Exception as e:
        logger.error(f"KB list_items error: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/{item_id}")
async def get_item(
    item_id: str,
    if_none_match: Optional[str] = Header(None),
    client_ip: str = Depends(get_client_ip)
):
    """Get a single item by ID"""
    
    # Rate limiting
    rate_limiter = get_rate_limiter()
    if not rate_limiter.check_rate_limit(client_ip):
        raise HTTPException(
            status_code=429, 
            detail="Rate limit exceeded",
            headers={"Retry-After": "60"}
        )
    
    # Generate run ID
    run_id = str(uuid.uuid4())
    
    try:
        kb_store = get_kb_store()
        
        # Check ETag for caching
        etag = kb_store.get_etag(item_id)
        if if_none_match and etag and if_none_match == etag:
            return JSONResponse(
                status_code=304,
                headers={
                    "x-run-id": run_id,
                    "etag": etag
                }
            )
        
        item = kb_store.get_item(item_id)
        if not item:
            raise HTTPException(status_code=404, detail=f"Item not found: {item_id}")
        
        response = JSONResponse(
            content=item,
            headers={
                "x-run-id": run_id,
                "etag": etag or "",
                "cache-control": "public, max-age=300",
                "x-rate-remaining": str(rate_limiter.get_remaining_requests(client_ip))
            }
        )
        
        logger.info(f"KB get_item: item_id={item_id}, run_id={run_id}")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"KB get_item error: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
