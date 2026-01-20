"""
Patient Knowledge Base Router - MVP Implementation

API endpoints for patient knowledge base operations.

Research Use Only - Not for Clinical Decision Making
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, Optional
import logging

from api.services.patient_knowledge_base_agent import PatientKnowledgeBaseAgent
from api.services.patient_knowledge_base.storage import PatientKBStorage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/patient-kb", tags=["Patient Knowledge Base"])


@router.post("/{patient_id}/build")
async def build_patient_kb(
    patient_id: str,
    patient_profile: Dict[str, Any],
    max_queries: int = 10
) -> Dict[str, Any]:
    """
    Build knowledge base for a patient.
    
    Args:
        patient_id: Patient identifier
        patient_profile: Complete patient profile
        max_queries: Maximum number of research queries to execute (default: 10)
    
    Returns:
        Build statistics and results
    """
    try:
        agent = PatientKnowledgeBaseAgent(patient_id, patient_profile)
        result = await agent.build_knowledge_base(max_queries=max_queries)
        return result
    except Exception as e:
        logger.error(f"Failed to build KB for {patient_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to build knowledge base: {str(e)}"
        )


@router.get("/{patient_id}/stats")
async def get_patient_kb_stats(patient_id: str) -> Dict[str, Any]:
    """
    Get knowledge base statistics for a patient.
    
    Args:
        patient_id: Patient identifier
    
    Returns:
        KB statistics (papers, entities, edge cases, etc.)
    """
    try:
        storage = PatientKBStorage(patient_id)
        stats = storage.get_kb_stats()
        return stats
    except Exception as e:
        logger.error(f"Failed to get KB stats for {patient_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get KB statistics: {str(e)}"
        )


@router.post("/{patient_id}/query")
async def query_patient_kb(
    patient_id: str,
    query: str,
    patient_profile: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Query patient's knowledge base.
    
    Args:
        patient_id: Patient identifier
        query: Natural language query
        patient_profile: Complete patient profile
    
    Returns:
        Query result with answer and supporting evidence
    """
    try:
        agent = PatientKnowledgeBaseAgent(patient_id, patient_profile)
        result = await agent.query_patient_kb(query)
        return result
    except Exception as e:
        logger.error(f"Failed to query KB for {patient_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to query knowledge base: {str(e)}"
        )


@router.get("/health")
async def health():
    """Health check for patient KB router"""
    return {"status": "healthy", "service": "patient_knowledge_base"}
