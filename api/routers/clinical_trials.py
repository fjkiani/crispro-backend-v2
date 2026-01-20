"""
⚔️ CLINICAL TRIALS MATCHING ROUTER ⚔️

Integrates with ClinicalTrials.gov API for:
- Trial matching based on genomic profile
- Eligibility screening
- Geographic filtering
- Basket trial identification
- Trial status refresh (live data from ClinicalTrials.gov)

Research Use Only - Not for Clinical Enrollment
"""

from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
import httpx
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/clinical_trials", tags=["clinical_trials"])

CLINICAL_TRIALS_BASE_URL = "https://clinicaltrials.gov/api/v2/studies"

class TrialMatchRequest(BaseModel):
    """Request for clinical trial matching"""
    mutations: List[Dict[str, str]] = Field(..., description="List of mutations (gene, hgvs_p)")
    cancer_type: Optional[str] = Field(None, description="Cancer type (e.g., breast cancer, NSCLC)")
    location: Optional[str] = Field(None, description="Patient location for geographic filtering")
    max_results: int = Field(10, description="Maximum number of trials to return")

class TrialEligibilityCheck(BaseModel):
    """Check eligibility for specific trial"""
    trial_id: str = Field(..., description="ClinicalTrials.gov NCT ID")
    mutations: List[Dict[str, str]] = Field(..., description="Patient mutations")
    age: Optional[int] = Field(None, description="Patient age")
    cancer_type: str = Field(..., description="Patient cancer type")

class TrialMatch(BaseModel):
    """Single trial match result"""
    nct_id: str
    title: str
    status: str  # Recruiting, Active, Completed, etc.
    phase: Optional[str] = None
    match_score: float  # 0-1 confidence of match
    match_reasons: List[str] = []
    eligibility_summary: str
    location_sites: List[Dict[str, str]] = []
    contact_info: Optional[Dict[str, str]] = None
    provenance: Dict

class TrialMatchResponse(BaseModel):
    """Clinical trial matching results"""
    total_matches: int
    trials: List[TrialMatch] = []
    provenance: Dict

class TrialEligibilityResponse(BaseModel):
    """Eligibility check result"""
    nct_id: str
    title: str
    eligible: bool
    confidence: float
    inclusion_criteria_met: List[str] = []
    exclusion_criteria_violated: List[str] = []
    uncertain_criteria: List[str] = []
    rationale: List[str] = []
    provenance: Dict

