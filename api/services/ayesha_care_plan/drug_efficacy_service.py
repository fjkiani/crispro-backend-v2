"""
Ayesha Drug Efficacy Service

Handles WIWFM (drug efficacy predictions) for Ayesha's care plan.
"""

import logging
from typing import Dict, Any, Optional

import httpx

logger = logging.getLogger(__name__)


class AyeshaDrugEfficacyService:
    """Service for drug efficacy (WIWFM)"""
    
    def __init__(self, api_base: str = "http://localhost:8000"):
        self.api_base = api_base
    
    async def get_drug_efficacy(
        self,
        client: httpx.AsyncClient,
        request: Any  # CompleteCareV2Request
    ) -> Optional[Dict[str, Any]]:
        """
        Get drug efficacy predictions (WIWFM).
        
        If tumor_context provided → full WIWFM S/P/E
        If no tumor_context → return "awaiting NGS" message
        
        Args:
            client: httpx async client
            request: Complete care request
        
        Returns:
            Drug efficacy response dict or None if error
        """
        try:
            # Check if NGS data available
            tumor_context = request.tumor_context or {}
            somatic_mutations = tumor_context.get("somatic_mutations", [])
            
            # We need actual genomic data (variants), not just gene names from IHC
            has_actionable_ngs = any(
                m.get("variant") or m.get("hgvs_p") or m.get("protein_change") 
                for m in somatic_mutations
            ) or bool(tumor_context.get("hrd_score")) or bool(tumor_context.get("tmb"))
            
            if not has_actionable_ngs:
                logger.info("⚠️  No actionable NGS data (variants/HRD/TMB) found - returning awaiting_ngs")
                return {
                    "status": "awaiting_ngs",
                    "message": "Personalized drug efficacy predictions require tumor NGS data (somatic mutations, HRD, TMB, MSI)",
                    "ngs_fast_track": {
                        "ctDNA": "Guardant360 - somatic BRCA/HRR, TMB, MSI (7-10 days)",
                        "tissue_HRD": "MyChoice - HRD score for PARP maintenance planning (7-14 days)",
                        "IHC": "WT1/PAX8/p53 - confirm high-grade serous histology (1-3 days)"
                    },
                    "confidence": None,
                    "note": "Once NGS available, WIWFM will provide Evo2-powered S/P/E drug ranking with 70-85% confidence"
                }
            
            # Has NGS → call full WIWFM
            if not somatic_mutations:
                logger.warning("⚠️  No somatic mutations provided - WIWFM may return default rankings")
            
            payload = {
                "mutations": somatic_mutations,
                "disease": "ovarian_cancer_hgs",
                "patient_context": {
                    "germline_status": request.germline_status,
                    "tumor_context": tumor_context
                }
            }
            
            if request.drug_query:
                payload["drug"] = request.drug_query
            
            response = await client.post(
                f"{self.api_base}/api/efficacy/predict",
                json=payload,
                timeout=60.0
            )
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"✅ Drug efficacy: {len(data.get('drugs', []))} drugs ranked")
                return data
            else:
                logger.warning(f"Drug efficacy API error: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Drug efficacy call failed: {str(e)}")
            return None


def get_ayesha_drug_efficacy_service(api_base: Optional[str] = None) -> AyeshaDrugEfficacyService:
    """Get singleton instance of Ayesha drug efficacy service"""
    global _drug_efficacy_service_instance
    if _drug_efficacy_service_instance is None:
        _drug_efficacy_service_instance = AyeshaDrugEfficacyService(api_base=api_base)
    return _drug_efficacy_service_instance


_drug_efficacy_service_instance: Optional[AyeshaDrugEfficacyService] = None
