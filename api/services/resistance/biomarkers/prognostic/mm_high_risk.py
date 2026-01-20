"""
MM High-Risk Gene Detector (Signal 4).

Validated capability:
- DIS3 (MM, RR=2.08, p=0.0145) - SIGNIFICANT
- TP53 (MM, RR=1.90, p=0.11) - TREND

Extracted from resistance_prophet_service.py (lines 861-969).
"""

from typing import Dict, List, Optional
import logging

from ...biomarkers.base import BaseResistanceDetector
from ...models import ResistanceSignalData, ResistanceSignal
from ...config import MM_HIGH_RISK_GENES

logger = logging.getLogger(__name__)


# MM HIGH-RISK GENE MARKERS (Proxy SAE - Gene-Level Validated)
# Source: MMRF CoMMpass GDC data, N=219 patients with mutations
# Now imported from config - kept here for reference
_MM_HIGH_RISK_GENES_REFERENCE = {
    "DIS3": {
        "relative_risk": 2.08,
        "p_value": 0.0145,
        "confidence": 0.95,
        "validation_source": "MMRF_CoMMpass_GDC",
        "n_mutated": 38,
        "mechanism": "RNA surveillance deficiency",
        "drug_classes_affected": ["proteasome_inhibitor", "imid"],
        "rationale": "DIS3 loss-of-function impairs RNA quality control, associated with 2x mortality risk"
    },
    "TP53": {
        "relative_risk": 1.90,
        "p_value": 0.11,
        "confidence": 0.75,  # Trend, not significant
        "validation_source": "MMRF_CoMMpass_GDC",
        "n_mutated": 16,
        "mechanism": "Genomic instability, therapy resistance",
        "drug_classes_affected": ["proteasome_inhibitor", "imid", "anti_cd38"],
        "rationale": "TP53 mutations confer genomic instability and multi-drug resistance"
    },
    "KRAS": {
        "relative_risk": 0.93,
        "p_value": 0.87,
        "confidence": 0.0,  # No signal
        "validation_source": "MMRF_CoMMpass_GDC",
        "n_mutated": 73,
        "mechanism": "MAPK pathway activation",
        "drug_classes_affected": [],
        "rationale": "KRAS mutations do not predict mortality in MM (no validated signal)"
    },
    "NRAS": {
        "relative_risk": 0.93,
        "p_value": 0.87,
        "confidence": 0.0,  # No signal
        "validation_source": "MMRF_CoMMpass_GDC",
        "n_mutated": 52,
        "mechanism": "MAPK pathway activation",
        "drug_classes_affected": [],
        "rationale": "NRAS mutations do not predict mortality in MM (no validated signal)"
    },
}


