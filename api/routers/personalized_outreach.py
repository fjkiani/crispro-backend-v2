"""
Personalized Outreach API Router

Endpoints:
1. POST /api/personalized-outreach/search-trials - Search clinical trials
2. POST /api/personalized-outreach/extract-intelligence - Extract intelligence from trial
3. POST /api/personalized-outreach/generate-email - Generate personalized email
"""
import logging
from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, List, Any, Optional
import os

from api.services.personalized_outreach.intelligence_extractor import IntelligenceExtractor
from api.services.personalized_outreach.email_generator import EmailGenerator
from api.services.personalized_outreach.models import (
    TrialSearchRequest,
    IntelligenceExtractionRequest,
    EmailGenerationRequest,
    IntelligenceProfileResponse,
    EmailResponse
)
from api.services.ctgov_query_builder import CTGovQueryBuilder, execute_query

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/personalized-outreach", tags=["personalized-outreach"])


def get_intelligence_extractor() -> IntelligenceExtractor:
    """Dependency for IntelligenceExtractor."""
    pubmed_email = os.getenv("NCBI_USER_EMAIL", "fahad@crispro.ai")
    pubmed_api_key = os.getenv("NCBI_API_KEY")
    return IntelligenceExtractor(pubmed_email=pubmed_email, pubmed_api_key=pubmed_api_key)


def get_email_generator() -> EmailGenerator:
    """Dependency for EmailGenerator."""
    return EmailGenerator()


@router.post("/search-trials", response_model=Dict[str, Any])
async def search_trials(request: TrialSearchRequest):
    """
    Search clinical trials matching criteria.
    
    Returns list of trials with basic information.
    """
    try:
        # Build query using CTGovQueryBuilder
        query_builder = CTGovQueryBuilder()
        
        # Add conditions
        if request.conditions:
            for condition in request.conditions:
                query_builder.add_condition(condition)
        
        # Add interventions
        if request.interventions:
            for intervention in request.interventions:
                query_builder.add_intervention(intervention)
        
        # Add keywords
        if request.keywords:
            for keyword in request.keywords:
                query_builder.add_keyword(keyword)
        
        # Add phases
        if request.phases:
            query_builder.set_phases(request.phases)
        
        # Add status
        if request.status:
            query_builder.set_status(request.status)
        
        # Execute query
        query_string = query_builder.build()
        trials = await execute_query(query_string, max_results=request.max_results)
        
        return {
            "trials": trials,
            "count": len(trials),
            "query": query_string
        }
    except Exception as e:
        logger.error(f"Failed to search trials: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/extract-intelligence", response_model=IntelligenceProfileResponse)
async def extract_intelligence(
    request: IntelligenceExtractionRequest,
    extractor: IntelligenceExtractor = Depends(get_intelligence_extractor)
):
    """
    Extract complete intelligence profile from a trial.
    
    Returns:
    - Trial intelligence (ClinicalTrials.gov data)
    - Research intelligence (PubMed publications)
    - Biomarker intelligence (KELIM fit, CA-125, platinum)
    - Goals (what PI is trying to achieve)
    - Value proposition (how we can help)
    """
    try:
        intelligence_profile = await extractor.extract_complete_intelligence(
            nct_id=request.nct_id,
            pi_name=request.pi_name,
            institution=request.institution
        )
        
        if intelligence_profile.get("status") == "failed":
            raise HTTPException(
                status_code=404,
                detail=f"Failed to extract intelligence: {intelligence_profile.get('error')}"
            )
        
        return IntelligenceProfileResponse(**intelligence_profile)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to extract intelligence: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate-email", response_model=EmailResponse)
async def generate_email(
    request: EmailGenerationRequest,
    generator: EmailGenerator = Depends(get_email_generator)
):
    """
    Generate personalized outreach email.
    
    Returns:
    - Subject line
    - Email body
    - Personalization quality score
    - Key points summary
    """
    try:
        email_result = generator.generate_personalized_email(
            intelligence_profile=request.intelligence_profile,
            outreach_config=request.outreach_config or {}
        )
        
        return EmailResponse(**email_result)
    except Exception as e:
        logger.error(f"Failed to generate email: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "personalized-outreach"}
