"""
Ayesha SOC (Standard of Care) Service

Handles SOC recommendations for Ayesha's care plan.
"""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class AyeshaSOCService:
    """Service for SOC recommendations"""
    
    def __init__(self):
        pass
    
    def get_soc_recommendation(
        self,
        has_ascites: bool = False,
        has_peritoneal_disease: bool = False
    ) -> Dict[str, Any]:
        """
        Get SOC recommendation for Stage IVB ovarian cancer.
        
        Args:
            has_ascites: Presence of ascites
            has_peritoneal_disease: Presence of peritoneal disease
        
        Returns:
            SOC recommendation dict
        """
        add_ons = []
        if has_ascites or has_peritoneal_disease:
            add_ons.append({
                "drug": "Bevacizumab 15 mg/kg",
                "rationale": "Ascites/peritoneal disease present → bevacizumab recommended (GOG-218, ICON7)",
                "confidence": 0.90
            })
        
        return {
            "regimen": "Carboplatin AUC 5-6 + Paclitaxel 175 mg/m²",
            "confidence": 0.95,
            "rationale": "NCCN Category 1 for first-line Stage IVB HGSOC",
            "add_ons": add_ons,
            "evidence": ["NCCN Guidelines v2024", "GOG-218", "ICON7"]
        }


def get_ayesha_soc_service() -> AyeshaSOCService:
    """Get singleton instance of Ayesha SOC service"""
    global _soc_service_instance
    if _soc_service_instance is None:
        _soc_service_instance = AyeshaSOCService()
    return _soc_service_instance


_soc_service_instance: Optional[AyeshaSOCService] = None
