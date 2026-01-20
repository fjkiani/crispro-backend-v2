from fastapi import APIRouter, HTTPException
import json
import logging
from pathlib import Path
from typing import List, Dict, Optional, Any
import uuid
from datetime import datetime

from api.services.llm_literature_service import get_llm_service

logger = logging.getLogger(__name__)

# Import SAE service at top to avoid NameError
try:
    from api.services.food_treatment_line_service import compute_food_treatment_line_features
    SAE_AVAILABLE = True
except ImportError:
    SAE_AVAILABLE = False
    print("WARNING: food_treatment_line_service not available - SAE features disabled")

router = APIRouter()

# Load data files
DATA_DIR = Path(__file__).parent.parent.parent.parent.parent / ".cursor/ayesha/hypothesis_validator/data"
DISEASE_AB_FILE = DATA_DIR / "disease_ab_dependencies.json"
FOOD_TARGETS_FILE = DATA_DIR / "food_targets.json"
CANCER_TYPE_FOODS_FILE = DATA_DIR / "cancer_type_food_recommendations.json"
BIOMARKER_FOODS_FILE = DATA_DIR / "biomarker_food_mapping.json"

# Load once at module import
with open(DISEASE_AB_FILE) as f:
    DISEASE_AB = json.load(f)
with open(FOOD_TARGETS_FILE) as f:
    FOOD_TARGETS = json.load(f)

# Load cancer type and biomarker food mappings (optional - may not exist)
def load_cancer_type_foods() -> Dict[str, Any]:
    """Load cancer type-specific food recommendations."""
    if CANCER_TYPE_FOODS_FILE.exists():
        try:
            with open(CANCER_TYPE_FOODS_FILE) as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load cancer type foods: {e}")
    return {"cancer_types": {}}

def load_biomarker_foods() -> Dict[str, Any]:
    """Load biomarker-specific food recommendations."""
    if BIOMARKER_FOODS_FILE.exists():
        try:
            with open(BIOMARKER_FOODS_FILE) as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load biomarker foods: {e}")
    return {"biomarker_mappings": {}}

