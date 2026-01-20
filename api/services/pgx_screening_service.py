"""
PGx Screening Service

Screens drugs for pharmacogenomic safety using patient germline variants.

Purpose: Screen drugs in care plans for PGx safety, providing toxicity tiers
and adjustment factors for risk-benefit composition.

Research Use Only - Not for Clinical Decision Making
"""

import logging
from typing import Dict, List, Any, Optional
from api.services.pgx_extraction_service import get_pgx_extraction_service
from api.services.dosing_guidance_service import get_dosing_guidance_service
from api.schemas.dosing import DosingGuidanceRequest

logger = logging.getLogger(__name__)


class PGxScreeningService:
    """
    Service for screening drugs against patient PGx variants.
    """
    
    def __init__(self):
        self.pgx_extraction = get_pgx_extraction_service()
        self.dosing_service = get_dosing_guidance_service()
    
    async def screen_drug(
        self,
        drug_name: str,
        germline_variants: List[Dict[str, Any]],
        treatment_line: Optional[str] = None,
        prior_therapies: Optional[List[str]] = None,
        disease: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Screen a single drug for PGx safety.
        
        Args:
            drug_name: Name of the drug to screen
            germline_variants: List of PGx variants from patient
            treatment_line: Treatment line (e.g., "first-line")
            prior_therapies: List of prior therapies
            disease: Disease type
        
        Returns:
            Dict with toxicity_tier, adjustment_factor, alerts, and recommendations
        """
        if not germline_variants:
            return {
                "toxicity_tier": None,
                "adjustment_factor": None,
                "screened": False,
                "alerts": [],
                "recommendations": [],
                "rationale": "No germline variants provided for PGx screening"
            }
        
        # Find relevant PGx variants for this drug
        relevant_variants = []
        drug_lower = drug_name.lower()
        
        for variant in germline_variants:
            gene = variant.get("gene", "").upper()
            gene_info = self.pgx_extraction.get_pharmacogene_info(gene)
            
            if gene_info:
                # Check if drug is associated with this pharmacogene
                associated_drugs = [d.lower() for d in gene_info.get("drugs", [])]
                if any(d in drug_lower or drug_lower in d for d in associated_drugs):
                    relevant_variants.append(variant)
        
        if not relevant_variants:
            return {
                "toxicity_tier": "LOW",
                "adjustment_factor": 1.0,
                "screened": True,
                "alerts": [],
                "recommendations": [],
                "rationale": f"No PGx variants found for {drug_name} - standard dosing appropriate"
            }
        
        # Get dosing guidance for each relevant variant
        alerts = []
        recommendations = []
        max_toxicity_tier = "LOW"
        min_adjustment_factor = 1.0
        
        for variant in relevant_variants:
            gene = variant.get("gene", "").upper()
            variant_hgvs = variant.get("variant") or variant.get("hgvs_c") or variant.get("hgvs_p") or ""
            
            try:
                # Convert treatment_line to int if string
                treatment_line_int = None
                if treatment_line:
                    if isinstance(treatment_line, str):
                        # Parse "first-line" -> 1, "second-line" -> 2, etc.
                        if "first" in treatment_line.lower() or "1" in treatment_line:
                            treatment_line_int = 1
                        elif "second" in treatment_line.lower() or "2" in treatment_line:
                            treatment_line_int = 2
                        elif "third" in treatment_line.lower() or "3" in treatment_line:
                            treatment_line_int = 3
                        else:
                            treatment_line_int = 1  # Default
                    else:
                        treatment_line_int = int(treatment_line)
                
                # Get dosing guidance
                dosing_request = DosingGuidanceRequest(
                    gene=gene,
                    variant=variant_hgvs,
                    drug=drug_name,
                    treatment_line=treatment_line_int,
                    prior_therapies=prior_therapies or [],
                    disease=disease
                )
                
                dosing_response = await self.dosing_service.get_dosing_guidance(dosing_request)
                
                # Extract toxicity tier and adjustment factor
                if dosing_response.contraindicated:
                    max_toxicity_tier = "HIGH"
                    min_adjustment_factor = 0.0
                    alerts.append({
                        "severity": "HIGH",
                        "gene": gene,
                        "variant": variant_hgvs,
                        "message": f"Contraindicated: {dosing_response.recommendations[0].recommendation if dosing_response.recommendations else 'High toxicity risk'}"
                    })
                elif dosing_response.recommendations:
                    rec = dosing_response.recommendations[0]
                    adj_factor = rec.adjustment_factor if rec.adjustment_factor is not None else 1.0
                    
                    if adj_factor <= 0.1:
                        max_toxicity_tier = "HIGH"
                        min_adjustment_factor = min(min_adjustment_factor, adj_factor)
                    elif adj_factor < 0.8:
                        if max_toxicity_tier != "HIGH":
                            max_toxicity_tier = "MODERATE"
                        min_adjustment_factor = min(min_adjustment_factor, adj_factor)
                    else:
                        min_adjustment_factor = min(min_adjustment_factor, adj_factor)
                    
                    recommendations.append({
                        "gene": gene,
                        "variant": variant_hgvs,
                        "adjustment_factor": adj_factor,
                        "recommendation": rec.recommendation,
                        "monitoring": rec.monitoring,
                        "alternatives": rec.alternatives
                    })
                
            except Exception as e:
                logger.warning(f"PGx screening failed for {gene} + {drug_name}: {e}")
                alerts.append({
                    "severity": "WARNING",
                    "gene": gene,
                    "variant": variant_hgvs,
                    "message": f"Screening incomplete: {str(e)}"
                })
        
        return {
            "toxicity_tier": max_toxicity_tier,
            "adjustment_factor": min_adjustment_factor,
            "screened": True,
            "alerts": alerts,
            "recommendations": recommendations,
            "rationale": f"PGx screening completed for {drug_name} - {len(relevant_variants)} relevant variant(s) found"
        }
    
    async def screen_drugs(
        self,
        drugs: List[Dict[str, Any]],
        germline_variants: List[Dict[str, Any]],
        treatment_line: Optional[str] = None,
        prior_therapies: Optional[List[str]] = None,
        disease: Optional[str] = None
    ) -> Dict[str, Dict[str, Any]]:
        """
        Screen multiple drugs for PGx safety.
        
        Args:
            drugs: List of drug dicts (must have "name" field)
            germline_variants: List of PGx variants from patient
            treatment_line: Treatment line
            prior_therapies: List of prior therapies
            disease: Disease type
        
        Returns:
            Dict mapping drug_name -> screening results
        """
        screening_results = {}
        
        for drug in drugs:
            drug_name = drug.get("name") or drug.get("drug") or "unknown"
            if drug_name == "unknown":
                continue
            
            screening_result = await self.screen_drug(
                drug_name=drug_name,
                germline_variants=germline_variants,
                treatment_line=treatment_line,
                prior_therapies=prior_therapies,
                disease=disease
            )
            
            screening_results[drug_name] = screening_result
        
        return screening_results


# Singleton instance
_service_instance: Optional[PGxScreeningService] = None


def get_pgx_screening_service() -> PGxScreeningService:
    """Get singleton instance of PGx screening service."""
    global _service_instance
    if _service_instance is None:
        _service_instance = PGxScreeningService()
    return _service_instance