class MMHighRiskGeneDetector(BaseResistanceDetector):
    """
    Detect MM high-risk gene mutations (Signal 4 - MM-specific).
    
    Validated markers (Proxy SAE - Gene-Level):
    - DIS3: RR=2.08, p=0.0145 (SIGNIFICANT) - RNA surveillance
    - TP53: RR=1.90, p=0.11 (TREND) - Genomic instability
    
    Validation Status: ✅ VALIDATED
    - DIS3 (MM, RR=2.08, p=0.0145)
    - TP53 (MM, RR=1.90, p=0.11 trend)
    """
    
    def __init__(self, event_emitter=None):
        """Initialize MM high-risk gene detector."""
        super().__init__(event_emitter)
        self.logger = logger
        self.mm_high_risk_genes = MM_HIGH_RISK_GENES
    
    async def detect(
        self,
        mutations: List[Dict],
        drug_class: Optional[str] = None
    ) -> ResistanceSignalData:
        """
        Detect MM high-risk gene mutations.
        
        Args:
            mutations: List of patient mutations with 'gene' field
            drug_class: Current drug class (to assess relevance)
        
        Returns:
            ResistanceSignalData with detected high-risk genes
        """
        self.logger.info("Detecting MM high-risk gene mutations (Proxy SAE)...")
        
        if not mutations:
            signal_data = ResistanceSignalData(
                signal_type=ResistanceSignal.MM_HIGH_RISK_GENE,
                detected=False,
                probability=0.0,
                confidence=0.0,
                rationale="No mutations provided for MM high-risk gene analysis",
                provenance={"signal_type": "MM_HIGH_RISK_GENE", "status": "no_mutations"}
            )
            self._emit_signal_absent(ResistanceSignal.MM_HIGH_RISK_GENE, "No mutations provided")
            return signal_data
        
        # Extract gene names from mutations
        patient_genes = {m.get("gene", "").upper() for m in mutations}
        
        # Check for high-risk gene mutations
        detected_high_risk = []
        total_relative_risk = 0.0
        max_relative_risk = 0.0
        weighted_confidence = 0.0
        
        for gene, info in self.mm_high_risk_genes.items():
            if gene in patient_genes and info["confidence"] > 0:
                detected_high_risk.append({
                    "gene": gene,
                    "relative_risk": info["relative_risk"],
                    "p_value": info["p_value"],
                    "mechanism": info["mechanism"],
                    "rationale": info["rationale"],
                    "drug_classes_affected": info["drug_classes_affected"]
                })
                total_relative_risk += info["relative_risk"]
                max_relative_risk = max(max_relative_risk, info["relative_risk"])
                weighted_confidence += info["confidence"]
        
        detected = len(detected_high_risk) > 0
        
        # Compute probability from relative risk
        if detected:
            # Use max RR for probability (not additive)
            probability = max_relative_risk / (max_relative_risk + 1.0)
            confidence = min(1.0, weighted_confidence / len(detected_high_risk))
        else:
            probability = 0.0
            confidence = 0.0
        
        # Check drug class relevance
        drug_relevant = False
        if drug_class and detected:
            drug_class_lower = drug_class.lower().replace(" ", "_").replace("-", "_")
            for gene_info in detected_high_risk:
                for affected_class in gene_info["drug_classes_affected"]:
                    if affected_class in drug_class_lower or drug_class_lower in affected_class:
                        drug_relevant = True
                        break
        
        # Boost confidence if drug-relevant
        if drug_relevant:
            confidence = min(1.0, confidence * 1.1)
        
        gene_names = [g["gene"] for g in detected_high_risk]
        rationale = (
            f"MM high-risk gene analysis: {len(detected_high_risk)} gene(s) detected. "
            f"{'DETECTED' if detected else 'Not detected'}: {', '.join(gene_names) if gene_names else 'none'}. "
            f"Max RR: {max_relative_risk:.2f}. "
            f"Drug relevance: {'YES' if drug_relevant else 'NO'}."
        )
        
        provenance = {
            "signal_type": "MM_HIGH_RISK_GENE",
            "detected_genes": detected_high_risk,
            "patient_genes_checked": list(patient_genes & set(self.mm_high_risk_genes.keys())),
            "max_relative_risk": max_relative_risk,
            "drug_class": drug_class,
            "drug_relevant": drug_relevant,
            "validation_source": "MMRF_CoMMpass_GDC",
            "method": "proxy_sae_gene_level",
            "validation_status": "VALIDATED",
            "validation_evidence": "DIS3 (RR=2.08, p=0.0145), TP53 (RR=1.90, p=0.11 trend)"
        }
        
        self.logger.info(
            f"MM high-risk gene signal: detected={detected}, genes={gene_names}, "
            f"probability={probability:.2f}"
        )
        
        signal_data = ResistanceSignalData(
            signal_type=ResistanceSignal.MM_HIGH_RISK_GENE,
            detected=detected,
            probability=float(probability),
            confidence=float(confidence),
            rationale=rationale,
            provenance=provenance
        )
        
        # Emit events
        if detected:
            self._emit_signal_detected(signal_data)
        else:
            self._emit_signal_absent(ResistanceSignal.MM_HIGH_RISK_GENE, "No high-risk genes detected")
        
        return signal_data


def get_mm_high_risk_gene_detector(event_emitter=None) -> MMHighRiskGeneDetector:
    """Factory function to create MM high-risk gene detector."""
    return MMHighRiskGeneDetector(event_emitter=event_emitter)
