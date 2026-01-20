"""
Research Intelligence API Router

Endpoint: POST /api/research/intelligence

Full LLM-based research intelligence using pubmearch + pubmed_parser + MOAT.
Includes query persistence, dossier generation, and value synthesis.
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from typing import Dict, List, Optional, Any
import logging
import uuid
from datetime import datetime

from api.services.research_intelligence.orchestrator import ResearchIntelligenceOrchestrator
from api.services.research_intelligence.dossier_generator import ResearchIntelligenceDossierGenerator
from api.services.research_intelligence.value_synthesizer import ValueSynthesizer
from api.services.research_intelligence.db_helper import (
    save_query_with_fallback,
    save_dossier_with_fallback,
    update_query_dossier_id
)
from api.middleware.auth_middleware import get_optional_user

# Try to import get_supabase_client from agent_manager, fallback to patient_service
try:
    from api.services.agent_manager import get_supabase_client
except ImportError:
    # Fallback to patient_service if agent_manager doesn't exist
    try:
        from api.services.patient_service import get_supabase_client
    except ImportError:
        # If neither exists, create a stub
        def get_supabase_client():
            logger.warning("⚠️ get_supabase_client not available - database operations will fail")
            return None

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/research", tags=["Research Intelligence"])


class ResearchIntelligenceRequest(BaseModel):
    """Request for research intelligence."""
    question: str
    context: Dict[str, Any]  # disease, treatment_line, biomarkers
    portals: Optional[List[str]] = ["pubmed"]  # Which portals to query
    synthesize: bool = True
    run_moat_analysis: bool = True
    persona: Optional[str] = "patient"  # NEW: persona selector


@router.post("/intelligence")
async def research_intelligence(
    request: ResearchIntelligenceRequest,
    user: Optional[Dict[str, Any]] = Depends(get_optional_user)
):
    """
    Research intelligence endpoint with auto-save and dossier generation.
    
    Uses pubmearch + pubmed_parser + LLM + MOAT to answer research questions.
    Automatically saves queries and generates dossiers for authenticated users.
    
    Example Request:
    ```json
    {
        "question": "How do purple potatoes help with ovarian cancer?",
        "context": {
            "disease": "ovarian_cancer_hgs",
            "treatment_line": "L2",
            "biomarkers": {"HRD": "POSITIVE"}
        },
        "persona": "patient"
    }
    ```
    
    Example Response:
    ```json
    {
        "research_plan": {...},
        "portal_results": {...},
        "parsed_content": {...},
        "synthesized_findings": {...},
        "moat_analysis": {...},
        "query_id": "uuid",
        "dossier": {
            "id": "uuid",
            "markdown": "...",
            "persona": "patient"
        },
        "value_synthesis": {
            "executive_summary": "...",
            "action_items": [...]
        }
    }
    ```
    """
    try:
        orchestrator = ResearchIntelligenceOrchestrator()
        
        result = await orchestrator.research_question(
            question=request.question,
            context=request.context
        )
        
        # NEW: Auto-save query to database
        query_id = None
        dossier_id = None
        dossier_markdown = None
        dossier_persona = request.persona or "patient"
        value_synthesis = None
        
        if user and user.get("user_id"):
            try:
                # Save query using direct PostgreSQL (bypasses PostgREST cache)
                query_data = {
                    "user_id": user["user_id"],
                    "question": request.question,
                    "context": request.context,
                    "options": {
                        "portals": request.portals,
                        "synthesize": request.synthesize,
                        "run_moat_analysis": request.run_moat_analysis,
                        "persona": request.persona or "patient"
                    },
                    "result": result,
                    "provenance": result.get("provenance"),
                    "persona": request.persona or "patient"
                }
                
                query_id = save_query_with_fallback(query_data)
                
                if query_id:
                    logger.info(f"✅ Saved query {query_id} for user {user['user_id']}")
                    
                    # Generate and save dossier
                    dossier_generator = ResearchIntelligenceDossierGenerator()
                    dossier = await dossier_generator.generate_dossier(
                        query_result=result,
                        persona=request.persona or "patient",
                        query_id=query_id
                    )
                    
                    dossier_markdown = dossier.get("markdown")
                    dossier_persona = dossier.get("persona", request.persona or "patient")
                    
                    # Save dossier using direct PostgreSQL
                    dossier_data = {
                        "query_id": query_id,
                        "user_id": user["user_id"],
                        "persona": dossier_persona,
                        "markdown": dossier_markdown
                    }
                    
                    dossier_id = save_dossier_with_fallback(dossier_data)
                    
                    if dossier_id:
                        # Update query with dossier_id
                        update_query_dossier_id(query_id, dossier_id)
                        logger.info(f"✅ Saved dossier {dossier_id} for query {query_id}")
                    
                    # Generate value synthesis
                    synthesizer = ValueSynthesizer()
                    value_synthesis = await synthesizer.synthesize_insights(
                        query_result=result,
                        persona=request.persona or "patient"
                    )
                else:
                    logger.warning("⚠️ Failed to save query (database unavailable)")
            except Exception as e:
                logger.warning(f"⚠️ Failed to save query/dossier (non-blocking): {e}", exc_info=True)
        
        return {
            **result,
            "query_id": query_id,  # NEW
            "dossier": {
                "id": dossier_id,
                "markdown": dossier_markdown,
                "persona": dossier_persona
            } if dossier_id else None,  # NEW
            "value_synthesis": value_synthesis  # NEW
        }
    
    except Exception as e:
        logger.error(f"Research intelligence failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/intelligence/history")
async def get_query_history(
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    persona: Optional[str] = Query(None),
    user: Optional[Dict[str, Any]] = Depends(get_optional_user)
):
    """Get user's query history."""
    if not user or not user.get("user_id"):
        raise HTTPException(401, "Authentication required")
    
    try:
        supabase = get_supabase_client()
        if not supabase:
            raise HTTPException(503, "Database service unavailable")
        
        query = supabase.table("research_intelligence_queries")\
            .select("id, question, context, persona, created_at, dossier_id")\
            .eq("user_id", user["user_id"])\
            .order("created_at", desc=True)\
            .range(offset, offset + limit - 1)
        
        if persona:
            query = query.eq("persona", persona)
        
        response = query.execute()
        
        return {
            "queries": response.data or [],
            "count": len(response.data or []),
            "limit": limit,
            "offset": offset
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get query history: {e}", exc_info=True)
        raise HTTPException(500, str(e))


@router.get("/intelligence/query/{query_id}")
async def get_query_by_id(
    query_id: str,
    user: Optional[Dict[str, Any]] = Depends(get_optional_user)
):
    """Get specific query by ID."""
    if not user or not user.get("user_id"):
        raise HTTPException(401, "Authentication required")
    
    try:
        supabase = get_supabase_client()
        if not supabase:
            raise HTTPException(503, "Database service unavailable")
        
        response = supabase.table("research_intelligence_queries")\
            .select("*")\
            .eq("id", query_id)\
            .eq("user_id", user["user_id"])\
            .single()\
            .execute()
        
        if not response.data:
            raise HTTPException(404, "Query not found")
        
        # Update last_accessed_at
        supabase.table("research_intelligence_queries")\
            .update({"last_accessed_at": datetime.utcnow().isoformat()})\
            .eq("id", query_id)\
            .execute()
        
        return response.data
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get query: {e}", exc_info=True)
        raise HTTPException(500, str(e))


@router.get("/intelligence/dossier/{dossier_id}")
async def get_dossier_by_id(
    dossier_id: str,
    user: Optional[Dict[str, Any]] = Depends(get_optional_user)
):
    """Get dossier by ID."""
    if not user or not user.get("user_id"):
        raise HTTPException(401, "Authentication required")
    
    try:
        supabase = get_supabase_client()
        if not supabase:
            raise HTTPException(503, "Database service unavailable")
        
        response = supabase.table("research_intelligence_dossiers")\
            .select("*")\
            .eq("id", dossier_id)\
            .eq("user_id", user["user_id"])\
            .single()\
            .execute()
        
        if not response.data:
            raise HTTPException(404, "Dossier not found")
        
        return response.data
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get dossier: {e}", exc_info=True)
        raise HTTPException(500, str(e))










