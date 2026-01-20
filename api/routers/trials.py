"""
⚔️ CLINICAL TRIALS SEARCH & REFRESH ROUTER ⚔️

Endpoints for:
- /api/search-trials - Search trials using AstraDB vector search (self-contained)
- /api/trials/refresh_status - Refresh live trial status from ClinicalTrials.gov

Research Use Only - Not for Clinical Enrollment
"""

from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
import os
import logging

logger = logging.getLogger(__name__)

from api.services.clinical_trial_search_service import ClinicalTrialSearchService

router = APIRouter(tags=["trials"])

# Initialize search service (singleton pattern)
_search_service: Optional[ClinicalTrialSearchService] = None

def get_search_service() -> ClinicalTrialSearchService:
    """Get singleton search service instance."""
    global _search_service
    if _search_service is None:
        _search_service = ClinicalTrialSearchService()
    return _search_service


class TrialSearchRequest(BaseModel):
    """Request for clinical trial search"""
    query: str = Field(..., description="Search query text")
    patient_context: Optional[Dict[str, Any]] = Field(None, description="Optional patient context")
    page_state: Optional[str] = Field(None, description="Pagination state token")


class RefreshStatusRequest(BaseModel):
    """Request for refreshing trial status"""
    nct_ids: List[str] = Field(..., description="List of NCT IDs to refresh")
    state_filter: Optional[str] = Field(None, description="Optional state filter (e.g., 'NY', 'CA')")


@router.post("/api/search-trials")
async def search_trials(request: TrialSearchRequest):
    """
    Search clinical trials using AstraDB vector search (self-contained).
    
    **Research Use Only - Not for Clinical Enrollment**
    
    Uses ClinicalTrialSearchService for semantic search via Google embeddings + AstraDB.
    No dependency on main backend - fully self-contained in minimal backend.
    
    Returns:
        {
            "success": true,
            "data": {
                "found_trials": [...],
                "query": "...",
                "total_results": 10
            },
            "provenance": {...}
        }
    """
    try:
        service = get_search_service()
        
        # Extract disease category from patient_context if available
        disease_category = None
        if request.patient_context:
            disease_category = request.patient_context.get("disease_category")
        
        # Perform semantic search
        result = await service.search_trials(
            query=request.query,
            disease_category=disease_category,
            top_k=20,  # Return top 20 matches
            min_score=0.5  # Minimum similarity threshold
        )
        
        logger.info(f"✅ Search completed: {result.get('data', {}).get('total_results', 0)} results")
        return result
        
    except Exception as e:
        logger.error(f"❌ Search trials failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.post("/api/trials/refresh_status")
async def refresh_status(request: RefreshStatusRequest):
    """
    Refresh live trial status and locations from ClinicalTrials.gov API v2.
    
    Uses the existing trial refresh service to fetch current status and locations.
    
    **Research Use Only - Not for Clinical Enrollment**
    
    Returns:
        {
            "refreshed_count": 2,
            "trial_data": {
                "NCT12345": {
                    "status": "RECRUITING",
                    "locations": [...],
                    "last_updated": "2024-10-20T12:00:00Z"
                }
            }
        }
    """
    try:
        from api.services.trial_refresh import refresh_trial_status_with_retry
        from api.services.trial_refresh.filters import filter_locations_by_state
        
        if not request.nct_ids:
            raise HTTPException(status_code=400, detail="nct_ids cannot be empty")
        
        # Refresh trials using existing service
        refreshed_data = await refresh_trial_status_with_retry(request.nct_ids)
        
        # Apply state filter if requested
        if request.state_filter:
            refreshed_data = filter_locations_by_state(refreshed_data, request.state_filter)
        
        return {
            "refreshed_count": len(refreshed_data),
            "trial_data": refreshed_data
        }
        
    except ImportError as e:
        logger.error(f"Failed to import trial refresh service: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Trial refresh service not available")
    except Exception as e:
        logger.error(f"Error refreshing trial status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/trials/{nct_id}/details")
async def get_trial_details(nct_id: str):
    """
    Get full trial details from database.
    
    **Priority 2 from TRIAL_CONTEXT_AND_DETAILS_ANALYSIS.md**
    
    Returns all 16 fields from the clinical_trials table:
    - Basic info (nct_id, title, status, phase, source_url)
    - Text fields (description_text, eligibility_text, inclusion_criteria_text, 
                   exclusion_criteria_text, objectives_text, raw_markdown, ai_summary)
    - JSON fields (metadata_json, pis_json, orgs_json, sites_json)
    
    **Research Use Only - Not for Clinical Enrollment**
    
    Fast response (<100ms) - no LLM generation required.
    """
    try:
        service = get_search_service()
        trial = await service.get_trial_details(nct_id)
        
        if not trial:
            raise HTTPException(
                status_code=404, 
                detail=f"Trial {nct_id} not found in database"
            )
        
        logger.info(f"✅ Retrieved trial details for {nct_id}")
        return trial
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get trial details: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get trial details: {str(e)}")

