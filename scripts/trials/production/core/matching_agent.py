"""
⚔️ PRODUCTION - Concern D: Patient Matching + Dossier Agent

Purpose: Compute eligibility, mechanism fit ranking, and generate reasoning/dossiers
based on candidates (Concern A), refreshed data (Concern B), and offline tags (Concern C).

Non-negotiables (Manager's Plan):
- M1: Hard filtering (stage, treatment line, recruiting, location)
- M2: Eligibility checklists (hard/soft criteria with reasoning)
- M3: Mechanism fit ranking (if SAE vector provided)
- M4: Scoring transparency (why eligible, why good fit)
- M5: Holistic score computation (Mechanism Fit + Eligibility + PGx Safety)

Consolidated from:
- trial_matching_agent.py (mechanism fit)
- eligibility_filters.py (hard/soft criteria)
- holistic_score_service.py (unified scoring)

Source of Truth: .cursor/ayesha/TRIAL_TAGGING_ANALYSIS_AND_NEXT_ROADBLOCK.md (lines 508-556)
"""

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent.parent))

# Import production core modules
from .discovery_agent import discover_candidates
from .refresh_agent import refresh_trials_incremental

# Import services
try:
    from api.services.holistic_score_service import get_holistic_score_service
    HOLISTIC_SCORE_AVAILABLE = True
except ImportError:
    HOLISTIC_SCORE_AVAILABLE = False
    logger.warning("⚠️ Holistic score service not available")

try:
    from api.services.mechanism_fit_ranker import MechanismFitRanker
    MECHANISM_RANKER_AVAILABLE = True
except ImportError:
    MECHANISM_RANKER_AVAILABLE = False
    logger.warning("⚠️ Mechanism fit ranker not available")

# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load MoA vectors
TRIAL_MOA_VECTORS = {}
try:
    moa_path = os.path.join(
        Path(__file__).resolve().parent.parent.parent.parent.parent,
        "api/resources/trial_moa_vectors.json"
    )
    if os.path.exists(moa_path):
        with open(moa_path, "r") as f:
            TRIAL_MOA_VECTORS = json.load(f)
        logger.info(f"✅ Loaded {len(TRIAL_MOA_VECTORS)} trial MoA vectors")
except Exception as e:
    logger.error(f"❌ Failed to load MoA vectors: {e}")


def _enrich_trial_with_moa(trial: Dict[str, Any]) -> Dict[str, Any]:
    """Attach MoA vector from trial_moa_vectors.json."""
    nct_id = trial.get("nct_id") or trial.get("nctId")
    if nct_id and nct_id in TRIAL_MOA_VECTORS:
        moa_data = TRIAL_MOA_VECTORS[nct_id]
        trial["moa_vector"] = moa_data.get("moa_vector", {})
        trial["moa_confidence"] = moa_data.get("confidence", 0.0)
        trial["moa_source"] = moa_data.get("source", "unknown")
    else:
        trial["moa_vector"] = {
            "ddr": 0.0, "mapk": 0.0, "pi3k": 0.0,
            "vegf": 0.0, "her2": 0.0, "io": 0.0, "efflux": 0.0
        }
        trial["moa_confidence"] = 0.0
        trial["moa_source"] = "default"
    return trial


