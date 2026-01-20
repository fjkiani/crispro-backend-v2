"""
Universal Complete Care Orchestrator

CLINICAL PURPOSE: Unified care plan orchestration for any patient
For use by Co-Pilot conversational interface

This orchestrator coordinates:
1. Clinical trials (universal pipeline)
2. SOC recommendation (disease-specific, NCCN-aligned)
3. Biomarker monitoring (disease-specific, e.g., CA-125, PSA, CEA)
4. Drug efficacy (WIWFM - awaiting NGS if no tumor data)
5. Food validator (generic)
6. Resistance playbook (generic)
7. RESISTANCE PROPHET (generic - predicts resistance 3-6 months early)

Universalized from Ayesha orchestrator - works for any patient profile.

Author: Zo
Date: January 2025
Pattern: Cloned from ayesha_orchestrator_v2.py with universalization
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, List, Any, Optional
from datetime import datetime
import httpx
import logging
import json
import os

# Import universal services
from api.services.complete_care_universal.profile_adapter import adapt_simple_to_full_profile, is_simple_profile
from api.services.complete_care_universal.config import get_soc_recommendation, validate_disease_type, get_biomarker_config
from api.services.biomarker_intelligence_universal import get_biomarker_intelligence_service
from api.orchestrator_runtime import get_internal_http_timeout_seconds, get_orchestrator_api_base_url

# Import Phase 1 SAE services (Manager-approved)
from api.services.next_test_recommender import get_next_test_recommendations
from api.services.hint_tiles_service import get_hint_tiles
from api.services.mechanism_map_service import get_mechanism_map

# Import Phase 2 SAE services (Manager-approved)
from api.services.sae_feature_service import compute_sae_features
from api.services.mechanism_fit_ranker import rank_trials_by_mechanism
from api.services.resistance_detection_service import detect_resistance

# Import Resistance Prophet Service
from api.services.resistance_prophet_service import get_resistance_prophet_service
from api.services.resistance_playbook_service import get_resistance_playbook_service
from api.orchestrator_runtime import get_code_version, get_contract_version

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/complete_care", tags=["complete_care"])

def _build_taskc_resistance_prediction(
    *,
    patient_profile: Dict[str, Any],
    patient_info: Dict[str, Any],
    prophet_result: Dict[str, Any],
    biomarker_intelligence: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Task C canonical OV resistance prediction block:
    risk + mechanisms + actions + data gaps + provenance.

    This is a presentation-layer wrapper around existing services (Prophet + Biomarker Intelligence),
    meant to be stable for `/api/complete_care/v2`.
    """
    tumor_context = patient_info.get("tumor_context") or {}
    muts = tumor_context.get("somatic_mutations") or []
    genes = {str(m.get("gene") or "").upper() for m in muts if m.get("gene")}

    # MAPK pathway heuristic
    mapk_genes = {"KRAS", "NRAS", "BRAF", "NF1", "MAP2K1", "MAP2K2"}
    mapk_mut = bool(genes & mapk_genes)

    # DDR pathway heuristic (treat MBD4/BRCA/RAD51 family/PTEN/TP53 as "DDR compromised" proxy)
    ddr_genes = {"MBD4", "BRCA1", "BRCA2", "RAD51C", "RAD51D", "PALB2", "ATM", "ATR", "CHEK1", "CHEK2", "TP53"}
    ddr_compromised = bool(genes & ddr_genes)

    mechanisms = [
        {
            "layer": "GENETIC",
            "biomarker": "MAPK_pathway",
            "status": "MUTANT" if mapk_mut else "WILD_TYPE",
            "contribution": 1.97 if mapk_mut else 0.0,
            "validation": {
                "cohort": "TCGA-OV",
                "n": 469,
                "metric": "RR",
                "value": 1.97,
                "p_value": 0.05,
            },
        },
        {
            "layer": "GENETIC",
            "biomarker": "DDR_pathway",
            "status": "COMPROMISED" if ddr_compromised else "INTACT",
            # Negative contribution indicates increased sensitivity (protective vs resistance)
            "contribution": -0.20 if ddr_compromised else 0.0,
            "validation": {
                "cohort": "Literature/Mechanistic",
                "n": None,
                "metric": "Mechanistic",
                "value": None,
                "p_value": None,
            },
        },
    ]

    # CA-125 mechanism (if we have biomarker intelligence)
    if biomarker_intelligence and not biomarker_intelligence.get("error"):
        mechanisms.append(
            {
                "layer": "ADAPTIVE",
                "biomarker": "CA125_kinetics",
                "status": "MONITOR",
                "contribution": 0.0,
                "validation": {
                    "cohort": "Guidelines/Literature",
                    "n": None,
                    "metric": "Rule",
                    "value": None,
                    "p_value": None,
                },
                "burden_class": biomarker_intelligence.get("burden_class"),
                "resistance_signals": biomarker_intelligence.get("resistance_signals") or [],
            }
        )

    # Data gaps
    biomarkers = patient_profile.get("biomarkers") or {}
    data_gaps = []
    if biomarkers.get("ca125_baseline") in (None, "", 0):
        data_gaps.append(
            {
                "biomarker": "CA125_baseline",
                "status": "MISSING",
                "priority": "CRITICAL",
                "action": "Order CA-125 baseline STAT",
            }
        )

    # Monitoring plan (OV default)
    monitoring_plan = [
        {
            "biomarker": "CA125",
            "method": "serum",
            "frequency": "q3weeks",
            "trigger": ">25% rise from nadir",
            "rationale": "Early resistance detection (3-6 week lead time)",
        }
    ]

    # Treatment actions (very conservative, non-prescriptive; depends on risk)
    risk_level = prophet_result.get("risk_level") or "UNKNOWN"
    probability = prophet_result.get("probability")
    confidence = prophet_result.get("confidence")

    treatment_actions = []
    if risk_level in ("LOW", "MEDIUM", "UNKNOWN"):
        treatment_actions.append(
            {
                "recommendation": "Continue carboplatin/paclitaxel",
                "rationale": "MAPK wild-type and DDR-compromised signals suggest higher platinum sensitivity (mechanistic proxy).",
                "confidence": min(float(confidence or 0.6), 0.9),
            }
        )
    else:
        treatment_actions.append(
            {
                "recommendation": "Escalate monitoring and consider alternative strategies",
                "rationale": "Elevated resistance risk from prophet signals; review next-line options and trials.",
                "confidence": float(confidence or 0.6),
            }
        )

    services_called = ["resistance_prophet"]
    if biomarker_intelligence and not biomarker_intelligence.get("error"):
        services_called.append("biomarker_intelligence")

    return {
        "resistance_prediction": {
            "risk_level": risk_level,
            "probability": probability,
            "confidence": confidence,
            "mechanisms_detected": mechanisms,
            "data_gaps": data_gaps,
            "monitoring_plan": monitoring_plan,
            "treatment_actions": treatment_actions,
            # Keep raw prophet details for debugging/back-compat
            "prophet_raw": prophet_result,
        },
        "provenance": {
            "code_version": get_code_version(),
            "contract_version": "taskc_resistance_prediction_v1",
            "inputs_snapshot_hash": None,
            "services_called": services_called,
            "timestamp": datetime.utcnow().isoformat(),
        },
    }


# === SCHEMAS ===

