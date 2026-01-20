"""
Ayesha IO Service

Handles safest IO selection for Ayesha's care plan.
"""

import logging
from typing import Dict, Any, Optional

from api.services.io_safest_selection_service import recommend_io_regimens

logger = logging.getLogger(__name__)


class AyeshaIOService:
    """Service for safest IO selection"""
    
    def __init__(self):
        pass
    
    def get_io_selection(
        self,
        request: Any  # CompleteCareV2Request
    ) -> Optional[Dict[str, Any]]:
        """
        Get safest IO regimen selection (irAE + eligibility).
        
        Args:
            request: Complete care request
        
        Returns:
            IO selection response dict or None if error
        """
        try:
            return recommend_io_regimens(
                patient_context={
                    "age": request.patient_age,
                    "autoimmune_history": request.autoimmune_history or [],
                },
                tumor_context=request.tumor_context or {},
                germline_mutations=request.germline_variants or [],
            )
        except Exception as e:
            logger.error(f"IO selection failed: {e}", exc_info=True)
            return {"error": str(e)}


def get_ayesha_io_service() -> AyeshaIOService:
    """Get singleton instance of Ayesha IO service"""
    global _io_service_instance
    if _io_service_instance is None:
        _io_service_instance = AyeshaIOService()
    return _io_service_instance


_io_service_instance: Optional[AyeshaIOService] = None