@router.post("/api/hypothesis/validate_food_ab")
async def validate_food_ab(
    compound: str,
    disease: str = "ovarian_cancer_hgs",
    germline_status: str = "negative",
    treatment_line: Optional[int] = None,
    prior_therapies: Optional[List[str]] = None
):
    """
    A→B Dependency Food Validator (NO TUMOR NGS REQUIRED)
    
    Strategy:
    1. Use disease biology to infer likely A alterations (TP53, HRD, inflammation)
    2. Map A → B dependencies from disease profile
    3. Check if food compound targets B
    4. Score plausibility, evidence, bioavailability
    5. Return verdict with mechanistic explanation
    
    For Ayesha (germline negative, ovarian HGS, L3 post-platinum):
    - Infers: TP53 mutation (96%), somatic HRD (50%), inflammation (80%), oxidative stress (90%)
    - Maps to B dependencies: DNA repair, glutathione, NF-κB, proteasome
    - Ranks foods by A→B match strength + evidence grade + bioavailability
    """
    
    # 1. Get disease A→B map (using new service)
    disease_data = get_disease_data(disease)
    
    if not disease_data:
        # Get available diseases from both sources
        available = list(DISEASE_AB.keys())
        try:
            universal_db_path = Path(__file__).parent.parent / "resources" / "universal_disease_pathway_database.json"
            if universal_db_path.exists():
                with open(universal_db_path) as f:
                    universal_db = json.load(f)
                available.extend(list(universal_db.get('diseases', {}).keys()))
        except:
            pass
        available = sorted(set(available))
        raise HTTPException(404, f"Disease '{disease}' not in database. Available: {available[:10]}...")
    
    # 2. Find food compound
    compound_lower = compound.lower()
    matched_food = None
    for food in FOOD_TARGETS['foods']:
        # Check compound name and aliases
        if compound_lower in food['compound'].lower():
            matched_food = food
            break
        for alias in food.get('aliases', []):
            if compound_lower in alias.lower():
                matched_food = food
                break
        if matched_food:
            break
    
    if not matched_food:
        available_compounds = [f['compound'] for f in FOOD_TARGETS['foods']]
        return {
            "status": "UNKNOWN",
            "message": f"No data for '{compound}'. Try: {', '.join(available_compounds[:3])}...",
            "available_compounds": available_compounds
        }
    
    # 3. Match food B-targets to disease B-dependencies
    ab_matches = []
    for A_alteration in disease_data['A_alterations']:
        A_name = A_alteration['A']
        A_prevalence = A_alteration['prevalence']
        A_pathways = A_alteration['pathways_disrupted']
        
        for B_dep in A_alteration['B_dependencies']:
            if not B_dep.get('targetable_with_food'):
                continue
            
            # Check if food targets this B
            B_name = B_dep['B']
            B_rationale = B_dep['rationale']
            food_b_targets = matched_food['B_targets']
            food_mechanisms = matched_food['mechanisms']
            
            # Match score: check if any food B-target overlaps with disease B-dependency
            match_score = 0.0
            matched_mechanism = ""
            
            for food_target in food_b_targets:
                # Exact or partial match
                if food_target.lower() in B_name.lower() or B_name.lower() in food_target.lower():
                    match_score = 1.0
                    # Find corresponding mechanism
                    for mech in food_mechanisms:
                        if food_target.lower() in mech.lower() or B_name.split()[0].lower() in mech.lower():
                            matched_mechanism = mech
                            break
                    break
                
                # Pathway-level match (e.g., "DNA repair" matches "DNA synthesis")
                for keyword in ['DNA', 'NF-κB', 'COX-2', 'Glutathione', 'Proteasome', 'Autophagy', 'STAT3', 'Immune']:
                    if keyword.lower() in food_target.lower() and keyword.lower() in B_name.lower():
                        match_score = 0.7
                        matched_mechanism = next((m for m in food_mechanisms if keyword.lower() in m.lower()), food_mechanisms[0])
                        break
            
            if match_score > 0:
                ab_matches.append({
                    "A": A_name,
                    "A_prevalence": A_prevalence,
                    "A_pathways": A_pathways,
                    "B": B_name,
                    "B_rationale": B_rationale,
                    "food_mechanism": matched_mechanism if matched_mechanism else food_mechanisms[0],
                    "match_score": match_score,
                    "match_strength": "STRONG" if match_score >= 0.9 else "MODERATE" if match_score >= 0.6 else "WEAK"
                })
    
    # 4. Compute overall verdict
    if not ab_matches:
        verdict = "NOT_RELEVANT"
        recommendation = f"{matched_food['compound']} doesn't target pathways likely disrupted in {disease_data['disease_name']}"
        overall_score = 0.0
        confidence = "N/A"
    else:
        # Weighted by A prevalence and match score
        weighted_score = sum([m['A_prevalence'] * m['match_score'] for m in ab_matches]) / max(len(ab_matches), 1)
        evidence_grade = matched_food['evidence_grade']
        bioavailability = matched_food['bioavailability']
        
        # Verdict logic
        if evidence_grade == "MODERATE" and weighted_score > 0.5 and bioavailability in ["GOOD", "MODERATE"]:
            verdict = "SUPPORTED"
            overall_score = 0.75
            confidence = "MODERATE"
        elif evidence_grade == "MODERATE" and bioavailability == "POOR":
            verdict = "WEAK_SUPPORT"
            overall_score = 0.50
            confidence = "LOW (bioavailability barrier)"
        elif evidence_grade == "WEAK" and weighted_score > 0.6:
            verdict = "WEAK_SUPPORT"
            overall_score = 0.55
            confidence = "LOW-MODERATE (limited evidence)"
        elif evidence_grade == "WEAK" and weighted_score > 0.3:
            verdict = "WEAK_SUPPORT"
            overall_score = 0.40
            confidence = "LOW"
        else:
            verdict = "WEAK_SUPPORT"
            overall_score = 0.30
            confidence = "LOW"
        
        recommendation = f"{matched_food['compound']} targets {len(ab_matches)} relevant A→B dependencies in {disease_data['disease_name']}"
    
    # 5. Treatment line context (post-platinum adjustments)
    line_context = ""
    if treatment_line and treatment_line >= 2 and prior_therapies:
        prior_str = str(prior_therapies).lower()
        
        if "platinum" in prior_str or "carboplatin" in prior_str or "cisplatin" in prior_str:
            # Platinum creates oxidative stress and DNA damage
            line_context_parts = []
            line_context_parts.append("⚠️ Post-platinum context: Elevated oxidative stress and DNA damage.")
            
            # Boost certain compounds
            if matched_food['compound'] in ["NAC (N-Acetylcysteine)", "Vitamin D", "Omega-3 Fatty Acids (EPA/DHA)"]:
                line_context_parts.append(f"✅ {matched_food['compound']} may help buffer platinum-induced stress and support recovery.")
                overall_score = min(overall_score + 0.10, 1.0)  # Modest boost
            
            if matched_food['compound'] == "NAC (N-Acetylcysteine)":
                line_context_parts.append("⏰ Timing: Take NAC 2-3 hours AFTER platinum infusion (avoid during infusion to prevent antioxidant interference).")
            
            line_context = " ".join(line_context_parts)
    
    # 6. Extract ovarian-specific relevance
    ovarian_relevance = matched_food.get('ab_relevance_ovarian', {})
    
    return {
        "status": "SUCCESS",
        "compound": matched_food['compound'],
        "aliases": matched_food.get('aliases', []),
        "verdict": verdict,
        "verdict_explanation": {
            "SUPPORTED": "✅ Moderate-to-strong evidence supports benefit",
            "WEAK_SUPPORT": "⚠️ Limited evidence, but biologically plausible (research use)",
            "NOT_RELEVANT": "❌ No credible mechanistic link to disease",
        }[verdict],
        "overall_score": round(overall_score, 2),
        "confidence": confidence,
        "ab_dependencies": ab_matches,
        "mechanisms": matched_food['mechanisms'],
        "evidence": {
            "grade": matched_food['evidence_grade'],
            "summary": matched_food['evidence_summary'],
            "ovarian_data": matched_food.get('ovarian_specific_data', {})
        },
        "bioavailability": {
            "status": matched_food['bioavailability'],
            "notes": matched_food.get('bioavailability_notes', "")
        },
        "recommendation": {
            "dosage": matched_food['dosage'],
            "safety": matched_food['safety'],
            "safety_notes": matched_food['safety_notes'],
            "cost": matched_food['cost'],
            "food_sources": matched_food.get('food_sources', []),
            "line_context": line_context
        },
        "ovarian_relevance": ovarian_relevance,
        "provenance": {
            "method": "disease_ab_mapping_v1",
            "disease": disease,
            "disease_name": disease_data['disease_name'],
            "germline_status": germline_status,
            "treatment_line": treatment_line,
            "prior_therapies": prior_therapies,
            "ab_matches_count": len(ab_matches),
            "ruo_disclaimer": "Research Use Only - supports, not replaces, clinical judgment"
        }
    }

@router.get("/api/hypothesis/list_compounds")
async def list_compounds():
    """List all available food/supplement compounds in database"""
    return {
        "compounds": [
            {
                "name": food['compound'],
                "aliases": food.get('aliases', []),
                "targets": food['B_targets'],
                "evidence_grade": food['evidence_grade']
            }
            for food in FOOD_TARGETS['foods']
        ]
    }

@router.get("/api/hypothesis/list_diseases")
async def list_diseases():
    """List all available disease profiles in database"""
    return {
        "diseases": [
            {
                "id": disease_id,
                "name": disease_data['disease_name'],
                "description": disease_data.get('description', ''),
                "alterations_count": len(disease_data['A_alterations'])
            }
            for disease_id, disease_data in DISEASE_AB.items()
        ]
    }

