"""
Rationale Builder.

Builds human-readable rationale for resistance predictions.
"""

from typing import List
from ..models import ResistanceSignalData, ResistanceRiskLevel


class RationaleBuilder:
    """
    Build human-readable rationale for resistance predictions.
    """
    
    @staticmethod
    def build(
        signals_detected: List[ResistanceSignalData],
        probability: float,
        risk_level: ResistanceRiskLevel
    ) -> List[str]:
        """
        Build human-readable rationale for prediction.
        
        Args:
            signals_detected: List of detected resistance signals
            probability: Overall resistance probability (0.0-1.0)
            risk_level: Resistance risk level
            
        Returns:
            List of rationale strings
        """
        rationale = []
        
        # Overall assessment
        rationale.append(
            f"Overall resistance probability: {probability:.1%} ({risk_level.value} risk)"
        )
        
        # Signal-by-signal rationale
        for sig in signals_detected:
            status = "✓ DETECTED" if sig.detected else "✗ Not detected"
            rationale.append(f"{sig.signal_type.value}: {status}")
            
            # Add mechanism breakdown for DNA repair
            if sig.mechanism_breakdown:
                mb = sig.mechanism_breakdown
                rationale.append(
                    f"  → Mechanism breakdown: DDR={mb.ddr_pathway_change:+.2f}, "
                    f"HRR={mb.hrr_essentiality_change:+.2f}, exon={mb.exon_disruption_change:+.2f}"
                )
            
            # Add escaped pathways
            if sig.escaped_pathways:
                rationale.append(f"  → Escaped pathways: {', '.join(sig.escaped_pathways)}")
        
        return rationale
    
    @staticmethod
    def build_mm_rationale(
        signals_detected: List[ResistanceSignalData],
        probability: float,
        risk_level: ResistanceRiskLevel
    ) -> List[str]:
        """
        Build MM-specific rationale.
        
        Args:
            signals_detected: List of detected resistance signals
            probability: Overall resistance probability (0.0-1.0)
            risk_level: Resistance risk level
            
        Returns:
            List of rationale strings
        """
        rationale = []
        
        rationale.append(
            f"MM resistance probability: {probability:.1%} ({risk_level.value} risk)"
        )
        
        for sig in signals_detected:
            status = "✓ DETECTED" if sig.detected else "✗ Not detected"
            rationale.append(f"{sig.signal_type.value}: {status}")
            
            if sig.provenance.get("detected_genes"):
                for gene_info in sig.provenance["detected_genes"]:
                    rationale.append(
                        f"  → {gene_info['gene']}: RR={gene_info['relative_risk']:.2f}, "
                        f"p={gene_info['p_value']:.4f} ({gene_info['mechanism']})"
                    )
        
        rationale.append("")
        rationale.append("Method: Proxy SAE (Gene-Level) - Validated on MMRF CoMMpass (N=219)")
        
        return rationale
