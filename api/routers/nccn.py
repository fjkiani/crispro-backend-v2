"""
⚔️ NCCN GUIDELINE COMPLIANCE ROUTER ⚔️

Checks therapy recommendations against NCCN guidelines:
- Breast cancer guidelines
- Lung cancer guidelines
- Colorectal cancer guidelines
- Multiple myeloma guidelines

Loads guidelines from external JSON config file for easy updates.

Research Use Only - Not for Clinical Diagnosis
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)
import json
import os
from pathlib import Path

router = APIRouter(prefix="/api/nccn", tags=["nccn"])

# Load NCCN guidelines from config file
NCCN_CONFIG_PATH = Path(__file__).parent / "nccn_guidelines_config.json"

def load_nccn_guidelines():
    """Load NCCN guidelines from JSON config file"""
    if not NCCN_CONFIG_PATH.exists():
        logger.error(f"NCCN config file not found: {NCCN_CONFIG_PATH}")
        return {}
    
    try:
        with open(NCCN_CONFIG_PATH, 'r') as f:
            config = json.load(f)
        logger.info(f"Loaded NCCN guidelines v{config.get('version', 'unknown')}")
        return config.get("guidelines", {})
    except Exception as e:
        logger.error(f"Failed to load NCCN config: {e}")
        return {}

# Load guidelines at module import
NCCN_GUIDELINES = load_nccn_guidelines()

class NCCNGuidelineRequest(BaseModel):
    """Request for NCCN guideline compliance check"""
    cancer_type: str = Field(..., description="Cancer type (e.g., breast, lung, colorectal, myeloma)")
    biomarkers: Dict[str, str] = Field(..., description="Biomarker status (e.g., {'HER2': 'positive', 'ER': 'positive'})")
    proposed_therapy: str = Field(..., description="Proposed therapy name")
    stage: Optional[str] = Field(None, description="Cancer stage (I, II, III, IV)")
    line_of_therapy: Optional[int] = Field(None, description="Line of therapy (1, 2, 3, etc.)")

class NCCNRecommendation(BaseModel):
    """Single NCCN recommendation"""
    therapy: str
    category: str  # 1, 2A, 2B, 3
    indication: str
    evidence_level: str  # High, Moderate, Low
    rationale: str

class NCCNGuidelineResponse(BaseModel):
    """NCCN guideline compliance result"""
    cancer_type: str
    proposed_therapy: str
    compliant: bool
    nccn_category: Optional[str] = None
    recommendation_summary: str
    alternative_therapies: List[NCCNRecommendation] = []
    warnings: List[str] = []
    rationale: List[str] = []
    provenance: Dict

# NCCN Guidelines now loaded from external JSON config file
# See nccn_guidelines_config.json for full guideline data

def find_nccn_recommendation(
    cancer_type: str,
    biomarkers: Dict[str, str],
    proposed_therapy: str,
    line_of_therapy: Optional[int]
) -> tuple[bool, Optional[str], List[NCCNRecommendation]]:
    """
    Find NCCN recommendation for given therapy.
    Returns (compliant, category, alternative_recommendations)
    """
    cancer_guidelines = NCCN_GUIDELINES.get(cancer_type.lower(), {})
    
    # Determine biomarker subtype
    subtype = None
    if cancer_type.lower() == "breast":
        if biomarkers.get("HER2") == "positive":
            subtype = "HER2_positive"
        elif biomarkers.get("BRCA1") == "mutant" or biomarkers.get("BRCA2") == "mutant":
            subtype = "BRCA_mutant"
    elif cancer_type.lower() == "lung":
        if biomarkers.get("EGFR") == "mutant":
            subtype = "EGFR_mutant"
        elif biomarkers.get("ALK") == "rearranged":
            subtype = "ALK_rearranged"
    elif cancer_type.lower() == "myeloma":
        subtype = "standard_risk"  # Simplified
    
    if not subtype or subtype not in cancer_guidelines:
        return False, None, []
    
    subtype_guidelines = cancer_guidelines[subtype]
    
    # Determine line of therapy key
    line_key = None
    if line_of_therapy == 1:
        line_key = "first_line"
    elif line_of_therapy and line_of_therapy >= 2:
        line_key = "relapsed" if cancer_type.lower() == "myeloma" else "second_line"
    elif "all_lines" in subtype_guidelines:
        line_key = "all_lines"
    
    if not line_key or line_key not in subtype_guidelines:
        # Try all_lines as fallback
        if "all_lines" in subtype_guidelines:
            line_key = "all_lines"
        else:
            return False, None, []
    
    recommendations = subtype_guidelines[line_key]
    
    # Check if proposed therapy matches any recommendation
    proposed_lower = proposed_therapy.lower()
    for rec in recommendations:
        if proposed_lower in rec["therapy"].lower() or rec["therapy"].lower() in proposed_lower:
            # Match found!
            nccn_rec = NCCNRecommendation(
                therapy=rec["therapy"],
                category=rec["category"],
                indication=rec["indication"],
                evidence_level=rec["evidence"],
                rationale=rec["rationale"]
            )
            return True, rec["category"], [nccn_rec]
    
    # No match - return alternatives
    alternatives = [
        NCCNRecommendation(
            therapy=rec["therapy"],
            category=rec["category"],
            indication=rec["indication"],
            evidence_level=rec["evidence"],
            rationale=rec["rationale"]
        )
        for rec in recommendations
    ]
    
    return False, None, alternatives

@router.post("/check_guideline", response_model=NCCNGuidelineResponse)
async def check_nccn_guideline(request: NCCNGuidelineRequest):
    """
    Check if proposed therapy complies with NCCN guidelines.
    
    **Research Use Only - Not for Clinical Diagnosis**
    
    Example:
    ```json
    {
        "cancer_type": "breast",
        "biomarkers": {"HER2": "positive", "ER": "positive"},
        "proposed_therapy": "trastuzumab deruxtecan",
        "stage": "IV",
        "line_of_therapy": 2
    }
    ```
    
    Returns NCCN category and alternative recommendations if non-compliant.
    """
    logger.info(f"NCCN guideline check: {request.cancer_type}, {request.proposed_therapy}")
    
    try:
        # Find NCCN recommendation
        compliant, category, alternatives = find_nccn_recommendation(
            request.cancer_type,
            request.biomarkers,
            request.proposed_therapy,
            request.line_of_therapy
        )
        
        # Build rationale
        rationale = []
        rationale.append(f"Cancer Type: {request.cancer_type}")
        rationale.append(f"Biomarkers: {', '.join([f'{k}={v}' for k, v in request.biomarkers.items()])}")
        if request.line_of_therapy:
            rationale.append(f"Line of Therapy: {request.line_of_therapy}")
        
        # Build recommendation summary
        if compliant:
            summary = f"✅ NCCN Category {category} recommendation. Therapy is guideline-compliant."
        else:
            summary = f"⚠️ Therapy is NOT listed in current NCCN guidelines for this indication. Consider NCCN-recommended alternatives."
        
        # Warnings
        warnings = []
        if not compliant:
            warnings.append("Proposed therapy not found in NCCN guidelines for this biomarker profile")
        if not category or category in ["2B", "3"]:
            warnings.append("Lower evidence level - consider consulting multidisciplinary team")
        
        response = NCCNGuidelineResponse(
            cancer_type=request.cancer_type,
            proposed_therapy=request.proposed_therapy,
            compliant=compliant,
            nccn_category=category,
            recommendation_summary=summary,
            alternative_therapies=alternatives,
            warnings=warnings,
            rationale=rationale,
            provenance={
                "method": "nccn_guideline_check_v1",
                "guideline_version": "2024.v1 (simplified)",
                "cancer_type": request.cancer_type,
                "biomarkers": request.biomarkers,
                "timestamp": "2025-01-26"
            }
        )
        
        logger.info(f"NCCN compliance: {'YES' if compliant else 'NO'} (category: {category})")
        return response
        
    except Exception as e:
        logger.error(f"NCCN guideline check failed: {e}")
        raise HTTPException(status_code=500, detail=f"NCCN guideline check failed: {str(e)}")

@router.get("/health")
async def health():
    """Health check for NCCN guidelines router"""
    return {"status": "operational", "service": "nccn_guidelines"}

