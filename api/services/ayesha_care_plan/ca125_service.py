"""
Ayesha CA-125 Service

Wraps the existing CA-125 intelligence service.
"""

import logging
from typing import Dict, Any, Optional

from api.services.ca125_intelligence import get_ca125_service

logger = logging.getLogger(__name__)


class AyeshaCA125Service:
    """Service for CA-125 intelligence"""
    
    def __init__(self):
        self._ca125_service = get_ca125_service()
    
    def get_ca125_intelligence(
        self,
        ca125_value: Optional[float] = None,
        baseline_value: Optional[float] = None,
        cycle: Optional[int] = None,
        treatment_ongoing: bool = False
    ) -> Dict[str, Any]:
        """
        Get CA-125 intelligence analysis.
        
        Args:
            ca125_value: Current CA-125 value
            baseline_value: Baseline CA-125 value
            cycle: Treatment cycle number
            treatment_ongoing: Whether treatment is ongoing
        
        Returns:
            CA-125 intelligence dict
        """
        return self._ca125_service.analyze_ca125(
            current_value=ca125_value or 2842.0,
            baseline_value=baseline_value,
            cycle=cycle,
            treatment_ongoing=treatment_ongoing
        )


def get_ayesha_ca125_service() -> AyeshaCA125Service:
    """Get singleton instance of Ayesha CA-125 service"""
    global _ca125_service_instance
    if _ca125_service_instance is None:
        _ca125_service_instance = AyeshaCA125Service()
    return _ca125_service_instance


_ca125_service_instance: Optional[AyeshaCA125Service] = None