@router.post("/api/hypothesis/validate_food_ab_enhanced")
async def validate_food_ab_enhanced(
    compound: str,
    disease: str = "ovarian_cancer_hgs",
    germline_status: str = "negative",
    treatment_line: Optional[int] = None,
    prior_therapies: Optional[List[str]] = None,
    use_llm: bool = True
):
    """
    Enhanced A→B Food Validator with LLM Literature Mining, SAE Features, and Complete Provenance
    
    Flow:
    1. Check hardcoded data first (fast, deterministic)
    2. Compute SAE features (line appropriateness, cross-resistance, sequencing fitness)
    3. If confidence < 0.7 OR use_llm=True, query LLM for additional evidence
    4. Merge results and boost confidence from literature
    5. Return structured SAE features + complete provenance
    
    This gives Ayesha dynamic, evidence-backed recommendations beyond hardcoded data.
    """
    import uuid
    from datetime import datetime
    from api.services.food_treatment_line_service import compute_food_treatment_line_features
    
    # Generate run_id and timestamp for provenance
    run_id = str(uuid.uuid4())
    timestamp = datetime.utcnow().isoformat() + "Z"
    
    # Step 1: Get hardcoded result (fast)
    base_result = await validate_food_ab(
        compound=compound,
        disease=disease,
        germline_status=germline_status,
        treatment_line=treatment_line,
        prior_therapies=prior_therapies
    )
    
    # If UNKNOWN compound, return early (but still include provenance)
    if base_result.get("status") == "UNKNOWN":
        return {
            **base_result,
            "provenance": {
                **base_result.get('provenance', {}),
                "run_id": run_id,
                "timestamp": timestamp,
                "method": "disease_ab_mapping_v1",
                "llm_enabled": use_llm
            }
        }
    
    # Step 2: Compute SAE features (treatment line intelligence)
    # ⚔️ INTEGRATION FIX: Load pathways from universal database (TCGA-weighted)
    # Fallback to DISEASE_AB for backward compatibility
    pathways_disrupted = []
    try:
        universal_db_path = Path(__file__).parent.parent / "resources" / "universal_disease_pathway_database.json"
        if universal_db_path.exists():
            with open(universal_db_path) as f:
                universal_db = json.load(f)
            disease_data = universal_db.get('diseases', {}).get(disease, {})
            pathways = disease_data.get('pathways', {})
            # Extract pathway names (keys) for pathway_disrupted list
            pathways_disrupted = list(pathways.keys())
            # Also add pathway descriptions for keyword matching
            for pathway_name, pathway_info in pathways.items():
                if isinstance(pathway_info, dict):
                    desc = pathway_info.get('description', pathway_name)
                    if desc not in pathways_disrupted:
                        pathways_disrupted.append(desc)
    except Exception as e:
        print(f"⚠️ Failed to load universal database, using DISEASE_AB fallback: {e}")
    
    # Fallback to old system if universal DB didn't provide pathways
    if not pathways_disrupted:
        pathways_disrupted = DISEASE_AB.get(disease, {}).get('likely_alterations', [])
    
    disease_context = {
        "disease": disease,
        "germline_status": germline_status,
        "biomarkers": {},  # Can be enhanced later with actual biomarker data
        "pathways_disrupted": pathways_disrupted
    }
    
    treatment_history = None
    if treatment_line is not None or prior_therapies:
        treatment_history = {
            "current_line": treatment_line or 0,
            "prior_therapies": prior_therapies or []
        }
    
    # Compute SAE scores with null safety
    sae_scores = None
    if SAE_AVAILABLE:
        try:
            sae_scores = compute_food_treatment_line_features(
                compound=compound,
                disease_context=disease_context,
                treatment_history=treatment_history
            )
        except Exception as e:
            print(f"⚠️ SAE computation failed: {e}")
            sae_scores = None
    
    # Structure SAE features with status/reason (with safe defaults)
    line_appropriateness = sae_scores.get("line_appropriateness", 0.6) if sae_scores else 0.6
    cross_resistance = sae_scores.get("cross_resistance", 0.0) if sae_scores else 0.0
    sequencing_fitness = sae_scores.get("sequencing_fitness", 0.6) if sae_scores else 0.6
    
    # Categorize line appropriateness
    if line_appropriateness >= 0.8:
        line_status = "appropriate"
        line_reason = f"Appropriate for treatment line {treatment_line or 'current'}"
    elif line_appropriateness >= 0.6:
        line_status = "moderate"
        line_reason = f"Moderately appropriate for treatment line {treatment_line or 'current'}"
    else:
        line_status = "inappropriate"
        line_reason = f"Limited appropriateness for treatment line {treatment_line or 'current'}"
    
    # Categorize cross-resistance risk
    if cross_resistance <= 0.3:
        cross_risk = "LOW"
        cross_reason = "No significant overlap detected with prior therapies"
    elif cross_resistance <= 0.6:
        cross_risk = "MEDIUM"
        cross_reason = "Some potential overlap with prior therapies"
    else:
        cross_risk = "HIGH"
        cross_reason = "Significant overlap with prior therapies - caution advised"
    
    # Determine sequencing fitness
    sequencing_optimal = sequencing_fitness >= 0.7
    if sequencing_optimal:
        seq_reason = "Good timing and sequencing fit for current treatment line"
    else:
        seq_reason = "Suboptimal sequencing - consider alternative timing"
    
    structured_sae = {
        "line_fitness": {
            "score": round(line_appropriateness, 3),
            "status": line_status,
            "reason": line_reason
        },
        "cross_resistance": {
            "risk": cross_risk,
            "score": round(cross_resistance, 3),
            "reason": cross_reason
        },
        "sequencing_fitness": {
            "score": round(sequencing_fitness, 3),
            "optimal": sequencing_optimal,
            "reason": seq_reason
        }
    }
    
    # Step 2: Query LLM if enabled and confidence is low OR explicitly requested
    llm_evidence = None
    if use_llm:
        llm_service = get_llm_service()
        if llm_service.available:
            # Convert disease ID to readable name
            disease_name = DISEASE_AB.get(disease, {}).get('disease_name', disease.replace('_', ' '))
            
            # Search for evidence
            llm_evidence = await llm_service.search_compound_evidence(
                compound=compound,
                disease=disease_name,
                max_results=10
            )
    
    # Step 3: Merge results
    if llm_evidence and llm_evidence.get('paper_count', 0) > 0:
        # Compute confidence boost from LLM
        llm_confidence = llm_evidence.get('confidence', 0.0)
        base_confidence_num = 0.5  # Default if confidence is string
        
        # Parse base confidence if it's a string
        base_conf_str = str(base_result.get('confidence', 'MODERATE'))
        if 'MODERATE' in base_conf_str:
            base_confidence_num = 0.6
        elif 'HIGH' in base_conf_str or 'STRONG' in base_conf_str:
            base_confidence_num = 0.8
        elif 'LOW' in base_conf_str:
            base_confidence_num = 0.3
        
        # Merge confidence (base + LLM boost, capped at 0.95)
        enhanced_confidence_num = min(base_confidence_num + (llm_confidence * 0.3), 0.95)
        
        # Upgrade evidence grade if LLM found strong evidence
        evidence_grade = base_result['evidence']['grade']
        if llm_evidence.get('paper_count', 0) >= 5 and llm_confidence >= 0.6:
            if evidence_grade == "WEAK":
                evidence_grade = "MODERATE"
            elif evidence_grade == "MODERATE" and llm_confidence >= 0.7:
                evidence_grade = "STRONG"
        
        # Boost overall score slightly if LLM confidence is high
        enhanced_score = base_result.get('overall_score', 0.0)
        if llm_confidence >= 0.6:
            enhanced_score = min(enhanced_score + 0.05, 1.0)
        
        # Convert enhanced confidence back to string
        if enhanced_confidence_num >= 0.8:
            enhanced_confidence = "HIGH"
        elif enhanced_confidence_num >= 0.6:
            enhanced_confidence = "MODERATE"
        elif enhanced_confidence_num >= 0.4:
            enhanced_confidence = "LOW-MODERATE"
        else:
            enhanced_confidence = "LOW"
        
        # Compute confidence breakdown for provenance
        evidence_quality = base_confidence_num
        pathway_match = base_result.get('overall_score', 0.0)  # Use overall score as pathway proxy
        safety_profile = 0.7 if base_result.get('bioavailability', {}).get('status') != 'POOR' else 0.5
        
        # Build enhanced response with complete provenance
        enhanced_result = {
            **base_result,
            "alignment_score": round(enhanced_score, 2),  # Renamed from efficacy_score per manager review
            "overall_score": round(enhanced_score, 2),  # Keep for backward compatibility
            "confidence": enhanced_confidence,
            "sae_features": structured_sae,
            "evidence": {
                **base_result['evidence'],
                "grade": evidence_grade
            },
            "llm_evidence": {
                "enabled": True,
                "paper_count": llm_evidence.get('paper_count', 0),
                "papers": [
                    {
                        "pmid": p.get('pmid', 'N/A'),
                        "title": p.get('title', 'N/A'),
                        "year": p.get('year', 'N/A'),
                        "similarity_score": round(p.get('similarity_score', 0), 3) if p.get('similarity_score') else None
                    }
                    for p in llm_evidence.get('papers', [])[:5]  # Top 5 papers
                ],
                "summary": llm_evidence.get('evidence_summary', ''),
                "confidence_boost": round(llm_confidence, 3),
                "query": llm_evidence.get('query', '')
            },
            "provenance": {
                "run_id": run_id,
                "timestamp": timestamp,
                "method": "disease_ab_mapping_v1_llm_enhanced",
                "disease": disease,
                "disease_name": DISEASE_AB.get(disease, {}).get('disease_name', disease.replace('_', ' ')),
                "germline_status": germline_status,
                "treatment_line": treatment_line,
                "prior_therapies": prior_therapies,
                "ab_matches_count": base_result.get('provenance', {}).get('ab_matches_count', 0),
                "llm_enabled": True,
                "llm_papers_found": llm_evidence.get('paper_count', 0),
                "data_sources": {
                    "pubmed_papers": llm_evidence.get('paper_count', 0),
                    "chembl_targets": len(base_result.get('mechanisms', [])),  # Proxy: mechanisms = targets
                    "treatment_lines": 1 if treatment_line else 0
                },
                "models_used": [
                    {"name": "SAE Feature Analysis", "version": "v2.1"},
                    {"name": "S/P/E Integration", "profile": "baseline"},
                    {"name": "LLM Literature Mining", "enabled": True}
                ],
                "confidence_breakdown": {
                    "evidence_quality": round(evidence_quality, 2),
                    "pathway_match": round(pathway_match, 2),
                    "safety_profile": round(safety_profile, 2)
                },
                "ruo_disclaimer": "Research Use Only - supports, not replaces, clinical judgment"
            }
        }
        
        return enhanced_result
    
    # If LLM unavailable or no papers found, return base result with SAE + complete provenance
    evidence_quality = 0.6 if base_result.get('confidence', '').upper() in ['MODERATE', 'HIGH'] else 0.4
    pathway_match = base_result.get('overall_score', 0.0)
    safety_profile = 0.7 if base_result.get('bioavailability', {}).get('status') != 'POOR' else 0.5
    
    return {
        **base_result,
        "sae_features": structured_sae,
        "llm_evidence": {
            "enabled": use_llm,
            "available": llm_evidence is not None if use_llm else False,
            "paper_count": 0,
            "message": "LLM service unavailable or no papers found" if use_llm else "LLM disabled"
        },
        "provenance": {
            "run_id": run_id,
            "timestamp": timestamp,
            "method": "disease_ab_mapping_v1",
            "disease": disease,
            "disease_name": DISEASE_AB.get(disease, {}).get('disease_name', disease.replace('_', ' ')),
            "germline_status": germline_status,
            "treatment_line": treatment_line,
            "prior_therapies": prior_therapies,
            "ab_matches_count": base_result.get('provenance', {}).get('ab_matches_count', 0),
            "llm_enabled": use_llm,
            "llm_papers_found": 0,
            "data_sources": {
                "pubmed_papers": 0,
                "chembl_targets": len(base_result.get('mechanisms', [])),
                "treatment_lines": 1 if treatment_line else 0
            },
            "models_used": [
                {"name": "SAE Feature Analysis", "version": "v2.1"},
                {"name": "S/P/E Integration", "profile": "baseline"}
            ],
            "confidence_breakdown": {
                "evidence_quality": round(evidence_quality, 2),
                "pathway_match": round(pathway_match, 2),
                "safety_profile": round(safety_profile, 2)
            },
            "ruo_disclaimer": "Research Use Only - supports, not replaces, clinical judgment"
        }
    }


