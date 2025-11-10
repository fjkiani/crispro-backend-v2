"""
KB Validation Endpoints
Handles schema validation for KB items
"""
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
import uuid
import logging

from ....services.kb_store import get_kb_store
from ....services.kb_validator import get_kb_validator
from ..utils.rate_limiter import get_rate_limiter
from ..utils.client_extractor import get_client_ip

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/validate", tags=["kb-validation"])

@router.get("")
async def validate_kb():
    """Validate all KB items against their schemas"""
    
    # Generate run ID
    run_id = str(uuid.uuid4())
    
    try:
        validator = get_kb_validator()
        summary = validator.get_validation_summary()
        
        response = JSONResponse(
            content=summary,
            headers={
                "x-run-id": run_id,
                "cache-control": "no-store"
            }
        )
        
        logger.info(f"KB validate: run_id={run_id}, valid={summary['valid_files']}, invalid={summary['invalid_files']}")
        return response
        
    except Exception as e:
        logger.error(f"KB validate error: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/item/{item_id}")
async def validate_item(item_id: str):
    """Validate a specific item against its schema"""
    
    # Generate run ID
    run_id = str(uuid.uuid4())
    
    try:
        kb_store = get_kb_store()
        validator = get_kb_validator()
        
        # Get the item
        item = kb_store.get_item(item_id)
        if not item:
            raise HTTPException(status_code=404, detail=f"Item not found: {item_id}")
        
        # Determine item type
        item_type = item_id.split("/")[0] if "/" in item_id else "unknown"
        
        # Validate the item
        is_valid, errors = validator.validate_item(item, item_type)
        
        result = {
            "item_id": item_id,
            "item_type": item_type,
            "is_valid": is_valid,
            "errors": errors
        }
        
        response = JSONResponse(
            content=result,
            headers={
                "x-run-id": run_id,
                "cache-control": "no-store"
            }
        )
        
        logger.info(f"KB validate_item: item_id={item_id}, is_valid={is_valid}, run_id={run_id}")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"KB validate_item error: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
