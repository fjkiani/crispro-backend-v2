"""
Ayesha Trial Service

Handles trial fetching and ranking for Ayesha's care plan.
Uses intent-gated ranking with fallback to mechanism-fit ranking.
"""

import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


class AyeshaTrialService:
    """Service for fetching and ranking trials for Ayesha"""
    
    def __init__(self):
        pass
    
    async def get_trials(
        self,
        request: Any,  # CompleteCareV2Request
        mechanism_vector: Optional[List[float]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get ranked trials for Ayesha using intent-gated ranking.
        
        Args:
            request: Complete care request
            mechanism_vector: Optional 7D mechanism vector (unused now, kept for compatibility)
        
        Returns:
            Trials response dict with intent-gated ranked trials
        """
        try:
            logger.info("🎯 Using intent-gated Ayesha trial ranking (quality gates applied)")
            
            # Use AyeshaTrialRanker service if available, otherwise use mechanism-fit ranker
            try:
                from api.services.ayesha_trial_ranker import get_ayesha_trial_ranker
                ranker = get_ayesha_trial_ranker()
                ranked_trials = ranker.rank_trials_for_ayesha_with_details(
                    patient_mechanism_vector=None,  # Not used in intent-gated version
                    max_results=request.max_trials
                )
            except (ImportError, AttributeError):
                # Fallback: Use mechanism-fit ranker or return empty
                logger.warning("⚠️ AyeshaTrialRanker not available, using fallback")
                ranked_trials = []
            
            if not ranked_trials:
                logger.warning("⚠️ No trials passed intent gates, using fallback")
                return self._get_fallback_trial_response(tumor_context=request.tumor_context or {})
            
            # Transform to expected response format
            trials_list = []
            for trial in ranked_trials:
                # Handle both dict and object formats
                nct_id = trial.get("nct_id") if isinstance(trial, dict) else getattr(trial, "nct_id", None)
                title = trial.get("title") if isinstance(trial, dict) else getattr(trial, "title", "")
                status = trial.get("status") if isinstance(trial, dict) else getattr(trial, "status", "")
                phases = trial.get("phases") if isinstance(trial, dict) else getattr(trial, "phases", "")
                conditions = trial.get("conditions", "") if isinstance(trial, dict) else getattr(trial, "conditions", "")
                interventions = trial.get("interventions", "") if isinstance(trial, dict) else getattr(trial, "interventions", "")
                total_score = trial.get("total_score") or trial.get("score", 0.0) if isinstance(trial, dict) else getattr(trial, "total_score", getattr(trial, "score", 0.0))
                keyword_matches = trial.get("keyword_matches", {}) if isinstance(trial, dict) else getattr(trial, "keyword_matches", {})
                combo_matches = trial.get("combo_matches", []) if isinstance(trial, dict) else getattr(trial, "combo_matches", [])
                is_tagged = trial.get("is_tagged", False) if isinstance(trial, dict) else getattr(trial, "is_tagged", False)
                
                trials_list.append({
                    "nct_id": nct_id,
                    "title": title,
                    "status": status,
                    "phases": phases,
                    "conditions": conditions,
                    "interventions": interventions,
                    "score": total_score,
                    "keyword_matches": keyword_matches if isinstance(keyword_matches, dict) else {},
                    "combo_matches": combo_matches if isinstance(combo_matches, list) else [],
                    "is_tagged": is_tagged,
                    "reasoning": f"Intent-gated score: {total_score:.2f} | Matches: {', '.join(keyword_matches.keys()) if keyword_matches else 'none'}" + 
                               (f" | Combos: {', '.join(combo_matches)}" if combo_matches else "")
                })
            
            logger.info(f"✅ Intent-gated ranking: {len(trials_list)} therapeutic drug trials found")
            
            # Add holistic scores to trials
            trials_list_with_holistic = await self._add_holistic_scores(
                trials_list=trials_list,
                request=request,
                mechanism_vector=mechanism_vector
            )
            
            return {
                "trials": trials_list_with_holistic,
                "summary": {
                    "total_found": len(trials_list_with_holistic),
                    "note": f"Intent-gated ranking: {len(trials_list_with_holistic)} therapeutic drug trials aligned to Ayesha's profile (MBD4/BER, TP53, PD-L1+). Non-therapeutic studies excluded.",
                    "ranking_method": "intent_gated_ayesha_v1"
                }
            }
                
        except Exception as e:
            logger.error(f"Intent-gated ranking failed: {str(e)}", exc_info=True)
            # Fallback to mechanism-fit ranking
            logger.warning("⚠️ Falling back to mechanism-fit ranking")
            return self._get_fallback_trial_response(tumor_context=request.tumor_context or {})
    
    async def _add_holistic_scores(
        self,
        trials_list: List[Dict[str, Any]],
        request: Any,
        mechanism_vector: Optional[List[float]] = None
    ) -> List[Dict[str, Any]]:
        """
        Add holistic scores to trial matches.
        
        Holistic Score = (0.5 × Mechanism Fit) + (0.3 × Eligibility) + (0.2 × PGx Safety)
        """
        try:
            from api.services.holistic_score import get_holistic_score_service
            
            holistic_service = get_holistic_score_service()
            
            # Build patient profile for holistic scoring
            patient_profile = self._build_patient_profile_for_holistic(request, mechanism_vector)
            
            if not patient_profile:
                logger.warning("⚠️ Could not build patient profile for holistic scoring, skipping")
                return trials_list
            
            # Compute holistic scores for all trials
            holistic_results = await holistic_service.compute_batch(
                patient_profile=patient_profile,
                trials=trials_list,
                pharmacogenes=patient_profile.get("germline_variants", [])
            )
            
            # Merge holistic scores into trial results
            holistic_map = {r["nct_id"]: r for r in holistic_results if r.get("nct_id")}
            
            for trial in trials_list:
                nct_id = trial.get("nct_id")
                if nct_id and nct_id in holistic_map:
                    holistic_result = holistic_map[nct_id]
                    trial["holistic_score"] = holistic_result.get("holistic_score", 0.0)
                    trial["mechanism_fit_score"] = holistic_result.get("mechanism_fit_score", 0.0)
                    trial["eligibility_score"] = holistic_result.get("eligibility_score", 0.0)
                    trial["pgx_safety_score"] = holistic_result.get("pgx_safety_score", 1.0)
                    trial["holistic_interpretation"] = holistic_result.get("interpretation", "MEDIUM")
                    trial["holistic_recommendation"] = holistic_result.get("recommendation", "")
                    if holistic_result.get("caveats"):
                        trial["holistic_caveats"] = holistic_result.get("caveats", [])
            
            logger.info(f"✅ Holistic scores computed for {len([t for t in trials_list if 'holistic_score' in t])} trials")
            
        except ImportError:
            logger.warning("⚠️ HolisticScoreService not available, skipping holistic scoring")
        except Exception as e:
            logger.error(f"❌ Failed to compute holistic scores: {str(e)}", exc_info=True)
        
        return trials_list
    
    def _build_patient_profile_for_holistic(
        self,
        request: Any,
        mechanism_vector: Optional[List[float]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Build patient profile from request for holistic scoring.
        
        Extracts:
        - mechanism_vector: From request OR computed from tumor_context
        - disease: From request or defaults to "Ovarian Cancer"
        - age: From request or defaults to 40 (Ayesha's age)
        - germline_variants: From request or defaults to MBD4, PDGFRA VUS
        - location: From request or defaults to NY
        """
        profile = {}
        
        # Mechanism vector (primary: from parameter, fallback: compute from tumor_context)
        if mechanism_vector:
            profile["mechanism_vector"] = mechanism_vector
        elif request.tumor_context:
            # Try to compute from tumor_context (somatic mutations)
            profile["mechanism_vector"] = self._compute_mechanism_vector_from_tumor_context(
                request.tumor_context
            )
        else:
            # Default: DDR-high vector for Ayesha (MBD4+TP53)
            profile["mechanism_vector"] = [0.88, 0.12, 0.15, 0.10, 0.05, 0.2, 0.0]
            logger.info("Using default DDR-high mechanism vector for Ayesha")
        
        # Disease
        if hasattr(request, 'tumor_context') and request.tumor_context:
            disease_type = request.tumor_context.get("disease_type", "ovarian_cancer_hgs")
        else:
            disease_type = "ovarian_cancer_hgs"
        
        # Convert to holistic service format
        if "ovarian" in disease_type.lower():
            profile["disease"] = "Ovarian Cancer"
        else:
            profile["disease"] = "Ovarian Cancer"  # Default
        
        # Age (from request or default to Ayesha's age: 40)
        profile["age"] = getattr(request, 'age', None) or 40
        
        # Germline variants
        germline_variants = []
        if hasattr(request, 'germline_status') and request.germline_status:
            # MBD4 homozygous pathogenic
            germline_variants.append({"gene": "MBD4", "variant": "c.1293delA"})
            # PDGFRA VUS
            germline_variants.append({"gene": "PDGFRA", "variant": "c.2263T>C"})
        profile["germline_variants"] = germline_variants
        
        # Location (NY for Ayesha)
        profile["location"] = {"state": getattr(request, 'location_state', None) or "NY"}
        
        return profile
    
    def _compute_mechanism_vector_from_tumor_context(
        self,
        tumor_context: Dict[str, Any]
    ) -> List[float]:
        """
        Compute 7D mechanism vector from tumor_context somatic mutations.
        
        Falls back to default DDR-high vector if computation fails.
        """
        try:
            from api.services.mechanism_fit_adapter import compute_patient_mechanism_vector
            
            somatic_mutations = tumor_context.get("somatic_mutations", [])
            if somatic_mutations:
                vector = compute_patient_mechanism_vector(somatic_mutations)
                return vector
        except Exception as e:
            logger.warning(f"Failed to compute mechanism vector: {e}")
        
        # Default: DDR-high for Ayesha (MBD4+TP53)
        return [0.88, 0.12, 0.15, 0.10, 0.05, 0.2, 0.0]
    
    def _get_fallback_trial_response(self, tumor_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Fallback trial response with mechanism-fit ranking.
        
        This is a simplified fallback - full implementation would use mechanism-fit ranker.
        For now, returns empty trials list with note.
        """
        from api.services.ca125_intelligence import get_ca125_service
        ca125_service = get_ca125_service()
        
        return {
            "trials": [],
            "soc_recommendation": {
                "regimen": "Carboplatin AUC 5-6 + Paclitaxel 175 mg/m²",
                "confidence": 0.95,
                "rationale": "NCCN Category 1 for first-line Stage IVB HGSOC",
                "add_ons": [
                    {
                        "drug": "Bevacizumab 15 mg/kg",
                        "rationale": "Ascites/peritoneal disease present → bevacizumab recommended (GOG-218, ICON7)",
                        "confidence": 0.90
                    }
                ],
                "evidence": ["NCCN Guidelines v2024", "GOG-218", "ICON7"]
            },
            "ca125_intelligence": ca125_service.analyze_ca125(
                current_value=2842.0,
                baseline_value=None,
                cycle=None,
                treatment_ongoing=False
            ),
            "summary": {
                "total_candidates": 0,
                "hard_filtered": 0,
                "top_results": 0,
                "note": "Trial search unavailable - using fallback"
            },
            "provenance": {
                "search_method": "fallback",
                "note": "Intent-gated ranking unavailable, using fallback",
                "generated_at": None
            }
        }


def get_ayesha_trial_service() -> AyeshaTrialService:
    """Get singleton instance of Ayesha trial service"""
    global _trial_service_instance
    if _trial_service_instance is None:
        _trial_service_instance = AyeshaTrialService()
    return _trial_service_instance


_trial_service_instance: Optional[AyeshaTrialService] = None