def _parse_interventions_for_drug_names(trial: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Parse interventions_json or interventions string and extract drug names for PGx screening."""
    interventions = []
    drug_names_extracted = []
    
    # Try interventions_json first (structured data)
    interventions_json = trial.get("interventions_json")
    if interventions_json:
        try:
            if isinstance(interventions_json, str):
                interventions_data = json.loads(interventions_json)
            else:
                interventions_data = interventions_json
            
            for intervention in interventions_data if isinstance(interventions_data, list) else [interventions_data]:
                if isinstance(intervention, dict):
                    # Structured dict format
                    name = intervention.get("name", "") or intervention.get("intervention_name", "")
                    intervention_type = intervention.get("type", "") or intervention.get("intervention_type", "")
                    
                    if intervention_type.upper() in ["DRUG", "BIOLOGICAL", "BIOLOGICAL/VACCINE"]:
                        if name:
                            drug_names_extracted.append(name.lower().strip())
                        if "other_name" in intervention:
                            drug_names_extracted.append(intervention["other_name"].lower().strip())
                elif isinstance(intervention, str) and intervention.strip():
                    # Simple string list format (common case)
                    drug_names_extracted.append(intervention.lower().strip())
        except (json.JSONDecodeError, TypeError, AttributeError) as e:
            logger.warning(f"Failed to parse interventions_json for {trial.get('nct_id')}: {e}")
    
    # Fallback to interventions string if no drugs extracted
    if not drug_names_extracted:
        interventions_str = trial.get("interventions")
        if interventions_str and isinstance(interventions_str, str):
            # Parse comma-separated or similar format
            for drug in interventions_str.split(","):
                drug = drug.strip()
                if drug and len(drug) > 2:  # Ignore very short entries
                    drug_names_extracted.append(drug.lower())
    
    # Build standardized interventions list for PGx screening
    if drug_names_extracted:
        unique_drugs = list(set(drug_names_extracted))
        for drug_name in unique_drugs:
            interventions.append({
                "name": drug_name,
                "type": "DRUG",
                "drug_names": [drug_name]
            })
        trial["interventions"] = interventions
    elif "interventions" not in trial:
        trial["interventions"] = []
    
    return interventions


async def match_patient_to_trials(
    patient_profile: Dict[str, Any],
    max_results: int = 10
) -> Dict[str, Any]:
    """
    Main matching function - integrates all concerns (A, B, C, D).
    
    Flow:
    1. Discover candidates (Concern A)
    2. Refresh trial data (Concern B)
    3. Attach MoA vectors (Concern C)
    4. Parse drug names
    5. Compute holistic scores (Concern D)
    6. Rank and return
    
    Args:
        patient_profile: Patient profile dict with:
            - disease: Cancer type
            - stage: Cancer stage
            - location_state: State for filtering
            - germline_variants: List of {gene, variant} for PGx screening
            - mechanism_vector: 7D SAE vector (optional)
            - age: Patient age (optional)
            - mutations: List of mutations (optional)
        max_results: Maximum number of trials to return
    
    Returns:
        Dict with:
            - matches: List of scored trial matches
            - total_candidates: Number of candidates discovered
            - total_scored: Number of trials scored
            - provenance: Source tracking
    """
    logger.info(f"⚔️ Patient Matching + Dossier: Starting for {patient_profile.get('disease')}")
    
    # Step 1: Discover candidates (Concern A)
    try:
        discovery_result = await discover_candidates(patient_profile)
        
        # ⚔️ CRITICAL FIX: Extract BOTH candidate_trial_ids AND candidates (full objects)
        # Discovery returns: {"candidate_trial_ids": [...], "candidates": [full_trial_objects...]}
        candidate_trial_ids = []
        discovery_candidates = []  # Full trial objects from discovery (with status!)
        discovery_candidates_lookup = {}  # NCT ID -> full trial object
        
        if isinstance(discovery_result, dict):
            # Extract NCT IDs
            candidate_trial_ids = discovery_result.get("candidate_trial_ids", [])
            
            # ⚔️ CRITICAL: Extract full candidate objects (these have status!)
            discovery_candidates = discovery_result.get("candidates", [])
            
            # Build lookup dict from discovery candidates
            for candidate in discovery_candidates:
                if isinstance(candidate, dict):
                    nct_id = candidate.get("nct_id") or candidate.get("id") or candidate.get("nctId")
                    if nct_id:
                        nct_id = str(nct_id)
                        discovery_candidates_lookup[nct_id] = candidate.copy()  # Preserve full data
                        if nct_id not in candidate_trial_ids:
                            candidate_trial_ids.append(nct_id)
            
            # If no candidates list, build from candidate_trial_ids
            if not discovery_candidates:
                candidate_trial_ids = discovery_result.get("candidate_trial_ids", [])
            
            # Ensure candidate_trial_ids are strings
            if candidate_trial_ids and isinstance(candidate_trial_ids[0], dict):
                candidate_trial_ids = [c.get("nct_id") or c.get("id") for c in candidate_trial_ids if isinstance(c, dict)]
                
        elif isinstance(discovery_result, list):
            # If discovery_result is directly a list of candidates
            discovery_candidates = discovery_result
            for c in discovery_result:
                if isinstance(c, dict):
                    nct_id = c.get("nct_id") or c.get("id") or c.get("nctId")
                    if nct_id:
                        nct_id = str(nct_id)
                        discovery_candidates_lookup[nct_id] = c.copy()
                        candidate_trial_ids.append(nct_id)
                elif isinstance(c, str):
                    candidate_trial_ids.append(str(c))
        
        # Remove None values and ensure all are strings
        candidate_trial_ids = [str(tid) for tid in candidate_trial_ids if tid]
        
        logger.info(f"✅ Discovery: {len(candidate_trial_ids)} candidate IDs, {len(discovery_candidates)} full objects")
        logger.info(f"   Discovery candidates lookup: {len(discovery_candidates_lookup)} trials with status preserved")
    except Exception as e:
        logger.error(f"❌ Discovery failed: {e}", exc_info=True)
        return {
            "matches": [],
            "total_candidates": 0,
            "total_scored": 0,
            "provenance": {
                "error": str(e),
                "error_type": type(e).__name__
            }
        }
    
    if not candidate_trial_ids:
        logger.warning("⚠️ No candidates discovered")
        return {
            "matches": [],
            "total_candidates": 0,
            "total_scored": 0,
            "provenance": discovery_result.get("provenance", {}) if isinstance(discovery_result, dict) else {}
        }
    
    # Step 2: Refresh trial data (Concern B)
    # ⚔️ FIX: Handle refresh_trials_incremental return format (may be dict or list)
    try:
        refresh_result = await refresh_trials_incremental(candidate_trial_ids[:max_results * 2])
        if isinstance(refresh_result, dict):
            refreshed_trials = refresh_result  # Dict mapping NCT ID to trial data
        elif isinstance(refresh_result, list):
            # Convert list to dict format
            refreshed_trials = {t.get("nct_id") or t.get("id"): t for t in refresh_result}
        else:
            refreshed_trials = {}
        logger.info(f"✅ Refresh: {len(refreshed_trials)} trials refreshed")
    except Exception as e:
        logger.warning(f"⚠️ Refresh failed: {e}, using candidates without refresh")
        refreshed_trials = {}
    
    # Step 3: Enrich with MoA vectors (Concern C) and drug names
    # ⚔️ CRITICAL FIX: Use discovery candidates as fallback when refresh fails
    enriched_trials = []
    for nct_id in candidate_trial_ids[:max_results * 3]:  # Over-fetch for filtering
        # Priority 1: Try refreshed data (may have fresh status)
        trial = {}
        if isinstance(refreshed_trials, dict):
            trial = refreshed_trials.get(nct_id, {})
        elif isinstance(refreshed_trials, list):
            # Find trial in list
            trial = next((t for t in refreshed_trials if (t.get("nct_id") or t.get("id")) == nct_id), {})
        
        # Priority 2: Fall back to discovery candidate (preserves status and other fields!)
        if not trial or not trial.get("status") or not trial.get("overall_status"):
            discovery_trial = discovery_candidates_lookup.get(nct_id)
            if discovery_trial:
                logger.debug(f"Using discovery data for {nct_id} (refresh unavailable or incomplete)")
                # Merge: discovery data as base, refresh data overwrites if present
                if trial:
                    discovery_trial.update(trial)  # Refresh data overwrites discovery
                trial = discovery_trial.copy()
            else:
                # Priority 3: Build minimal trial dict only if no discovery data
                logger.warning(f"No discovery or refresh data for {nct_id} - creating minimal dict")
                trial = {"nct_id": nct_id}
        
        # Ensure nct_id is set
        trial["nct_id"] = trial.get("nct_id") or trial.get("id") or nct_id
        
        # ⚔️ CRITICAL FIX: Preserve status from discovery if present
        if not trial.get("status") and not trial.get("overall_status"):
            # Try to get from discovery candidate
            discovery_trial = discovery_candidates_lookup.get(nct_id)
            if discovery_trial:
                trial["status"] = discovery_trial.get("status") or discovery_trial.get("overall_status")
                trial["overall_status"] = discovery_trial.get("overall_status") or discovery_trial.get("status")
        
        # Enrich with MoA vectors
        trial = _enrich_trial_with_moa(trial)
        
        # Parse drug names
        _parse_interventions_for_drug_names(trial)
        
        # ⚔️ CRITICAL FIX: Preserve status from discovery, only use UNKNOWN as last resort
        # Status should already be set from discovery or refresh above
        if not trial.get("overall_status"):
            trial["overall_status"] = trial.get("status") or trial.get("overall_status") or "UNKNOWN"
        if not trial.get("status"):
            trial["status"] = trial.get("overall_status") or "UNKNOWN"
        
        # Preserve conditions from discovery
        if not trial.get("conditions"):
            trial["conditions"] = [patient_profile.get("disease", "Unknown")]
        
        enriched_trials.append(trial)
    
    logger.info(f"✅ Enrichment: {len(enriched_trials)} trials enriched")
    
    # Step 4: Compute holistic scores (Concern D)
    if HOLISTIC_SCORE_AVAILABLE and enriched_trials:
        try:
            holistic_service = get_holistic_score_service()
            
            # Extract patient data for holistic scoring
            pharmacogenes = patient_profile.get("germline_variants", [])
            
            scored_results = await holistic_service.compute_batch(
                patient_profile=patient_profile,
                trials=enriched_trials,
                pharmacogenes=pharmacogenes
            )
            
            # Merge holistic scores back into trials
            score_lookup = {r.get("nct_id"): r for r in scored_results}
            for trial in enriched_trials:
                nct_id = trial.get("nct_id")
                if nct_id in score_lookup:
                    score_data = score_lookup[nct_id]
                    trial["holistic_score"] = score_data.get("holistic_score", 0.0)
                    trial["holistic_interpretation"] = score_data.get("interpretation")
                    trial["holistic_recommendation"] = score_data.get("recommendation")
                    trial["holistic_caveats"] = score_data.get("caveats", [])
                    trial["mechanism_fit_score"] = score_data.get("mechanism_fit_score", 0.0)
                    trial["eligibility_score"] = score_data.get("eligibility_score", 0.0)
                    trial["pgx_safety_score"] = score_data.get("pgx_safety_score", 1.0)
            
            # Sort by holistic score
            enriched_trials.sort(
                key=lambda t: t.get("holistic_score", 0.0),
                reverse=True
            )
            
            logger.info(f"✅ Holistic scoring: {len(scored_results)} trials scored")
        except Exception as e:
            logger.error(f"❌ Holistic scoring failed: {e}", exc_info=True)
    
    # Step 5: Return top matches
    top_matches = enriched_trials[:max_results]
    
    return {
        "matches": top_matches,
        "total_candidates": len(candidate_trial_ids),
        "total_scored": len(enriched_trials),
        "moa_coverage": f"{len([t for t in enriched_trials if t.get('moa_confidence', 0) > 0])}/{len(enriched_trials)}",
        "provenance": {
            "discovery_method": discovery_result.get("provenance", {}).get("source", "unknown"),
            "holistic_scoring": HOLISTIC_SCORE_AVAILABLE and len(top_matches) > 0,
            "mechanism_fit_applied": patient_profile.get("mechanism_vector") is not None,
            "pgx_screening_applied": len(patient_profile.get("germline_variants", [])) > 0,
            "generated_at": datetime.utcnow().isoformat()
        }
    }


async def main():
    """Example usage of matching agent."""
    patient_profile = {
        "disease": "Ovarian Cancer",
        "stage": "IV",
        "location_state": "NY",
        "mechanism_vector": [0.88, 0.12, 0.15, 0.10, 0.05, 0.2, 0.0],  # DDR-high
        "germline_variants": [{"gene": "DPYD", "variant": "*2A"}],
        "age": 65,
        "mutations": [{"gene": "BRCA1"}, {"gene": "TP53"}]
    }
    
    result = await match_patient_to_trials(patient_profile, max_results=10)
    print(f"✅ Found {len(result['matches'])} matches")
    print(f"   Total candidates: {result['total_candidates']}")
    print(f"   MoA coverage: {result['moa_coverage']}")
    print(f"   Holistic scoring: {result['provenance']['holistic_scoring']}")


if __name__ == "__main__":
    asyncio.run(main())
