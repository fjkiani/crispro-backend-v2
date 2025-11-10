"""
KB Search Endpoints
Handles search and vector search functionality
"""
from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.responses import JSONResponse
from typing import List, Optional, Dict, Any
import uuid
import logging
import os

from ....services.kb_store import get_kb_store
from ..utils.rate_limiter import get_rate_limiter
from ..utils.client_extractor import get_client_ip

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/search", tags=["kb-search"])

@router.get("")
async def search_items(
    q: str = Query(..., description="Search query"),
    types: Optional[str] = Query(None, description="Comma-separated list of types to search"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of results"),
    client_ip: str = Depends(get_client_ip)
):
    """Search across KB items using keyword matching"""
    
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
        
        # Parse types
        type_list = None
        if types:
            type_list = [t.strip() for t in types.split(",") if t.strip()]
        
        results = kb_store.search(q, type_list, limit)
        
        response = JSONResponse(
            content=results,
            headers={
                "x-run-id": run_id,
                "cache-control": "no-store",
                "x-rate-remaining": str(rate_limiter.get_remaining_requests(client_ip))
            }
        )
        
        logger.info(f"KB search: q={q}, types={type_list}, limit={limit}, hits={len(results.get('hits', []))}, run_id={run_id}")
        return response
        
    except Exception as e:
        logger.error(f"KB search error: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.post("/vector")
async def vector_search(
    request: Dict[str, Any],
    client_ip: str = Depends(get_client_ip)
):
    """Vector search using Redis (Phase 2 - optional)"""
    
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
        # Check if Redis is configured
        if not os.getenv("REDIS_URL"):
            return JSONResponse(
                status_code=503,
                content={
                    "error": "Vector search not available",
                    "message": "Redis not configured",
                    "retry_after": 300
                },
                headers={
                    "x-run-id": run_id,
                    "retry-after": "300"
                }
            )
        
        # TODO: Implement vector search when Redis is available
        # For now, return empty results
        results = {
            "query": request.get("query", ""),
            "results": [],
            "message": "Vector search not yet implemented"
        }
        
        response = JSONResponse(
            content=results,
            headers={
                "x-run-id": run_id,
                "cache-control": "no-store",
                "x-rate-remaining": str(rate_limiter.get_remaining_requests(client_ip))
            }
        )
        
        logger.info(f"KB vector_search: query={request.get('query', '')}, run_id={run_id}")
        return response
        
    except Exception as e:
        logger.error(f"KB vector_search error: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
