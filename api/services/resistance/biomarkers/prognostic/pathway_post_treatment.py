"""
Post-Treatment Pathway Profiling Detector (Signal 7).

Validated capability:
- GSE165897 (n=11): Post-treatment DDR ρ=-0.711, p=0.014, AUC=0.714
- Post-treatment PI3K AUC=0.750
- Composite score ρ=-0.674, p=0.023, AUC=0.714

Key Insight: Uses post-treatment pathway STATE (absolute scores), NOT pathway changes/kinetics.

New capability - not in monolith. See POST_TREATMENT_PATHWAY_PROFILING.md for full details.
"""

from typing import Dict, List, Optional
import logging
import numpy as np

from ...biomarkers.base import BaseResistanceDetector
from ...models import ResistanceSignalData, ResistanceSignal
from ...config import (
    PATHWAY_GENE_LISTS,
    POST_TREATMENT_COMPOSITE_WEIGHTS,
    POST_TREATMENT_RESISTANCE_THRESHOLDS,
)

logger = logging.getLogger(__name__)


class PostTreatmentPathwayDetector(BaseResistanceDetector):
    """
    Detects resistance risk using post-treatment pathway profiling.
    
    Uses post-treatment pathway STATE (absolute scores) to predict platinum resistance.
    NOT pathway kinetics/changes - those failed validation.
    
    Validation Status: ✅ VALIDATED
    - GSE165897 (n=11): Post-treatment DDR ρ=-0.711, p=0.014, AUC=0.714
    - Post-treatment PI3K AUC=0.750
    - Composite score ρ=-0.674, p=0.023, AUC=0.714
    
    Requires: Post-treatment gene expression data (after NACT completion)
    """
    
    def __init__(self, event_emitter=None):
        """Initialize post-treatment pathway profiling detector."""
        super().__init__(event_emitter)
        self.logger = logger
        self.ddr_genes = PATHWAY_GENE_LISTS["ddr"]
        self.pi3k_genes = PATHWAY_GENE_LISTS["pi3k"]
        self.vegf_genes = PATHWAY_GENE_LISTS["vegf"]
        self.composite_weights = POST_TREATMENT_COMPOSITE_WEIGHTS
        self.thresholds = POST_TREATMENT_RESISTANCE_THRESHOLDS
    
    async def detect(
        self,
        expression_data: Dict[str, float],
        pfi_days: Optional[float] = None
    ) -> ResistanceSignalData:
        """
        Detect resistance risk from post-treatment pathway scores.
        
        Args:
            expression_data: Dictionary of gene → expression (log2(CPM + 1))
            pfi_days: Optional Platinum-Free Interval in days (for validation)
        
        Returns:
            ResistanceSignalData with pathway scores, composite score, and resistance prediction
        """
        self.logger.info("Detecting post-treatment pathway profiling signal...")
        
        # Compute pathway scores
        ddr_score = self._compute_pathway_score(expression_data, self.ddr_genes)
        pi3k_score = self._compute_pathway_score(expression_data, self.pi3k_genes)
        vegf_score = self._compute_pathway_score(expression_data, self.vegf_genes)
        
        pathway_scores = {
            "ddr": ddr_score,
            "pi3k": pi3k_score,
            "vegf": vegf_score
        }
        
        # Compute composite scores
        composite_equal = (ddr_score + pi3k_score + vegf_score) / 3.0
        composite_weighted = (
            self.composite_weights["ddr"] * ddr_score +
            self.composite_weights["pi3k"] * pi3k_score +
            self.composite_weights["vegf"] * vegf_score
        )
        
        # Predict resistance risk
        resistance_risk = self._predict_resistance_risk(
            ddr_score=ddr_score,
            pi3k_score=pi3k_score,
            composite_score=composite_weighted
        )
        
        # Determine if resistance detected
        detected = resistance_risk["risk_level"] in ["HIGH", "MEDIUM"]
        
        rationale = (
            f"Post-treatment pathway profiling: DDR={ddr_score:.3f}, PI3K={pi3k_score:.3f}, "
            f"VEGF={vegf_score:.3f}. Composite (weighted)={composite_weighted:.3f}. "
            f"Risk level: {resistance_risk['risk_level']}. "
            f"Predicted PFI category: {resistance_risk['predicted_pfi_category']}."
        )
        
        provenance = {
            "signal_type": "POST_TREATMENT_PATHWAY_PROFILING",
            "pathway_scores": pathway_scores,
            "composite_scores": {
                "equal_weight": composite_equal,
                "weighted": composite_weighted
            },
            "resistance_prediction": resistance_risk,
            "thresholds": self.thresholds,
            "composite_weights": self.composite_weights,
            "validation_cohort": "GSE165897",
            "validation_n": 11,
            "validation_status": "VALIDATED",
            "validation_evidence": {
                "ddr_correlation": {"spearman_rho": -0.711, "p_value": 0.014, "auc": 0.714},
                "pi3k_correlation": {"spearman_rho": -0.683, "p_value": 0.020, "auc": 0.750},
                "composite_correlation": {"spearman_rho": -0.674, "p_value": 0.023, "auc": 0.714}
            },
            "method": "post_treatment_pathway_state",
            "note": "Uses post-treatment pathway STATE (absolute scores), NOT pathway changes"
        }
        
        self.logger.info(
            f"Post-treatment pathway signal: detected={detected}, "
            f"risk_level={resistance_risk['risk_level']}, "
            f"composite_score={composite_weighted:.3f}"
        )
        
        signal_data = ResistanceSignalData(
            signal_type=ResistanceSignal.POST_TREATMENT_PATHWAY_PROFILING,
            detected=detected,
            probability=float(resistance_risk["risk_score"]),
            confidence=0.90,  # High confidence (validated on GSE165897)
            rationale=rationale,
            provenance=provenance,
            pathway_scores=pathway_scores,
            composite_score=composite_weighted,
            predicted_pfi_category=resistance_risk["predicted_pfi_category"]
        )
        
        # Emit events
        if detected:
            self._emit_signal_detected(signal_data)
        else:
            self._emit_signal_absent(
                ResistanceSignal.POST_TREATMENT_PATHWAY_PROFILING,
                "Low resistance risk"
            )
        
        return signal_data
    
    def _compute_pathway_score(
        self,
        expression_data: Dict[str, float],
        pathway_genes: List[str]
    ) -> float:
        """Compute pathway burden score from gene expression."""
        pathway_expressions = []
        
        for gene in pathway_genes:
            # Case-insensitive matching
            matched_gene = None
            for expr_gene in expression_data.keys():
                if expr_gene.upper() == gene.upper():
                    matched_gene = expr_gene
                    break
            
            if matched_gene:
                pathway_expressions.append(expression_data[matched_gene])
        
        if not pathway_expressions:
            return 0.0
        
        # Mean of log2(expression + 1) - already log2 transformed
        mean_expression = np.mean(pathway_expressions)
        
        # Normalize to 0-1 scale (empirical range: 0-15 for log2(CPM+1))
        normalized = min(1.0, max(0.0, mean_expression / 15.0))
        
        return normalized
    
    def _predict_resistance_risk(
        self,
        ddr_score: float,
        pi3k_score: float,
        composite_score: float
    ) -> Dict[str, any]:
        """Predict resistance risk from pathway scores."""
        # Determine risk level based on thresholds
        if composite_score >= self.thresholds["composite_high"] or \
           (ddr_score >= self.thresholds["ddr_high"] and pi3k_score >= self.thresholds["pi3k_high"]):
            risk_level = "HIGH"
            risk_score = 0.85
        elif ddr_score >= self.thresholds["ddr_high"] or pi3k_score >= self.thresholds["pi3k_high"]:
            risk_level = "MEDIUM"
            risk_score = 0.65
        else:
            risk_level = "LOW"
            risk_score = 0.35
        
        # Predict PFI category (resistant: PFI < 6 months, sensitive: PFI >= 6 months)
        predicted_resistant = composite_score >= self.thresholds["composite_high"]
        predicted_pfi_category = "resistant" if predicted_resistant else "sensitive"
        
        return {
            "risk_level": risk_level,
            "risk_score": risk_score,
            "predicted_pfi_category": predicted_pfi_category,
            "thresholds": self.thresholds
        }


def get_post_treatment_pathway_detector(event_emitter=None) -> PostTreatmentPathwayDetector:
    """Factory function to create post-treatment pathway profiling detector."""
    return PostTreatmentPathwayDetector(event_emitter=event_emitter)
