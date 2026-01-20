"""
DNA Repair Restoration Detector (Signal 1).

Validated capability:
- NF1 (OV, RR=2.10, p<0.05)
- PI3K (OV, RR=1.39, p=0.02)

Extracted from resistance_prophet_service.py (lines 570-666).
"""

from typing import Dict, Optional
import math
import logging

from ...biomarkers.base import BaseResistanceDetector
from ...models import ResistanceSignalData, ResistanceSignal, MechanismBreakdown
from ...config import (
    PATHWAY_CONTRIBUTIONS,
    DNA_REPAIR_THRESHOLD,
    CONFIDENCE_CONFIG,
)

logger = logging.getLogger(__name__)


class DNARepairRestorationDetector(BaseResistanceDetector):
    """
    Detects DNA repair capacity restoration (Signal 1).
    
    Enhanced (Jan 28, 2025):
    - Returns mechanism_breakdown with DDR/HRR/exon changes
    - Returns pathway_contributions (DDR=0.60, HRR=0.20, exon=0.20)
    - Documents baseline_source
    
    Logic:
    - Compare current DNA repair capacity to baseline
    - Restoration detected if capacity drops (tumor restoring repair)
    - Indicates PARP resistance mechanism
    
    Validation Status: ✅ VALIDATED
    - NF1 (OV, RR=2.10, p<0.05)
    - PI3K (OV, RR=1.39, p=0.02)
    """
    
    def __init__(self, event_emitter=None):
        """Initialize DNA repair restoration detector."""
        super().__init__(event_emitter)
        self.logger = logger
    
    async def detect(
        self,
        current_sae: Dict,
        baseline_sae: Dict,
        baseline_source: str = "patient_baseline"
    ) -> ResistanceSignalData:
        """
        Detect DNA repair capacity restoration.
        
        Args:
            current_sae: Current SAE features (dna_repair_capacity, pathway_burden_ddr, etc.)
            baseline_sae: Baseline SAE features (pre-treatment if available)
            baseline_source: Source of baseline ("patient_baseline" or "population_average")
        
        Returns:
            ResistanceSignalData with detection results and mechanism_breakdown
        """
        self.logger.info("Detecting DNA repair restoration signal (enhanced)...")
        
        # Extract DNA repair capacity
        current_repair = current_sae.get("dna_repair_capacity", 0.0)
        baseline_repair = baseline_sae.get("dna_repair_capacity", 0.5)
        
        # Extract pathway-level features for mechanism breakdown
        current_ddr = current_sae.get(
            "pathway_burden_ddr",
            current_sae.get("mechanism_vector", [0.5] * 7)[0] if current_sae.get("mechanism_vector") else 0.5
        )
        baseline_ddr = baseline_sae.get(
            "pathway_burden_ddr",
            baseline_sae.get("mechanism_vector", [0.5] * 7)[0] if baseline_sae.get("mechanism_vector") else 0.5
        )
        
        current_hrr = current_sae.get("essentiality_hrr", 0.5)
        baseline_hrr = baseline_sae.get("essentiality_hrr", 0.5)
        
        current_exon = current_sae.get("exon_disruption_score", 0.5)
        baseline_exon = baseline_sae.get("exon_disruption_score", 0.5)
        
        # Compute mechanism breakdown (changes)
        ddr_change = current_ddr - baseline_ddr
        hrr_change = current_hrr - baseline_hrr
        exon_change = current_exon - baseline_exon
        
        mechanism_breakdown = MechanismBreakdown(
            ddr_pathway_change=float(ddr_change),
            hrr_essentiality_change=float(hrr_change),
            exon_disruption_change=float(exon_change)
        )
        
        # Compute DNA repair capacity change
        repair_change = current_repair - baseline_repair
        
        # Restoration = DNA repair capacity DROPPING (tumor repairing its repair deficiency)
        # A negative change means the patient's tumor is becoming MORE repair-proficient
        detected = repair_change < -DNA_REPAIR_THRESHOLD
        
        # Compute probability (sigmoid mapping)
        # More negative change = higher restoration probability
        probability = 1.0 / (1.0 + math.exp(10 * (repair_change + DNA_REPAIR_THRESHOLD)))
        probability = max(0.0, min(1.0, probability))
        
        # Confidence depends on baseline quality
        confidence = (
            CONFIDENCE_CONFIG["patient_baseline_confidence"]
            if baseline_source == "patient_baseline"
            else CONFIDENCE_CONFIG["population_baseline_confidence"]
        )
        
        rationale = (
            f"DNA repair capacity change: {repair_change:+.2f} "
            f"(baseline={baseline_repair:.2f} → current={current_repair:.2f}). "
            f"{'RESTORATION DETECTED' if detected else 'No restoration'} "
            f"(threshold={-DNA_REPAIR_THRESHOLD:+.2f}). "
            f"Mechanism breakdown: DDR={ddr_change:+.2f}, HRR={hrr_change:+.2f}, exon={exon_change:+.2f}."
        )
        
        provenance = {
            "signal_type": "DNA_REPAIR_RESTORATION",
            "baseline_capacity": float(baseline_repair),
            "current_capacity": float(current_repair),
            "absolute_change": float(repair_change),
            "threshold": float(DNA_REPAIR_THRESHOLD),
            "detection_method": "threshold_comparison",
            "baseline_source": baseline_source,
            "baseline_penalty_applied": baseline_source == "population_average",
            "mechanism_breakdown": {
                "ddr_pathway_change": float(ddr_change),
                "hrr_essentiality_change": float(hrr_change),
                "exon_disruption_change": float(exon_change)
            },
            "pathway_contributions": PATHWAY_CONTRIBUTIONS,
            "validation_status": "VALIDATED",
            "validation_evidence": "NF1 (OV, RR=2.10, p<0.05), PI3K (OV, RR=1.39, p=0.02)"
        }
        
        self.logger.info(
            f"DNA repair signal: detected={detected}, probability={probability:.2f}, "
            f"confidence={confidence:.2f}"
        )
        
        # Build signal-specific data
        signal_specific_data = {
            "mechanism_breakdown": mechanism_breakdown,
            "pathway_contributions": PATHWAY_CONTRIBUTIONS.copy()
        }
        
        signal_data = ResistanceSignalData(
            signal_type=ResistanceSignal.DNA_REPAIR_RESTORATION,
            detected=detected,
            probability=float(probability),
            confidence=float(confidence),
            rationale=rationale,
            provenance=provenance,
            signal_specific_data=signal_specific_data,
            # Legacy field for backward compatibility
            mechanism_breakdown=mechanism_breakdown
        )
        
        # Emit events
        if detected:
            self._emit_signal_detected(signal_data)
        else:
            self._emit_signal_absent(ResistanceSignal.DNA_REPAIR_RESTORATION, "No restoration detected")
        
        return signal_data


def get_dna_repair_restoration_detector(event_emitter=None) -> DNARepairRestorationDetector:
    """
    Factory function to create DNA repair restoration detector.
    
    Args:
        event_emitter: Optional event emitter for event-driven architecture
    
    Returns:
        DNARepairRestorationDetector instance
    """
    return DNARepairRestorationDetector(event_emitter=event_emitter)