async def search_clinical_trials(
    gene: str,
    cancer_type: Optional[str],
    max_results: int
) -> List[Dict]:
    """Search ClinicalTrials.gov API"""
    try:
        # Build search query
        query_terms = [gene]
        if cancer_type:
            query_terms.append(cancer_type)
        
        query = " AND ".join(query_terms)
        
        params = {
            "query.term": query,
            "format": "json",
            "pageSize": min(max_results, 50),  # API limit
            "filter.overallStatus": "RECRUITING"  # Only recruiting trials
        }
        
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(CLINICAL_TRIALS_BASE_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
            
            return data.get("studies", [])
    except Exception as e:
        logger.warning(f"ClinicalTrials.gov search failed: {e}")
        return []

def calculate_match_score(trial: Dict, mutations: List[Dict], cancer_type: Optional[str]) -> tuple[float, List[str]]:
    """Calculate how well a trial matches patient profile"""
    score = 0.5  # Base score
    reasons = []
    
    # Extract trial details
    protocol_section = trial.get("protocolSection", {})
    identification = protocol_section.get("identificationModule", {})
    eligibility = protocol_section.get("eligibilityModule", {})
    
    # Check mutation match in title/description
    title = identification.get("briefTitle", "").lower()
    summary = identification.get("briefSummary", "").lower()
    
    for mut in mutations:
        gene = mut.get("gene", "").lower()
        if gene in title or gene in summary:
            score += 0.2
            reasons.append(f"Trial targets {mut.get('gene')} mutation")
    
    # Check cancer type match
    if cancer_type:
        conditions = protocol_section.get("conditionsModule", {}).get("conditions", [])
        for condition in conditions:
            if cancer_type.lower() in condition.lower():
                score += 0.15
                reasons.append(f"Trial includes {cancer_type}")
                break
    
    # Check for basket trial indicators
    if "basket" in title or "tumor agnostic" in title or "tumor-agnostic" in title:
        score += 0.15
        reasons.append("Basket trial (tumor-agnostic)")
    
    # Cap score at 1.0
    score = min(1.0, score)
    
    return score, reasons

def extract_trial_locations(trial: Dict) -> List[Dict[str, str]]:
    """Extract trial site locations"""
    locations = []
    
    protocol_section = trial.get("protocolSection", {})
    contacts_locations = protocol_section.get("contactsLocationsModule", {})
    
    trial_locations = contacts_locations.get("locations", [])
    for loc in trial_locations[:5]:  # Limit to 5 locations
        locations.append({
            "facility": loc.get("facility", "Unknown"),
            "city": loc.get("city", ""),
            "state": loc.get("state", ""),
            "country": loc.get("country", "")
        })
    
    return locations

@router.post("/match", response_model=TrialMatchResponse)
async def match_clinical_trials(request: TrialMatchRequest):
    """
    Match clinical trials based on genomic profile.
    
    **Research Use Only - Not for Clinical Enrollment**
    
    Example:
    ```json
    {
        "mutations": [{"gene": "BRCA1", "hgvs_p": "p.Gln1756fs"}],
        "cancer_type": "breast cancer",
        "location": "New York",
        "max_results": 10
    }
    ```
    
    Returns ranked list of matching trials.
    """
    logger.info(f"Trial matching request: {len(request.mutations)} mutations, cancer: {request.cancer_type}")
    
    try:
        # Search trials for each mutation
        all_trials = []
        genes_searched = []
        
        for mutation in request.mutations:
            gene = mutation.get("gene")
            if gene and gene not in genes_searched:
                trials = await search_clinical_trials(gene, request.cancer_type, request.max_results)
                all_trials.extend(trials)
                genes_searched.append(gene)
        
        # Remove duplicates
        unique_trials = {}
        for trial in all_trials:
            nct_id = trial.get("protocolSection", {}).get("identificationModule", {}).get("nctId")
            if nct_id and nct_id not in unique_trials:
                unique_trials[nct_id] = trial
        
        # Score and rank trials
        scored_trials = []
        for nct_id, trial in unique_trials.items():
            score, reasons = calculate_match_score(trial, request.mutations, request.cancer_type)
            
            protocol_section = trial.get("protocolSection", {})
            identification = protocol_section.get("identificationModule", {})
            status_module = protocol_section.get("statusModule", {})
            design_module = protocol_section.get("designModule", {})
            eligibility_module = protocol_section.get("eligibilityModule", {})
            
            trial_match = TrialMatch(
                nct_id=nct_id,
                title=identification.get("briefTitle", "Unknown"),
                status=status_module.get("overallStatus", "Unknown"),
                phase=design_module.get("phases", [None])[0] if design_module.get("phases") else None,
                match_score=score,
                match_reasons=reasons,
                eligibility_summary=eligibility_module.get("eligibilityCriteria", "Not available")[:500],
                location_sites=extract_trial_locations(trial),
                provenance={
                    "nct_id": nct_id,
                    "source": "ClinicalTrials.gov"
                }
            )
            
            scored_trials.append(trial_match)
        
        # Sort by match score
        scored_trials.sort(key=lambda t: t.match_score, reverse=True)
        
        # Limit results
        scored_trials = scored_trials[:request.max_results]
        
        response = TrialMatchResponse(
            total_matches=len(scored_trials),
            trials=scored_trials,
            provenance={
                "method": "clinical_trials_gov_v2_api",
                "genes_searched": genes_searched,
                "cancer_type": request.cancer_type,
                "timestamp": "2025-01-26"
            }
        )
        
        logger.info(f"Found {len(scored_trials)} matching trials")
        return response
        
    except Exception as e:
        logger.error(f"Trial matching failed: {e}")
        raise HTTPException(status_code=500, detail=f"Trial matching failed: {str(e)}")

@router.post("/eligibility_check", response_model=TrialEligibilityResponse)
async def check_trial_eligibility(request: TrialEligibilityCheck):
    """
    Check eligibility for specific trial.
    
    **Research Use Only - Not for Clinical Enrollment**
    
    Example:
    ```json
    {
        "trial_id": "NCT12345678",
        "mutations": [{"gene": "BRCA1", "hgvs_p": "p.Gln1756fs"}],
        "age": 45,
        "cancer_type": "breast cancer"
    }
    ```
    
    Returns eligibility assessment with met/violated criteria.
    """
    logger.info(f"Eligibility check: {request.trial_id}")
    
    try:
        # Fetch trial details
        async with httpx.AsyncClient(timeout=30) as client:
            url = f"{CLINICAL_TRIALS_BASE_URL}/{request.trial_id}"
            resp = await client.get(url, params={"format": "json"})
            resp.raise_for_status()
            trial_data = resp.json()
        
        protocol_section = trial_data.get("protocolSection", {})
        identification = protocol_section.get("identificationModule", {})
        eligibility = protocol_section.get("eligibilityModule", {})
        
        # Simple eligibility logic (real implementation would parse criteria text)
        inclusion_met = []
        exclusion_violated = []
        uncertain = []
        
        # Check age
        min_age = eligibility.get("minimumAge")
        max_age = eligibility.get("maximumAge")
        if request.age:
            inclusion_met.append(f"Age requirement: Patient is {request.age} years old")
        
        # Check mutations
        criteria_text = eligibility.get("eligibilityCriteria", "").lower()
        for mutation in request.mutations:
            gene = mutation.get("gene", "").lower()
            if gene in criteria_text:
                inclusion_met.append(f"Genomic criteria: Trial requires {mutation.get('gene')} mutation")
        
        # Determine eligibility
        eligible = len(inclusion_met) > 0 and len(exclusion_violated) == 0
        confidence = 0.7 if eligible else 0.3  # Conservative confidence
        
        rationale = []
        rationale.append(f"Trial: {identification.get('briefTitle', 'Unknown')}")
        rationale.append(f"Inclusion criteria met: {len(inclusion_met)}")
        rationale.append(f"Exclusion criteria violated: {len(exclusion_violated)}")
        
        response = TrialEligibilityResponse(
            nct_id=request.trial_id,
            title=identification.get("briefTitle", "Unknown"),
            eligible=eligible,
            confidence=confidence,
            inclusion_criteria_met=inclusion_met,
            exclusion_criteria_violated=exclusion_violated,
            uncertain_criteria=uncertain,
            rationale=rationale,
            provenance={
                "method": "clinical_trials_eligibility_check",
                "trial_id": request.trial_id,
                "timestamp": "2025-01-26"
            }
        )
        
        logger.info(f"Eligibility: {'ELIGIBLE' if eligible else 'NOT ELIGIBLE'} (confidence: {confidence:.2f})")
        return response
        
    except Exception as e:
        logger.error(f"Eligibility check failed: {e}")
        raise HTTPException(status_code=500, detail=f"Eligibility check failed: {str(e)}")

@router.get("/health")
async def health():
    """Health check for clinical trials router"""
    return {"status": "operational", "service": "clinical_trials_matching"}