# Import new services for dynamic validation
try:
    from api.services.dynamic_food_extraction import get_dynamic_extractor
    from api.services.enhanced_evidence_service import get_enhanced_evidence_service
    from api.services.dietician_recommendations import get_dietician_service
    from api.services.food_spe_integration import FoodSPEIntegrationService
    # Note: compute_food_treatment_line_features already imported at top
    DYNAMIC_SERVICES_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ Dynamic food services not available: {e}")
    DYNAMIC_SERVICES_AVAILABLE = False

# Import research intelligence for complex questions
try:
    from api.services.research_intelligence.orchestrator import ResearchIntelligenceOrchestrator
    RESEARCH_INTELLIGENCE_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Research intelligence not available: {e}")
    RESEARCH_INTELLIGENCE_AVAILABLE = False

@router.post("/api/hypothesis/validate_food_dynamic")
async def validate_food_dynamic(
    request: Dict[str, Any]
):
    """
    Dynamic Food Validator - Works for ANY food/supplement
    
    Complete end-to-end validation:
    1. Dynamic target extraction (ChEMBL/PubChem/LLM)
    2. Pathway mapping to cancer mechanisms
    3. Evidence mining (PubMed + LLM synthesis)
    4. S/P/E + SAE scoring
    5. Dietician recommendations
    
    Request:
    {
        "compound": "Resveratrol",  // ANY compound name
        "disease_context": {
            "disease": "ovarian_cancer_hgs",
            "mutations": [{"gene": "TP53", "hgvs_p": "R248Q"}],
            "biomarkers": {"HRD": "POSITIVE", "TMB": 8.2},
            "pathways_disrupted": ["DNA repair", "Angiogenesis"]
        },
        "treatment_history": {
            "current_line": "L3",
            "prior_therapies": ["carboplatin", "paclitaxel"]
        },
        "patient_medications": ["warfarin", "metformin"],  // Optional
        "use_evo2": false  // Phase 1: disabled
    }
    
    Response:
    {
        "compound": "Resveratrol",
        "overall_score": 0.65,
        "confidence": 0.82,
        "verdict": "WEAK_SUPPORT",
        "spe_breakdown": {"sequence": 0.5, "pathway": 0.75, "evidence": 0.70},
        "sae_features": {...},
        "targets": ["SIRT1", "NF-κB", "COX-2"],
        "pathways": ["Angiogenesis", "Inflammation"],
        "mechanisms": ["angiogenesis", "inflammation"],
        "evidence": {
            "papers": [...],
            "evidence_grade": "MODERATE",
            "total_papers": 15,
            "rct_count": 2
        },
        "dietician_recommendations": {
            "dosage": {...},
            "timing": {...},
            "interactions": {...},
            "monitoring": {...},
            "safety": {...},
            "meal_planning": {...}
        },
        "provenance": {...}
    }
    """
    
    if not DYNAMIC_SERVICES_AVAILABLE:
        return {
            "status": "ERROR",
            "error": "Dynamic food services not available - missing dependencies",
            "fallback": "Use /validate_food_ab endpoint for hardcoded compounds"
        }
    
    import uuid
    from datetime import datetime
    
    compound = request.get("compound", "").strip()
    if not compound:
        raise HTTPException(400, "compound is required")
    
    disease_context = request.get("disease_context", {})
    treatment_history = request.get("treatment_history")
    patient_medications = request.get("patient_medications", [])
    use_evo2 = request.get("use_evo2", False)
    
    disease = disease_context.get("disease", "ovarian_cancer_hgs")
    
    # Load pathways from universal database if not provided
    if not disease_context.get("pathways_disrupted"):
        pathways_disrupted = []
        
        # Try to load from universal database first
        universal_db_path = Path(__file__).parent.parent.parent / "resources" / "universal_disease_pathway_database.json"
        if universal_db_path.exists():
            try:
                with open(universal_db_path, 'r') as f:
                    universal_db = json.load(f)
                    disease_data = universal_db.get("diseases", {}).get(disease)
                    if disease_data:
                        pathways = disease_data.get("pathways", {})
                        pathways_disrupted = list(pathways.keys())
                        # Also add descriptions for better matching
                        for key, desc in pathways.items():
                            if isinstance(desc, dict) and desc.get("description"):
                                if desc["description"] not in pathways_disrupted:
                                    pathways_disrupted.append(desc["description"])
            except Exception as e:
                logger.warning(f"Failed to load pathways from universal DB: {e}")
        
        # Fallback to DISEASE_AB if universal DB doesn't have it
        if not pathways_disrupted:
            pathways_disrupted = DISEASE_AB.get(disease, {}).get('likely_alterations', [])
        
        disease_context["pathways_disrupted"] = pathways_disrupted
    
    run_id = str(uuid.uuid4())
    
    try:
        # [1] DYNAMIC TARGET EXTRACTION
        extractor = get_dynamic_extractor()
        extraction_result = await extractor.extract_all(compound, disease)
        
        if extraction_result.get("error") and not extraction_result.get("targets"):
            return {
                "status": "ERROR",
                "error": extraction_result.get("error", f"No information found for '{compound}'"),
                "suggestion": "Try checking spelling or use a more specific compound name",
                "provenance": {
                    "run_id": run_id,
                    "method": "dynamic_extraction",
                    "timestamp": datetime.utcnow().isoformat()
                }
            }
        
        targets = extraction_result.get("targets", [])
        pathways = extraction_result.get("pathways", [])
        mechanisms = extraction_result.get("mechanisms", [])
        
        # [1.5] RESEARCH INTELLIGENCE BOOST (for complex questions like "purple potatoes")
        # Use research intelligence if:
        # 1. Standard extraction found few/no targets, OR
        # 2. Compound is a whole food (not a pure compound), OR
        # 3. Request explicitly asks for research intelligence
        use_research_intelligence = (
            RESEARCH_INTELLIGENCE_AVAILABLE and (
                request.get("use_research_intelligence", False) or
                (len(targets) < 2 and len(pathways) < 2) or
                any(word in compound.lower() for word in ["potato", "berry", "fruit", "vegetable", "food", "extract"])
            )
        )
        
        research_intelligence_result = None
        ri_mechanisms = []
        ri_pathways = []
        if use_research_intelligence:
            try:
                logger.info(f"🔬 Using Research Intelligence for '{compound}'")
                orchestrator = ResearchIntelligenceOrchestrator()
                
                # Check if orchestrator is available
                if not orchestrator.is_available():
                    logger.warning("⚠️ Research Intelligence orchestrator not fully available, skipping")
                    research_intelligence_result = None
                    ri_mechanisms = []
                    ri_pathways = []
                else:
                    # Build context for research intelligence
                    ri_context = {
                        "disease": disease,
                        "treatment_line": treatment_history.get("current_line", "L1") if treatment_history else "L1",
                        "biomarkers": disease_context.get("biomarkers", {})
                    }
                
                    # Formulate research question
                    research_question = f"How does {compound} help with {disease.replace('_', ' ')}?"
                
                    # Run research intelligence
                    research_intelligence_result = await orchestrator.research_question(
                        question=research_question,
                        context=ri_context
                    )
                
                    # Extract mechanisms and pathways from research intelligence
                    synthesized = research_intelligence_result.get("synthesized_findings", {})
                    ri_mechanisms = synthesized.get("mechanisms", [])
                
                    # Add mechanisms from research intelligence
                    mechanisms_added = 0
                    targets_added = 0
                    for mech in ri_mechanisms:

                        if mech_name and mech_name not in [m.lower() for m in mechanisms]:

                            mechanisms.append(mech_name)
                            mechanisms_added += 1

                        # Extract targets if available
                        target = mech.get("target", "")
                        if target and target not in targets:

                            targets.append(target)
                            targets_added += 1
                        targets_added += 1
                
                    # Extract pathways from MOAT analysis
                    moat_analysis = research_intelligence_result.get("moat_analysis", {})
                    ri_pathways = moat_analysis.get("pathways", [])
                    pathways_added = 0
                    for pathway in ri_pathways:
                        pathways.append(pathway)

                        pathways_added += 1

                
                    logger.info(f"✅ Research Intelligence found {len(ri_mechanisms)} mechanisms, {len(ri_pathways)} pathways")
                    logger.info(f"   Added: {mechanisms_added} mechanisms, {targets_added} targets, {pathways_added} pathways")
                
                    # Also enhance evidence with research intelligence papers if available
                    portal_results = research_intelligence_result.get("portal_results", {})
                    pubmed_results = portal_results.get("pubmed", {})
                    ri_papers = pubmed_results.get("articles", [])
                    if ri_papers and evidence_result:
                        # Merge papers from research intelligence




                        existing_pmids = {p.get("pmid", "") for p in evidence_result.get("papers", [])}

                        new_papers = [

                        {
                            "title": p.get("title", ""),
                            "abstract": p.get("abstract", ""),
                            "pmid": p.get("pmid", ""),
                            "journal": p.get("journal", ""),
                            "source": "research_intelligence"
                        }
                    for p in ri_papers[:10]  # Top 10
                    if p.get("pmid") and p.get("pmid") not in existing_pmids
                    ]
                    if new_papers:
                        evidence_result.setdefault("papers", []).extend(new_papers)
                        evidence_result["total_papers"] = evidence_result.get("total_papers", 0) + len(new_papers)
                        logger.info(f"   Added {len(new_papers)} papers from research intelligence")
                    research_intelligence_result = None
                    ri_mechanisms = []
                    ri_pathways = []
                
            except Exception as e:
                logger.warning(f"⚠️ Research Intelligence failed: {e}, continuing with standard extraction")
                import traceback
                logger.debug(traceback.format_exc())
                research_intelligence_result = None
                ri_mechanisms = []
                ri_pathways = []
        
        # [2] ENHANCED EVIDENCE MINING (with treatment line context)
        evidence_service = get_enhanced_evidence_service()
        # Extract treatment line from treatment_history if available
        treatment_line_for_evidence = None
        if treatment_history and 'current_line' in treatment_history:
            treatment_line_for_evidence = treatment_history.get('current_line')
        
        evidence_result = await evidence_service.get_complete_evidence(
            compound=compound,
            disease=disease,
            pathways=pathways,
            treatment_line=treatment_line_for_evidence
        )
        
        evidence_grade = evidence_result.get("evidence_grade", "INSUFFICIENT")
        
        # [3] S/P/E + SAE SCORING
        spe_service = FoodSPEIntegrationService()
        
        # Compute S/P/E score (includes SAE features computation)
        spe_result = await spe_service.compute_spe_score(
            compound=compound,
            targets=targets,
            pathways=pathways,
            disease_context=disease_context,
            evidence_grade=evidence_grade,
            treatment_history=treatment_history,
            evo2_enabled=use_evo2
        )
        
        # Extract SAE features from SPE result
        sae_features_flat = spe_result.get("sae_features", {})
        
        # [PHASE 2 & 3] Apply cancer type and biomarker boosts to overall_score
        base_overall_score = spe_result.get("overall_score", 0.5)
        boost_applied = 0.0
        boost_reasons = []
        
        # === CANCER TYPE FOOD BOOST ===
        cancer_type_boost = 0.0
        cancer_type_foods = load_cancer_type_foods()
        cancer_recs = cancer_type_foods.get("cancer_types", {}).get(disease, {})
        compound_lower = compound.lower()  # Define once
        
        if cancer_recs:
            # Check if compound matches any recommended food
            for food_rec in cancer_recs.get("recommended_foods", []):
                food_compound = food_rec.get("compound", "").lower()
                if compound_lower in food_compound or food_compound in compound_lower:
                    cancer_type_boost = 0.1
                    boost_reasons.append(f"Cancer type match ({disease})")
                    
                    # Extra boost for treatment line match
                    treatment_lines = food_rec.get("treatment_lines", ["L1", "L2", "L3"])
                    current_line = treatment_history.get("current_line", "L1") if treatment_history else "L1"
                    # Normalize line format
                    from api.services.food_treatment_line_service import normalize_treatment_line
                    current_line = normalize_treatment_line(current_line)
                    
                    if current_line in treatment_lines:
                        cancer_type_boost += 0.05
                        boost_reasons.append(f"Treatment line match ({current_line})")
                    break
        
        # === BIOMARKER FOOD BOOST ===
        biomarker_boost = 0.0
        biomarker_foods = load_biomarker_foods()
        biomarkers = disease_context.get("biomarkers", {})
        
        def check_biomarker_match(biomarker_key: str, compound_list: List[str]) -> bool:
            """Check if compound matches any in biomarker compound list."""
            return any(compound_lower in rec or rec in compound_lower for rec in compound_list)
        
        # Check HRD+
        if biomarkers.get("HRD") == "POSITIVE":
            hrd_recs = biomarker_foods.get("biomarker_mappings", {}).get("HRD_POSITIVE", {})
            hrd_compounds = [f.get("compound", "").lower() for f in hrd_recs.get("recommended_foods", [])]
            if check_biomarker_match("HRD_POSITIVE", hrd_compounds):
                biomarker_boost = max(biomarker_boost, 0.1)
                boost_reasons.append("HRD+ biomarker match")
        
        # Check TMB-H (>=10)
        tmb_value = biomarkers.get("TMB", 0)
        if isinstance(tmb_value, (int, float)) and tmb_value >= 10:
            tmb_recs = biomarker_foods.get("biomarker_mappings", {}).get("TMB_HIGH", {})
            tmb_compounds = [f.get("compound", "").lower() for f in tmb_recs.get("recommended_foods", [])]
            if check_biomarker_match("TMB_HIGH", tmb_compounds):
                biomarker_boost = max(biomarker_boost, 0.1)
                boost_reasons.append("TMB-H biomarker match")
        
        # Check MSI-H
        if biomarkers.get("MSI") == "HIGH":
            msi_recs = biomarker_foods.get("biomarker_mappings", {}).get("MSI_HIGH", {})
            msi_compounds = [f.get("compound", "").lower() for f in msi_recs.get("recommended_foods", [])]
            if check_biomarker_match("MSI_HIGH", msi_compounds):
                biomarker_boost = max(biomarker_boost, 0.1)
                boost_reasons.append("MSI-H biomarker match")
        
        # Check HER2+
        if biomarkers.get("HER2") == "POSITIVE":
            her2_recs = biomarker_foods.get("biomarker_mappings", {}).get("HER2_POSITIVE", {})
            her2_compounds = [f.get("compound", "").lower() for f in her2_recs.get("recommended_foods", [])]
            if check_biomarker_match("HER2_POSITIVE", her2_compounds):
                biomarker_boost = max(biomarker_boost, 0.1)
                boost_reasons.append("HER2+ biomarker match")
        
        # Check BRCA mutant (from mutations or biomarkers)
        if biomarkers.get("BRCA") in ["POSITIVE", "MUTANT"] or any(
            mut.get("gene", "").upper() in ["BRCA1", "BRCA2"] 
            for mut in disease_context.get("mutations", [])
        ):
            brca_recs = biomarker_foods.get("biomarker_mappings", {}).get("BRCA_MUTANT", {})
            brca_compounds = [f.get("compound", "").lower() for f in brca_recs.get("recommended_foods", [])]
            if check_biomarker_match("BRCA_MUTANT", brca_compounds):
                biomarker_boost = max(biomarker_boost, 0.1)
                boost_reasons.append("BRCA mutant biomarker match")
        
        # Apply boosts (additive, capped at 1.0)
        total_boost = cancer_type_boost + biomarker_boost
        boosted_score = min(1.0, base_overall_score + total_boost)
        boost_applied = boosted_score - base_overall_score
        
        # [CRITICAL FIX] Transform flat SAE structure to nested structure for frontend (using new service)
        structured_sae = build_sae_structure(sae_features_flat, treatment_history)
        
        # [4] DIETICIAN RECOMMENDATIONS
        dietician_service = get_dietician_service()
        recommendations = dietician_service.generate_complete_recommendations(
            compound=compound,
            evidence=evidence_result,
            patient_medications=patient_medications,
            disease_context=disease_context
        )
        
        # [5] TOXICITY MITIGATION CHECK (THE MOAT - Phase 2)
        toxicity_mitigation = None
        if patient_medications:
            try:
                from api.services.toxicity_pathway_mappings import (
                    compute_pathway_overlap, get_mitigating_foods, get_drug_moa
                )
                
                # Extract genes from disease_context mutations (conservative: treat as potential germline)
                germline_genes = []
                mutations = disease_context.get("mutations", [])
                for mut in mutations:
                    if isinstance(mut, dict) and mut.get("gene"):
                        germline_genes.append(mut["gene"])
                    elif isinstance(mut, str):
                        # Handle string format like "BRCA1 V600E" or just "BRCA1"
                        gene = mut.split()[0] if " " in mut else mut
                        germline_genes.append(gene)
                
                # Check each medication for toxicity mitigation
                for drug in patient_medications:
                    if not drug or not isinstance(drug, str):
                        continue
                    
                    drug_name = drug.strip()
                    moa = get_drug_moa(drug_name)
                    
                    # Only proceed if we have a known MoA and germline genes
                    if moa != "unknown" and germline_genes:
                        # Compute pathway overlap
                        pathway_overlap = compute_pathway_overlap(germline_genes, moa)
                        mitigating_foods = get_mitigating_foods(pathway_overlap)
                        
                        # Check if current compound is a mitigating food
                        compound_lower = compound.lower()
                        for food in mitigating_foods:
                            food_name_lower = food["compound"].lower()
                            
                            # Flexible matching: check if compound name appears in food name or vice versa
                            # Examples: "NAC" matches "NAC (N-Acetyl Cysteine)", "Vitamin D" matches "Vitamin D3"
                            if (compound_lower in food_name_lower or 
                                food_name_lower.split("(")[0].strip().lower() in compound_lower or
                                any(word in compound_lower for word in food_name_lower.split() if len(word) > 3)):
                                
                                toxicity_mitigation = {
                                    "mitigates": True,
                                    "target_drug": drug_name,
                                    "target_moa": moa,
                                    "pathway": food["pathway"],
                                    "mechanism": food["mechanism"],
                                    "timing": food["timing"],
                                    "evidence_tier": food.get("evidence_tier", "MODERATE"),
                                    "dose": food.get("dose", ""),
                                    "care_plan_ref": food.get("care_plan_ref", "")
                                }
                                break
                    
                    if toxicity_mitigation:
                        break
                        
            except Exception as e:
                # Don't fail the entire request if toxicity check fails
                # Use print for visibility during testing
                print(f"⚠️ Toxicity mitigation check failed: {e}")
                import traceback
                traceback.print_exc()
                logger.warning(f"Toxicity mitigation check failed: {e}")
        
        # [5.5] LLM ENHANCEMENT (PHASE 3 - Optional)
        enable_llm_enhancement = request.get("enable_llm_enhancement", False)
        if toxicity_mitigation and enable_llm_enhancement:
            try:
                from api.services.llm_toxicity_service import get_llm_toxicity_service
                llm_service = get_llm_toxicity_service()
                
                if llm_service["available"]:
                    # Extract germline genes from disease_context
                    germline_genes = []
                    if disease_context:
                        mutations = disease_context.get("mutations", [])
                        for mut in mutations:
                            if isinstance(mut, dict) and mut.get("gene"):
                                germline_genes.append(mut["gene"])
                            elif isinstance(mut, str):
                                gene = mut.split()[0] if " " in mut else mut
                                germline_genes.append(gene)
                    
                    # Generate LLM-enhanced rationale
                    enhanced = await llm_service["generate_rationale"](
                        compound=compound,
                        drug_name=toxicity_mitigation["target_drug"],
                        drug_moa=toxicity_mitigation["target_moa"],
                        toxicity_pathway=toxicity_mitigation["pathway"],
                        germline_genes=germline_genes,
                        cancer_type=disease_context.get("disease", "cancer") if disease_context else "cancer",
                        treatment_phase=treatment_history.get("current_line", "active treatment") if treatment_history else "active treatment",
                        base_mechanism=toxicity_mitigation["mechanism"],
                        timing=toxicity_mitigation["timing"],
                        dose=toxicity_mitigation.get("dose", ""),
                        provider="gemini"
                    )
                    
                    # Add LLM-enhanced fields to toxicity_mitigation
                    if enhanced.get("llm_enhanced"):
                        toxicity_mitigation["llm_rationale"] = enhanced.get("rationale")
                        toxicity_mitigation["patient_summary"] = enhanced.get("patient_summary")
                        toxicity_mitigation["llm_enhanced"] = True
                        toxicity_mitigation["llm_confidence"] = enhanced.get("confidence", 0.75)
            except Exception as e:
                logger.warning(f"LLM enhancement failed: {e}")
                # Don't fail the request - just continue without LLM enhancement
        
        # [6] BUILD COMPLETE RESPONSE (PHASE 2 ENHANCED + PHASE 3 LLM) - using new service
        response = build_validation_response(
            compound=compound,
            extraction_result=extraction_result,
            evidence_result=evidence_result,
            spe_result=spe_result,
            sae_features_flat=sae_features_flat,
            recommendations=recommendations,
            toxicity_mitigation=toxicity_mitigation,
            boosted_score=boosted_score,
            base_overall_score=base_overall_score,
            boost_applied=boost_applied,
            boost_reasons=boost_reasons,
            treatment_history=treatment_history,
            use_evo2=use_evo2,
            use_research_intelligence=use_research_intelligence,
            research_intelligence_result=research_intelligence_result,
            run_id=run_id
        )
        
        # Update boosts with cancer_type and biomarker values (response builder sets them to 0.0)
        if response.get("provenance", {}).get("boosts"):
            response["provenance"]["boosts"]["cancer_type_boost"] = round(cancer_type_boost, 3)
            response["provenance"]["boosts"]["biomarker_boost"] = round(biomarker_boost, 3)
        
        return response
        
    except Exception as e:
        print(f"❌ Error in dynamic food validation: {e}")
        import traceback
        traceback.print_exc()
        
        return {
            "status": "ERROR",
            "error": str(e),
            "compound": compound,
            "provenance": {
                "run_id": run_id,
                "timestamp": datetime.utcnow().isoformat()
            }
        }