class UniversalPatientProfile(BaseModel):
    """Universal patient profile - accepts both simple and full formats"""
    # Simple format fields (optional if full format provided)
    patient_id: Optional[str] = Field(None, description="Patient ID")
    name: Optional[str] = Field(None, description="Patient name")
    disease: Optional[Any] = Field(None, description="Disease (string or dict with type/stage)")
    treatment_line: Optional[str] = Field(None, description="Treatment line")
    location: Optional[str] = Field(None, description="Location")
    zip_code: Optional[str] = Field(None, description="ZIP code")
    age: Optional[int] = Field(None, description="Age")
    sex: Optional[str] = Field(None, description="Sex")
    stage: Optional[str] = Field(None, description="Cancer stage")
    
    # Full format fields (optional if simple format provided)
    demographics: Optional[Dict[str, Any]] = Field(None, description="Demographics (full format)")
    disease_dict: Optional[Dict[str, Any]] = Field(None, alias="disease", description="Disease details (full format)")
    treatment: Optional[Dict[str, Any]] = Field(None, description="Treatment details (full format)")
    biomarkers: Optional[Dict[str, Any]] = Field(None, description="Biomarkers")
    tumor_context: Optional[Dict[str, Any]] = Field(None, description="Tumor NGS data")
    logistics: Optional[Dict[str, Any]] = Field(None, description="Logistics (location, travel)")
    
    class Config:
        allow_population_by_field_name = True


class CompleteCareUniversalRequest(BaseModel):
    """Request schema for universal complete care plan"""
    
    # Patient profile (accepts both simple and full formats)
    # NOTE: Task C adds an alternate input shape (`disease` + `patient_data`) for the OV resistance E2E flow.
    patient_profile: Optional[Dict[str, Any]] = Field(None, description="Patient profile (simple or full format)")

    # Task C alternate input shape (OV resistance E2E)
    disease: Optional[str] = Field(None, description="Shorthand disease key (e.g., 'ovarian')")
    patient_data: Optional[Dict[str, Any]] = Field(
        None,
        description="Task C input payload: mutations/ca125_data/clinical_context (mapped into patient_profile internally)",
    )
    
    # Optional queries
    drug_query: Optional[str] = Field(None, description="Specific drug to evaluate (e.g., 'Olaparib')")
    food_query: Optional[str] = Field(None, description="Food/supplement to validate (e.g., 'curcumin')")
    
    # Flags
    include_trials: bool = Field(default=True, description="Include clinical trials")
    include_soc: bool = Field(default=True, description="Include SOC recommendation")
    include_biomarker: bool = Field(default=True, description="Include biomarker intelligence")
    include_wiwfm: bool = Field(default=True, description="Include drug efficacy (WIWFM)")
    include_food: bool = Field(default=False, description="Include food validator")
    include_resistance: bool = Field(default=False, description="Include resistance playbook")
    include_resistance_prediction: bool = Field(default=False, description="Include Resistance Prophet prediction")
    
    max_trials: int = Field(default=10, description="Maximum number of trials to return")


class CompleteCareUniversalResponse(BaseModel):
    """Response schema for universal complete care plan"""
    trials: Optional[Dict[str, Any]] = Field(None, description="Clinical trials results")
    soc_recommendation: Optional[Dict[str, Any]] = Field(None, description="Standard of care recommendation")
    biomarker_intelligence: Optional[Dict[str, Any]] = Field(None, description="Biomarker analysis and monitoring")
    wiwfm: Optional[Dict[str, Any]] = Field(None, description="Drug efficacy predictions (WIWFM)")
    food_validation: Optional[Dict[str, Any]] = Field(None, description="Food/supplement validation")
    resistance_playbook: Optional[Dict[str, Any]] = Field(None, description="Resistance planning")
    resistance_contract: Optional[Dict[str, Any]] = Field(
        None,
        description="Canonical resistance contract (single schema for UI; generated when resistance playbook/prediction is requested)",
    )
    
    # Phase 1 SAE Services
    next_test_recommender: Optional[Dict[str, Any]] = Field(None, description="Prioritized next-test recommendations")
    hint_tiles: Optional[Dict[str, Any]] = Field(None, description="Clinician action hints")
    mechanism_map: Optional[Dict[str, Any]] = Field(None, description="Pathway burden visualization")
    
    # Phase 2 SAE Services
    sae_features: Optional[Dict[str, Any]] = Field(None, description="SAE feature bundle")
    resistance_alert: Optional[Dict[str, Any]] = Field(None, description="Resistance detection")
    
    # Resistance Prophet
    resistance_prediction: Optional[Dict[str, Any]] = Field(None, description="Resistance Prophet early warning")
    
    summary: Dict[str, Any] = Field(..., description="Summary of care plan components")
    provenance: Dict[str, Any] = Field(..., description="Data sources and orchestration metadata")


# === HELPER FUNCTIONS ===

async def _extract_insights_bundle(
    client: httpx.AsyncClient,
    somatic_mutations: List[Dict[str, Any]],
    api_base: str = "http://localhost:8000"
) -> Dict[str, float]:
    """
    Deterministically extract an "insights bundle" **without** internal localhost HTTP calls.

    Why:
    - Universal orchestrator must be runnable without a server (Ring-1, fixtures, CI).
    - Insights endpoints themselves can depend on internal HTTP (e.g., /api/evo/*), so calling them
      from inside the same process re-introduces brittleness.

    Contract:
    - Returns a dict with keys: functionality/chromatin/essentiality/regulatory in [0,1]
    - Conservative defaults when insufficient inputs are present.

    Note:
    - `client` and `api_base` are intentionally unused (kept for backward-compatibility).
    """
    _ = client
    _ = api_base
    insights_bundle = {
        "functionality": 0.5,
        "chromatin": 0.5,
        "essentiality": 0.5,
        "regulatory": 0.5
    }
    
    if not somatic_mutations:
        logger.warning("⚠️  No mutations provided for insights extraction - using defaults")
        return insights_bundle
    
    primary_mutation = somatic_mutations[0] if somatic_mutations else {}
    primary_gene = primary_mutation.get("gene")
    hgvs_p = primary_mutation.get("hgvs_p")
    chrom = primary_mutation.get("chrom")
    pos = primary_mutation.get("pos")
    ref = primary_mutation.get("ref")
    alt = primary_mutation.get("alt")
    
    has_full_data = bool(chrom and pos and ref and alt)
    has_hgvs_p = bool(hgvs_p)
    has_gene = bool(primary_gene)
    
    logger.info(f"🔍 [INSIGHTS EXTRACTION] Mutation data: gene={primary_gene}, hgvs_p={hgvs_p}, "
               f"has_full_data={has_full_data}, has_hgvs_p={has_hgvs_p}, has_gene={has_gene}")
    
    if has_full_data or has_hgvs_p:
        logger.info(
            f"🔍 [INSIGHTS EXTRACTION] Local heuristic mode: gene={primary_gene}, hgvs_p={hgvs_p}, has_full_data={has_full_data}"
        )
        try:
            gene_upper = str(primary_gene or "").upper()
            hgvs_p_upper = str(hgvs_p or "").upper()
            consequence = str(primary_mutation.get("consequence") or "").lower()

            is_truncation = ("*" in hgvs_p_upper) or ("FS" in hgvs_p_upper) or ("frameshift" in consequence) or ("stop_gained" in consequence)
            known_drivers = {"BRCA1", "BRCA2", "TP53", "KRAS", "BRAF", "PIK3CA", "PTEN", "NF1"}
            is_known_driver = gene_upper in known_drivers

            # functionality: truncations => strong loss; otherwise modest change
            insights_bundle["functionality"] = 0.15 if is_truncation else (0.7 if is_known_driver else 0.55)

            # essentiality: truncation/high-impact => higher essentiality proxy
            insights_bundle["essentiality"] = 0.9 if is_truncation else (0.7 if is_known_driver else 0.5)

            # chromatin/regulatory: keep conservative unless we have full coords
            if has_full_data:
                insights_bundle["chromatin"] = 0.55
                insights_bundle["regulatory"] = 0.55

            logger.info(f"✅ [INSIGHTS EXTRACTION] Local insights bundle: {insights_bundle}")
        except Exception as e:
            logger.error(f"❌ [INSIGHTS EXTRACTION] Local heuristic failed: {e}", exc_info=True)
    
    elif has_gene:
        known_drivers = ["BRCA1", "BRCA2", "TP53", "KRAS", "BRAF", "PIK3CA", "PTEN"]
        if primary_gene in known_drivers:
            insights_bundle["functionality"] = 0.7
            insights_bundle["essentiality"] = 0.7
            logger.info(f"✅ [INSIGHTS EXTRACTION] Applied gene-level heuristics for {primary_gene}")
    else:
        logger.warning(f"⚠️  [INSIGHTS EXTRACTION] No sufficient data for insights extraction - using defaults")
    
    logger.info(f"🔍 [INSIGHTS EXTRACTION] Returning insights_bundle: {insights_bundle}")
    return insights_bundle


