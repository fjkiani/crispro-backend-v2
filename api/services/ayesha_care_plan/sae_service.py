"""
Ayesha SAE Service

Handles SAE Phase 1 and Phase 2 services for Ayesha's care plan.
"""

import logging
from typing import Dict, Any, Optional, List

from api.services.next_test_recommender import get_next_test_recommendations
from api.services.hint_tiles_service import get_hint_tiles
from api.services.mechanism_map_service import get_mechanism_map
from api.services.sae_feature_service import compute_sae_features
from api.services.resistance_detection_service import detect_resistance
from api.services.pathway_to_mechanism_vector import get_mechanism_vector_from_response

from .utils import extract_insights_bundle

logger = logging.getLogger(__name__)


class AyeshaSAEService:
    """Service for SAE Phase 1 and Phase 2 services"""
    
    def __init__(self, api_base: str = "http://localhost:8000"):
        self.api_base = api_base
    
    def get_next_test_recommendations(
        self,
        germline_status: str,
        tumor_context: Optional[Dict[str, Any]],
        treatment_history: List[Dict[str, Any]],
        disease: str,
        sae_features: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Get next-test recommendations (Phase 1 SAE).
        
        Manager's priority: HRD → ctDNA → SLFN11 → ABCB1
        
        Args:
            germline_status: Germline mutation status
            tumor_context: Tumor context
            treatment_history: Treatment history
            disease: Disease type
            sae_features: SAE features (optional, for dynamic prioritization)
        
        Returns:
            Next-test recommendations dict
        """
        try:
            return get_next_test_recommendations(
                germline_status=germline_status,
                tumor_context=tumor_context,
                treatment_history=treatment_history,
                disease=disease,
                sae_features=sae_features
            )
        except Exception as e:
            logger.error(f"Next-test recommender failed: {e}")
            return {
                "error": str(e),
                "recommendations": [],
                "note": "Service temporarily unavailable"
            }
    
    def get_hint_tiles(
        self,
        germline_status: str,
        tumor_context: Optional[Dict[str, Any]],
        ca125_intelligence: Optional[Dict[str, Any]],
        next_test_recommendations: List[Dict[str, Any]],
        treatment_history: List[Dict[str, Any]],
        trials_matched: int,
        sae_features: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Get hint tiles (Phase 1 SAE).
        
        Max 4, suggestive tone, priority: Test → Trials → Monitor → Avoid
        
        Args:
            germline_status: Germline mutation status
            tumor_context: Tumor context
            ca125_intelligence: CA-125 intelligence
            next_test_recommendations: Next-test recommendations
            treatment_history: Treatment history
            trials_matched: Number of trials matched
            sae_features: SAE features (optional, for hotspot detection)
        
        Returns:
            Hint tiles dict
        """
        try:
            return get_hint_tiles(
                germline_status=germline_status,
                tumor_context=tumor_context,
                ca125_intelligence=ca125_intelligence,
                next_test_recommendations=next_test_recommendations,
                treatment_history=treatment_history,
                trials_matched=trials_matched,
                sae_features=sae_features
            )
        except Exception as e:
            logger.error(f"Hint tiles failed: {e}")
            return {
                "error": str(e),
                "hint_tiles": [],
                "note": "Service temporarily unavailable"
            }
    
    def get_mechanism_map(
        self,
        tumor_context: Optional[Dict[str, Any]],
        sae_features: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Get mechanism map (Phase 1 SAE).
        
        Pre-NGS: all gray; Post-NGS: color-coded
        
        Args:
            tumor_context: Tumor context
            sae_features: SAE features (optional)
        
        Returns:
            Mechanism map dict
        """
        try:
            return get_mechanism_map(
                tumor_context=tumor_context,
                sae_features=sae_features
            )
        except Exception as e:
            logger.error(f"Mechanism map failed: {e}")
            return {
                "error": str(e),
                "chips": [],
                "status": "error",
                "note": "Service temporarily unavailable"
            }
    
    async def compute_sae_features(
        self,
        client: Any,  # httpx.AsyncClient
        tumor_context: Optional[Dict[str, Any]],
        wiwfm_response: Optional[Dict[str, Any]],
        ca125_intelligence: Optional[Dict[str, Any]],
        treatment_history: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """
        Compute SAE features (Phase 2 SAE).
        
        Args:
            client: httpx async client
            tumor_context: Tumor context
            wiwfm_response: WIWFM response (for pathway scores)
            ca125_intelligence: CA-125 intelligence
            treatment_history: Treatment history
        
        Returns:
            SAE features dict or None if error
        """
        if not tumor_context:
            return {"status": "awaiting_ngs"}
        
        try:
            # Extract pathway scores from WIWFM response, fallback to proxy defaults
            pathway_scores = None
            sae_source = "proxy"
            
            if wiwfm_response:
                wiwfm_provenance = wiwfm_response.get("provenance", {})
                confidence_breakdown = wiwfm_provenance.get("confidence_breakdown", {})
                pathway_scores = confidence_breakdown.get("pathway_disruption")
                
                if pathway_scores:
                    sae_source = "wiwfm_extracted"
                    logger.info(f"✅ Extracted pathway scores from WIWFM: {pathway_scores}")
                else:
                    logger.warning("⚠️  pathway_disruption not in WIWFM response - using proxy defaults")
            
            # Fallback: Use proxy defaults
            if not pathway_scores:
                pathway_scores = {"ddr": 0.5, "mapk": 0.2, "pi3k": 0.2, "vegf": 0.3, "her2": 0.0}
                logger.info(f"📊 Using proxy SAE pathway scores (source: {sae_source})")
            
            # Extract insights bundle
            somatic_mutations = tumor_context.get("somatic_mutations", [])
            logger.info(f"🔍 [P0 FIX] Extracting insights bundle for {len(somatic_mutations)} mutations...")
            
            insights_bundle = await extract_insights_bundle(
                client,
                somatic_mutations,
                api_base=self.api_base
            )
            
            logger.info(f"📊 Final insights_bundle before SAE computation: essentiality={insights_bundle.get('essentiality'):.3f}")
            
            # Compute SAE features
            return compute_sae_features(
                insights_bundle=insights_bundle,
                pathway_scores=pathway_scores,
                tumor_context=tumor_context,
                treatment_history=treatment_history,
                ca125_intelligence=ca125_intelligence
            )
            
        except Exception as e:
            logger.error(f"❌ SAE features computation failed: {e}", exc_info=True)
            return None
    
    def detect_resistance(
        self,
        current_hrd: float,
        previous_hrd: Optional[float],
        current_dna_repair_capacity: float,
        previous_dna_repair_capacity: Optional[float],
        ca125_intelligence: Optional[Dict[str, Any]],
        treatment_on_parp: bool
    ) -> Dict[str, Any]:
        """
        Detect resistance (Phase 2 SAE).
        
        2-of-3 triggers, HR restoration, immediate alerts
        
        Args:
            current_hrd: Current HRD score
            previous_hrd: Previous HRD score (optional)
            current_dna_repair_capacity: Current DNA repair capacity
            previous_dna_repair_capacity: Previous DNA repair capacity (optional)
            ca125_intelligence: CA-125 intelligence
            treatment_on_parp: Whether on PARP treatment
        
        Returns:
            Resistance alert dict
        """
        try:
            return detect_resistance(
                current_hrd=current_hrd,
                previous_hrd=previous_hrd,
                current_dna_repair_capacity=current_dna_repair_capacity,
                previous_dna_repair_capacity=previous_dna_repair_capacity,
                ca125_intelligence=ca125_intelligence,
                treatment_on_parp=treatment_on_parp
            )
        except Exception as e:
            logger.error(f"Resistance detection failed: {e}")
            return {"error": str(e), "resistance_detected": False}
    
    def extract_mechanism_vector(
        self,
        wiwfm_response: Optional[Dict[str, Any]],
        tumor_context: Optional[Dict[str, Any]]
    ) -> Optional[tuple]:
        """
        Extract mechanism vector from WIWFM response.
        
        Args:
            wiwfm_response: WIWFM response
            tumor_context: Tumor context
        
        Returns:
            Tuple of (mechanism_vector, dimension_used) or None
        """
        if not wiwfm_response or wiwfm_response.get("status") == "awaiting_ngs":
            return None
        
        try:
            return get_mechanism_vector_from_response(
                wiwfm_response,
                tumor_context=tumor_context,
                use_7d=True  # Use 7D vector [DDR, MAPK, PI3K, VEGF, HER2, IO, Efflux]
            )
        except Exception as e:
            logger.warning(f"Failed to extract mechanism vector: {e}")
            return None


def get_ayesha_sae_service(api_base: Optional[str] = None) -> AyeshaSAEService:
    """Get singleton instance of Ayesha SAE service"""
    global _sae_service_instance
    if _sae_service_instance is None:
        _sae_service_instance = AyeshaSAEService(api_base=api_base)
    return _sae_service_instance


_sae_service_instance: Optional[AyeshaSAEService] = None
