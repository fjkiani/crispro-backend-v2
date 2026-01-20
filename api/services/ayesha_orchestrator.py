"""
Ayesha Complete Care Orchestrator

Orchestrates drug efficacy + food validator endpoints to return unified care plan.
Implements graceful degradation - returns partial results if one service fails.
Uses parallel API calls for optimal performance.
"""

import httpx
import asyncio
import os
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)

API_BASE = os.getenv("VITE_API_ROOT", "http://127.0.0.1:8000")

# Fallback food targets if drug call fails
FALLBACK_FOOD_TARGETS = ["vitamin_d", "curcumin", "omega3"]


async def call_drug_efficacy(
    client: httpx.AsyncClient,
    patient_context: Dict[str, Any],
    mutations: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Call drug efficacy endpoint.
    
    Args:
        client: httpx async client
        patient_context: Patient context dict
        mutations: Optional list of mutations (if None, will use disease defaults)
    
    Returns:
        Drug efficacy response dict or None if error
    """
    try:
        # If no mutations provided, create default mutation based on disease
        if not mutations:
            mutations = _get_default_mutations_for_disease(patient_context.get("disease", "ovarian_cancer_hgs"))
        
        payload = {
            "model_id": "evo2_1b",
            "mutations": mutations,
            "disease": patient_context.get("disease"),
            "germline_status": patient_context.get("germline_status", "unknown"),  # Sporadic Cancer Support
            "tumor_context": patient_context.get("tumor_context"),                # Sporadic Cancer Support
            "options": {
                "adaptive": True,
                "ensemble": False
            },
            "api_base": API_BASE
        }
        
        response = await client.post(
            f"{API_BASE}/api/efficacy/predict",
            json=payload,
            timeout=60.0
        )
        
        if response.status_code == 200:
            data = response.json()
            return data
        else:
            logger.error(f"Drug efficacy API error: {response.status_code}")
            return None
            
    except Exception as e:
        logger.error(f"Drug efficacy call failed: {str(e)}")
        return None


async def call_resistance_playbook(
    client: httpx.AsyncClient,
    patient_context: Dict[str, Any],
    drug_results: Optional[Dict[str, Any]] = None
) -> Optional[Dict[str, Any]]:
    """
    Call resistance playbook endpoint (NEW - Section 17).
    
    Args:
        client: httpx async client
        patient_context: Patient context dict
        drug_results: Drug efficacy results (for SAE features)
    
    Returns:
        Resistance playbook response or None if error
    """
    try:
        # Extract tumor_context and treatment_history
        tumor_context = patient_context.get("tumor_context")
        treatment_history = patient_context.get("treatment_history", {})
        
        # Skip if no tumor context (requires genomic data)
        if not tumor_context:
            logger.info("Skipping resistance playbook - no tumor context available")
            return None
        
        # Extract SAE features from drug results (if available)
        sae_features = None
        if drug_results and "drugs" in drug_results:
            # Extract SAE from top drug
            top_drug = drug_results["drugs"][0] if drug_results["drugs"] else {}
            sae_features = top_drug.get("sae_features")
        
        # Build payload
        payload = {
            "tumor_context": tumor_context,
            "treatment_history": treatment_history,
            "sae_features": sae_features
        }
        
        response = await client.post(
            f"{API_BASE}/api/care/resistance_playbook",
            json=payload,
            timeout=30.0
        )
        
        if response.status_code == 200:
            data = response.json()
            logger.info(f"✅ Resistance playbook: {len(data.get('risks', []))} risks, {len(data.get('combo_strategies', []))} combos")
            return data
        else:
            logger.warning(f"Resistance playbook API error: {response.status_code}")
            return None
            
    except Exception as e:
        logger.error(f"Resistance playbook call failed: {str(e)}")
        return None


def _get_default_mutations_for_disease(disease: str) -> List[Dict[str, Any]]:
    """Get default mutations for disease type (fallback if no NGS data)"""
    disease_mutations = {
        "ovarian_cancer_hgs": [
            {
                "gene": "TP53",
                "hgvs_p": "R273H",
                "chrom": "17",
                "pos": 7577120,
                "ref": "G",
                "alt": "A"
            }
        ],
        "breast_cancer": [
            {
                "gene": "PIK3CA",
                "hgvs_p": "E545K",
                "chrom": "3",
                "pos": 178936091,
                "ref": "G",
                "alt": "A"
            }
        ]
    }
    return disease_mutations.get(disease, disease_mutations["ovarian_cancer_hgs"])


def extract_food_targets_from_drug_mechanisms(
    drug_results: Dict[str, Any]
) -> List[str]:
    """
    Extract food targets from top drug mechanisms using pathway overlap.
    
    Strategy:
    - Top 3 drugs by efficacy_score
    - Extract their MoA/pathways
    - Map to supportive food targets (pathway overlap)
    
    Args:
        drug_results: Drug efficacy response
    
    Returns:
        List of food target pathways/mechanisms
    """
    if not drug_results or "drugs" not in drug_results:
        return []
    
    # Get top 3 drugs
    drugs = sorted(
        drug_results.get("drugs", []),
        key=lambda x: x.get("efficacy_score", 0.0),
        reverse=True
    )[:3]
    
    food_targets = []
    
    # Map drug mechanisms to food pathways
    mechanism_to_food = {
        "dna_repair": ["dna_repair_support", "antioxidant"],
        "parp_inhibition": ["dna_repair_support", "folate"],
        "angiogenesis": ["anti_angiogenic", "omega3"],
        "immunotherapy": ["immune_modulation", "vitamin_d"],
        "proteasome": ["anti_inflammatory", "curcumin"],
        "inflammation": ["anti_inflammatory", "omega3", "curcumin"],
        "oxidative_stress": ["antioxidant", "nac", "green_tea"]
    }
    
    for drug in drugs:
        moa = drug.get("moa", "").lower() or ""
        rationale = drug.get("rationale", "")
        
        # Handle rationale as list or string
        if isinstance(rationale, list):
            rationale_text = " ".join(str(r) for r in rationale).lower()
        else:
            rationale_text = str(rationale).lower()
        
        # Extract pathways from rationale or MoA
        for mechanism, food_paths in mechanism_to_food.items():
            if mechanism in moa or mechanism in rationale_text:
                food_targets.extend(food_paths)
    
    # Remove duplicates
    return list(set(food_targets))


async def call_food_validator(
    client: httpx.AsyncClient,
    patient_context: Dict[str, Any],
    food_targets: Optional[List[str]] = None,
    top_n: int = 5
) -> Dict[str, Any]:
    """
    Call food validator for supportive compounds.
    
    If food_targets provided, calls validator for specific compounds.
    Otherwise, calls for common supportive compounds.
    
    Args:
        client: httpx async client
        patient_context: Patient context dict
        food_targets: Optional list of food pathways to target
        top_n: Number of top foods to return
    
    Returns:
        Food recommendations dict or None if error
    """
    try:
        # Default supportive compounds if no targets specified
        default_compounds = ["Vitamin D", "Omega-3", "Curcumin", "Green Tea", "NAC", "Folate"]
        
        # If food_targets provided, map to compounds (simple heuristic)
        compounds_to_check = []
        if food_targets and len(food_targets) > 0:
            target_to_compound = {
                "dna_repair_support": ["Vitamin D", "Folate"],
                "antioxidant": ["NAC", "Green Tea"],
                "anti_inflammatory": ["Omega-3", "Curcumin"],
                "immune_modulation": ["Vitamin D", "Omega-3"],
                "anti_angiogenic": ["Green Tea", "Curcumin"],
                "dna_repair": ["Vitamin D", "Folate"],
                "folate": ["Folate", "Vitamin D"]
            }
            for target in food_targets:
                target_lower = target.lower()
                for key, compounds in target_to_compound.items():
                    if key.lower() in target_lower or target_lower in key.lower():
                        compounds_to_check.extend(compounds)
        
        # Fallback to defaults if no matches
        if not compounds_to_check:
            compounds_to_check = default_compounds
        
        # Remove duplicates while preserving order
        seen = set()
        compounds_to_check = [x for x in compounds_to_check if not (x in seen or seen.add(x))]
        
        # Call food validator for each compound and aggregate
        food_results = []
        
        for compound in compounds_to_check[:top_n]:
            try:
                # Extract treatment line and prior therapies
                treatment_line = 3  # Default L3
                if patient_context.get("treatment_history") and len(patient_context["treatment_history"]) > 0:
                    treatment_line = patient_context["treatment_history"][-1].get("line", 3)
                
                prior_therapies = [
                    drug for tx in patient_context.get("treatment_history", [])
                    for drug in tx.get("drugs", [])
                ]
                prior_therapies_str = ",".join(prior_therapies) if prior_therapies else ""
                
                # ⚔️ BUILD PAYLOAD FOR NEW DYNAMIC ENDPOINT
                disease = patient_context.get("disease", "ovarian_cancer")
                disease = _map_disease_to_food_validator_format(disease)
                
                # Build new payload structure for /validate_food_dynamic
                payload = {
                    "compound": compound,
                    "disease_context": {
                        "disease": disease,
                        "biomarkers": patient_context.get("biomarkers", {}),
                        "pathways_disrupted": patient_context.get("pathways_disrupted", [])
                    },
                    "treatment_history": {
                        "current_line": f"L{treatment_line}",
                        "prior_therapies": prior_therapies[:5] if prior_therapies else []
                    },
                    "patient_medications": patient_context.get("patient_medications", []),
                    "use_evo2": False,  # Keep Evo2 off for orchestrator calls (stability)
                    "use_llm": True
                }
                
                response = await client.post(
                    f"{API_BASE}/api/hypothesis/validate_food_dynamic",
                    json=payload,
                    timeout=60.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    # ⚔️ FIX: Check status field and ensure SUCCESS
                    if data.get("status") == "SUCCESS" and data.get("overall_score", 0.0) > 0:
                        recommendation = data.get("recommendation", {}) or {}
                        
                        # PHASE 2: Extract calibrated fields
                        spe_percentile = data.get("spe_percentile")
                        interpretation = data.get("interpretation")
                        provenance = data.get("provenance", {})
                        
                        food_results.append({
                            "compound": data.get("compound"),
                            "targets": data.get("mechanisms", [])[:5],  # Top 5 mechanisms as targets
                            "pathways": _extract_pathways_from_data(data),
                            "efficacy_score": data.get("overall_score", 0.0),
                            "confidence": _parse_confidence_to_float(data.get("confidence", "MODERATE")),
                            # PHASE 2: Calibrated scoring
                            "spe_percentile": spe_percentile,
                            "interpretation": interpretation,
                            # Existing fields
                            "sae_features": data.get("sae_features"),
                            "dosage": recommendation.get("dosage"),
                            "rationale": _build_food_rationale_phase2(data),  # Enhanced rationale
                            "citations": _extract_citations(data),
                            # PHASE 2: Provenance tracking
                            "compound_resolution": provenance.get("compound_resolution"),
                            "tcga_weights_used": provenance.get("tcga_weights", {}).get("used", False)
                        })
            except Exception as e:
                logger.warning(f"Food validator failed for {compound}: {str(e)}")
                continue
        
        # Sort by efficacy_score and return top N
        food_results.sort(key=lambda x: x.get("efficacy_score", 0.0), reverse=True)
        
        return {
            "foods": food_results[:top_n],
            "total_evaluated": len(compounds_to_check),
            "successful": len(food_results)
        }
        
    except Exception as e:
        logger.error(f"Food validator orchestration failed: {str(e)}")
        return None


def _extract_pathways_from_data(data: Dict[str, Any]) -> List[str]:
    """Extract pathway names from food validation data"""
    pathways = []
    
    # From A→B dependencies
    ab_deps = data.get("ab_dependencies", [])
    for dep in ab_deps:
        pathways.append(dep.get("A_pathways", []))
    
    # Flatten and dedupe
    flat_pathways = [p for sublist in pathways for p in (sublist if isinstance(sublist, list) else [sublist])]
    return list(set(flat_pathways))[:10]  # Top 10


def _build_food_rationale(data: Dict[str, Any]) -> str:
    """Build rationale string from food validation data"""
    verdict = data.get("verdict_explanation", "")
    ab_count = len(data.get("ab_dependencies", []))
    
    rationale = f"{verdict}. "
    if ab_count > 0:
        rationale += f"Found {ab_count} A→B mechanistic match(es). "
    
    evidence_grade = data.get("evidence", {}).get("grade", "")
    if evidence_grade:
        rationale += f"Evidence grade: {evidence_grade}."
    
    return rationale.strip()


def _build_food_rationale_phase2(data: Dict[str, Any]) -> str:
    """
    PHASE 2: Build enhanced rationale with calibrated scoring.
    
    Includes:
    - Verdict explanation
    - Calibrated percentile interpretation
    - Mechanistic matches
    - Evidence grade
    """
    rationale_parts = []
    
    # Verdict explanation
    verdict_exp = data.get("verdict_explanation", "")
    if verdict_exp:
        rationale_parts.append(verdict_exp)
    
    # PHASE 2: Calibrated percentile interpretation
    interpretation = data.get("interpretation")
    if interpretation:
        rationale_parts.append(f"Scores {interpretation.lower()} compared to other compounds")
    
    # Mechanistic matches
    ab_count = len(data.get("ab_dependencies", []))
    if ab_count > 0:
        rationale_parts.append(f"Found {ab_count} A→B mechanistic match(es)")
    
    # Evidence grade
    evidence_grade = data.get("evidence", {}).get("grade", "")
    if evidence_grade:
        rationale_parts.append(f"Evidence grade: {evidence_grade}")
    
    return ". ".join(rationale_parts) + "." if rationale_parts else "No significant evidence found."


def _extract_citations(data: Dict[str, Any]) -> List[str]:
    """Extract citation PMIDs from food validation data"""
    citations = []
    
    # From LLM evidence
    llm_evidence = data.get("llm_evidence", {})
    if llm_evidence.get("papers"):
        for paper in llm_evidence["papers"][:3]:
            if paper.get("pmid") and paper.get("pmid") != "N/A":
                citations.append(paper["pmid"])
    
    return citations


def _map_disease_to_food_validator_format(disease: str) -> str:
    """
    Map disease names to food validator's expected format.
    Food validator uses specific disease codes in its database.
    """
    if not disease:
        return "ovarian_cancer_hgs"  # Default
    
    disease_lower = disease.lower().replace(" ", "_").replace("-", "_")
    
    # Direct mapping for known variants
    disease_map = {
        # Ovarian cancer variants
        "ovarian_cancer": "ovarian_cancer_hgs",
        "ovarian": "ovarian_cancer_hgs",
        "ovarian_cancer_hgs": "ovarian_cancer_hgs",
        
        # Breast cancer variants
        "breast_cancer": "breast_cancer",
        "breast": "breast_cancer",
        
        # Lung cancer variants
        "lung_cancer": "lung_cancer",
        "lung": "lung_cancer",
        "nsclc": "lung_cancer",
        
        # Colorectal variants
        "colorectal_cancer": "colorectal_cancer",
        "colorectal": "colorectal_cancer",
        "colon_cancer": "colorectal_cancer",
        
        # Pancreatic variants
        "pancreatic_cancer": "pancreatic_cancer",
        "pancreatic": "pancreatic_cancer",
        
        # Prostate variants
        "prostate_cancer": "prostate_cancer",
        "prostate": "prostate_cancer",
        
        # Melanoma variants
        "melanoma": "melanoma",
        "skin_cancer": "melanoma",
        
        # Leukemia variants
        "leukemia": "leukemia",
        "aml": "leukemia",
        "all": "leukemia",
        "cll": "leukemia",
        
        # Multiple myeloma
        "multiple_myeloma": "multiple_myeloma",
        "myeloma": "multiple_myeloma",
        "mm": "multiple_myeloma"
    }
    
    # Try exact match first
    if disease_lower in disease_map:
        return disease_map[disease_lower]
    
    # Try partial match (e.g., "ovarian_cancer_serous" → "ovarian_cancer_hgs")
    for key, value in disease_map.items():
        if key in disease_lower or disease_lower in key:
            return value
    
    # Fallback: return as-is (food validator will handle unknown)
    return disease_lower


def _parse_confidence_to_float(confidence: str) -> float:
    """Parse confidence string to float"""
    if isinstance(confidence, (int, float)):
        return float(confidence)
    
    conf_str = str(confidence).upper()
    if "HIGH" in conf_str or "STRONG" in conf_str:
        return 0.8
    elif "MODERATE" in conf_str:
        return 0.6
    elif "LOW" in conf_str:
        return 0.4
    else:
        return 0.5


def compute_integrated_confidence(
    drug_results: Optional[Dict[str, Any]],
    food_results: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Compute integrated confidence from drug + food components.
    
    Uses weighted average: drug (60%) + food (40%)
    
    Args:
        drug_results: Drug efficacy results or None
        food_results: Food validation results or None
    
    Returns:
        {integrated_confidence, confidence_breakdown}
    """
    drug_confidence = 0.0
    food_confidence = 0.0
    
    # Extract drug confidence
    if drug_results and "drugs" in drug_results and len(drug_results["drugs"]) > 0:
        # Average confidence of top 3 drugs
        top_drugs = sorted(
            drug_results["drugs"],
            key=lambda x: x.get("efficacy_score", 0.0),
            reverse=True
        )[:3]
        drug_confidence = sum(
            d.get("confidence", 0.0) for d in top_drugs
        ) / len(top_drugs) if top_drugs else 0.0
    
    # Extract food confidence
    if food_results and "foods" in food_results and len(food_results["foods"]) > 0:
        # Average confidence of top 3 foods
        top_foods = sorted(
            food_results["foods"],
            key=lambda x: x.get("efficacy_score", 0.0),
            reverse=True
        )[:3]
        food_confidence = sum(
            f.get("confidence", 0.0) for f in top_foods
        ) / len(top_foods) if top_foods else 0.0
    
    # Weighted average: drug 60%, food 40%
    integrated_confidence = (drug_confidence * 0.6) + (food_confidence * 0.4)
    
    return {
        "integrated_confidence": round(integrated_confidence, 3),
        "confidence_breakdown": {
            "drug_component": round(drug_confidence, 3),
            "food_component": round(food_confidence, 3),
            "integration_method": "weighted_average"
        }
    }


async def build_complete_care_plan(
    patient_context: Dict[str, Any],
    mutations: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Main orchestration function - builds complete care plan.
    
    Flow:
    1. Call drug efficacy endpoint (parallel-ready)
    2. Extract food targets from drug mechanisms
    3. Call food validator for supportive compounds
    4. Call resistance playbook (NEW - Section 17)
    5. Compute integrated confidence
    6. Return unified response with graceful error handling
    
    Args:
        patient_context: Complete patient context
        mutations: Optional mutations (if None, uses disease defaults)
    
    Returns:
        Complete care plan response dict
    """
    run_id = str(uuid.uuid4())
    timestamp = datetime.utcnow().isoformat() + "Z"
    
    errors = []
    drug_results = None
    food_results = None
    resistance_playbook = None  # NEW: Section 17
    
    async with httpx.AsyncClient() as client:
        # Step 1: Call drug efficacy
        try:
            drug_results = await call_drug_efficacy(client, patient_context, mutations)
            if not drug_results:
                errors.append("Drug efficacy analysis unavailable")
        except Exception as e:
            logger.error(f"Drug efficacy orchestration failed: {str(e)}")
            errors.append(f"Drug efficacy error: {str(e)}")
        
        # Step 2: Extract food targets from drug mechanisms
        food_targets = []
        if drug_results:
            food_targets = extract_food_targets_from_drug_mechanisms(drug_results)
        
        # Step 3: Call food validator
        try:
            food_results = await call_food_validator(client, patient_context, food_targets)
            if not food_results:
                errors.append("Food validation analysis unavailable")
        except Exception as e:
            logger.error(f"Food validator orchestration failed: {str(e)}")
            errors.append(f"Food validation error: {str(e)}")
        
        # Step 4: Call resistance playbook (NEW - Section 17)
        try:
            resistance_playbook = await call_resistance_playbook(client, patient_context, drug_results)
        except Exception as e:
            logger.warning(f"Resistance playbook failed: {str(e)}")
            # Non-blocking - continue without resistance playbook
        
        # Step 5: Compute integrated confidence
        confidence_data = compute_integrated_confidence(drug_results, food_results)
        
        # Step 6: Build unified response
        response = {
            "run_id": run_id,
            "timestamp": timestamp,
            "patient_context": patient_context,
            "drug_recommendations": [],
            "food_recommendations": [],
            "resistance_playbook": None,  # NEW: Section 17
            "integrated_confidence": confidence_data["integrated_confidence"],
            "confidence_breakdown": confidence_data["confidence_breakdown"],
            "provenance": {
                "drug_analysis": {
                    "endpoint": "/api/efficacy/predict",
                    "data_sources": ["pubmed", "clinvar", "chembl"],
                    "papers_reviewed": 0,  # Will be populated from drug_results if available
                    "run_id": drug_results.get("provenance", {}).get("run_id") if drug_results else None,
                    "timestamp": drug_results.get("provenance", {}).get("timestamp") if drug_results else None
                },
                "food_analysis": {
                    "endpoint": "/api/hypothesis/validate_food_ab_enhanced",
                    "data_sources": ["pubmed", "chembl"],
                    "papers_reviewed": 0,  # Will be populated from food_results if available
                    "run_id": None,
                    "timestamp": None
                },
                "resistance_analysis": {  # NEW: Section 17
                    "endpoint": "/api/care/resistance_playbook",
                    "enabled": bool(resistance_playbook),
                    "version": "1.0"
                }
            }
        }
        
        # Populate drug recommendations
        if drug_results and "drugs" in drug_results:
            for drug in drug_results["drugs"][:5]:  # Top 5
                response["drug_recommendations"].append({
                    "drug": drug.get("name", "Unknown"),
                    "efficacy_score": drug.get("efficacy_score", 0.0),
                    "confidence": drug.get("confidence", 0.0),
                    "tier": drug.get("evidence_tier", "insufficient"),
                    "sae_features": drug.get("sae_features"),
                    "rationale": _extract_drug_rationale(drug),
                    "citations": drug.get("citations", []),
                    "badges": drug.get("badges", []),
                    "insights": drug.get("insights")
                })
            
            # Update provenance with drug data
            drug_prov = drug_results.get("provenance", {})
            if drug_prov:
                response["provenance"]["drug_analysis"]["papers_reviewed"] = drug_prov.get("llm_papers_found", 0)
        
        # Populate food recommendations
        if food_results and "foods" in food_results:
            for food in food_results["foods"][:5]:  # Top 5
                response["food_recommendations"].append({
                    "compound": food.get("compound"),
                    "targets": food.get("targets", []),
                    "pathways": food.get("pathways", []),
                    "efficacy_score": food.get("efficacy_score", 0.0),
                    "confidence": food.get("confidence", 0.0),
                    "sae_features": food.get("sae_features"),
                    "dosage": food.get("dosage"),
                    "rationale": food.get("rationale"),
                    "citations": food.get("citations", [])
                })
        
        # Populate resistance playbook (NEW - Section 17)
        if resistance_playbook:
            response["resistance_playbook"] = {
                "risks": resistance_playbook.get("risks", []),
                "combo_strategies": resistance_playbook.get("combo_strategies", [])[:3],  # Top 3
                "next_line_switches": resistance_playbook.get("next_line_switches", [])[:3],  # Top 3
                "trial_keywords": resistance_playbook.get("trial_keywords", []),
                "provenance": resistance_playbook.get("provenance", {})
            }
        
        # Add errors if any
        if errors:
            response["errors"] = errors
        
        return response


def _extract_drug_rationale(drug: Dict[str, Any]) -> str:
    """Extract rationale from drug result"""
    rationale_list = drug.get("rationale", [])
    if isinstance(rationale_list, list) and rationale_list:
        # Concatenate rationale items
        return ". ".join([str(r.get("value", r)) if isinstance(r, dict) else str(r) for r in rationale_list[:3]])
    return drug.get("rationale", "No rationale available")

