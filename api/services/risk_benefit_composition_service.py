"""
Risk-Benefit Composition Service

Deterministic composition of drug efficacy scores with PGx toxicity tiers
into a unified risk-benefit score for trial matching and drug ranking.

Purpose: Combine S/P/E efficacy scores with PGx safety screening to produce
integrated feasibility scores that prevent trial failures.

Research Use Only - Not for Clinical Decision Making
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class RiskBenefitResult:
    """Result of risk-benefit composition."""
    composite_score: float
    action_label: str
    efficacy_score: float
    toxicity_tier: Optional[str]
    adjustment_factor: Optional[float]
    rationale: str
    provenance: Dict[str, Any]


class RiskBenefitCompositionService:
    """
    Service for composing efficacy and toxicity into risk-benefit scores.
    
    Policy (EC2-aligned):
    - HIGH toxicity → Hard veto (score=0, AVOID)
    - MODERATE toxicity → Penalized (score × adjustment_factor)
    - LOW/None toxicity → Full score
    """
    
    def compose_risk_benefit(
        self,
        efficacy_score: float,
        toxicity_tier: Optional[str] = None,
        adjustment_factor: Optional[float] = None
    ) -> RiskBenefitResult:
        """
        Compose efficacy and toxicity into unified risk-benefit score.
        
        Args:
            efficacy_score: From S/P/E framework (0.0 - 1.0)
            toxicity_tier: From PGx screening ("LOW", "MODERATE", "HIGH", or None)
            adjustment_factor: From PGx screening (0.0 - 1.0, where 1.0 = no adjustment)
        
        Returns:
            RiskBenefitResult with composite score, action label, and rationale
        """
        # Handle missing PGx data
        if toxicity_tier is None or adjustment_factor is None:
            return RiskBenefitResult(
                composite_score=efficacy_score,
                action_label="PREFERRED (PGx UNSCREENED)",
                efficacy_score=efficacy_score,
                toxicity_tier=None,
                adjustment_factor=None,
                rationale="No PGx screening data available - using efficacy score only",
                provenance={
                    "pgx_screened": False,
                    "composition_method": "efficacy_only"
                }
            )
        
        # Hard veto for HIGH toxicity or contraindicated
        if toxicity_tier == "HIGH" or adjustment_factor <= 0.1:
            return RiskBenefitResult(
                composite_score=0.0,
                action_label="AVOID / HIGH-RISK",
                efficacy_score=efficacy_score,
                toxicity_tier=toxicity_tier,
                adjustment_factor=adjustment_factor,
                rationale=f"High toxicity risk ({toxicity_tier}, adjustment={adjustment_factor:.2f}) - hard veto applied",
                provenance={
                    "pgx_screened": True,
                    "composition_method": "hard_veto",
                    "veto_reason": "high_toxicity"
                }
            )
        
        # Penalized for MODERATE toxicity
        if toxicity_tier == "MODERATE" or adjustment_factor < 0.8:
            composite = round(efficacy_score * adjustment_factor, 3)
            return RiskBenefitResult(
                composite_score=composite,
                action_label="CONSIDER WITH MONITORING",
                efficacy_score=efficacy_score,
                toxicity_tier=toxicity_tier,
                adjustment_factor=adjustment_factor,
                rationale=f"Moderate toxicity risk ({toxicity_tier}, adjustment={adjustment_factor:.2f}) - score penalized: {efficacy_score:.3f} × {adjustment_factor:.2f} = {composite:.3f}",
                provenance={
                    "pgx_screened": True,
                    "composition_method": "penalized",
                    "penalty_factor": adjustment_factor
                }
            )
        
        # No concerns - full efficacy
        return RiskBenefitResult(
            composite_score=efficacy_score,
            action_label="PREFERRED",
            efficacy_score=efficacy_score,
            toxicity_tier=toxicity_tier,
            adjustment_factor=adjustment_factor,
            rationale=f"Low toxicity risk ({toxicity_tier}, adjustment={adjustment_factor:.2f}) - no penalty applied",
            provenance={
                "pgx_screened": True,
                "composition_method": "no_penalty"
            }
        )
    
    def compose_drug_ranking(
        self,
        drugs: List[Dict[str, Any]],
        pgx_screening: Optional[Dict[str, Dict[str, Any]]] = None
    ) -> List[Dict[str, Any]]:
        """
        Compose risk-benefit scores for a list of drugs.
        
        Args:
            drugs: List of drug dicts with efficacy_score
            pgx_screening: Optional dict mapping drug_name -> {toxicity_tier, adjustment_factor}
        
        Returns:
            List of drugs with added composite_score and action_label
        """
        pgx_screening = pgx_screening or {}
        
        ranked_drugs = []
        for drug in drugs:
            drug_name = drug.get("name", "unknown")
            efficacy_score = drug.get("efficacy_score", 0.0)
            
            # Get PGx screening results for this drug
            pgx_result = pgx_screening.get(drug_name, {})
            toxicity_tier = pgx_result.get("toxicity_tier")
            adjustment_factor = pgx_result.get("adjustment_factor")
            
            # Compose risk-benefit
            result = self.compose_risk_benefit(
                efficacy_score=efficacy_score,
                toxicity_tier=toxicity_tier,
                adjustment_factor=adjustment_factor
            )
            
            # Add to drug dict
            ranked_drug = {
                **drug,
                "composite_score": result.composite_score,
                "action_label": result.action_label,
                "toxicity_tier": result.toxicity_tier,
                "adjustment_factor": result.adjustment_factor,
                "risk_benefit_rationale": result.rationale,
                "risk_benefit_provenance": result.provenance
            }
            
            ranked_drugs.append(ranked_drug)
        
        # Sort by composite score (descending)
        ranked_drugs.sort(key=lambda d: d["composite_score"], reverse=True)
        
        return ranked_drugs


# Singleton instance
_service_instance: Optional[RiskBenefitCompositionService] = None


def get_risk_benefit_composition_service() -> RiskBenefitCompositionService:
    """Get singleton instance of risk-benefit composition service."""
    global _service_instance
    if _service_instance is None:
        _service_instance = RiskBenefitCompositionService()
    return _service_instance


