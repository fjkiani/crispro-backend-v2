"""
Ayesha Care Plan Orchestrator

Thin orchestrator that coordinates all care plan services.
Replaces the monolithic 1700+ line orchestrator with focused service calls.
"""

import logging
import os
from datetime import datetime
from typing import Dict, Any, Optional, List

import httpx

from .schemas import CompleteCareV2Request, CompleteCareV2Response
from .trial_service import get_ayesha_trial_service
from .soc_service import get_ayesha_soc_service
from .ca125_service import get_ayesha_ca125_service
from .drug_efficacy_service import get_ayesha_drug_efficacy_service
from .food_service import get_ayesha_food_service
from .resistance_service import get_ayesha_resistance_service
from .io_service import get_ayesha_io_service
from .sae_service import get_ayesha_sae_service

logger = logging.getLogger(__name__)


class AyeshaCarePlanOrchestrator:
    """
    Orchestrator for Ayesha's complete care plan v2.
    
    Coordinates all care plan components:
    - Clinical trials (intent-gated ranking)
    - SOC recommendation (NCCN-aligned)
    - CA-125 monitoring
    - Drug efficacy (WIWFM)
    - Food validator + supplements
    - Resistance playbook + Resistance Prophet
    - SAE Phase 1 and 2 services
    - IO selection
    """
    
    def __init__(self, api_base: Optional[str] = None):
        self.api_base = api_base or os.getenv("API_BASE_URL", "http://localhost:8000")
        
        # Initialize services
        self.trial_service = get_ayesha_trial_service()
        self.soc_service = get_ayesha_soc_service()
        self.ca125_service = get_ayesha_ca125_service()
        self.drug_efficacy_service = get_ayesha_drug_efficacy_service(api_base=self.api_base)
        self.food_service = get_ayesha_food_service(api_base=self.api_base)
        self.resistance_service = get_ayesha_resistance_service(api_base=self.api_base)
        self.io_service = get_ayesha_io_service()
        self.sae_service = get_ayesha_sae_service(api_base=self.api_base)
    
    async def get_complete_care_plan(
        self,
        request: CompleteCareV2Request
    ) -> CompleteCareV2Response:
        """
        Get complete care plan for Ayesha.
        
        Args:
            request: Complete care request
        
        Returns:
            Complete care plan response
        """
        logger.info(f"Complete care v2: CA-125={request.ca125_value}, stage={request.stage}, germline={request.germline_status}")
        
        # Initialize results
        results = {
            "trials": None,
            "soc_recommendation": None,
            "ca125_intelligence": None,
            "wiwfm": None,
            "io_selection": None,
            "food_validation": None,
            "supplement_recommendations": None,
            "resistance_playbook": None,
            # Phase 1 SAE Services
            "next_test_recommender": None,
            "hint_tiles": None,
            "mechanism_map": None,
            # Phase 2 SAE Services
            "sae_features": None,
            "resistance_alert": None,
            # Resistance Prophet
            "resistance_prediction": None
        }
        
        # Create async HTTP client
        mechanism_vector = None
        async with httpx.AsyncClient() as client:
            
            # 1. Drug Efficacy (WIWFM) - Called before trials to extract mechanism vector
            if request.include_wiwfm:
                wiwfm_response = await self.drug_efficacy_service.get_drug_efficacy(client, request)
                results["wiwfm"] = wiwfm_response
                
                # 2a. PGx Safety Gate (Ayesha) — augment WIWFM drugs with PGx screening
                try:
                    from api.services.pgx_care_plan_integration import integrate_pgx_into_drug_efficacy
                    patient_profile = {
                        "dse": {"type": "ovarian_cancer_hgs"},
                        "treatment": {"line": request.treatment_line, "history": request.treatment_history or []},
                        "germline_variants": request.germline_variants or [],
                    }
                    results["wiwfm"] = await integrate_pgx_into_drug_efficacy(
                        drug_efficacy_response=results.get("wiwfm"),
                        patient_profile=patient_profile,
                        treatment_line=request.treatment_line,
                        prior_therapies=request.treatment_history or [],
                    )
                except Exception as e:
                    logger.error(f"PGx integration into WIWFM (Ayesha) failed: {e}", exc_info=True)
                
                # 2b. Safest IO selection (RUO)
                if request.include_io_selection:
                    results["io_selection"] = self.io_service.get_io_selection(request)
                
                # Extract mechanism vector from drug efficacy response
                mechanism_vector_result = self.sae_service.extract_mechanism_vector(
                    wiwfm_response,
                    request.tumor_context
                )
                if mechanism_vector_result:
                    mechanism_vector, dimension_used = mechanism_vector_result
                    logger.info(f"✅ Extracted {dimension_used} mechanism vector from drug efficacy: {mechanism_vector}")
            
            # 2. Trials (includes SOC + CA-125)
            if request.include_trials or request.include_soc or request.include_ca125:
                trials_response = await self.trial_service.get_trials(request, mechanism_vector)
                if trials_response:
                    if request.include_trials:
                        results["trials"] = {
                            "trials": trials_response.get("trials", []),
                            "summary": trials_response.get("summary", {}),
                            "provenance": trials_response.get("provenance", {})
                        }
                        
                        # PGx Trial Safety Gate (Ayesha)
                        try:
                            from api.services.pgx_care_plan_integration import add_pgx_safety_gate_to_trials
                            patient_profile = {
                                "disease": {"type": "ovarian_cancer_hgs"},
                                "treatment": {"line": request.treatment_line, "history": request.treatment_history or []},
                                "germline_variants": request.germline_variants or [],
                            }
                            results["trials"] = await add_pgx_safety_gate_to_trials(
                                trials_response=results.get("trials"),
                                patient_profile=patient_profile,
                                treatment_line=request.treatment_line,
                                prior_therapies=request.treatment_history or [],
                            )
                        except Exception as e:
                            logger.error(f"PGx trial safety gate (Ayesha) failed: {e}", exc_info=True)
                    
                    if request.include_soc:
                        results["soc_recommendation"] = trials_response.get("soc_recommendation") or self.soc_service.get_soc_recommendation(
                            has_ascites=request.has_ascites,
                            has_peritoneal_disease=request.has_peritoneal_disease
                        )
                    
                    if request.include_ca125:
                        results["ca125_intelligence"] = trials_response.get("ca125_intelligence") or self.ca125_service.get_ca125_intelligence(
                            ca125_value=request.ca125_value
                        )
            
            # 3. Food Validator (optional)
            if request.include_food and request.food_query:
                results["food_validation"] = await self.food_service.validate_food(client, request.food_query)
            
            # 4. Supplement Recommendations (based on SOC drugs + treatment line)
            if request.include_food and results.get("soc_recommendation"):
                results["supplement_recommendations"] = await self.food_service.get_supplement_recommendations(
                    client,
                    results.get("soc_recommendation"),
                    request
                )
            
            # 5. Resistance Playbook (optional)
            if request.include_resistance:
                results["resistance_playbook"] = await self.resistance_service.get_resistance_playbook(client, request)
        
        # ===================================================================
        # PHASE 1 SAE SERVICES (Manager-approved, Jan 13 2025)
        # ===================================================================
        
        # 6. Next-Test Recommender
        results["next_test_recommender"] = self.sae_service.get_next_test_recommendations(
            germline_status=request.germline_status,
            tumor_context=request.tumor_context,
            treatment_history=request.treatment_history or [],
            disease="ovarian_cancer_hgs",
            sae_features=results.get("sae_features")
        )
        
        # 7. Hint Tiles
        trials_matched = len(results["trials"]["trials"]) if results["trials"] and "trials" in results["trials"] else 0
        results["hint_tiles"] = self.sae_service.get_hint_tiles(
            germline_status=request.germline_status,
            tumor_context=request.tumor_context,
            ca125_intelligence=results["ca125_intelligence"],
            next_test_recommendations=results["next_test_recommender"].get("recommendations", []) if results["next_test_recommender"] else [],
            treatment_history=request.treatment_history or [],
            trials_matched=trials_matched,
            sae_features=results.get("sae_features")
        )
        
        # 8. Mechanism Map
        sae_features_for_map = results.get("sae_features")
        if not sae_features_for_map and results.get("wiwfm"):
            sae_features_for_map = results["wiwfm"].get("sae_features")
        results["mechanism_map"] = self.sae_service.get_mechanism_map(
            tumor_context=request.tumor_context,
            sae_features=sae_features_for_map
        )
        
        # ===================================================================
        # PHASE 2 SAE SERVICES (Manager-approved, Jan 13 2025)
        # ===================================================================
        
        if request.tumor_context:
            # 9. SAE Features
            results["sae_features"] = await self.sae_service.compute_sae_features(
                client,
                request.tumor_context,
                results.get("wiwfm"),
                results["ca125_intelligence"],
                request.treatment_history or []
            )
            
            # 10. Resistance Alert
            if results.get("sae_features") and results["sae_features"].get("status") != "awaiting_ngs":
                results["resistance_alert"] = self.sae_service.detect_resistance(
                    current_hrd=request.tumor_context.get("hrd_score", 0.0),
                    previous_hrd=None,
                    current_dna_repair_capacity=results["sae_features"].get("dna_repair_capacity", 0.0),
                    previous_dna_repair_capacity=None,
                    ca125_intelligence=results["ca125_intelligence"],
                    treatment_on_parp=False
                )
        else:
            results["sae_features"] = {"status": "awaiting_ngs"}
            results["resistance_alert"] = {"status": "awaiting_ngs"}
        
        # ===================================================================
        # RESISTANCE PROPHET (Manager-approved, Jan 14, 2025)
        # Manager Q7: Opt-in via include_resistance_prediction=true
        # ===================================================================
        
        if request.include_resistance_prediction:
            results["resistance_prediction"] = await self.resistance_service.get_resistance_prediction(
                current_sae_features=results.get("sae_features"),
                baseline_sae_features=None,
                ca125_history=None,  # Manager Q3: Phase 1 retrospective WITHOUT CA-125
                treatment_history=request.treatment_history or [],
                current_drug_class="platinum_chemotherapy"
            )
        
        # Generate summary and provenance
        summary = self._generate_summary(results, request)
        provenance = self._generate_provenance(results, request)
        
        return CompleteCareV2Response(
            trials=results["trials"],
            soc_recommendation=results["soc_recommendation"],
            ca125_intelligence=results["ca125_intelligence"],
            wiwfm=results["wiwfm"],
            io_selection=results["io_selection"],
            food_validation=results["food_validation"],
            supplement_recommendations=results["supplement_recommendations"],
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
    
    def _generate_summary(self, results: Dict[str, Any], request: CompleteCareV2Request) -> Dict[str, Any]:
        """Generate summary of care plan components"""
        summary = {
            "components_included": [],
            "ngs_status": "pending" if not request.tumor_context else "available",
            "confidence_level": "high (90-100%)" if not request.tumor_context else "moderate-high (70-90%)",
            "reasoning": "Confidence is high for guideline-based recommendations (trials, SOC, CA-125). " +
                        "Confidence is moderate for personalized predictions (WIWFM requires NGS)."
        }
        
        component_map = {
            "trials": "clinical_trials",
            "soc_recommendation": "soc_recommendation",
            "ca125_intelligence": "ca125_monitoring",
            "wiwfm": "wiwfm",
            "food_validation": "food_validation",
            "supplement_recommendations": "supplement_recommendations",
            "resistance_playbook": "resistance_playbook",
            "resistance_prediction": "resistance_prediction",
            "next_test_recommender": "next_test_recommender",
            "hint_tiles": "hint_tiles",
            "mechanism_map": "mechanism_map"
        }
        
        for key, component_name in component_map.items():
            if results.get(key):
                summary["components_included"].append(component_name)
        
        return summary
    
    def _generate_provenance(self, results: Dict[str, Any], request: CompleteCareV2Request) -> Dict[str, Any]:
        """Generate provenance metadata"""
        summary = self._generate_summary(results, request)
        
        return {
            "orchestrator": "complete_care_v2_modular",
            "for_patient": "AK (Stage IVB ovarian cancer)",
            "endpoints_called": summary["components_included"],
            "ngs_status": summary["ngs_status"],
            "generated_at": datetime.utcnow().isoformat(),
            "run_id": f"complete_care_v2_{int(datetime.utcnow().timestamp())}",
            "note": "This is NOT a demo. Real clinical decision support for Ayesha's life.",
            "sae_phase1_enabled": True,
            "sae_services": ["next_test_recommender", "hint_tiles", "mechanism_map"],
            "resistance_prophet_enabled": request.include_resistance_prediction,
            "resistance_prophet_phase": "phase1_retrospective_no_ca125",
            "manager_policy_sae": "MANAGER_ANSWERS_TO_ZO_SAE_QUESTIONS.md (Jan 13, 2025)",
            "manager_policy_prophet": "MANAGER_ANSWERS_TO_RESISTANCE_PROPHET_QUESTIONS.md (Jan 14, 2025)",
            "architecture": "modular_service_based"
        }


def get_ayesha_care_plan_orchestrator(api_base: Optional[str] = None) -> AyeshaCarePlanOrchestrator:
    """Get singleton instance of Ayesha care plan orchestrator"""
    global _orchestrator_instance
    if _orchestrator_instance is None:
        _orchestrator_instance = AyeshaCarePlanOrchestrator(api_base=api_base)
    return _orchestrator_instance


_orchestrator_instance: Optional[AyeshaCarePlanOrchestrator] = None
