"""
Ayesha Resistance Service

Handles resistance playbook and Resistance Prophet for Ayesha's care plan.
"""

import logging
from typing import Dict, Any, Optional

import httpx

from api.services.resistance_prophet_service import get_resistance_prophet_service

logger = logging.getLogger(__name__)


class AyeshaResistanceService:
    """Service for resistance playbook and Resistance Prophet"""
    
    def __init__(self, api_base: str = "http://localhost:8000"):
        self.api_base = api_base
        self._prophet_service = None
    
    async def get_resistance_playbook(
        self,
        client: httpx.AsyncClient,
        request: Any  # CompleteCareV2Request
    ) -> Optional[Dict[str, Any]]:
        """
        Get resistance playbook.
        
        Requires tumor_context for resistance mechanism detection.
        
        Args:
            client: httpx async client
            request: Complete care request
        
        Returns:
            Resistance playbook response dict or None if error
        """
        tumor_context = request.tumor_context or {}
        if not tumor_context:
            return {
                "status": "awaiting_ngs",
                "message": "Resistance playbook requires tumor NGS data to detect resistance mechanisms",
                "note": "Once NGS available, resistance playbook will provide SAE-powered combo strategies and next-line switches"
            }
        
        try:
            payload = {
                "tumor_context": tumor_context,
                "treatment_history": {},  # Empty for treatment-naive
                "sae_features": None  # Will be extracted from drug efficacy if available
            }
            
            response = await client.post(
                f"{self.api_base}/api/care/resistance_playbook",
                json=payload,
                timeout=30.0
            )
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"✅ Resistance playbook: {len(data.get('risks', []))} risks identified")
                return data
            else:
                logger.warning(f"Resistance playbook API error: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Resistance playbook call failed: {str(e)}")
            return None
    
    async def get_resistance_prediction(
        self,
        current_sae_features: Optional[Dict[str, Any]],
        baseline_sae_features: Optional[Dict[str, Any]] = None,
        ca125_history: Optional[Any] = None,
        treatment_history: Optional[list] = None,
        current_drug_class: str = "platinum_chemotherapy"
    ) -> Optional[Dict[str, Any]]:
        """
        Get Resistance Prophet prediction.
        
        Manager Q7: Opt-in via include_resistance_prediction=true
        Manager Q3: Phase 1 = retrospective WITHOUT CA-125 (DNA repair + pathway escape)
        
        Args:
            current_sae_features: Current SAE features
            baseline_sae_features: Baseline SAE features (optional)
            ca125_history: CA-125 history (optional, not used in Phase 1)
            treatment_history: Treatment history
            current_drug_class: Current drug class
        
        Returns:
            Resistance prediction dict or None if error
        """
        if not current_sae_features or current_sae_features.get("status") == "awaiting_ngs":
            return {
                "status": "insufficient_data",
                "message": "Resistance prediction requires tumor NGS data and SAE features",
                "required": ["tumor_context", "sae_features"],
                "note": "Once NGS available, Resistance Prophet will predict treatment failure 3-6 months early"
            }
        
        try:
            if self._prophet_service is None:
                self._prophet_service = get_resistance_prophet_service()
            
            prediction = await self._prophet_service.predict_resistance(
                current_sae_features=current_sae_features,
                baseline_sae_features=baseline_sae_features,
                ca125_history=ca125_history,
                treatment_history=treatment_history or [],
                current_drug_class=current_drug_class
            )
            
            # Convert dataclass to dict for JSON serialization
            return {
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
            
        except Exception as e:
            logger.error(f"Resistance Prophet prediction failed: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e),
                "message": "Resistance prediction service encountered an error",
                "note": "Contact support if this persists"
            }


def get_ayesha_resistance_service(api_base: Optional[str] = None) -> AyeshaResistanceService:
    """Get singleton instance of Ayesha resistance service"""
    global _resistance_service_instance
    if _resistance_service_instance is None:
        _resistance_service_instance = AyeshaResistanceService(api_base=api_base)
    return _resistance_service_instance


_resistance_service_instance: Optional[AyeshaResistanceService] = None
