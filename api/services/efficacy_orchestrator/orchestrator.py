"""
Efficacy Orchestrator: Main composition logic for efficacy prediction.
"""
import os
import uuid
import asyncio
import sys
from typing import Dict, Any, List, Optional

from .models import EfficacyRequest, EfficacyResponse
from .sequence_processor import SequenceProcessor
from .drug_scorer import DrugScorer
from .cohort_signals import compute_cohort_signals, apply_cohort_lifts
from .calibration_snapshot import compute_calibration_snapshot, get_percentile_lift
from .sporadic_gates import apply_sporadic_gates  # NEW: Sporadic Cancer Strategy (Day 2)
from ..pathway import get_default_panel, aggregate_pathways
from ..insights import bundle as bundle_insights, InsightsBundle
from ..evidence import literature, clinvar_prior
from ..confidence import create_confidence_config
from api.config import get_feature_flags

# Phase 3: Treatment Line Integration
# Import treatment line services from Ayesha's treatment_lines module
ayesha_path = os.path.join(os.path.dirname(__file__), "../../../../.cursor/ayesha/treatment_lines")
if os.path.exists(ayesha_path) and ayesha_path not in sys.path:
    sys.path.insert(0, ayesha_path)

try:
    from backend.services.treatment_line_integration import (
        compute_treatment_line_features,
        modulate_confidence_with_treatment_line
    )
    from backend.schemas.treatment_history import TreatmentHistory
    TREATMENT_LINE_AVAILABLE = True
except ImportError:
    TREATMENT_LINE_AVAILABLE = False
    print("⚠️  Treatment line integration not available - skipping treatment line features")