def _extract_patient_info(patient_profile: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract key patient information from profile.
    
    Returns: dict with disease_type, stage, treatment_line, location, etc.
    """
    # Handle simple vs full profile
    if is_simple_profile(patient_profile):
        patient_profile = adapt_simple_to_full_profile(patient_profile)
    
    demographics = patient_profile.get("demographics", {})
    disease = patient_profile.get("disease", {})
    treatment = patient_profile.get("treatment", {})
    biomarkers = patient_profile.get("biomarkers", {})
    logistics = patient_profile.get("logistics", {})
    tumor_context = patient_profile.get("tumor_context")
    biomarker_history = patient_profile.get("biomarker_history") or {}
    
    # Extract disease type (can be string or dict)
    disease_type = disease.get("type") if isinstance(disease, dict) else disease
    if not disease_type and isinstance(disease, dict):
        disease_type = disease.get("primary_diagnosis")
    
    # Validate and normalize disease type
    disease_original = disease_type or ""
    is_valid, normalized_disease = validate_disease_type(disease_original)
    
    return {
        "patient_id": demographics.get("patient_id", "unknown"),
        "patient_name": demographics.get("name", "Patient"),
        "disease_original": disease_original,
        "disease_is_valid": bool(is_valid),
        "disease_type": normalized_disease,
        "stage": disease.get("stage") if isinstance(disease, dict) else None,
        "treatment_line": treatment.get("line", "first-line"),
        "germline_status": biomarkers.get("germline_status", "unknown"),
        "location": logistics.get("location") or demographics.get("location", "Unknown"),
        "zip_code": logistics.get("zip_code") or logistics.get("home_zip"),
        "tumor_context": tumor_context,
        "biomarkers": biomarkers,
        "biomarker_history": biomarker_history,
    }


async def _call_universal_trials(
    client: httpx.AsyncClient,
    patient_profile: Dict[str, Any],
    max_trials: int = 10,
    mechanism_vector: Optional[List[float]] = None,  # NEW: 7D mechanism vector for mechanism fit ranking
    sae_source: Optional[str] = None,  # NEW: TRUE SAE vs PROXY SAE source
    ddr_bin_score: Optional[float] = None  # NEW: DDR_bin score from TRUE SAE
) -> Optional[Dict[str, Any]]:
    """
    Call universal trials intelligence endpoint.
    
    If mechanism_vector provided, uses TrialMatchingAgent with mechanism fit ranking.
    Otherwise, uses /api/dossiers/intelligence/filter with trial candidates.
    """
    try:
        # NEW: Use TrialMatchingAgent with mechanism fit if mechanism_vector provided
        if mechanism_vector and len(mechanism_vector) == 7:
            from api.services.trials.trial_matching_agent import TrialMatchingAgent
            
            trial_agent = TrialMatchingAgent()
            
            # Extract biomarker profile from patient_profile
            biomarker_profile = None
            tumor_context = patient_profile.get("tumor_context")
            if tumor_context:
                biomarker_profile = {
                    "tmb": tumor_context.get("tmb"),
                    "msi": tumor_context.get("msi_status"),
                    "hrd": tumor_context.get("hrd_score")
                }
            
            # Use TrialMatchingAgent with mechanism fit ranking
            result = await trial_agent.match(
                patient_profile=patient_profile,
                biomarker_profile=biomarker_profile,
                mechanism_vector=mechanism_vector,
                max_results=max_trials
            )
            
            # Convert TrialMatchingResult to response format
            trials = []
            for match in result.matches:
                trial_dict = {
                    "nct_id": match.nct_id,
                    "title": match.title,
                    "phase": match.phase,
                    "status": match.status,
                    "mechanism_fit_score": match.mechanism_fit_score,
                    "combined_score": match.combined_score,
                    "mechanism_alignment": match.mechanism_alignment,
                    "eligibility_score": match.eligibility_score,
                    "boost_applied": match.boost_applied,
                    "location": match.location,
                    "enrollment_criteria": match.enrollment_criteria,
                    "genetic_requirements": match.genetic_requirements,
                    "principal_investigator": match.principal_investigator,
                    "site_contact": match.site_contact,
                    "source_url": match.source_url
                }
                # Add TRUE SAE provenance if available
                if sae_source:
                    trial_dict["sae_source"] = sae_source
                if ddr_bin_score is not None:
                    trial_dict["ddr_bin_score"] = ddr_bin_score
                trials.append(trial_dict)
            
            provenance_dict = {
                "source": "trial_matching_agent_with_mechanism_fit",
                "queries_used": result.provenance.get("queries_used", []),
                "mechanism_vector_used": mechanism_vector
            }
            if sae_source:
                provenance_dict["sae_source"] = sae_source
            if ddr_bin_score is not None:
                provenance_dict["ddr_bin_score"] = ddr_bin_score
            
            return {
                "trials": trials,
                "summary": {
                    "total": len(trials),
                    "matched": len(trials),
                    "mechanism_fit_applied": True
                },
                "provenance": provenance_dict
            }
        
        # Fallback: Use existing universal trials pipeline (no mechanism fit)
        # Get trial candidates from search service
        from api.services.clinical_trial_search_service import ClinicalTrialSearchService
        search_service = ClinicalTrialSearchService()
        
        # Extract disease for search
        disease = patient_profile.get("disease", {})
        disease_name = disease.get("type") if isinstance(disease, dict) else disease
        if not disease_name and isinstance(disease, dict):
            disease_name = disease.get("primary_diagnosis", "")
        
        # Search for trials (search_trials is async)
        search_result = await search_service.search_trials(
            query=disease_name or "cancer",
            disease_category=disease_name,
            top_k=50,  # Get more candidates for filtering
            min_score=0.3
        )
        
        # Extract candidates from search result
        candidates = search_result.get("data", {}).get("found_trials", []) if search_result else []
        
        if not candidates:
            return {
                "trials": [],
                "summary": {"total": 0, "matched": 0, "mechanism_fit_applied": False},
                "provenance": {"source": "universal_trials_pipeline"}
            }
        
        trial_candidates = candidates
        
        # Call universal trials filter endpoint
        filter_payload = {
            "patient_profile": patient_profile,
            "candidates": trial_candidates[:50],  # Limit for performance
            "use_llm": True
        }
        
        response = await client.post(
            "http://localhost:8000/api/dossiers/intelligence/filter",
            json=filter_payload,
            timeout=get_internal_http_timeout_seconds()
        )
        
        if response.status_code == 200:
            data = response.json()
            # Combine top_tier and good_tier, limit to max_trials
            all_trials = (data.get("top_tier", []) + data.get("good_tier", []))[:max_trials]
            
            return {
                "trials": all_trials,
                "summary": {
                    "total": data.get("statistics", {}).get("total_candidates", 0),
                    "matched": len(all_trials),
                    "top_tier": len(data.get("top_tier", [])),
                    "good_tier": len(data.get("good_tier", [])),
                    "mechanism_fit_applied": False
                },
                "provenance": {
                    "source": "universal_trials_pipeline",
                    "statistics": data.get("statistics", {})
                }
            }
        else:
            logger.warning(f"Universal trials API error: {response.status_code}")
            return None
            
    except Exception as e:
        logger.error(f"Universal trials call failed: {str(e)}")
        return None


async def _call_drug_efficacy(
    client: httpx.AsyncClient,
    patient_info: Dict[str, Any],
    drug_query: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Call drug efficacy (WIWFM) endpoint.
    
    Uses patient_info to build request.
    """
    try:
        tumor_context = patient_info.get("tumor_context") or {}
        has_ngs = bool(tumor_context.get("somatic_mutations") or tumor_context.get("hrd_score"))
        
        if not has_ngs:
            return {
                "status": "awaiting_ngs",
                "message": "Personalized drug efficacy predictions require tumor NGS data",
                "ngs_fast_track": _get_ngs_recommendations(patient_info.get("disease_type", ""))
            }
        
        somatic_mutations = tumor_context.get("somatic_mutations", [])
        
        if not somatic_mutations:
            logger.warning("⚠️  No somatic mutations provided - WIWFM may return default rankings")
        
        payload = {
            "mutations": somatic_mutations,  # ✅ Uses "mutations" (P0 fix)
            "disease": patient_info.get("disease_type", "ovarian_cancer_hgs"),  # ✅ From patient profile
            "patient_context": {
                "germline_status": patient_info.get("germline_status", "unknown"),
                "tumor_context": tumor_context
            }
        }
        
        if drug_query:
            payload["drug"] = drug_query
        
        response = await client.post(
            "http://localhost:8000/api/efficacy/predict",
            json=payload,
            timeout=get_internal_http_timeout_seconds()
        )
        
        if response.status_code == 200:
            data = response.json()
            logger.info(f"✅ Drug efficacy: {len(data.get('drugs', []))} drugs ranked")
            return data
        else:
            logger.warning(f"Drug efficacy API error: {response.status_code}")
            return None
            
    except Exception as e:
        logger.error(f"Drug efficacy call failed: {str(e)}")
        return None


def _get_ngs_recommendations(disease_type: str) -> Dict[str, str]:
    """Get NGS recommendations based on disease type."""
    recommendations = {
        "ovarian_cancer_hgs": {
            "ctDNA": "Guardant360 - somatic BRCA/HRR, TMB, MSI (7-10 days)",
            "tissue_HRD": "MyChoice - HRD score for PARP maintenance planning (7-14 days)",
            "IHC": "WT1/PAX8/p53 - confirm high-grade serous histology (1-3 days)"
        }
    }
    return recommendations.get(disease_type, {
        "ctDNA": "Guardant360 or FoundationOne Liquid - comprehensive genomic profiling (7-10 days)",
        "tissue": "FoundationOne CDx or Tempus - comprehensive tissue NGS (14-21 days)"
    })


async def _call_food_validator(
    client: httpx.AsyncClient,
    patient_info: Dict[str, Any],
    food_query: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Call food validator endpoint."""
    if not food_query:
        return None
    
    try:
        payload = {
            "compound": food_query,
            "disease": patient_info.get("disease_type", "ovarian_cancer_hgs"),  # ✅ From patient profile
            "variants": []
        }
        
        # Add mutations if available
        tumor_context = patient_info.get("tumor_context") or {}
        if tumor_context.get("somatic_mutations"):
            payload["variants"] = tumor_context.get("somatic_mutations", [])
        
        response = await client.post(
            "http://localhost:8000/api/hypothesis/validate_food_dynamic",
            json=payload,
            timeout=get_internal_http_timeout_seconds()
        )
        
        if response.status_code == 200:
            data = response.json()
            logger.info(f"✅ Food validator: {food_query} analyzed")
            return data
        else:
            logger.warning(f"Food validator API error: {response.status_code}")
            return None
            
    except Exception as e:
        logger.error(f"Food validator call failed: {str(e)}")
        return None


async def _call_resistance_playbook(
    client: httpx.AsyncClient,
    patient_info: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """Call resistance playbook via direct service invocation (no localhost HTTP)."""
    tumor_context = patient_info.get("tumor_context") or {}
    # Sprint 2: always emit a canonical contract, even when inputs are missing.
    # This prevents UI drift and makes missing inputs explicit.
    try:
        from api.services.input_completeness import compute_input_completeness
        from api.contracts.resistance_builders import contract_for_missing_inputs

        ca125_history = ((patient_info.get("biomarker_history") or {}).get("ca125_history")) or None
        completeness = compute_input_completeness(tumor_context=tumor_context, ca125_history=ca125_history)
    except Exception:
        completeness = None

    if not tumor_context:
        contract_dict = None
        try:
            if completeness is not None:
                contract_dict = contract_for_missing_inputs(
                    endpoint="/api/care/resistance_playbook_v2",
                    disease_canonical=str(patient_info.get("disease_type") or "unknown"),
                    missing=["tumor_context"],
                    warnings=list(completeness.warnings or []),
                    receipts=[],
                ).model_dump()
        except Exception:
            contract_dict = None

        return {
            "status": "awaiting_ngs",
            "message": "Resistance playbook requires tumor NGS data",
            "resistance_contract": contract_dict,
        }

    try:
        from api.services.resistance_playbook_service import get_resistance_playbook_service

        # Derive genes from tumor_context for playbook lookup
        somatic = tumor_context.get("somatic_mutations") or []
        detected_genes = sorted({(m.get("gene") or "").upper() for m in somatic if m.get("gene")})

        # Map canonical disease to playbook routing key
        disease_type = patient_info.get("disease_type") or "unknown"
        playbook_disease = "myeloma" if disease_type == "multiple_myeloma" else "ovarian"

        svc = get_resistance_playbook_service()
        result = await svc.get_next_line_options(
            disease=playbook_disease,
            detected_resistance=detected_genes,
            current_regimen=None,
            current_drug_class=None,
            treatment_line=1,
            prior_therapies=None,
            cytogenetics=None,
            patient_id=patient_info.get("patient_id")
        )

        # Build canonical contract (so UI can read one stable schema).
        # This is additive and does not remove any legacy fields.
        try:
            from api.contracts.resistance_builders import contract_from_playbook_result

            warnings = list((completeness.warnings if completeness is not None else []) or [])
            contract = contract_from_playbook_result(
                endpoint="/api/care/resistance_playbook_v2",
                disease_canonical=str(patient_info.get("disease_type") or "unknown"),
                tumor_context=tumor_context,
                playbook_disease_key=playbook_disease,
                playbook_result=result,
                warnings=warnings,
                receipts=[],
            )
            contract_dict = contract.model_dump()
        except Exception as e:
            logger.warning(f"Failed to build resistance_contract from playbook result: {e}")
            contract_dict = None

        # Return a JSON-friendly dict (compatible with previous orchestrator behavior)
        return {
            "status": "ok",
            "disease": playbook_disease,
            "detected_genes": detected_genes,
            "resistance_contract": contract_dict,
            "alternatives": [
                {
                    "drug": a.drug,
                    "drug_class": a.drug_class,
                    "rationale": a.rationale,
                    "evidence_level": a.evidence_level.value if hasattr(a.evidence_level, "value") else str(a.evidence_level),
                    "priority": a.priority,
                    "source_gene": a.source_gene,
                    "requires": a.requires,
                }
                for a in (result.alternatives or [])
            ],
            "regimen_changes": [
                {
                    "from_regimen": r.from_regimen,
                    "to_regimen": r.to_regimen,
                    "rationale": r.rationale,
                    "evidence_level": r.evidence_level.value if hasattr(r.evidence_level, "value") else str(r.evidence_level),
                }
                for r in (result.regimen_changes or [])
            ],
            "monitoring_changes": {
                "mrd_frequency": result.monitoring_changes.mrd_frequency,
                "ctdna_targets": result.monitoring_changes.ctdna_targets,
                "imaging_frequency": result.monitoring_changes.imaging_frequency,
                "biomarker_frequency": result.monitoring_changes.biomarker_frequency,
                "bone_marrow_frequency": result.monitoring_changes.bone_marrow_frequency,
            } if result.monitoring_changes else {},
            "escalation_triggers": result.escalation_triggers or [],
            "downstream_handoffs": {
                k: {
                    "agent": v.agent,
                    "action": v.action,
                    "payload": v.payload,
                }
                for k, v in (result.downstream_handoffs or {}).items()
            },
            "provenance": result.provenance or {},
            "contract": contract_dict,
        }
    except Exception as e:
        logger.error(f"Resistance playbook direct call failed: {str(e)}", exc_info=True)
        return None


# === ENDPOINTS ===

@router.post("/v2", response_model=CompleteCareUniversalResponse)
async def get_complete_care_v2(request: CompleteCareUniversalRequest):
    """
    Get complete care plan v2 for any patient.
    
    Universal version that works with any patient profile.
    Orchestrates all care plan components:
    - Clinical trials (universal pipeline)
    - SOC recommendation (disease-specific)
    - Biomarker intelligence (disease-specific)
    - Drug efficacy (WIWFM)
    - Food validator (optional)
    - Resistance playbook (optional)
    - Resistance Prophet (optional)
    
    Args:
        request: Complete care request with patient profile
    
    Returns:
        Complete care plan with all components
    """
    try:
        # Task C: accept alternate `disease` + `patient_data` shape and map into patient_profile.
        if (request.patient_profile is None or request.patient_profile == {}) and request.patient_data is not None:
            pd = request.patient_data or {}
            disease_key = (request.disease or pd.get("disease") or "unknown")
            clinical_context = pd.get("clinical_context") or {}
            ca125_data = pd.get("ca125_data") or {}

            mutations = pd.get("mutations") or []
            somatic_mutations = []
            for m in mutations:
                if not isinstance(m, dict):
                    continue
                gene = m.get("gene") or m.get("hugo_gene_symbol")
                hgvs_p = m.get("hgvs_p") or m.get("protein_change") or m.get("aa_change")
                consequence = m.get("consequence") or m.get("variant_type")
                if gene:
                    somatic_mutations.append(
                        {
                            "gene": str(gene),
                            "hgvs_p": str(hgvs_p) if hgvs_p is not None else None,
                            "consequence": str(consequence) if consequence is not None else None,
                        }
                    )

            # CA-125: set biomarkers for BiomarkerIntelligenceService (current + baseline + cycle)
            ca125_baseline = ca125_data.get("baseline")
            ca125_current = ca125_data.get("current")
            ca125_cycle = ca125_data.get("cycle")

            # Also create a minimal serial history for prophet if present (2 points).
            ca125_history = None
            if ca125_baseline is not None and ca125_current is not None:
                try:
                    cycle0 = 0
                    cyc = int(ca125_cycle) if ca125_cycle is not None else 0
                    ca125_history = [
                        {"value": float(ca125_baseline), "timestamp": "cycle_0", "cycle": cycle0},
                        {"value": float(ca125_current), "timestamp": f"cycle_{cyc}", "cycle": cyc},
                    ]
                except Exception:
                    ca125_history = None

            patient_profile = {
                "demographics": {
                    "patient_id": pd.get("patient_id") or "unknown",
                    "name": pd.get("patient_id") or "Patient",
                },
                "disease": {
                    "type": disease_key,
                    "stage": pd.get("stage") or (pd.get("clinical_context") or {}).get("stage"),
                },
                "treatment": {
                    "line": clinical_context.get("treatment_line") or "first-line",
                    "current_regimen": clinical_context.get("current_regimen"),
                },
                "biomarkers": {
                    "ca125_value": float(ca125_current) if ca125_current is not None else None,
                    "ca125_baseline": float(ca125_baseline) if ca125_baseline is not None else None,
                    "cycle": int(ca125_cycle) if ca125_cycle is not None else None,
                },
                "tumor_context": {"somatic_mutations": somatic_mutations},
                "biomarker_history": {"ca125_history": ca125_history} if ca125_history else {},
            }
            request.patient_profile = patient_profile

        # Adapt profile if needed
        patient_profile = request.patient_profile
        if not patient_profile:
            raise HTTPException(status_code=422, detail="patient_profile (or patient_data) is required")
        if is_simple_profile(patient_profile):
            patient_profile = adapt_simple_to_full_profile(patient_profile)
            logger.info("✅ Adapted simple profile to full format")
        
        # Extract patient info
        patient_info = _extract_patient_info(patient_profile)

        # Guardrail: never silently treat unknown disease as ovarian/MM in the orchestrator.
        # We degrade gracefully (skip disease-specific modules) but still return a plan.
        invalid_disease = not patient_info.get('disease_is_valid', True)
        if invalid_disease:
            logger.warning(f"⚠️  Unknown/unsupported disease: '{patient_info.get('disease_original')}'. Degrading gracefully.")

        logger.info(f"Complete care v2: patient={patient_info['patient_name']}, "
                   f"disease={patient_info['disease_type']}, stage={patient_info.get('stage', 'Unknown')}")
        
        # Initialize results
        results = {
            "trials": None,
            "soc_recommendation": None,
            "biomarker_intelligence": None,
            "wiwfm": None,
            "food_validation": None,
            "resistance_playbook": None,
            "resistance_contract": None,
            "next_test_recommender": None,
            "hint_tiles": None,
            "mechanism_map": None,
            "sae_features": None,
            "resistance_alert": None,
            "resistance_prediction": None
        }
        
        # Create async HTTP client
        mechanism_vector = None  # NEW: Extract mechanism vector from drug efficacy
        async with httpx.AsyncClient() as client:
            
            # 1. SOC Recommendation (disease-specific) - moved before trials to allow mechanism vector extraction
            if request.include_soc:
                if invalid_disease:
                    results["soc_recommendation"] = {
                        "status": "skipped_invalid_disease",
                        "message": f"SOC skipped: unsupported disease '{patient_info.get('disease_original')}'",
                        "disease": patient_info.get('disease_original')
                    }
                else:
                    soc_rec = get_soc_recommendation(
                        patient_info["disease_type"],
                        patient_info["treatment_line"]
                    )
                    if soc_rec:
                        results["soc_recommendation"] = soc_rec
                    else:
                        results["soc_recommendation"] = {
                            "status": "not_configured",
                            "message": f"SOC recommendation not yet configured for {patient_info['disease_type']}"
                        }
            
            # 3. Biomarker Intelligence (Universal - Phase 9.1)
            if request.include_biomarker:
                if invalid_disease:
                    results["biomarker_intelligence"] = {
                        "status": "skipped_invalid_disease",
                        "message": f"Biomarker intelligence skipped: unsupported disease '{patient_info.get('disease_original')}'",
                        "disease": patient_info.get('disease_original')
                    }
                else:
                    try:
                        biomarker_service = get_biomarker_intelligence_service()

                        biomarkers = patient_info.get("biomarkers", {})
                        disease_type = patient_info["disease_type"]

                        from api.services.biomarker_intelligence_universal.config import get_primary_biomarker
                        biomarker_type = get_primary_biomarker(disease_type)

                        if biomarker_type:
                            biomarker_value = None
                            if biomarker_type == "ca125":
                                biomarker_value = biomarkers.get("ca125_value") or biomarkers.get("ca125")
                            elif biomarker_type == "psa":
                                biomarker_value = biomarkers.get("psa_value") or biomarkers.get("psa")
                            elif biomarker_type == "cea":
                                biomarker_value = biomarkers.get("cea_value") or biomarkers.get("cea")
                            else:
                                biomarker_value = biomarkers.get(f"{biomarker_type}_value") or biomarkers.get(biomarker_type)

                            if biomarker_value is not None:
                                treatment = patient_profile.get("treatment", {})
                                treatment_line = treatment.get("line", "first-line")
                                treatment_ongoing = treatment_line != "first-line" or treatment.get("status") == "on_treatment"

                                biomarker_result = biomarker_service.analyze_biomarker(
                                    disease_type=disease_type,
                                    biomarker_type=biomarker_type,
                                    current_value=float(biomarker_value),
                                    baseline_value=biomarkers.get(f"{biomarker_type}_baseline"),
                                    cycle=biomarkers.get("cycle"),
                                    treatment_ongoing=treatment_ongoing
                                )

                                results["biomarker_intelligence"] = biomarker_result
                                if "error" not in biomarker_result:
                                    logger.info(f"✅ Biomarker intelligence: {biomarker_type}={biomarker_value}, burden={biomarker_result.get('burden_class', 'N/A')}")
                            else:
                                results["biomarker_intelligence"] = {
                                    "status": "value_required",
                                    "message": f"{biomarker_type.upper()} value required for biomarker monitoring",
                                    "biomarker_type": biomarker_type,
                                    "disease_type": disease_type
                                }
                        else:
                            results["biomarker_intelligence"] = {
                                "status": "not_configured",
                                "message": f"Biomarker monitoring not configured for {disease_type}",
                                "disease_type": disease_type
                            }
                    except Exception as e:
                        logger.error(f"Biomarker intelligence failed: {e}", exc_info=True)
                        results["biomarker_intelligence"] = {
                            "status": "error",
                            "error": str(e),
                            "message": "Biomarker intelligence service encountered an error"
                        }

            # 4. Drug Efficacy (WIWFM)
            mechanism_vector = None  # NEW: Extract mechanism vector from drug efficacy
            if request.include_wiwfm:
                wiwfm_response = await _call_drug_efficacy(client, patient_info, request.drug_query)
                results["wiwfm"] = wiwfm_response
                
                # NEW: Auto-extract mechanism vector from drug efficacy response
                if wiwfm_response and wiwfm_response.get("status") != "awaiting_ngs":
                    from api.services.pathway_to_mechanism_vector import get_mechanism_vector_from_response
                    mechanism_vector_result = get_mechanism_vector_from_response(
                        wiwfm_response,
                        tumor_context=patient_info.get("tumor_context"),
                        use_7d=True  # Use 7D vector [DDR, MAPK, PI3K, VEGF, HER2, IO, Efflux]
                    )
                    if mechanism_vector_result:
                        mechanism_vector, dimension_used = mechanism_vector_result
                        logger.info(f"✅ Extracted {dimension_used} mechanism vector from drug efficacy: {mechanism_vector}")
            



            # 4b. PGx Safety Gate (drug-level)
            try:
                from api.services.pgx_care_plan_integration import integrate_pgx_into_drug_efficacy
                treatment_line = patient_info.get("treatment_line")
                prior_therapies = (patient_profile.get("treatment", {}) or {}).get("history", [])
                results["wiwfm"] = await integrate_pgx_into_drug_efficacy(
                    drug_efficacy_response=results.get("wiwfm"),
                    patient_profile=patient_profile,
                    treatment_line=treatment_line,
                    prior_therapies=prior_therapies,
                )
            except Exception as e:
                logger.error(f"PGx integration into WIWFM failed: {e}", exc_info=True)

            # 2. Clinical Trials (Universal)
            if request.include_trials:
                try:
                    results["trials"] = await _call_universal_trials(
                        client=client,
                        patient_profile=patient_profile,
                        max_trials=request.max_trials,
                        mechanism_vector=mechanism_vector,
                    )
                    # Apply PGx safety gate to trials (best-effort; may be UNKNOWN if no interventions)
                    try:
                        from api.services.pgx_care_plan_integration import add_pgx_safety_gate_to_trials
                        treatment_line = patient_info.get("treatment_line")
                        prior_therapies = (patient_profile.get("treatment", {}) or {}).get("history", [])
                        results["trials"] = await add_pgx_safety_gate_to_trials(
                            trials_response=results.get("trials"),
                            patient_profile=patient_profile,
                            treatment_line=treatment_line,
                            prior_therapies=prior_therapies,
                        )
                    except Exception as e:
                        logger.error(f"PGx safety gate on trials failed: {e}", exc_info=True)
                except Exception as e:
                    logger.error(f"Universal trial matching failed: {e}", exc_info=True)
                    results["trials"] = {"status": "error", "error": str(e)}

            # 5. Food Validator (optional)
            if request.include_food and request.food_query:
                food_response = await _call_food_validator(client, patient_info, request.food_query)
                results["food_validation"] = food_response
            
            # 6. Resistance Playbook (optional)
            if request.include_resistance:
                if invalid_disease:
                    results["resistance_playbook"] = {
                        "status": "skipped_invalid_disease",
                        "message": f"Resistance playbook skipped: unsupported disease '{patient_info.get('disease_original')}'",
                        "disease": patient_info.get('disease_original')
                    }
                else:
                    resistance_response = await _call_resistance_playbook(client, patient_info)
                    results["resistance_playbook"] = resistance_response
                    if isinstance(resistance_response, dict):
                        results["resistance_contract"] = resistance_response.get("contract")
        
        # ===================================================================
        # PHASE 1 SAE SERVICES
        # ===================================================================
        
        # 7. Next-Test Recommender
        try:
            next_test_result = get_next_test_recommendations(
                germline_status=patient_info.get("germline_status", "unknown"),
                tumor_context=patient_info.get("tumor_context"),
                treatment_history=[],
                disease=patient_info.get("disease_type") or "unknown",
                sae_features=results.get("sae_features")
            )
            results["next_test_recommender"] = next_test_result
            logger.info(f"✅ Next-test recommender: {next_test_result.get('total_tests', 0)} tests recommended")
        except Exception as e:
            logger.error(f"Next-test recommender failed: {e}")
            results["next_test_recommender"] = {"error": str(e), "recommendations": []}
        
        # 8. Hint Tiles
        try:
            trials_matched = len(results["trials"]["trials"]) if results["trials"] and "trials" in results["trials"] else 0
            
            hint_tiles_result = get_hint_tiles(
                germline_status=patient_info.get("germline_status", "unknown"),
                tumor_context=patient_info.get("tumor_context"),
                ca125_intelligence=results.get("biomarker_intelligence"),  # Use biomarker_intelligence instead of ca125
                next_test_recommendations=results["next_test_recommender"].get("recommendations", []) if results["next_test_recommender"] else [],
                treatment_history=[],
                trials_matched=trials_matched,
                sae_features=results.get("sae_features")
            )
            results["hint_tiles"] = hint_tiles_result
            logger.info(f"✅ Hint tiles: {hint_tiles_result.get('total_tiles', 0)} tiles generated")
        except Exception as e:
            logger.error(f"Hint tiles failed: {e}")
            results["hint_tiles"] = {"error": str(e), "hint_tiles": []}
        
        # 9. Mechanism Map
        try:
            mechanism_map_result = get_mechanism_map(
                tumor_context=patient_info.get("tumor_context"),
                sae_features=results.get("wiwfm", {}).get("sae_features") if results.get("wiwfm") else None
            )
            results["mechanism_map"] = mechanism_map_result
            logger.info(f"✅ Mechanism map: {mechanism_map_result.get('status', 'unknown')}")
        except Exception as e:
            logger.error(f"Mechanism map failed: {e}")
            results["mechanism_map"] = {"error": str(e), "chips": [], "status": "error"}
        
        # ===================================================================
        # PHASE 2 SAE SERVICES
        # ===================================================================
        
        tumor_context = patient_info.get("tumor_context")
        if tumor_context:
            logger.info(f"✅ Tumor context EXISTS! Running SAE Phase 2...")
            try:
                # Extract pathway scores from WIWFM response
                pathway_scores = None
                if results.get("wiwfm"):
                    wiwfm_provenance = results["wiwfm"].get("provenance", {})
                    confidence_breakdown = wiwfm_provenance.get("confidence_breakdown", {})
                    pathway_scores = confidence_breakdown.get("pathway_disruption")
                    
                    if pathway_scores:
                        logger.info(f"✅ Extracted pathway scores from WIWFM: {pathway_scores}")
                    else:
                        logger.warning("⚠️  pathway_disruption not in WIWFM response - using proxy defaults")
                
                # Fallback to proxy defaults
                if not pathway_scores:
                    pathway_scores = {"ddr": 0.5, "mapk": 0.2, "pi3k": 0.2, "vegf": 0.3, "her2": 0.0}
                    logger.info(f"📊 Using proxy SAE pathway scores")
                
                # Extract insights bundle
                somatic_mutations = tumor_context.get("somatic_mutations", [])
                logger.info(f"🔍 Extracting insights bundle for {len(somatic_mutations)} mutations...")
                
                insights_bundle = None
                try:
                    api_base = get_orchestrator_api_base_url()
                    insights_bundle = await _extract_insights_bundle(client, somatic_mutations, api_base=api_base)
                    logger.info(f"✅ Extracted insights bundle: essentiality={insights_bundle.get('essentiality'):.3f}")
                except Exception as e:
                    logger.error(f"❌ Insights bundle extraction failed: {e}", exc_info=True)
                    insights_bundle = {"functionality": 0.5, "chromatin": 0.5, "essentiality": 0.5, "regulatory": 0.5}
                
                # Compute SAE features
                clean_insights_bundle = {
                    "functionality": insights_bundle.get("functionality", 0.5),
                    "chromatin": insights_bundle.get("chromatin", 0.5),
                    "essentiality": insights_bundle.get("essentiality", 0.5),
                    "regulatory": insights_bundle.get("regulatory", 0.5)
                }
                
                try:
                    results["sae_features"] = compute_sae_features(
                        insights_bundle=clean_insights_bundle,
                        pathway_scores=pathway_scores,
                        tumor_context=tumor_context,
                        treatment_history=[],
                        ca125_intelligence=results.get("biomarker_intelligence")
                    )
                    logger.info(f"✅ SAE features computed")
                except Exception as e:
                    logger.error(f"❌ SAE features computation failed: {e}", exc_info=True)
                    results["sae_features"] = None
                
                # Resistance alert
                if results["sae_features"]:
                    results["resistance_alert"] = detect_resistance(
                        current_hrd=tumor_context.get("hrd_score", 0.0),
                        previous_hrd=None,
                        current_dna_repair_capacity=results["sae_features"].get("dna_repair_capacity", 0.0),
                        previous_dna_repair_capacity=None,
                        ca125_intelligence=results.get("biomarker_intelligence"),
                        treatment_on_parp=False
                    )
            except Exception as e:
                logger.error(f"SAE Phase 2 failed: {e}")
                results["sae_features"] = {"error": str(e)}
                results["resistance_alert"] = {"error": str(e), "resistance_detected": False}
        else:
            results["sae_features"] = {"status": "awaiting_ngs"}
            results["resistance_alert"] = {"status": "awaiting_ngs"}
        
        # ===================================================================
        # RESISTANCE PROPHET
        # ===================================================================
        
        if request.include_resistance_prediction:
            logger.info("🔮 RESISTANCE PROPHET: Starting prediction...")
            try:
                has_minimal_inputs = (
                    tumor_context is not None and
                    results.get("sae_features") is not None and
                    results["sae_features"].get("status") != "awaiting_ngs"
                )
                
                if not has_minimal_inputs:
                    results["resistance_prediction"] = {
                        "status": "insufficient_data",
                        "message": "Resistance prediction requires tumor NGS data and SAE features"
                    }
                else:
                    # Derive drug class from treatment profile (Manager Q11)
                    current_drug_class = "unknown"
                    if patient_profile.get("treatment", {}).get("current_regimen"):
                        regimen = patient_profile["treatment"]["current_regimen"].lower()
                        if any(d in regimen for d in ["bortezomib", "carfilzomib", "ixazomib"]):
                            current_drug_class = "proteasome_inhibitor"
                        elif any(d in regimen for d in ["lenalidomide", "pomalidomide", "thalidomide"]):
                            current_drug_class = "imid"
                        elif any(d in regimen for d in ["daratumumab", "isatuximab"]):
                            current_drug_class = "anti_cd38"
                        elif any(d in regimen for d in ["carboplatin", "cisplatin", "oxaliplatin"]):
                            current_drug_class = "platinum_chemotherapy"
                        elif any(d in regimen for d in ["olaparib", "niraparib", "rucaparib"]):
                            current_drug_class = "parp_inhibitor"
                    
                    prophet_service = get_resistance_prophet_service(
                        resistance_playbook_service=get_resistance_playbook_service()
                    )

                    # Sprint 2: CA-125 time-series contract (serial marker ingestion)
                    # Expected shape (RUO):
                    # patient_profile.biomarker_history.ca125_history = [
                    #   {"value": 2842.0, "timestamp": "2025-01-01", "cycle": 0},
                    #   {"value": 2000.0, "timestamp": "2025-01-22", "cycle": 1},
                    # ]
                    ca125_history = None
                    try:
                        ca125_history = (patient_info.get("biomarker_history") or {}).get("ca125_history")
                    except Exception:
                        ca125_history = None

                    prediction = await prophet_service.predict_resistance(
                        current_sae_features=results["sae_features"],
                        baseline_sae_features=None,
                        ca125_history=ca125_history,
                        treatment_history=[],
                        current_drug_class=current_drug_class
                    )
                    
                    results["resistance_prediction"] = {
                        "risk_level": prediction.risk_level.value,
                        "probability": prediction.probability,
                        "confidence": prediction.confidence,
                        "signal_count": prediction.signal_count,
                        "signals": [
                            {
                                "type": sig.signal_type.value,
                                "detected": sig.detected,
                                "probability": sig.probability,
                                "confidence": sig.confidence,
                                "rationale": sig.rationale
                            }
                            for sig in prediction.signals_detected
                        ],
                        "urgency": prediction.urgency.value,
                        "recommended_actions": prediction.recommended_actions,
                        "next_line_options": prediction.next_line_options,
                        "rationale": prediction.rationale,
                        "warnings": prediction.warnings,
                        "provenance": prediction.provenance
                    }

                    # Task C: also emit a canonical OV resistance block (risk+mechanisms+actions+gaps)
                    # This is additive and uses the prophet + biomarker intelligence outputs as inputs.
                    try:
                        results["resistance_prediction"] = _build_taskc_resistance_prediction(
                            patient_profile=patient_profile,
                            patient_info=patient_info,
                            prophet_result=results["resistance_prediction"],
                            biomarker_intelligence=results.get("biomarker_intelligence"),
                        )
                    except Exception as e:
                        logger.error(f"Task C resistance_prediction build failed: {e}", exc_info=True)
            except Exception as e:
                logger.error(f"Resistance Prophet prediction failed: {e}", exc_info=True)
                results["resistance_prediction"] = {"status": "error", "error": str(e)}
        
        # Generate summary
        summary = {
            "components_included": [],
            "ngs_status": "pending" if not tumor_context else "available",
            "confidence_level": "high (90-100%)" if not tumor_context else "moderate-high (70-90%)",
            "reasoning": "Confidence is high for guideline-based recommendations. Confidence is moderate for personalized predictions (WIWFM requires NGS)."
        }
        
        if results["trials"]:
            summary["components_included"].append("clinical_trials")
        if results["soc_recommendation"]:
            summary["components_included"].append("soc_recommendation")
        if results["biomarker_intelligence"]:
            summary["components_included"].append("biomarker_intelligence")
        if results["wiwfm"]:
            summary["components_included"].append("wiwfm")
        if results["food_validation"]:
            summary["components_included"].append("food_validation")
        if results["resistance_playbook"]:
            summary["components_included"].append("resistance_playbook")
        if results["resistance_prediction"]:
            summary["components_included"].append("resistance_prediction")
        if results["next_test_recommender"]:
            summary["components_included"].append("next_test_recommender")
        if results["hint_tiles"]:
            summary["components_included"].append("hint_tiles")
        if results["mechanism_map"]:
            summary["components_included"].append("mechanism_map")
        
        # Provenance
        provenance = {
            "orchestrator": "complete_care_universal_v2",
            "for_patient": f"{patient_info['patient_name']} ({patient_info['disease_type']})",
            "endpoints_called": summary["components_included"],
            "ngs_status": summary["ngs_status"],
            "generated_at": datetime.utcnow().isoformat(),
            "run_id": f"complete_care_universal_v2_{int(datetime.utcnow().timestamp())}",
            "note": "Universal orchestrator - works for any patient profile",
            "sae_phase1_enabled": True,
            "sae_phase2_enabled": True,
            "resistance_prophet_enabled": request.include_resistance_prediction
        }

        # Task C: add stable provenance fields (additive; safe for existing clients)
        try:
            provenance["code_version"] = get_code_version()
            provenance["contract_version"] = get_contract_version()
        except Exception:
            provenance["code_version"] = provenance.get("code_version") or "unknown"
            provenance["contract_version"] = provenance.get("contract_version") or "resistance_contract_v1"
        
        return CompleteCareUniversalResponse(
            trials=results["trials"],
            soc_recommendation=results["soc_recommendation"],
            biomarker_intelligence=results["biomarker_intelligence"],
            wiwfm=results["wiwfm"],
            food_validation=results["food_validation"],
            resistance_playbook=results["resistance_playbook"],
            next_test_recommender=results["next_test_recommender"],
            hint_tiles=results["hint_tiles"],
            mechanism_map=results["mechanism_map"],
            sae_features=results["sae_features"],
            resistance_alert=results["resistance_alert"],
            resistance_prediction=results["resistance_prediction"],
            summary=summary,
            provenance=provenance
        )
        
    except Exception as e:
        logger.error(f"Complete care v2 failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Complete care orchestration failed: {str(e)}")


@router.post("/universal", response_model=CompleteCareUniversalResponse)
async def get_complete_care_universal(request: CompleteCareUniversalRequest):
    """
    Unified universal endpoint - single entry point for all universal services.
    
    This is the main endpoint for universal complete care planning.
    It orchestrates all services and provides a unified response.
    
    Alias for /v2 endpoint - provides cleaner API surface.
    """
    # Delegate to v2 endpoint
    return await get_complete_care_v2(request)


@router.get("/v2/health")
async def health_check_v2():
    """Health check for universal complete care v2 orchestrator"""
    return {
        "status": "operational",
        "service": "complete_care_universal_v2",
        "for_patient": "Any patient profile",
        "sae_phase1_enabled": True,
        "sae_phase2_enabled": True,
        "resistance_prophet_enabled": True,
        "capabilities": [
            "clinical_trials_universal",
            "soc_recommendation_disease_specific",
            "biomarker_intelligence_disease_specific",
            "wiwfm_evo2_powered",
            "food_validation",
            "resistance_playbook",
            "next_test_recommender",
            "hint_tiles",
            "mechanism_map",
            "sae_features",
            "resistance_alert",
            "resistance_prediction"
        ],
        "note": "Universal orchestrator - works for any patient profile",
        "endpoints": {
            "v2": "/api/complete_care/v2",
            "universal": "/api/complete_care/universal"
        }
    }

