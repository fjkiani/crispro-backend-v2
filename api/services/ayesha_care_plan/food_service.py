"""
Ayesha Food Service

Handles food validation and supplement recommendations for Ayesha's care plan.
"""

import logging
from typing import Dict, Any, Optional, List

import httpx

from .utils import extract_drugs_from_regimen

logger = logging.getLogger(__name__)


class AyeshaFoodService:
    """Service for food validation and supplement recommendations"""
    
    def __init__(self, api_base: str = "http://localhost:8000"):
        self.api_base = api_base
    
    async def validate_food(
        self,
        client: httpx.AsyncClient,
        food_query: Optional[str]
    ) -> Optional[Dict[str, Any]]:
        """
        Validate food/supplement.
        
        Args:
            client: httpx async client
            food_query: Food/supplement to validate
        
        Returns:
            Food validation response dict or None if error
        """
        if not food_query:
            return None
        
        try:
            payload = {
                "compound": food_query,
                "disease": "ovarian_cancer_hgs",
                "variants": []  # Can add mutations if NGS available
            }
            
            response = await client.post(
                f"{self.api_base}/api/hypothesis/validate_food_dynamic",
                json=payload,
                timeout=60.0
            )
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"✅ Food validator: {food_query} analyzed")
                return data
            else:
                logger.warning(f"Food validator API error: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Food validator call failed: {str(e)}")
            return None
    
    async def get_supplement_recommendations(
        self,
        client: httpx.AsyncClient,
        soc_recommendation: Optional[Dict[str, Any]],
        request: Any  # CompleteCareV2Request
    ) -> Optional[Dict[str, Any]]:
        """
        Get supplement recommendations based on SOC drugs + treatment line.
        
        Args:
            client: httpx async client
            soc_recommendation: SOC recommendation dict with regimen
            request: Complete care request
        
        Returns:
            Supplement recommendations response dict or None if error
        """
        if not soc_recommendation:
            return None
        
        try:
            # Extract drugs from SOC regimen
            regimen = soc_recommendation.get("regimen", "")
            drugs = extract_drugs_from_regimen(regimen, soc_recommendation.get("add_ons", []))
            
            if not drugs:
                logger.warning("⚠️  No drugs extracted from SOC recommendation - skipping supplement recommendations")
                return None
            
            payload = {
                "drugs": drugs,
                "treatment_line": request.treatment_line or "first-line",
                "disease": "ovarian_cancer_hgs",
                "treatment_history": request.treatment_history or [],
                "germline_variants": request.germline_variants or []
            }
            
            response = await client.post(
                f"{self.api_base}/api/supplements/recommendations",
                json=payload,
                timeout=30.0
            )
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"✅ Supplement recommendations: {len(data.get('recommendations', []))} recommended, {len(data.get('avoid', []))} to avoid")
                return data
            else:
                logger.warning(f"Supplement recommendations API error: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Supplement recommendations call failed: {str(e)}")
            return None


def get_ayesha_food_service(api_base: Optional[str] = None) -> AyeshaFoodService:
    """Get singleton instance of Ayesha food service"""
    global _food_service_instance
    if _food_service_instance is None:
        _food_service_instance = AyeshaFoodService(api_base=api_base)
    return _food_service_instance


_food_service_instance: Optional[AyeshaFoodService] = None