class EfficacyOrchestrator:
    """Main orchestrator for efficacy prediction."""
    
    def __init__(self, sequence_processor: SequenceProcessor = None,
                 drug_scorer: DrugScorer = None):
        self.sequence_processor = sequence_processor or SequenceProcessor()
        self.drug_scorer = drug_scorer or DrugScorer()
    
    async def predict(self, request: EfficacyRequest) -> EfficacyResponse:
        """
        Predict drug efficacy for given mutations.
        
        Args:
            request: Efficacy prediction request
            
        Returns:
            Efficacy prediction response
        """
        run_id = str(uuid.uuid4())
        feature_flags = get_feature_flags()
        
        # Initialize response
        response = EfficacyResponse(
            drugs=[],
            run_signature=run_id,
            scoring_strategy={},
            evidence_tier="insufficient",
            schema_version="v1",  # Add schema version
            provenance={
                "run_id": run_id,
                "profile": "baseline",
                "cache": "miss",
                "flags": {  # Add feature flags to provenance
                    "fusion_active": bool(os.getenv("FUSION_AM_URL")),
                    "evo_use_delta_only": bool(os.getenv("EVO_USE_DELTA_ONLY", "1")),
                    "evidence_enabled": bool(os.getenv("EVIDENCE_ENABLED", "1")),
                    "confidence_v2": bool(os.getenv("CONFIDENCE_V2", "0") == "1")
                }
            }
        )
        
        try:
            # Get drug panel
            panel = get_default_panel()

            # Optional: limit panel size for fast-mode runs to reduce work
            limit_n = 0
            try:
                limit_n = int((request.options or {}).get("limit_panel", 0))
            except Exception:
                limit_n = 0
            if limit_n and limit_n > 0:
                panel = panel[:limit_n]
            
            # 1) Sequence scoring
            seq_scores = await self.sequence_processor.score_sequences(request, feature_flags)
            response.provenance["sequence_scoring"] = {
                "mode": seq_scores[0].scoring_mode if seq_scores else "none",
                "count": len(seq_scores)
            }
            
            if not seq_scores:
                return response
            
            # 2) Pathway aggregation
            pathway_scores = aggregate_pathways([self.drug_scorer.seq_score_to_dict(score) for score in seq_scores])
            
            # 3) Primary gene and variant extraction
            primary_gene = seq_scores[0].variant.get("gene", "")
            primary_variant = seq_scores[0].variant
            hgvs_p = primary_variant.get("hgvs_p", "")
            
            # 4) Evidence gathering (parallel) — gated by feature flags and fast mode
            fast_mode = bool((request.options or {}).get("fast", False))
            evidence_enabled_flag = bool(feature_flags.get("evidence_enabled", True))
            gather_evidence = (not fast_mode) and evidence_enabled_flag and primary_gene and hgvs_p

            evidence_tasks = []
            if gather_evidence:
                # Literature evidence for each drug
                for drug in panel:
                    evidence_tasks.append(
                        literature(
                            request.api_base, primary_gene, hgvs_p,
                            drug["name"], drug["moa"]
                        )
                    )
                # ClinVar prior
                clinvar_task = clinvar_prior(request.api_base, primary_gene, primary_variant)
            else:
                clinvar_task = None
            
            # Execute evidence tasks with timeout handling
            evidence_results = []
            evidence_timeout = False
            if evidence_tasks:
                try:
                    evidence_results = await asyncio.wait_for(
                        asyncio.gather(*evidence_tasks, return_exceptions=True),
                        timeout=30.0  # 30 second timeout
                    )
                except asyncio.TimeoutError:
                    evidence_timeout = True
                    evidence_results = []
                    response.provenance["fallback"] = "evidence_timeout"
            elif fast_mode and not evidence_enabled_flag:
                response.provenance["fallback"] = "evidence_disabled_fast_mode"
            
            clinvar_result = None
            if clinvar_task:
                try:
                    clinvar_result = await asyncio.wait_for(clinvar_task, timeout=10.0)
                except asyncio.TimeoutError:
                    clinvar_result = None
                    if not evidence_timeout:
                        response.provenance["fallback"] = "clinvar_timeout"
            
            # 5) Insights bundle — skip in fast mode
            insights = InsightsBundle()
            if (not fast_mode) and primary_gene and primary_variant and hgvs_p:
                insights = await bundle_insights(request.api_base, primary_gene, primary_variant, hgvs_p)
            elif fast_mode:
                response.provenance["insights"] = "skipped_fast_mode"
            
            # 6) Cohort signals and calibration snapshot — skip in fast mode unless explicitly requested
            cohort_signals = None
            calibration_snapshot = None
            if not fast_mode and request.include_cohort_overlays:
                cohort_signals = compute_cohort_signals(
                    request.mutations,
                    request.disease or "",
                    request.include_cohort_overlays
                )
            if not fast_mode and request.include_calibration_snapshot:
                calibration_snapshot = compute_calibration_snapshot(
                    [self.drug_scorer.seq_score_to_dict(score) for score in seq_scores],
                    pathway_scores,
                    request.include_calibration_snapshot
                )
            
            
            # 7) Drug scoring (with optional ablations)
            drugs_out = []
            confidence_config = create_confidence_config(
                fusion_active=bool(os.getenv("FUSION_AM_URL"))
            )
            
            for i, drug in enumerate(panel):
                # Apply ablation mode by masking components
                # Default to SP in fast mode to avoid evidence influence
                ablation = (request.ablation_mode or ("SP" if fast_mode else "SPE")).upper()
                use_S = "S" in ablation
                use_P = "P" in ablation
                use_E = "E" in ablation

                # Shallow copies/masks
                masked_seq_scores = seq_scores if use_S else []
                masked_pathway_scores = pathway_scores if use_P else {}
                masked_evidence = (evidence_results[i] if (use_E and i < len(evidence_results)) else None)

                drug_result = await self.drug_scorer.score_drug(
                    drug, masked_seq_scores, masked_pathway_scores,
                    masked_evidence, clinvar_result if use_E else None,
                    insights, confidence_config, request.disease or "",
                    include_fda_badges=bool((request.options or {}).get("include_fda_badges", False))
                )
                
                # Apply cohort lifts if enabled
                if cohort_signals:
                    original_confidence = drug_result.confidence
                    drug_result.confidence = apply_cohort_lifts(
                        original_confidence, cohort_signals, drug["name"]
                    )
                
                # NEW: Apply sporadic cancer gates (Day 2 - Module M3)
                sporadic_gates_provenance = None
                if hasattr(request, 'germline_status') or hasattr(request, 'tumor_context'):
                    try:
                        # Extract germline status and tumor context from request
                        germline_status = getattr(request, 'germline_status', 'unknown')
                        tumor_context_data = getattr(request, 'tumor_context', None)
                        
                        # Convert TumorContext object to dict if needed
                        tumor_context_dict = None
                        if tumor_context_data:
                            if hasattr(tumor_context_data, '__dict__'):
                                tumor_context_dict = tumor_context_data.__dict__
                            elif isinstance(tumor_context_data, dict):
                                tumor_context_dict = tumor_context_data
                        
                        # Apply sporadic gates
                        adjusted_efficacy, adjusted_confidence, sporadic_rationale = apply_sporadic_gates(
                            drug_name=drug["name"],
                            drug_class=drug.get("class", ""),
                            moa=drug.get("moa", ""),
                            efficacy_score=drug_result.efficacy_score,
                            confidence=drug_result.confidence,
                            germline_status=germline_status,
                            tumor_context=tumor_context_dict
                        )
                        
                        # Update drug result if gates changed anything
                        if adjusted_efficacy != drug_result.efficacy_score or adjusted_confidence != drug_result.confidence:
                            drug_result.efficacy_score = adjusted_efficacy
                            drug_result.confidence = adjusted_confidence
                            
                            # Track provenance
                            sporadic_gates_provenance = {
                                "germline_status": germline_status,
                                "level": sporadic_rationale[-1].get("level", "L0") if sporadic_rationale else "L0",
                                "gates_applied": [r["gate"] for r in sporadic_rationale if "gate" in r],
                                "efficacy_delta": adjusted_efficacy - drug_result.efficacy_score,
                                "confidence_delta": adjusted_confidence - drug_result.confidence,
                                "rationale": sporadic_rationale
                            }
                    except Exception as e:
                        # Graceful degradation if sporadic gates fail
                        import logging
                        logging.getLogger(__name__).warning(f"⚠️  Sporadic gates computation failed for {drug['name']}: {e}")
                        sporadic_gates_provenance = {"error": str(e)}
                
                # Phase 3: Apply treatment line modulation if enabled
                treatment_line_provenance = None
                if TREATMENT_LINE_AVAILABLE and request.treatment_history:
                    try:
                        # Parse treatment history
                        treatment_hist = TreatmentHistory(**request.treatment_history)
                        
                        # Compute treatment line features
                        treatment_line_features = compute_treatment_line_features(
                            drug_name=drug["name"],
                            disease=request.disease or "unknown",
                            treatment_history=treatment_hist
                        )
                        
                        # Apply confidence modulation
                        original_confidence = drug_result.confidence
                        modulated_confidence, rationale = modulate_confidence_with_treatment_line(
                            base_confidence=original_confidence,
                            treatment_line_features=treatment_line_features
                        )
                        
                        # Update confidence
                        drug_result.confidence = modulated_confidence
                        
                        # Track provenance
                        treatment_line_provenance = {
                            "current_line": treatment_line_features["current_line"],
                            "prior_therapies": treatment_line_features["prior_therapies"],
                            "line_appropriateness": treatment_line_features["line_appropriateness"],
                            "cross_resistance_risk": treatment_line_features["cross_resistance_risk"],
                            "sequencing_fitness": treatment_line_features["sequencing_fitness"],
                            "nccn_category": treatment_line_features["nccn_category"],
                            "confidence_penalty": original_confidence - modulated_confidence,
                            "rationale": rationale
                        }
                    except Exception as e:
                        # Graceful degradation if treatment line computation fails
                        print(f"⚠️  Treatment line computation failed for {drug['name']}: {e}")
                        treatment_line_provenance = {"error": str(e)}
                
                # Convert to dict and add treatment line provenance + sporadic gates provenance
                drug_dict = drug_result.__dict__
                if treatment_line_provenance:
                    drug_dict["treatment_line_provenance"] = treatment_line_provenance
                if sporadic_gates_provenance:
                    drug_dict["sporadic_gates_provenance"] = sporadic_gates_provenance
                
                drugs_out.append(drug_dict)
            
            # Sort by confidence
            drugs_out.sort(key=lambda d: d["confidence"], reverse=True)
            
            # 7) Determine overall evidence tier
            if drugs_out:
                top_drug = drugs_out[0]
                response.evidence_tier = top_drug["evidence_tier"]
                
                # Add confidence breakdown for top drug (for EvidenceBand)
                response.provenance["confidence_breakdown"] = {
                    "top_drug": top_drug.get("name"),
                    "confidence": top_drug.get("confidence"),
                    "tier": top_drug.get("evidence_tier"),
                    "badges": top_drug.get("badges", []),
                    "rationale": top_drug.get("rationale", []),
                    "S_contribution": next((r.get("percentile", 0) for r in top_drug.get("rationale", []) if r.get("type") == "sequence"), 0),
                    "P_contribution": next((r.get("percentile", 0) for r in top_drug.get("rationale", []) if r.get("type") == "pathway"), 0),
                    "E_contribution": next((r.get("strength", 0) for r in top_drug.get("rationale", []) if r.get("type") == "evidence"), 0)
                }
            
            # 8) Extract SAE features if requested (P2 feature)
            if (request.options or {}).get("include_sae_features"):
                try:
                    from api.services.sae_service import extract_sae_features_from_real_data, sae_features_to_dict
                    
                    # Collect all real data sources for SAE
                    sae_bundle = extract_sae_features_from_real_data(
                        variant=request.mutations[0] if request.mutations else {},
                        evo_scores={
                            "delta": seq_scores[0].sequence_disruption if seq_scores else 0.0,
                            "calibrated_seq_percentile": (seq_scores[0].calibrated_seq_percentile or 0.0) if seq_scores else 0.0,
                            "hotspot_floor_applied": False
                        } if seq_scores else None,
                        insights={
                            "functionality": getattr(insights, "functionality", 0.0),
                            "chromatin": getattr(insights, "chromatin", 0.0),
                            "essentiality": getattr(insights, "essentiality", 0.0),
                            "regulatory": getattr(insights, "regulatory", 0.0)
                        },
                        pathway_disruption=pathway_scores,
                        fusion_score=None,
                        clinvar_data=(
                            (lambda c: (
                                {"classification": (
                                    c.get("classification") or 
                                    (c.get("clinvar",{}) if isinstance(c.get("clinvar"), dict) else {}).get("classification")
                                )}
                            ))(getattr(clinvar_result, "deep_analysis", {}))
                            if getattr(clinvar_result, "deep_analysis", None) else None
                        ),
                        toxicity_factors=None,  # Not available in efficacy orchestrator
                        offtarget_result=None,  # Not available in efficacy orchestrator
                        evidence_data=None,
                        cohort_signals=cohort_signals if cohort_signals else None
                    )
                    
                    # Add SAE features to response
                    response.sae_features = sae_features_to_dict(sae_bundle)
                    
                    # Add SAE attribution to confidence breakdown
                    if "confidence_breakdown" in response.provenance:
                        response.provenance["confidence_breakdown"]["sae_attribution"] = {
                            "boosting_features": sae_bundle.boosting_features,
                            "limiting_features": sae_bundle.limiting_features,
                            "overall_impact": sae_bundle.overall_impact
                        }
                    
                    response.provenance["sae_enabled"] = True
                except Exception as e:
                    response.provenance["sae_error"] = str(e)
                    response.provenance["sae_enabled"] = False
            
            response.drugs = drugs_out
            response.cohort_signals = cohort_signals
            response.calibration_snapshot = calibration_snapshot
            response.scoring_strategy = {
                "approach": seq_scores[0].scoring_mode if seq_scores else "none",
                "source": seq_scores[0].scoring_strategy.get("source", "unknown") if seq_scores else "unknown",
                "models_tested": seq_scores[0].scoring_strategy.get("models_tested", []) if seq_scores else [],
                "windows_tested": seq_scores[0].scoring_strategy.get("windows_tested", []) if seq_scores else [],
                "ablation_mode": (request.ablation_mode or "SPE").upper()
            }

            # Minimal provenance for lifts/components used
            response.provenance["lifts"] = {
                "ablation_mode": (request.ablation_mode or "SPE").upper()
            }

            # Optional: trials shortlist stub (toggle via request.options)
            try:
                if (request.options or {}).get("include_trials_stub"):
                    response.provenance["trials"] = {
                        "shortlist_compression": "50+ → 7",
                        "categories": {"likely": 3, "potential": 4, "unlikely": 0}
                    }
            except Exception:
                pass
            
        except Exception as e:
            response.provenance["error"] = str(e)
            # Return empty response with error in provenance
        
        return response
    
    async def explain(self, request: EfficacyRequest) -> Dict[str, Any]:
        """
        Explain efficacy prediction (simplified version).
        
        Args:
            request: Efficacy prediction request
            
        Returns:
            Explanation dictionary
        """
        # For now, return basic explanation
        # This can be expanded with more detailed explanations
        return {
            "explanation": "Efficacy prediction based on sequence disruption, pathway alignment, and evidence strength",
            "method": "Multi-modal scoring with confidence modulation",
            "run_signature": str(uuid.uuid4())
        }


# Factory function for creating orchestrator
def create_efficacy_orchestrator(api_base: str = "http://127.0.0.1:8000") -> EfficacyOrchestrator:
    """
    Create efficacy orchestrator with default components.
    
    Args:
        api_base: Base API URL
        
    Returns:
        Configured EfficacyOrchestrator
    """
    from ..sequence_scorers import FusionAMScorer, Evo2Scorer, MassiveOracleScorer
    
    fusion_scorer = FusionAMScorer()
    evo_scorer = Evo2Scorer(api_base)
    massive_scorer = MassiveOracleScorer()
    
    sequence_processor = SequenceProcessor(fusion_scorer, evo_scorer, massive_scorer)
    drug_scorer = DrugScorer()
    
    return EfficacyOrchestrator(sequence_processor, drug_scorer)
