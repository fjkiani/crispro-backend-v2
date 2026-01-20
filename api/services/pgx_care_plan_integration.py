"""
PGx Care Plan Integration

Integrates PGx screening and risk-benefit composition into care plan orchestrator.

Purpose: Add PGx safety screening to drug efficacy results and compose
integrated feasibility scores for trial matching.

Research Use Only - Not for Clinical Decision Making
"""

import logging
from typing import Dict, List, Any, Optional
from api.services.pgx_screening_service import get_pgx_screening_service
from api.services.risk_benefit_composition_service import get_risk_benefit_composition_service

logger = logging.getLogger(__name__)


async def integrate_pgx_into_drug_efficacy(
    drug_efficacy_response: Dict[str, Any],
    patient_profile: Dict[str, Any],
    treatment_line: Optional[str] = None,
    prior_therapies: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Integrate PGx screening into drug efficacy response.
    
    Args:
        drug_efficacy_response: Response from drug efficacy API (WIWFM)
        patient_profile: Patient profile with germline_variants
        treatment_line: Treatment line
        prior_therapies: List of prior therapies
    
    Returns:
        Enhanced drug efficacy response with PGx screening and risk-benefit scores
    """
    if not drug_efficacy_response or drug_efficacy_response.get("status") == "awaiting_ngs":
        return drug_efficacy_response
    
    # Extract germline variants
    germline_variants = patient_profile.get("germline_variants", [])
    if not germline_variants:
        logger.info("No germline variants found - skipping PGx screening")
        return drug_efficacy_response
    
    # Extract drugs from efficacy response
    drugs = drug_efficacy_response.get("drugs", [])
    if not drugs:
        return drug_efficacy_response
    
    # Screen drugs for PGx safety
    try:
        pgx_screening_service = get_pgx_screening_service()
    except Exception as e:
        logger.error(f"Failed to get PGx screening service: {e}", exc_info=True)
        # Return unchanged response if service unavailable
        return drug_efficacy_response
    
    disease = patient_profile.get("disease", {}).get("type") if isinstance(patient_profile.get("disease"), dict) else patient_profile.get("disease")
    
    try:
        screening_results = await pgx_screening_service.screen_drugs(
            drugs=drugs,
            germline_variants=germline_variants,
            treatment_line=treatment_line,
            prior_therapies=prior_therapies,
            disease=disease
        )
        # Ensure screening_results is a dict (should always be, but defensive check)
        if screening_results is None:
            logger.warning("PGx screening returned None - using empty dict")
            screening_results = {}
    except Exception as e:
        logger.error(f"PGx screening failed: {e}", exc_info=True)
        # Return unchanged response if screening fails
        return drug_efficacy_response
    
    # Compose risk-benefit scores
    try:
        risk_benefit_service = get_risk_benefit_composition_service()
    except Exception as e:
        logger.error(f"Failed to get risk-benefit service: {e}", exc_info=True)
        # Continue without risk-benefit composition (use efficacy scores only)
        risk_benefit_service = None
    
    enhanced_drugs = []
    for drug in drugs:
        drug_name = drug.get("name") or drug.get("drug") or "unknown"
        efficacy_score = drug.get("efficacy_score", 0.0)
        
        # Get PGx screening results
        pgx_result = screening_results.get(drug_name, {})
        toxicity_tier = pgx_result.get("toxicity_tier")
        adjustment_factor = pgx_result.get("adjustment_factor")
        
        # Compose risk-benefit (with fallback if service unavailable)
        if risk_benefit_service is not None:
            try:
                risk_benefit = risk_benefit_service.compose_risk_benefit(
                    efficacy_score=efficacy_score,
                    toxicity_tier=toxicity_tier,
                    adjustment_factor=adjustment_factor
                )
            except Exception as e:
                logger.warning(f"Risk-benefit composition failed for {drug_name}: {e}")
                # Fallback: use efficacy score as composite score
                risk_benefit = type('RiskBenefitResult', (), {
                    'composite_score': efficacy_score,
                    'action_label': 'STANDARD USE (PGx screened, risk-benefit unavailable)',
                    'rationale': f'PGx screening completed but risk-benefit composition failed',
                    'provenance': {'pgx_screened': True, 'composition_method': 'fallback'}
                })()
        else:
            # Fallback: use efficacy score as composite score
            risk_benefit = type('RiskBenefitResult', (), {
                'composite_score': efficacy_score,
                'action_label': 'STANDARD USE (PGx screened, risk-benefit unavailable)',
                'rationale': f'PGx screening completed but risk-benefit service unavailable',
                'provenance': {'pgx_screened': True, 'composition_method': 'fallback'}
            })()
        
        # Enhance drug dict
        enhanced_drug = {
            **drug,
            "pgx_screening": pgx_result,
            "composite_score": risk_benefit.composite_score,
            "action_label": risk_benefit.action_label,
            "risk_benefit_rationale": risk_benefit.rationale,
            "risk_benefit_provenance": risk_benefit.provenance
        }
        
        enhanced_drugs.append(enhanced_drug)
    
    # Sort by composite score (descending)
    enhanced_drugs.sort(key=lambda d: d.get("composite_score", 0.0), reverse=True)
    
    # Build enhanced response
    enhanced_response = {
        **drug_efficacy_response,
        "drugs": enhanced_drugs,
        "pgx_screening_summary": {
            "screened_drugs": len(screening_results),
            "high_risk_drugs": sum(1 for r in screening_results.values() if r.get("toxicity_tier") == "HIGH"),
            "moderate_risk_drugs": sum(1 for r in screening_results.values() if r.get("toxicity_tier") == "MODERATE"),
            "low_risk_drugs": sum(1 for r in screening_results.values() if r.get("toxicity_tier") == "LOW" or r.get("toxicity_tier") is None)
        }
    }
    
    logger.info(f"✅ PGx screening integrated: {len(enhanced_drugs)} drugs screened, {enhanced_response['pgx_screening_summary']['high_risk_drugs']} high-risk")
    
    return enhanced_response


async def add_pgx_safety_gate_to_trials(
    trials_response: Dict[str, Any],
    patient_profile: Dict[str, Any],
    treatment_line: Optional[str] = None,
    prior_therapies: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Add PGx safety gate to trial matches.
    
    Args:
        trials_response: Response from trial matching API
        patient_profile: Patient profile with germline_variants
        treatment_line: Treatment line
        prior_therapies: List of prior therapies
    
    Returns:
        Enhanced trials response with PGx safety flags
    """
    if not trials_response or not trials_response.get("trials"):
        return trials_response
    
    # Extract germline variants
    germline_variants = patient_profile.get("germline_variants", [])
    if not germline_variants:
        return trials_response
    
    # Extract drugs from trials
    trials = trials_response.get("trials", [])
    all_drugs = set()
    trials_with_interventions = []
    trials_without_interventions = []
    
    for trial in trials:
        interventions = trial.get("interventions", [])
        if not interventions or len(interventions) == 0:
            # Trial has no intervention data - mark as UNKNOWN
            trials_without_interventions.append(trial)
        else:
            trials_with_interventions.append(trial)
            for intervention in interventions:
                # Handle dict format (from matching agent)
                if isinstance(intervention, dict):
                    drug_name = intervention.get("name") or intervention.get("drug")
                    if drug_name:
                        all_drugs.add(drug_name.lower().strip())
                    # Also check drug_names list
                    for dn in intervention.get("drug_names", []):
                        if dn:
                            all_drugs.add(dn.lower().strip())
                # Handle string format (comma-separated or simple name)
                elif isinstance(intervention, str) and intervention.strip():
                    all_drugs.add(intervention.lower().strip())
    
    # If no trials have interventions, mark all as UNKNOWN and return early
    if not all_drugs:
        enhanced_trials = []
        for trial in trials:
            enhanced_trial = {
                **trial,
                "pgx_safety": {
                    "has_high_risk_drug": False,
                    "has_moderate_risk_drug": False,
                    "alerts": [],
                    "safety_status": "UNKNOWN_NO_INTERVENTIONS",
                    "reason": "Trial payload does not include intervention drug list"
                }
            }
            enhanced_trials.append(enhanced_trial)
        
        return {
            **trials_response,
            "trials": enhanced_trials,
            "pgx_safety_summary": {
                "total_trials": len(enhanced_trials),
                "high_risk_trials": 0,
                "moderate_risk_trials": 0,
                "safe_trials": 0,
                "unknown_trials": len(enhanced_trials)
            }
        }
    
    # Screen all drugs
    try:
        pgx_screening_service = get_pgx_screening_service()
    except Exception as e:
        logger.error(f"Failed to get PGx screening service for trials: {e}", exc_info=True)
        # Return trials with UNKNOWN status if service unavailable
        enhanced_trials = []
        for trial in trials:
            enhanced_trials.append({
                **trial,
                "pgx_safety": {
                    "has_high_risk_drug": False,
                    "has_moderate_risk_drug": False,
                    "alerts": [],
                    "safety_status": "UNKNOWN_SERVICE_UNAVAILABLE",
                    "reason": f"PGx screening service unavailable: {str(e)}",
                },
            })
        return {
            **trials_response,
            "trials": enhanced_trials,
            "pgx_safety_summary": {
                "total_trials": len(enhanced_trials),
                "high_risk_trials": 0,
                "moderate_risk_trials": 0,
                "safe_trials": 0,
                "unknown_trials": len(enhanced_trials),
            },
        }
    
    disease = patient_profile.get("disease", {}).get("type") if isinstance(patient_profile.get("disease"), dict) else patient_profile.get("disease")
    
    drugs_list = [{"name": d} for d in all_drugs]
    try:
        screening_results = await pgx_screening_service.screen_drugs(
            drugs=drugs_list,
            germline_variants=germline_variants,
            treatment_line=treatment_line,
            prior_therapies=prior_therapies,
            disease=disease
        )
        # Ensure screening_results is a dict (should always be, but defensive check)
        if screening_results is None:
            logger.warning("PGx screening returned None for trials - using empty dict")
            screening_results = {}
    except Exception as e:
        logger.error(f"PGx screening failed for trials: {e}", exc_info=True)
        # Return trials with UNKNOWN status if screening fails
        enhanced_trials = []
        for trial in trials:
            enhanced_trials.append({
                **trial,
                "pgx_safety": {
                    "has_high_risk_drug": False,
                    "has_moderate_risk_drug": False,
                    "alerts": [],
                    "safety_status": "UNKNOWN_SCREENING_FAILED",
                    "reason": f"PGx screening failed: {str(e)}",
                },
            })
        return {
            **trials_response,
            "trials": enhanced_trials,
            "pgx_safety_summary": {
                "total_trials": len(enhanced_trials),
                "high_risk_trials": 0,
                "moderate_risk_trials": 0,
                "safe_trials": 0,
                "unknown_trials": len(enhanced_trials),
            },
        }
    
    # Add safety flags to trials
    enhanced_trials = []
    for trial in trials:
        interventions = trial.get("interventions", [])
        
        # CRITICAL: If trial has no interventions, mark as UNKNOWN (not SAFE)
        if not interventions or len(interventions) == 0:
            enhanced_trial = {
                **trial,
                "pgx_safety": {
                    "has_high_risk_drug": False,
                    "has_moderate_risk_drug": False,
                    "alerts": [],
                    "safety_status": "UNKNOWN_NO_INTERVENTIONS",
                    "reason": "Trial payload does not include intervention drug list"
                }
            }
            enhanced_trials.append(enhanced_trial)
            continue
        
        # Trial has interventions - screen each drug
        has_high_risk_drug = False
        has_moderate_risk_drug = False
        pgx_alerts = []
        
        for intervention in interventions:
            drug_name = intervention.get("name") or intervention.get("drug")
            if drug_name:
                pgx_result = screening_results.get(drug_name, {})
                if pgx_result.get("toxicity_tier") == "HIGH":
                    has_high_risk_drug = True
                    pgx_alerts.extend(pgx_result.get("alerts", []))
                elif pgx_result.get("toxicity_tier") == "MODERATE":
                    has_moderate_risk_drug = True
        
        enhanced_trial = {
            **trial,
            "pgx_safety": {
                "has_high_risk_drug": has_high_risk_drug,
                "has_moderate_risk_drug": has_moderate_risk_drug,
                "alerts": pgx_alerts,
                "safety_status": "HIGH_RISK" if has_high_risk_drug else ("MODERATE_RISK" if has_moderate_risk_drug else "SAFE")
            }
        }
        
        enhanced_trials.append(enhanced_trial)
    
    # Build enhanced response
    unknown_trials = sum(1 for t in enhanced_trials if t["pgx_safety"]["safety_status"] == "UNKNOWN_NO_INTERVENTIONS")
    enhanced_response = {
        **trials_response,
        "trials": enhanced_trials,
        "pgx_safety_summary": {
            "total_trials": len(enhanced_trials),
            "high_risk_trials": sum(1 for t in enhanced_trials if t["pgx_safety"]["has_high_risk_drug"]),
            "moderate_risk_trials": sum(1 for t in enhanced_trials if t["pgx_safety"]["has_moderate_risk_drug"]),
            "safe_trials": sum(1 for t in enhanced_trials if t["pgx_safety"]["safety_status"] == "SAFE"),
            "unknown_trials": unknown_trials
        }
    }
    
    logger.info(f"✅ PGx safety gate applied: {enhanced_response['pgx_safety_summary']['high_risk_trials']} high-risk trials flagged")
    
    return enhanced_response


