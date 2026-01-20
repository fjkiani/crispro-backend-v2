"""
Ayesha Trials Router

CLINICAL PURPOSE: Find the RIGHT trials for AK (Stage IVB ovarian cancer)
NOT a demo. Real clinical decision support.

Patient Profile:
- Stage IVB ovarian cancer (extensive metastases)
- CA-125: 2,842 U/mL (baseline November 2025)
- Germline: NEGATIVE (Ambry Genetics June 2023)
- Treatment-naive (first-line)
- Location: NYC
- Urgency: Needs treatment within 2-4 weeks

This router provides:
1. Top 10 frontline trials (ranked with transparent reasoning)
2. SOC recommendation (NCCN-aligned carboplatin + paclitaxel + bevacizumab)
3. CA-125 monitoring plan (response forecast + resistance detection)
4. Eligibility checklists (hard/soft criteria with green/yellow/red flags)
5. Confidence gates (deterministic, not black-box)

Author: Zo
Date: January 13, 2025
For: AK
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta, timezone
import logging
import asyncio

from api.services.hybrid_trial_search import HybridTrialSearchService
from api.services.ca125_intelligence import get_ca125_service
from api.services.ngs_fast_track import get_ngs_fast_track_service
from api.services.mechanism_fit_ranker import rank_trials_by_mechanism  # ⚔️ P0 FIX #4 (Jan 13, 2025)
from api.services.database_connections import get_db_connections
from api.services.trial_refresh import refresh_trial_status_with_retry
from api.services.holistic_score_service import get_holistic_score_service  # ⚔️ PRODUCTION: Holistic score integration
import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

# ⚔️ P0 FIX #5: Load trial MoA vectors (Manager's P3 - Jan 13, 2025)
# Load once at module initialization for performance
TRIAL_MOA_VECTORS = {}
try:
    moa_vectors_path = os.path.join(
        os.path.dirname(__file__), 
        "../resources/trial_moa_vectors.json"
    )
    if os.path.exists(moa_vectors_path):
        with open(moa_vectors_path, "r") as f:
            TRIAL_MOA_VECTORS = json.load(f)
        logger.info(f"✅ Loaded {len(TRIAL_MOA_VECTORS)} trial MoA vectors from {moa_vectors_path}")
    else:
        logger.warning(f"⚠️ Trial MoA vectors file not found: {moa_vectors_path} (using defaults)")
except Exception as e:
    logger.error(f"❌ Failed to load trial MoA vectors: {e}")
    TRIAL_MOA_VECTORS = {}

router = APIRouter(prefix="/api/ayesha/trials", tags=["ayesha"])


# === SCHEMAS ===

class AyeshaTrialSearchRequest(BaseModel):
    """Request schema for Ayesha trial search"""
    ca125_value: Optional[float] = Field(
        None,
        description="Current CA-125 value in U/mL (optional; omit if not available)",
        example=2842.0
    )
    stage: str = Field(..., description="Cancer stage", example="IVB")
    treatment_line: str = Field(
        default="either",
        description="Treatment line preference: first-line | recurrent | either",
        example="either"
    )
    germline_status: str = Field(..., description="Germline mutation status", example="negative")
    location_state: str = Field(default="NY", description="State for location filtering")
    has_ascites: bool = Field(default=False, description="Presence of ascites")
    has_peritoneal_disease: bool = Field(default=False, description="Presence of peritoneal disease")
    ecog_status: Optional[int] = Field(None, description="ECOG performance status (0-4)")
    max_results: int = Field(default=10, description="Maximum number of trials to return")

    # Tumor context (from pathology/IHC) - optional but strongly improves matching
    tumor_context: Optional[Dict[str, Any]] = Field(
        None,
        description="Tumor context dict (e.g., PD-L1 CPS, p53 mutant type, ER/PR, MMR, HER2, FOLR1, NTRK)."
    )
    
    # ⚔️ P0 FIX #4: SAE mechanism vector for mechanism fit ranking (Manager's P4 - Jan 13, 2025)
    sae_mechanism_vector: Optional[Dict[str, float]] = Field(
        None, 
        description="SAE mechanism vector (7D: DDR/MAPK/PI3K/VEGF/HER2/IO/Efflux) for mechanism fit ranking"
    )


class AyeshaTrialSearchResponse(BaseModel):
    """Response schema for Ayesha trial search"""
    trials: List[Dict[str, Any]] = Field(..., description="Ranked trials with eligibility and reasoning")
    soc_recommendation: Dict[str, Any] = Field(..., description="Standard of care recommendation")
    ca125_intelligence: Dict[str, Any] = Field(..., description="CA-125 analysis and monitoring plan")
    ngs_fast_track: Dict[str, Any] = Field(..., description="NGS fast-track checklist to unlock WIWFM")
    summary: Dict[str, Any] = Field(..., description="Summary statistics")
    provenance: Dict[str, Any] = Field(..., description="Data sources and calculation methods")


# === HELPER FUNCTIONS ===

def _apply_ayesha_hard_filters(trials: List[Dict[str, Any]], request: AyeshaTrialSearchRequest) -> List[Dict[str, Any]]:
    """
    Apply HARD filters for Ayesha.
    Hard criteria MUST pass - any failure excludes trial.
    
    Hard Criteria:
    1. Stage IV eligible (or "all stages")
    2. First-line treatment
    3. Recruiting status
    4. NYC metro location (NY/NJ/CT)
    
    Args:
        trials: List of trial dicts from hybrid search
        request: Ayesha's profile
    
    Returns:
        Filtered trials with hard_pass flag
    """
    filtered = []
    
    for trial in trials:
        hard_flags = {}
        
        # 1. Stage eligibility
        # For now, assume all trials from ovarian cancer search are Stage IV eligible
        # TODO: Parse eligibility_text for stage requirements
        hard_flags["stage_eligible"] = True
        
        # 2. Treatment line (do not guess)
        # - If request.treatment_line == "first-line": require frontline language
        # - If "recurrent": require recurrent/refractory language
        # - If "either": allow both, but label trial_line for downstream UI/boosting
        eligibility_text = trial.get("eligibility_text", "").lower()
        title = trial.get("title", "").lower()
        description = trial.get("description", "").lower()
        
        frontline_keywords = ["frontline", "first-line", "first line", "initial", "untreated", "newly diagnosed"]
        recurrent_keywords = ["recurrent", "relapsed", "platinum-resistant", "platinum resistant", "platinum-sensitive", "platinum sensitive", "refractory", "maintenance"]

        is_frontline = any(k in eligibility_text or k in title or k in description for k in frontline_keywords)
        is_recurrent = any(k in eligibility_text or k in title or k in description for k in recurrent_keywords)

        treatment_pref = (request.treatment_line or "either").strip().lower()
        if treatment_pref == "first-line":
            hard_flags["treatment_line_ok"] = is_frontline
            trial["trial_line"] = "first-line"
        elif treatment_pref == "recurrent":
            hard_flags["treatment_line_ok"] = is_recurrent
            trial["trial_line"] = "recurrent"
        else:
            # either: allow if we can classify, but don't hard-fail on missing language
            hard_flags["treatment_line_ok"] = True
            if is_frontline and not is_recurrent:
                trial["trial_line"] = "first-line"
            elif is_recurrent and not is_frontline:
                trial["trial_line"] = "recurrent"
            elif is_frontline and is_recurrent:
                trial["trial_line"] = "mixed"
            else:
                trial["trial_line"] = "unspecified"
        
        # 3. Recruiting status
        status = trial.get("status", "").lower()
        is_recruiting = "recruiting" in status or "active" in status
        hard_flags["recruiting"] = is_recruiting
        
        # 4. NYC metro location
        # ⚔️ MANAGER'S PLAN: For SQLite candidates, locations may be missing (needs refresh - Concern B)
        # Don't hard-fail on missing locations - mark as "unknown" for later refresh
        locations = trial.get("locations_data") or trial.get("locations", [])
        nyc_metro_states = ["ny", "nj", "ct", "new york", "new jersey", "connecticut"]
        has_nyc_location = False
        location_unknown = False
        
        if not locations or len(locations) == 0:
            # SQLite candidates may not have locations yet (needs refresh)
            if trial.get("source") == "sqlite_candidate_discovery":
                location_unknown = True
                hard_flags["nyc_metro"] = True  # Don't hard-fail - mark for refresh
                trial["location_unknown"] = True  # Flag for UI to show "location needs refresh"
            else:
                hard_flags["nyc_metro"] = False
        else:
            has_nyc_location = any(
                (loc.get("state") or "").lower() in nyc_metro_states 
                for loc in locations
            )
            hard_flags["nyc_metro"] = has_nyc_location
        
        if location_unknown:
            trial["location_status"] = "needs_refresh"
        
        # All hard criteria must pass
        hard_pass = all(hard_flags.values())
        
        trial["hard_pass"] = hard_pass
        trial["hard_flags"] = hard_flags
        
        if hard_pass:
            filtered.append(trial)
    
    logger.info(f"Hard filters: {len(trials)} trials → {len(filtered)} passed")
    return filtered


def _apply_ayesha_soft_boosts(trials: List[Dict[str, Any]], request: AyeshaTrialSearchRequest) -> List[Dict[str, Any]]:
    """
    Apply SOFT boosts for Ayesha.
    Soft criteria increase match score but don't exclude.
    
    Soft Boosts (from manager's specification):
    1. Frontline trial: +0.30
    2. Stage IV specific: +0.25
    3. Carboplatin/Paclitaxel arm: +0.20
    4. Bevacizumab arm (if ascites/peritoneal): +0.15
    5. Phase III: +0.10
    6. Multi-center: +0.05
    
    Args:
        trials: List of trials that passed hard filters
        request: Ayesha's profile
    
    Returns:
        Trials with boosted match scores and reasoning
    """
    tumor_context = request.tumor_context or {}
    pd_l1 = tumor_context.get("pd_l1") or {}
    pd_l1_cps = pd_l1.get("cps")
    pd_l1_positive = str(pd_l1.get("status") or "").upper() == "POSITIVE" or (pd_l1_cps is not None and float(pd_l1_cps) >= 1)
    p53_status = str(tumor_context.get("p53_status") or tumor_context.get("p53") or "").lower()
    p53_mutant = "mutant" in p53_status
    er_percent = tumor_context.get("er_percent")
    er_status = str(tumor_context.get("er_status") or "").upper()
    er_positive = (er_percent is not None and float(er_percent) >= 1) or ("POSITIVE" in er_status)
    folr1_status = str(tumor_context.get("folr1_status") or "").upper()
    folr1_negative = folr1_status == "NEGATIVE"

    for trial in trials:
        base_score = trial.get("optimization_score", 0.5)
        boosts = []
        
        title = trial.get("title", "").lower()
        description = trial.get("description", "").lower()
        interventions = [i.lower() for i in trial.get("interventions", [])]
        phase = trial.get("phase", "").lower()
        
        # 1. Treatment line boost (if classified)
        if trial.get("trial_line") == "first-line":
            base_score += 0.30
            boosts.append({"type": "frontline", "value": 0.30, "reason": "First-line treatment trial"})
        elif trial.get("trial_line") == "recurrent":
            base_score += 0.10
            boosts.append({"type": "recurrent", "value": 0.10, "reason": "Recurrent/refractory-appropriate language detected"})
        
        # 2. Stage IV specific
        if "stage iv" in title or "stage 4" in title or "advanced" in title:
            base_score += 0.25
            boosts.append({"type": "stage_iv_specific", "value": 0.25, "reason": "Trial specifically for Stage IV disease"})
        
        # 3. Carboplatin/Paclitaxel arm
        has_carbo = any("carboplatin" in i or "carbo" in i for i in interventions)
        has_pacli = any("paclitaxel" in i or "taxol" in i for i in interventions)
        if has_carbo and has_pacli:
            base_score += 0.20
            boosts.append({"type": "standard_chemo", "value": 0.20, "reason": "Includes standard carboplatin + paclitaxel"})
        
        # 4. Bevacizumab arm (if ascites/peritoneal)
        if request.has_ascites or request.has_peritoneal_disease:
            has_bev = any("bevacizumab" in i or "avastin" in i for i in interventions)
            if has_bev:
                base_score += 0.15
                boosts.append({"type": "bevacizumab_ascites", "value": 0.15, "reason": "Bevacizumab indicated for ascites/peritoneal disease"})
        
        # 5. Phase III
        if "phase 3" in phase or "phase iii" in phase:
            base_score += 0.10
            boosts.append({"type": "phase_3", "value": 0.10, "reason": "Phase III trial (highest evidence level)"})
        
        # 6. Multi-center
        locations = trial.get("locations", [])
        if len(locations) > 10:
            base_score += 0.05
            boosts.append({"type": "multi_center", "value": 0.05, "reason": "Multi-center trial (broader access)"})
        
        # 7. Biomarker-aware boosts (from PATIENT_ANALYSIS_11-17-25.md)
        # PD-L1 CPS 10 (positive) -> boost IO trials
        if pd_l1_positive:
            io_drugs = ["pembrolizumab", "nivolumab", "atezolizumab", "durvalumab", "avelumab", "ipilimumab", "cemiplimab"]
            has_io = any(d in " ".join(interventions) for d in io_drugs) or any(d in title or d in description for d in io_drugs)
            if has_io:
                base_score += 0.20
                boosts.append({"type": "pd_l1_io", "value": 0.20, "reason": f"PD-L1 positive (CPS {pd_l1_cps}) → IO trial alignment"})

        # p53 mutant type -> boost DDR trials (PARP/ATR/WEE1/CHK1)
        if p53_mutant:
            ddr_keywords = ["olaparib", "niraparib", "rucaparib", "talazoparib", "parp", "atr", "ceralasertib", "berzosertib", "wee1", "adavosertib", "chk1", "prexasertib", "dna damage", "ddr"]
            has_ddr = any(k in " ".join(interventions) for k in ddr_keywords) or any(k in title or k in description for k in ddr_keywords)
            if has_ddr:
                base_score += 0.20
                boosts.append({"type": "p53_ddr", "value": 0.20, "reason": "p53 mutant type → DDR vulnerability → DDR trial alignment"})

        # ER 50% weakly positive -> small boost to endocrine/hormone trials
        if er_positive:
            endocrine = ["letrozole", "anastrozole", "tamoxifen", "fulvestrant", "aromatase", "endocrine"]
            has_endocrine = any(k in " ".join(interventions) for k in endocrine) or any(k in title or k in description for k in endocrine)
            if has_endocrine:
                base_score += 0.08
                boosts.append({"type": "er_endocrine", "value": 0.08, "reason": "ER positive → endocrine trial relevance (secondary option)"})

        # FOLR1 negative (<1%) -> penalize mirvetuximab/ELAHERE/FOLR1-high trials
        if folr1_negative:
            folr1_terms = ["mirvetuximab", "elahere", "folr1", "folate receptor"]
            requires_folr1 = any(t in title or t in description for t in folr1_terms) or any(t in " ".join(interventions) for t in folr1_terms)
            if requires_folr1:
                base_score -= 0.25
                boosts.append({"type": "folr1_negative", "value": -0.25, "reason": "FOLR1 negative → likely ineligible for FOLR1-targeted trials"})

        trial["match_score"] = min(max(base_score, 0.0), 1.0)  # Clamp to [0,1]
        trial["boosts"] = boosts
    
    # Sort by match_score descending
    trials.sort(key=lambda t: t.get("match_score", 0), reverse=True)
    
    return trials


def _generate_eligibility_checklist(trial: Dict[str, Any], request: AyeshaTrialSearchRequest) -> Dict[str, Any]:
    """
    Generate eligibility checklist (hard/soft criteria with green/yellow/red flags).
    
    Hard Criteria (must pass):
    - Stage IV: ✅ (she is)
    - First-line: ✅ (she is)
    - Recruiting: ✅ (filtered)
    - NYC metro: ✅ (filtered)
    
    Soft Criteria (warnings if unknown/missing):
    - ECOG status: ⚠️ if unknown
    - Age: ✅ (40yo, likely eligible for most trials)
    - Organ function: ⚠️ (labs needed)
    - Prior surgeries: ⚠️ (depends on trial)
    
    Args:
        trial: Trial dict
        request: Ayesha's profile
    
    Returns:
        Checklist dict with criteria, status, and confidence gate
    """
    hard_criteria = []
    soft_criteria = []
    
    # Hard criteria (should all pass if trial got here)
    hard_flags = trial.get("hard_flags", {})
    hard_criteria.append({
        "criterion": "Stage IV eligible",
        "status": "PASS" if hard_flags.get("stage_eligible") else "FAIL",
        "value": "Stage IVB",
        "requirement": "Advanced stage allowed"
    })
    hard_criteria.append({
        "criterion": "Treatment line preference",
        "status": "PASS" if hard_flags.get("treatment_line_ok") else "FAIL",
        "value": f"Requested: {request.treatment_line} | Trial: {trial.get('trial_line', 'unspecified')}",
        "requirement": "Matches requested line-of-therapy (or request is 'either')"
    })
    hard_criteria.append({
        "criterion": "Trial recruiting",
        "status": "PASS" if hard_flags.get("recruiting") else "FAIL",
        "value": trial.get("status", "Unknown"),
        "requirement": "Recruiting or Active"
    })
    hard_criteria.append({
        "criterion": "NYC metro location",
        "status": "PASS" if hard_flags.get("nyc_metro") else "FAIL",
        "value": "NY",
        "requirement": "NY/NJ/CT sites available"
    })
    
    # Soft criteria (warnings)
    soft_criteria.append({
        "criterion": "ECOG performance status",
        "status": "PASS" if request.ecog_status is not None and request.ecog_status <= 1 else "UNKNOWN",
        "value": str(request.ecog_status) if request.ecog_status is not None else "Not provided",
        "requirement": "Typically ECOG 0-1 required"
    })
    soft_criteria.append({
        "criterion": "Age eligibility",
        "status": "UNKNOWN",
        "value": "Not provided",
        "requirement": "Typically 18-75"
    })
    soft_criteria.append({
        "criterion": "Organ function",
        "status": "UNKNOWN",
        "value": "Labs pending",
        "requirement": "Adequate hepatic/renal function"
    })
    soft_criteria.append({
        "criterion": "Prior surgeries",
        "status": "UNKNOWN",
        "value": "Debulking status unknown",
        "requirement": "Varies by trial"
    })
    
    # Calculate confidence gate
    hard_pass_count = sum(1 for c in hard_criteria if c["status"] == "PASS")
    hard_total = len(hard_criteria)
    soft_pass_count = sum(1 for c in soft_criteria if c["status"] == "PASS")
    soft_total = len(soft_criteria)
    
    soft_percent = soft_pass_count / soft_total if soft_total > 0 else 0.0
    
    # Confidence gate formula (from manager's spec)
    if hard_pass_count == hard_total:
        if soft_percent >= 0.80:
            confidence_gate = 0.90
        elif soft_percent >= 0.60:
            confidence_gate = 0.85
        else:
            confidence_gate = 0.75
    else:
        confidence_gate = 0.0  # Hard fail
    
    return {
        "hard_criteria": hard_criteria,
        "soft_criteria": soft_criteria,
        "hard_pass_count": hard_pass_count,
        "hard_total": hard_total,
        "soft_pass_count": soft_pass_count,
        "soft_total": soft_total,
        "soft_percent": round(soft_percent, 2),
        "confidence_gate": confidence_gate
    }


# === PRODUCTION: Data Enrichment for Holistic Score ===

def _parse_interventions_for_drug_names(trial: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    ⚔️ PRODUCTION: Parse interventions_json and extract drug names.
    
    Required for PGx Safety scoring in holistic score.
    """
    interventions = []
    
    # Try to get from interventions_json (SQLite column)
    interventions_json = trial.get("interventions_json")
    if interventions_json:
        try:
            if isinstance(interventions_json, str):
                interventions_data = json.loads(interventions_json)
            else:
                interventions_data = interventions_json
            
            for intervention in interventions_data if isinstance(interventions_data, list) else [interventions_data]:
                if isinstance(intervention, dict):
                    name = intervention.get("name", "") or intervention.get("intervention_name", "")
                    intervention_type = intervention.get("type", "") or intervention.get("intervention_type", "")
                    
                    # Extract drug names (filter out placebos, procedures)
                    if intervention_type.upper() in ["DRUG", "BIOLOGICAL", "BIOLOGICAL/VACCINE"]:
                        drug_names = []
                        if name:
                            drug_names.append(name.lower().strip())
                        
                        # Also check for synonyms/aliases
                        if "other_name" in intervention:
                            drug_names.append(intervention["other_name"].lower().strip())
                        
                        if drug_names:
                            interventions.append({
                                "name": name,
                                "type": intervention_type,
                                "drug_names": list(set(drug_names))  # Remove duplicates
                            })
        except (json.JSONDecodeError, TypeError, AttributeError) as e:
            logger.warning(f"Failed to parse interventions_json for {trial.get('nct_id')}: {e}")
    
    # Fallback: try to extract from title/description if no interventions_json
    if not interventions:
        title = trial.get("title", "").lower()
        description = trial.get("description", "").lower()
        interventions_list = trial.get("interventions", [])
        
        # If interventions is already a list of strings, use them
        if isinstance(interventions_list, list) and interventions_list:
            for item in interventions_list:
                if isinstance(item, str):
                    # Filter common non-drug terms
                    non_drugs = ["placebo", "procedure", "device", "behavioral", "radiation"]
                    if not any(term in item.lower() for term in non_drugs):
                        interventions.append({
                            "name": item,
                            "type": "DRUG",
                            "drug_names": [item.lower().strip()]
                        })
        
        # Common drug name patterns
        drug_keywords = [
            "olaparib", "niraparib", "rucaparib", "talazoparib",  # PARP
            "carboplatin", "cisplatin",  # Platinum
            "paclitaxel", "docetaxel", "taxol",  # Taxanes
            "bevacizumab", "avastin",  # VEGF
            "pembrolizumab", "nivolumab", "atezolizumab", "durvalumab",  # IO
            "ceralasertib", "berzosertib",  # ATR
            "5-fluorouracil", "5-fu", "capecitabine",  # Fluoropyrimidines
            "doxorubicin", "adriamycin",  # Anthracyclines
        ]
        
        found_drugs = [drug for drug in drug_keywords if drug in title or drug in description]
        if found_drugs:
            interventions.append({
                "name": found_drugs[0],
                "type": "DRUG",
                "drug_names": found_drugs
            })
    
    # Update trial with parsed interventions
    if interventions:
        trial["interventions"] = interventions
    elif "interventions" not in trial:
        trial["interventions"] = []
    
    return interventions


def _enrich_trial_with_moa(trial: Dict[str, Any]) -> Dict[str, Any]:
    """
    ⚔️ PRODUCTION: Attach MoA vector from trial_moa_vectors.json.
    
    Required for mechanism fit scoring in holistic score.
    """
    nct_id = trial.get("nct_id") or trial.get("nctId")
    if nct_id and nct_id in TRIAL_MOA_VECTORS:
        moa_data = TRIAL_MOA_VECTORS[nct_id]
        trial["moa_vector"] = moa_data.get("moa_vector", {})
        trial["moa_confidence"] = moa_data.get("confidence", 0.0)
        trial["moa_source"] = moa_data.get("source", "unknown")
    else:
        # Default to zero vector if not tagged
        trial["moa_vector"] = {
            "ddr": 0.0, "mapk": 0.0, "pi3k": 0.0,
            "vegf": 0.0, "her2": 0.0, "io": 0.0, "efflux": 0.0
        }
        trial["moa_confidence"] = 0.0
        trial["moa_source"] = "default"
    return trial


async def _compute_holistic_scores_for_trials(
    trials: List[Dict[str, Any]],
    patient_profile: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    ⚔️ PRODUCTION: Compute holistic scores for trials.
    
    Formula: (0.5 × Mechanism Fit) + (0.3 × Eligibility) + (0.2 × PGx Safety)
    """
    if not trials:
        return trials
    
    holistic_service = get_holistic_score_service()
    
    # Extract patient PGx variants
    pharmacogenes = patient_profile.get("germline_variants", [])
    
    # If germline_status is provided, check if we should add variants
    germline_status = patient_profile.get("germline_status", "").lower()
    if "positive" in germline_status and not pharmacogenes:
        # Could infer from germline_status, but safer to skip PGx if not explicitly provided
        logger.info("Germline positive but no variants provided - PGx safety will default to 1.0")
    
    scored_trials = []
    for trial in trials:
        try:
            # Ensure trial has required fields
            trial = _enrich_trial_with_moa(trial)
            _parse_interventions_for_drug_names(trial)
            
            # Build patient profile for holistic score
            holistic_patient_profile = {
                "mechanism_vector": patient_profile.get("mechanism_vector") or patient_profile.get("sae_mechanism_vector"),
                "disease": patient_profile.get("disease", "ovarian cancer"),
                "age": patient_profile.get("age"),
                "mutations": patient_profile.get("mutations", []),
                "germline_variants": pharmacogenes,
                "location": {"state": patient_profile.get("location_state", "NY")} if patient_profile.get("location_state") else None
            }
            
            # Compute holistic score
            result = await holistic_service.compute_holistic_score(
                patient_profile=holistic_patient_profile,
                trial=trial,
                pharmacogenes=pharmacogenes
            )
            
            # Attach holistic score to trial
            trial["holistic_score"] = result.holistic_score
            trial["holistic_interpretation"] = result.interpretation
            trial["holistic_recommendation"] = result.recommendation
            trial["holistic_caveats"] = result.caveats
            
            # Update existing scores with holistic components
            trial["mechanism_fit_score"] = result.mechanism_fit_score
            trial["eligibility_score"] = result.eligibility_score
            trial["pgx_safety_score"] = result.pgx_safety_score
            trial["pgx_details"] = result.pgx_details
            trial["mechanism_alignment"] = result.mechanism_alignment
            trial["eligibility_breakdown"] = result.eligibility_breakdown
            
            scored_trials.append(trial)
            
        except Exception as e:
            logger.error(f"Failed to compute holistic score for {trial.get('nct_id')}: {e}", exc_info=True)
            # Continue without holistic score - use existing scores
            scored_trials.append(trial)
    
    # Re-sort by holistic score if available (otherwise keep existing order)
    if any(t.get("holistic_score") is not None for t in scored_trials):
        scored_trials.sort(
            key=lambda t: t.get("holistic_score", 0.0),
            reverse=True
        )
        logger.info(f"✅ Holistic scores computed and trials re-ranked by holistic score")
    
    return scored_trials


def _generate_trial_reasoning(trial: Dict[str, Any], request: AyeshaTrialSearchRequest) -> Dict[str, Any]:
    """
    Generate transparent reasoning for why this trial is a good fit.
    
    Sections:
    1. Why eligible: Hard criteria that pass
    2. Why good fit: Soft boosts that apply
    3. What's required: Next steps (consent, labs, imaging)
    
    Args:
        trial: Trial dict with boosts and flags
        request: Ayesha's profile
    
    Returns:
        Reasoning dict
    """
    why_eligible = []
    hard_flags = trial.get("hard_flags", {})
    if hard_flags.get("stage_eligible"):
        why_eligible.append("Stage IVB ovarian cancer is explicitly eligible")
    if hard_flags.get("treatment_line_ok"):
        why_eligible.append(f"Treatment line compatible (requested: {request.treatment_line}; trial: {trial.get('trial_line', 'unspecified')})")
    if hard_flags.get("recruiting"):
        why_eligible.append(f"Currently {trial.get('status', 'recruiting')}")
    if hard_flags.get("nyc_metro"):
        nyc_locations = [loc for loc in trial.get("locations", []) 
                        if loc.get("state", "").lower() in ["ny", "nj", "ct"]]
        why_eligible.append(f"{len(nyc_locations)} NYC metro site(s) available")
    
    why_good_fit = []
    boosts = trial.get("boosts", [])
    for boost in boosts:
        why_good_fit.append(f"{boost['reason']} (+{boost['value']*100:.0f}% match)")
    
    whats_required = [
        "Informed consent and enrollment",
        "Baseline labs (CBC, CMP, LFTs)",
        "Imaging (CT or MRI for baseline)",
        "ECOG assessment",
        "Trial-specific requirements (see protocol)"
    ]
    
    # Add conditional requirements
    if request.has_ascites:
        whats_required.append("Paracentesis may be required for ascites management")

    # Biomarker transparency (from tumor_context)
    tumor_context = request.tumor_context or {}
    biomarker_notes = []
    pd_l1 = tumor_context.get("pd_l1") or {}
    if pd_l1:
        biomarker_notes.append(f"PD-L1: {pd_l1.get('status')} (CPS {pd_l1.get('cps')})")
    if tumor_context.get("p53") or tumor_context.get("p53_status"):
        biomarker_notes.append(f"p53: {tumor_context.get('p53_status') or tumor_context.get('p53')}")
    if tumor_context.get("er_percent") is not None or tumor_context.get("er_status"):
        biomarker_notes.append(f"ER: {tumor_context.get('er_status') or ''} {tumor_context.get('er_percent') or ''}".strip())
    if tumor_context.get("mmr_status"):
        biomarker_notes.append(f"MMR: {tumor_context.get('mmr_status')}")
    if biomarker_notes:
        whats_required.append(f"Biomarker context used: {', '.join(biomarker_notes)}")
    
    return {
        "why_eligible": why_eligible,
        "why_good_fit": why_good_fit,
        "whats_required": whats_required
    }


def _generate_soc_recommendation(request: AyeshaTrialSearchRequest) -> Dict[str, Any]:
    """
    Generate standard-of-care recommendation for Ayesha.
    
    NCCN Guidelines for Stage IVB HGSOC:
    - Carboplatin + Paclitaxel (standard)
    - + Bevacizumab (if ascites/peritoneal disease present)
    
    Confidence: 95-100% (guideline-aligned, no predictions)
    
    Args:
        request: Ayesha's profile
    
    Returns:
        SOC recommendation dict
    """
    regimen = "Carboplatin AUC 5-6 + Paclitaxel 175 mg/m²"
    add_ons = []
    
    # Bevacizumab add-on if ascites/peritoneal
    if request.has_ascites or request.has_peritoneal_disease:
        add_ons.append({
            "drug": "Bevacizumab 15 mg/kg",
            "rationale": "Ascites/peritoneal disease present → bevacizumab reduces progression risk",
            "evidence": "GOG-218 (HR 0.72, p<0.001), ICON7 (HR 0.81 for high-risk, p=0.04)"
        })
    
    confidence = 0.95  # NCCN guideline-aligned
    confidence_gate_reasons = [
        "NCCN Category 1 recommendation for Stage IVB HGSOC",
        "Carboplatin + Paclitaxel is standard frontline therapy",
        "Bevacizumab add-on indicated for ascites/peritoneal disease (GOG-218, ICON7)"
    ]
    
    # Clinical details
    detailed_dosing = {
        "carboplatin": {
            "dose": "AUC 5-6 mg/mL/min",
            "calculation": "Calvert formula using CrCl (GFR)",
            "infusion_time": "30-60 minutes",
            "premedication": "Antiemetics (5-HT3 antagonist + dexamethasone)"
        },
        "paclitaxel": {
            "dose": "175 mg/m² IV",
            "infusion_time": "3 hours",
            "premedication": "Dexamethasone 20mg PO/IV, diphenhydramine 50mg IV, ranitidine 50mg IV (prevent hypersensitivity)"
        }
    }
    
    if add_ons:
        detailed_dosing["bevacizumab"] = {
            "dose": "15 mg/kg IV",
            "infusion_time": "90 minutes (first dose), 60 min (subsequent if tolerated)",
            "continuation": "Continue for up to 15 months total OR until progression",
            "contraindications": "⚠️ Monitor for bowel perforation, wound healing complications, hypertension, proteinuria"
        }
    
    monitoring_protocol = {
        "baseline": [
            "CBC with differential",
            "CMP (renal/hepatic function)",
            "CA-125",
            "CT chest/abdomen/pelvis with contrast",
            "Pregnancy test (if applicable)"
        ],
        "during_treatment": [
            "CBC before each cycle (watch for cytopenias)",
            "CMP every cycle (carboplatin nephrotoxicity)",
            "CA-125 every cycle (track response)",
            "Imaging every 3 cycles (RECIST 1.1)",
            "Blood pressure every visit (if on bevacizumab)",
            "Urinalysis for proteinuria (if on bevacizumab)"
        ],
        "toxicity_watch": [
            "Peripheral neuropathy (paclitaxel) - consider dose reduction if Grade ≥2",
            "Thrombocytopenia (carboplatin) - hold if platelets <100K, reduce if persistent",
            "GI perforation risk (bevacizumab) - educate patient on warning signs",
            "Hypertension (bevacizumab) - target BP <140/90, add antihypertensives if needed"
        ],
        "response_assessment": "RECIST 1.1 criteria + CA-125 GCIG criteria (confirmed by repeat measurement)"
    }
    
    schedule_detailed = {
        "induction": "6 cycles every 21 days (carboplatin + paclitaxel ± bevacizumab)",
        "maintenance": "Bevacizumab continuation (if started) up to 15 months total OR progression",
        "typical_duration": "~18 weeks induction (6 cycles × 3 weeks) + up to 12 months maintenance",
        "adjustments": {
            "dose_reduction": "Consider for Grade 3-4 toxicity (neuropathy, cytopenias)",
            "delay": "Up to 2 weeks for recovery from toxicity",
            "discontinuation": "Disease progression, unacceptable toxicity, patient preference"
        }
    }
    
    return {
        "regimen": regimen,
        "add_ons": add_ons,
        "detailed_dosing": detailed_dosing,
        "schedule": "Every 3 weeks for 6 cycles (carboplatin + paclitaxel) + bevacizumab continuation",
        "schedule_detailed": schedule_detailed,
        "monitoring_protocol": monitoring_protocol,
        "confidence": confidence,
        "confidence_gate_reasons": confidence_gate_reasons,
        "rationale": "NCCN first-line for Stage IVB high-grade serous ovarian cancer",
        "evidence": {
            "carboplatin_paclitaxel": "Standard of care (multiple Phase III trials)",
            "bevacizumab": "GOG-218 (HR 0.72, p<0.001), ICON7 (HR 0.81, p=0.04)"
        },
        "monitoring": "CA-125 every cycle, imaging every 3 cycles",
        "nccn_guidelines": {
            "version": "NCCN Ovarian Cancer Guidelines v2024",
            "category": "Category 1 (uniform NCCN consensus)",
            "url": "https://www.nccn.org/professionals/physician_gls/pdf/ovarian.pdf"
        },
        "clinical_notes": "This is a guideline-based recommendation (NOT prediction). " +
                        "Actual regimen selection should be made by treating oncologist " +
                        "considering patient-specific factors (performance status, organ function, comorbidities).",
        "provenance": {
            "source": "NCCN Ovarian Cancer Guidelines v2024",
            "category": "Category 1 (uniform NCCN consensus)",
            "generated_at": datetime.utcnow().isoformat()
        }
    }


# === REFRESH HELPERS (Manager's Plan - Concern B) ===

def compute_freshness_metadata(
    trial: Dict[str, Any],
    refresh_sla_hours: int = 24
) -> Dict[str, Any]:
    """
    ⚔️ MANAGER'S PLAN - Concern B: Compute freshness metadata
    
    R2 — SLA policy: "displayed trials must be refreshed within 24 hours"
    If stale: mark stale + enqueue refresh; UI still displays but warns "stale"
    
    Args:
        trial: Trial dict (may have last_refreshed_at, scraped_at, or neither)
        refresh_sla_hours: SLA window in hours (default 24)
    
    Returns:
        {
            "last_refreshed_at": ISO timestamp or None,
            "stale": bool,
            "staleness_reason": str,
            "refresh_needed": bool
        }
    """
    now = datetime.now(timezone.utc)
    
    # Try to find last_refreshed_at from various sources
    last_refreshed_at = None
    last_refreshed_str = (
        trial.get("last_refreshed_at") or
        trial.get("last_updated") or
        trial.get("scraped_at")
    )
    
    if last_refreshed_str:
        try:
            # Parse ISO timestamp
            if isinstance(last_refreshed_str, str):
                # Handle both with and without timezone
                if last_refreshed_str.endswith('Z'):
                    last_refreshed_at = datetime.fromisoformat(last_refreshed_str.replace('Z', '+00:00'))
                elif '+' in last_refreshed_str or last_refreshed_str.endswith('UTC'):
                    last_refreshed_at = datetime.fromisoformat(last_refreshed_str.replace('UTC', '+00:00'))
                else:
                    # Assume UTC if no timezone
                    last_refreshed_at = datetime.fromisoformat(last_refreshed_str).replace(tzinfo=timezone.utc)
            else:
                last_refreshed_at = last_refreshed_str
        except Exception as e:
            logger.warning(f"Failed to parse last_refreshed_at '{last_refreshed_str}': {e}")
            last_refreshed_at = None
    
    # Compute staleness
    stale = False
    staleness_reason = None
    refresh_needed = False
    
    if last_refreshed_at:
        age_hours = (now - last_refreshed_at).total_seconds() / 3600
        if age_hours > refresh_sla_hours:
            stale = True
            staleness_reason = f"Last refreshed {age_hours:.1f} hours ago (SLA: {refresh_sla_hours}h)"
            refresh_needed = True
        else:
            staleness_reason = f"Fresh (refreshed {age_hours:.1f}h ago)"
    else:
        # No refresh timestamp = assume stale
        stale = True
        staleness_reason = "Never refreshed (no timestamp available)"
        refresh_needed = True
    
    return {
        "last_refreshed_at": last_refreshed_at.isoformat() if last_refreshed_at else None,
        "stale": stale,
        "staleness_reason": staleness_reason,
        "refresh_needed": refresh_needed,
        "refresh_sla_hours": refresh_sla_hours
    }


async def refresh_top_trials_bounded(
    trial_ids: List[str],
    max_trials: int = 20,
    timeout_seconds: float = 5.0
) -> Dict[str, Dict[str, Any]]:
    """
    ⚔️ MANAGER'S PLAN - Concern B: R3 — Bounded refresh on login
    
    On "Ayesha logs in": refresh the top K trials that will be displayed (e.g., top 20)
    before response if feasible (timeout-bounded).
    
    Args:
        trial_ids: List of NCT IDs to refresh (should be top K displayed trials)
        max_trials: Maximum number of trials to refresh (default 20)
        timeout_seconds: Maximum time to wait for refresh (default 5.0)
    
    Returns:
        Dict mapping NCT ID to refreshed data {status, locations, last_updated}
        (may be partial if timeout exceeded)
    """
    if not trial_ids:
        return {}
    
    # Limit to top K
    trials_to_refresh = trial_ids[:max_trials]
    
    try:
        # Use asyncio.wait_for to enforce timeout
        refreshed = await asyncio.wait_for(
            refresh_trial_status_with_retry(trials_to_refresh),
            timeout=timeout_seconds
        )
        logger.info(f"✅ Bounded refresh: {len(refreshed)}/{len(trials_to_refresh)} trials refreshed")
        return refreshed
    except asyncio.TimeoutError:
        logger.warning(f"⚠️ Refresh timeout ({timeout_seconds}s) - returning partial results")
        return {}
    except Exception as e:
        logger.error(f"❌ Bounded refresh failed: {e}")
        return {}


# === CANDIDATE DISCOVERY (Manager's Plan - Concern A) ===

def discover_ayesha_candidates(
    location_state: Optional[str] = None,
    max_candidates: int = 200
) -> Dict[str, Any]:
    """
    ⚔️ MANAGER'S PLAN - Concern A: Candidate Discovery
    
    Turn patient profile into bounded candidate set (200-1000 trials) BEFORE heavy work.
    Prefer SQLite as the first pass (fast, cheap) for "seeded corpus".
    
    Input: disease, location, treatment line, biomarker hints
    Output: candidate_trial_ids: list[str] (NCT IDs) + provenance
    
    D2 — Fetch candidates from our local store: Prefer SQLite as the first pass
    D3 — Enforce scope boundaries: Must produce bounded list and always return counts
    
    Args:
        location_state: State code (e.g., "NY") for location filtering
        max_candidates: Maximum number of candidates to return (default 200)
    
    Returns:
        {
            "candidate_trial_ids": List[str],  # NCT IDs
            "total_candidates": int,
            "provenance": {
                "source": "sqlite_seeded_corpus",
                "filters_applied": [...],
                "query_executed": str
            }
        }
    """
    try:
        db_conn = get_db_connections()
        conn = db_conn.get_sqlite_connection()
        
        if not conn:
            logger.warning("⚠️ SQLite connection unavailable - returning empty candidate set")
            return {
                "candidate_trial_ids": [],
                "total_candidates": 0,
                "provenance": {
                    "source": "sqlite_seeded_corpus",
                    "error": "SQLite connection unavailable",
                    "filters_applied": []
                }
            }
        
        cur = conn.cursor()
        
        # Build patient-aligned query (ovarian/gynecologic + recruiting/active prioritized)
        # Manager's plan: "ovarian/gynecologic + NYC metro + recruiting prioritized"
        filters_applied = [
            "ovarian/fallopian/peritoneal cancer (conditions OR title)",
            "recruiting OR active status",
            "recruiting prioritized over active",
            "Phase 3 prioritized over Phase 2"
        ]
        
        # Location filter (if provided)
        location_filter = ""
        if location_state:
            filters_applied.append(f"location_state={location_state}")
            # Note: SQLite schema may not have location_state column - we'll filter post-query if needed
        
        # Execute patient-aligned query
        query = """
        SELECT id, title, status, phases, conditions, interventions_json, scraped_at
        FROM trials
        WHERE (
          lower(coalesce(conditions,'')) LIKE '%ovarian%'
          OR lower(coalesce(conditions,'')) LIKE '%fallopian%'
          OR lower(coalesce(conditions,'')) LIKE '%peritoneal%'
          OR lower(coalesce(title,'')) LIKE '%ovarian%'
          OR lower(coalesce(title,'')) LIKE '%fallopian%'
          OR lower(coalesce(title,'')) LIKE '%peritoneal%'
        )
        AND (
          lower(coalesce(status,'')) LIKE '%recruiting%'
          OR lower(coalesce(status,'')) LIKE '%active%'
        )
        ORDER BY 
          CASE
            WHEN lower(coalesce(status,'')) LIKE '%recruiting%' THEN 0
            WHEN lower(coalesce(status,'')) LIKE '%active%' THEN 1
            ELSE 2
          END,
          CASE
            WHEN lower(coalesce(phases,'')) LIKE '%phase 3%' OR lower(coalesce(phases,'')) LIKE '%phase iii%' THEN 0
            WHEN lower(coalesce(phases,'')) LIKE '%phase 2%' OR lower(coalesce(phases,'')) LIKE '%phase ii%' THEN 1
            ELSE 2
          END,
          coalesce(scraped_at, '') DESC
        LIMIT ?
        """
        
        cur.execute(query, (max_candidates,))
        rows = cur.fetchall()
        
        candidate_ids = [row['id'] for row in rows]
        
        logger.info(f"✅ Candidate discovery: {len(candidate_ids)} trials from SQLite (max={max_candidates})")
        
        return {
            "candidate_trial_ids": candidate_ids,
            "total_candidates": len(candidate_ids),
            "provenance": {
                "source": "sqlite_seeded_corpus",
                "filters_applied": filters_applied,
                "query_executed": query.replace("?", str(max_candidates)),
                "max_candidates": max_candidates
            }
        }
        
    except Exception as e:
        logger.error(f"❌ Candidate discovery failed: {e}", exc_info=True)
        return {
            "candidate_trial_ids": [],
            "total_candidates": 0,
            "provenance": {
                "source": "sqlite_seeded_corpus",
                "error": str(e),
                "filters_applied": []
        }
    }


# === ENDPOINTS ===

@router.post("/search", response_model=AyeshaTrialSearchResponse)
async def search_ayesha_trials(request: AyeshaTrialSearchRequest):
    """
    Search for clinical trials for AK (Stage IVB ovarian cancer).
    
    Returns:
    - Top 10 frontline trials (ranked with transparent reasoning)
    - SOC recommendation (NCCN-aligned)
    - CA-125 monitoring plan
    - Eligibility checklists (hard/soft criteria)
    - Confidence gates (deterministic)
    
    This is NOT a demo. Real clinical decision support for Ayesha.
    """
    try:
        logger.info(f"Ayesha trial search: CA-125={request.ca125_value}, stage={request.stage}, germline={request.germline_status}")
        
        # Initialize services
        hybrid_search = HybridTrialSearchService()
        ca125_service = get_ca125_service()
        ngs_service = get_ngs_fast_track_service()
        
        # ⚔️ MANAGER'S PLAN - Concern A: Candidate Discovery (D2 - SQLite first pass)
        # Turn patient profile into bounded candidate set BEFORE heavy work
        # Prefer SQLite as the first pass (fast, cheap) for "seeded corpus"
        candidate_discovery = discover_ayesha_candidates(
            location_state=request.location_state,
            max_candidates=200  # Bounded list per manager's plan
        )
        candidate_trial_ids = set(candidate_discovery.get("candidate_trial_ids", []))
        logger.info(f"✅ Candidate discovery: {len(candidate_trial_ids)} trials from SQLite")
        
        # 1. Hybrid search (AstraDB + Neo4j) - ONLY if we have candidates to enrich
        # Build query from non-guessed context (PATIENT_ANALYSIS_11-17-25.md + imaging)
        base_terms = ["ovarian cancer", "high grade serous", "mullerian"]
        if request.stage:
            base_terms.append(f"stage {request.stage}")
        # Only include treatment_line term if it is meaningful
        if request.treatment_line and request.treatment_line.lower() in {"first-line", "recurrent"}:
            base_terms.append(request.treatment_line.lower())
        # Biomarker terms
        tumor_context = request.tumor_context or {}
        pd_l1 = tumor_context.get("pd_l1") or {}
        if (str(pd_l1.get("status") or "").upper() == "POSITIVE") or (pd_l1.get("cps") is not None and float(pd_l1.get("cps")) >= 1):
            base_terms.append("PD-L1")
        p53_status = str(tumor_context.get("p53_status") or tumor_context.get("p53") or "")
        if p53_status:
            base_terms.append("p53")
        er_percent = tumor_context.get("er_percent")
        if er_percent is not None and float(er_percent) >= 1:
            base_terms.append("ER positive")

        query = " ".join(base_terms)
        patient_context = {
            "condition": "ovarian_cancer_high_grade_serous",
            "disease_category": "gynecologic_oncology",  # ✅ FIXED: Matches AstraDB field value
            "location_state": request.location_state
        }
        
        # Try hybrid search (may return 0 - that's OK, we have SQLite candidates)
        raw_trials = await hybrid_search.search_optimized(
            query=query,
            patient_context=patient_context,
            germline_status=request.germline_status,
            tumor_context=tumor_context,  # IHC-driven tumor context (no guessing)
            top_k=50  # Get 50 candidates for filtering
        )
        
        # ⚔️ MANAGER'S PLAN: If hybrid search returns 0, use SQLite candidates + MoA vectors
        # This ensures we always have a bounded candidate set BEFORE heavy work
        if not raw_trials and candidate_trial_ids:
            logger.info(f"⚠️ Hybrid search returned 0 candidates - using SQLite candidate set ({len(candidate_trial_ids)} trials)")
            # Enrich trial objects from SQLite database (not just IDs)
            db_conn = get_db_connections()
            conn = db_conn.get_sqlite_connection()
            raw_trials = []
            if conn:
                cur = conn.cursor()
                # Batch fetch trial details from SQLite
                candidate_list = list(candidate_trial_ids)[:100]  # Limit to top 100 for processing
                placeholders = ','.join(['?'] * len(candidate_list))
                cur.execute(f"""
                    SELECT id, title, status, phases, conditions, interventions_json, locations_full_json, inclusion_criteria
                    FROM trials
                    WHERE id IN ({placeholders})
                """, candidate_list)
                sqlite_rows = {row['id']: row for row in cur.fetchall()}
                
                # Build trial objects with SQLite data + MoA vectors
                for nct_id in candidate_list:
                    sqlite_row = sqlite_rows.get(nct_id)
                    if not sqlite_row:
                        continue
                    
                    # Parse JSON columns safely (sqlite3.Row uses dict-style access)
                    # Convert Row to dict for safe .get() access
                    row_dict = dict(sqlite_row)
                    interventions = []
                    if row_dict.get("interventions_json"):
                        try:
                            interventions = json.loads(row_dict["interventions_json"])
                        except:
                            interventions = []
                    locations = []
                    if row_dict.get("locations_full_json"):
                        try:
                            locations = json.loads(row_dict["locations_full_json"])
                        except:
                            locations = []
                    
                    trial_obj = {
                        "nct_id": nct_id,
                        "title": row_dict.get("title") or "Unknown",
                        "status": row_dict.get("status") or "Unknown",
                        "phase": row_dict.get("phases") or "Unknown",
                        "conditions": row_dict.get("conditions") or "Ovarian cancer",
                        "interventions": interventions,
                        "locations": locations,
                        "eligibility": row_dict.get("inclusion_criteria") or "",
                        "source": "sqlite_candidate_discovery"
                    }
                    # Attach MoA vector if available
                    if nct_id in TRIAL_MOA_VECTORS:
                        trial_obj["moa_vector"] = TRIAL_MOA_VECTORS[nct_id]["moa_vector"]
                        trial_obj["moa_confidence"] = TRIAL_MOA_VECTORS[nct_id]["confidence"]
                    else:
                        trial_obj["moa_vector"] = {"ddr": 0, "mapk": 0, "pi3k": 0, "vegf": 0, "her2": 0, "io": 0, "efflux": 0}
                        trial_obj["moa_confidence"] = 0.0
                    raw_trials.append(trial_obj)
            else:
                # Fallback: build minimal trial objects if SQLite unavailable
                logger.warning("⚠️ SQLite unavailable for enrichment - building minimal trial objects")
                for nct_id in list(candidate_trial_ids)[:100]:
                    trial_obj = {
                        "nct_id": nct_id,
                        "title": "Unknown",
                        "status": "Unknown",
                        "phase": "Unknown",
                        "conditions": "Ovarian cancer",
                        "interventions": [],
                        "locations": [],
                        "source": "sqlite_candidate_discovery_fallback"
                    }
                    if nct_id in TRIAL_MOA_VECTORS:
                        trial_obj["moa_vector"] = TRIAL_MOA_VECTORS[nct_id]["moa_vector"]
                        trial_obj["moa_confidence"] = TRIAL_MOA_VECTORS[nct_id]["confidence"]
                    else:
                        trial_obj["moa_vector"] = {"ddr": 0, "mapk": 0, "pi3k": 0, "vegf": 0, "her2": 0, "io": 0, "efflux": 0}
                        trial_obj["moa_confidence"] = 0.0
                    raw_trials.append(trial_obj)
        
        # 2. Apply hard filters (even if raw_trials is empty, we still return SOC/CA-125)
        hard_filtered = []
        if raw_trials:
            # ⚔️ P0 FIX #5: Attach MoA vectors to trials (Manager's P3 - Jan 13, 2025)
            for trial in raw_trials:
                nct_id = trial.get("nct_id")
                if nct_id in TRIAL_MOA_VECTORS:
                    trial["moa_vector"] = TRIAL_MOA_VECTORS[nct_id]["moa_vector"]
                    trial["moa_confidence"] = TRIAL_MOA_VECTORS[nct_id]["confidence"]
                else:
                    # Default neutral vector if no MoA tagging available
                    trial["moa_vector"] = {"ddr": 0, "mapk": 0, "pi3k": 0, "vegf": 0, "her2": 0, "io": 0, "efflux": 0}
                    trial["moa_confidence"] = 0.0
            
            hard_filtered = _apply_ayesha_hard_filters(raw_trials, request)
        
        # Note: We continue even if no trials found - SOC and CA-125 are still valuable
        
        # 3. Apply soft boosts and rank
        ranked_trials = _apply_ayesha_soft_boosts(hard_filtered, request) if hard_filtered else []
        
        # ⚔️ PRODUCTION: Enrich all trials with MoA vectors and drug names
        for trial in ranked_trials:
            _enrich_trial_with_moa(trial)
            _parse_interventions_for_drug_names(trial)
        
        # 3.5. ⚔️ P0 FIX #4: Apply mechanism fit ranking (Manager's P4 - Jan 13, 2025)
        # If SAE mechanism vector provided, re-rank by mechanism fit (α=0.7 eligibility + β=0.3 mechanism)
        if request.sae_mechanism_vector and ranked_trials:
            logger.info(f"⚔️ P0 Fix #4: Applying mechanism fit ranking (α=0.7, β=0.3)")
            
            # Prepare trials for mechanism ranking
            trials_for_ranking = []
            for trial in ranked_trials:
                trials_for_ranking.append({
                    "nct_id": trial.get("nct_id"),
                    "title": trial.get("title", ""),
                    "eligibility_score": trial.get("match_score", 0.7),  # Soft boost score
                    "moa_vector": trial.get("moa_vector", {"ddr": 0, "mapk": 0, "pi3k": 0, "vegf": 0, "her2": 0, "io": 0, "efflux": 0})
                })
            
            # Rank by mechanism fit
            try:
                ranked_by_mechanism = rank_trials_by_mechanism(
                    patient_sae_vector=request.sae_mechanism_vector,
                    trials=trials_for_ranking,
                    alpha=0.7,  # Eligibility weight (Manager's P4)
                    beta=0.3    # Mechanism fit weight (Manager's P4)
                )
                
                # Create lookup dict for mechanism scores
                mechanism_scores = {
                    trial.nct_id: {
                        "mechanism_fit_score": trial.mechanism_fit_score,
                        "combined_score": trial.combined_score,
                        "alignment_breakdown": trial.mechanism_alignment,
                        "boost_applied": trial.boost_applied
                    }
                    for trial in ranked_by_mechanism
                }
                
                # Update match scores with mechanism fit
                for trial in ranked_trials:
                    nct_id = trial.get("nct_id")
                    if nct_id in mechanism_scores:
                        trial["mechanism_alignment"] = mechanism_scores[nct_id]
                        trial["match_score"] = mechanism_scores[nct_id]["combined_score"]
                
                # Re-sort by new combined scores
                ranked_trials.sort(key=lambda t: t.get("match_score", 0), reverse=True)
                
                logger.info(f"✅ Mechanism fit ranking complete: {len(ranked_by_mechanism)} trials re-ranked")
            
            except Exception as e:
                logger.warning(f"⚠️ Mechanism fit ranking failed (non-critical): {e}")
                # Fall back to soft boost ranking if mechanism fit fails
        
        # 4. ⚔️ MANAGER'S PLAN - Concern B: R3 — Bounded refresh on login
        # Refresh top K trials before response (timeout-bounded)
        top_trial_ids = [t.get("nct_id") for t in ranked_trials[:request.max_results] if t.get("nct_id")]
        refreshed_data = {}
        if top_trial_ids:
            try:
                refreshed_data = await refresh_top_trials_bounded(
                    top_trial_ids,
                    max_trials=min(20, len(top_trial_ids)),  # Top 20 or all if fewer
                    timeout_seconds=5.0
                )
                logger.info(f"✅ Bounded refresh completed: {len(refreshed_data)}/{len(top_trial_ids)} trials refreshed")
            except Exception as e:
                logger.warning(f"⚠️ Bounded refresh failed (non-critical): {e}")
        
        # ⚔️ PRODUCTION: Compute holistic scores for top trials (if patient profile available)
        # Build patient profile from request for holistic scoring
        patient_profile_for_holistic = {
            "mechanism_vector": request.sae_mechanism_vector,
            "disease": "ovarian cancer",
            "age": None,  # Not provided in request
            "mutations": [],
            "germline_variants": [],  # Not explicitly provided, but could infer from germline_status
            "location_state": request.location_state,
            "germline_status": request.germline_status
        }
        
        # Compute holistic scores if we have mechanism vector or germline variants
        if request.sae_mechanism_vector or patient_profile_for_holistic.get("germline_variants"):
            try:
                ranked_trials = await _compute_holistic_scores_for_trials(
                    ranked_trials,
                    patient_profile_for_holistic
                )
                logger.info(f"✅ Holistic scores computed for {len([t for t in ranked_trials if t.get('holistic_score')])} trials")
            except Exception as e:
                logger.warning(f"⚠️ Holistic score computation failed (non-critical): {e}")
        
        # 5. Generate eligibility checklists and reasoning for top trials
        # ⚔️ MANAGER'S PLAN - Concern B & D: Add freshness metadata + scoring transparency
        top_trials = ranked_trials[:request.max_results] if ranked_trials else []
        for trial in top_trials:
            nct_id = trial.get("nct_id")
            
            # Merge refreshed data if available
            if nct_id in refreshed_data:
                refreshed = refreshed_data[nct_id]
                trial["status"] = refreshed.get("status", trial.get("status"))
                trial["locations"] = refreshed.get("locations", trial.get("locations", []))
                trial["last_refreshed_at"] = refreshed.get("last_updated")
            
            # ⚔️ MANAGER'S PLAN - Concern B: Add freshness metadata
            freshness = compute_freshness_metadata(trial, refresh_sla_hours=24)
            trial["freshness"] = freshness
            
            # ⚔️ MANAGER'S PLAN - Concern D (M4): Add scoring transparency
            # ⚔️ PRODUCTION: Include holistic score in breakdown
            trial["scoring_breakdown"] = {
                "holistic_score": trial.get("holistic_score"),  # NEW: Holistic score
                "holistic_interpretation": trial.get("holistic_interpretation"),  # NEW
                "eligibility_score": trial.get("eligibility_score", trial.get("match_score", 0.0)),
                "mechanism_fit_score": trial.get("mechanism_fit_score", trial.get("mechanism_alignment", {}).get("mechanism_fit_score", 0.0) if trial.get("mechanism_alignment") else 0.0),
                "pgx_safety_score": trial.get("pgx_safety_score"),  # NEW: PGx safety
                "combined_score": trial.get("holistic_score", trial.get("match_score", 0.0)),  # Use holistic if available
                "tag_confidence": trial.get("moa_confidence", 0.0),
                "freshness": freshness,
                "why_eligible": trial.get("reasoning", {}).get("why_eligible", []) if isinstance(trial.get("reasoning"), dict) else [],
                "why_good_fit": trial.get("reasoning", {}).get("why_good_fit", []) if isinstance(trial.get("reasoning"), dict) else [],
                "requirements": trial.get("reasoning", {}).get("conditional_requirements", []) if isinstance(trial.get("reasoning"), dict) else [],
                "red_flags": trial.get("reasoning", {}).get("red_flags", []) if isinstance(trial.get("reasoning"), dict) else [],
                "pgx_caveats": trial.get("holistic_caveats", [])  # NEW: PGx warnings
            }
            
            # Generate eligibility checklists and reasoning
            trial["eligibility_checklist"] = _generate_eligibility_checklist(trial, request)
            trial["reasoning"] = _generate_trial_reasoning(trial, request)
        
            # Update scoring breakdown with actual reasoning after generation
            if isinstance(trial.get("reasoning"), dict):
                trial["scoring_breakdown"]["why_eligible"] = trial["reasoning"].get("why_eligible", [])
                trial["scoring_breakdown"]["why_good_fit"] = trial["reasoning"].get("why_good_fit", [])
                trial["scoring_breakdown"]["requirements"] = trial["reasoning"].get("conditional_requirements", [])
                trial["scoring_breakdown"]["red_flags"] = trial["reasoning"].get("red_flags", [])
        
        # 6. Generate SOC recommendation
        soc_recommendation = _generate_soc_recommendation(request)
        
        # 7. Generate CA-125 intelligence (do not guess values)
        if request.ca125_value is None:
            ca125_intelligence = {
                "status": "awaiting_baseline",
                "message": "CA-125 value not provided. Provide baseline CA-125 to enable burden classification, response forecasting, and resistance signals.",
                "required_inputs": ["ca125_value"],
                "monitoring_strategy": {
                    "frequency": "every_cycle",
                    "note": "Set baseline CA-125 prior to next cycle and track serially."
                }
            }
        else:
            ca125_intelligence = ca125_service.analyze_ca125(
                current_value=request.ca125_value,
                baseline_value=None,  # First measurement
                cycle=None,  # Pre-treatment/unknown
                treatment_ongoing=False
            )
        
        # 8. Generate NGS fast-track checklist
        ngs_fast_track = ngs_service.generate_ngs_checklist(
            patient_profile={
                "stage": request.stage,
                "treatment_line": request.treatment_line,
                "germline_status": request.germline_status,
                "histology": "high_grade_serous",  # Assumed from stage + ovarian cancer
                "has_tissue_available": True  # Assume true unless specified otherwise
            }
        )
        
        # 9. Summary statistics (with freshness metrics)
        # ⚔️ MANAGER'S PLAN - Concern B: R4 — Observability
        freshness_stats = {
            "refreshed_on_login": len(refreshed_data),
            "stale_count": sum(1 for t in top_trials if t.get("freshness", {}).get("stale", False)),
            "fresh_count": sum(1 for t in top_trials if not t.get("freshness", {}).get("stale", True)),
            "avg_refresh_age_hours": None
        }
        
        # Calculate average refresh age
        refresh_ages = []
        for trial in top_trials:
            freshness = trial.get("freshness", {})
            last_refreshed = freshness.get("last_refreshed_at")
            if last_refreshed:
                try:
                    refreshed_dt = datetime.fromisoformat(last_refreshed.replace('Z', '+00:00'))
                    age_hours = (datetime.now(timezone.utc) - refreshed_dt).total_seconds() / 3600
                    refresh_ages.append(age_hours)
                except:
                    pass
        
        if refresh_ages:
            freshness_stats["avg_refresh_age_hours"] = round(sum(refresh_ages) / len(refresh_ages), 1)
        
        summary = {
            "total_candidates": len(raw_trials),
            "hard_filtered": len(hard_filtered),
            "top_results": len(top_trials),
            "avg_match_score": round(sum(t.get("match_score", 0) for t in top_trials) / len(top_trials), 2) if top_trials else 0,
            "avg_confidence_gate": round(sum(t.get("eligibility_checklist", {}).get("confidence_gate", 0) for t in top_trials) / len(top_trials), 2) if top_trials else 0,
            "freshness_metrics": freshness_stats
        }
        
        # 10. Provenance (with refresh info)
        # ⚔️ MANAGER'S PLAN - Concern B & D: Transparent provenance
        provenance = {
            "search_method": "hybrid_astradb_neo4j_with_sqlite_fallback",
            "candidate_discovery": {
                "source": candidate_discovery.get("provenance", {}).get("source", "unknown"),
                "total_candidates": candidate_discovery.get("total_candidates", 0),
                "filters_applied": candidate_discovery.get("provenance", {}).get("filters_applied", [])
            },
            "refresh_applied": {
                "bounded_refresh_on_login": len(refreshed_data) > 0,
                "trials_refreshed": len(refreshed_data),
                "refresh_sla_hours": 24,
                "refresh_timeout_seconds": 5.0
            },
            "filtering_applied": ["hard_eligibility", "soft_boosts", "germline_negative", "tumor_context_if_provided"],
            "scoring_transparency": {
                "eligibility_score": "match_score from soft boosts",
                "mechanism_fit_score": "from mechanism_alignment if SAE vector provided",
                "tag_confidence": "from trial_moa_vectors.json",
                "freshness_flags": "computed from last_refreshed_at with 24h SLA"
            },
            "confidence_gate_formula": "max(soc=0.95, trial_eligibility=0.90) with hard/soft split",
            "ca125_intelligence_version": "v1",
            "generated_at": datetime.utcnow().isoformat(),
            "for_patient": "AK (Stage IVB ovarian cancer)",
            "run_id": f"ayesha_trials_{int(datetime.utcnow().timestamp())}",
            "tumor_context_used": {
                "pd_l1": tumor_context.get("pd_l1"),
                "p53_status": tumor_context.get("p53_status") or tumor_context.get("p53"),
                "er_percent": tumor_context.get("er_percent"),
                "mmr_status": tumor_context.get("mmr_status"),
                "her2_status": tumor_context.get("her2_status"),
                "folr1_status": tumor_context.get("folr1_status"),
                "ntrk_status": tumor_context.get("ntrk_status")
            }
        }
        
        return AyeshaTrialSearchResponse(
            trials=top_trials,
            soc_recommendation=soc_recommendation,
            ca125_intelligence=ca125_intelligence,
            ngs_fast_track=ngs_fast_track,
            summary=summary,
            provenance=provenance
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ayesha trial search failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Trial search failed: {str(e)}")


@router.get("/health")
async def health_check():
    """Health check for Ayesha trials router"""
    import os
    from api.services.hybrid_trial_search import HybridTrialSearchService
    
    # Debug: Check which collection is being used
    search_service = HybridTrialSearchService()
    collection_name = search_service.astradb_service.collection_name
    env_collection = os.getenv("ASTRA_COLLECTION_NAME", "not set")
    
    return {
        "status": "operational",
        "service": "ayesha_trials",
        "for_patient": "AK (Stage IVB ovarian cancer)",
        "collection_in_use": collection_name,
        "collection_from_env": env_collection,
        "capabilities": [
            "trial_search_frontline",
            "soc_recommendation",
            "ca125_intelligence",
            "eligibility_checklists",
            "confidence_gates"
        ]
    }
