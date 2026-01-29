"""
Resistance Prophet Service (Modular V2)
Orchestrates disease-agnostic resistance prediction by delegating to:
- Signal Detectors (Ovarian, MM)
- Aggregation Logic (Risk Engine)
- Action Determinators
- Playbook Service (for Next Steps)

Refactored from monolithic version.
"""

from typing import List, Dict, Optional, Tuple, Any
import logging
from datetime import datetime

# Core Modules
from api.services.resistance_prophet.schemas import (
    ResistancePrediction, ResistanceRiskLevel, UrgencyLevel, ResistanceSignal, ResistanceSignalData
)
from api.services.resistance_prophet.constants import (
    HIGH_RISK_PROBABILITY, MIN_SIGNALS_FOR_HIGH
)
from api.services.resistance_prophet.baseline import get_population_baseline
from api.services.resistance_prophet.aggregation import (
    compute_probability, stratify_risk, has_prior_therapy
)
from api.services.resistance_prophet.actions import determine_actions, build_rationale
from api.services.resistance_prophet.engine import calculate_resistance_prediction

# Signal Detectors
from api.services.resistance_prophet.signals.ovarian import (
    detect_restoration, detect_escape, detect_genomic_resistance
)
from api.services.resistance_prophet.signals.mm import (
    detect_mm_high_risk_genes, detect_mm_cytogenetics
)

# Shim
from api.services.resistance_prophet.shim import serialize_to_legacy

logger = logging.getLogger(__name__)

class ResistanceProphetService:
    """
    Resistance Prophet V2 (Modular)
    """
    
    def __init__(
        self, 
        sae_service=None, 
        ca125_service=None,
        treatment_line_service=None,
        resistance_playbook_service=None
    ):
        self.sae_service = sae_service
        self.ca125_service = ca125_service
        self.treatment_line_service = treatment_line_service
        self.playbook_service = resistance_playbook_service
        logger.info("ResistanceProphetService V2 (Modular) initialized")

    def _build_naive_response(self, baseline_source: str) -> ResistancePrediction:
        """Return early response for naive patient"""
        return ResistancePrediction(
            risk_level=ResistanceRiskLevel.NOT_APPLICABLE,
            probability=0.0,
            confidence=0.0,
            signals_detected=[],
            signal_count=0,
            urgency=UrgencyLevel.ROUTINE,
            recommended_actions=[{
                "action": "ESTABLISH_BASELINE",
                "rationale": "Patient is treatment naive."
            }],
            next_line_options=[],
            rationale=["Patient is treatment naive. Resistance prediction requires prior specific therapy exposure."],
            provenance={"reason": "treatment_naive"},
            warnings=[],
            baseline_source=baseline_source,
            baseline_penalty_applied=False
        )

    def _apply_legacy_safety_caps(self, prediction: ResistancePrediction, has_ca125: bool) -> ResistancePrediction:
        """
        Restore Legacy Safety Rules:
        If CA-125 is unavailable and signal count >= 2:
        1. Cap Risk Level to MEDIUM (if HIGH)
        2. Cap Confidence to 0.60
        3. Set confidence_cap = "MEDIUM"
        """
        # Legacy Logic Condition:
        if prediction.signal_count >= 2 and prediction.probability >= HIGH_RISK_PROBABILITY:
            # Rule 1: Cap Risk
            if prediction.risk_level == ResistanceRiskLevel.HIGH:
                prediction.risk_level = ResistanceRiskLevel.MEDIUM
                prediction.warnings.append("Risk capped to MEDIUM due to missing CA-125 data.")
            
            # Rule 2: Cap Confidence
            if prediction.confidence > 0.60:
                prediction.confidence = 0.60
                prediction.confidence_cap = "MEDIUM"
                
        return prediction

    async def predict_resistance(
        self,
        patient_id: str,
        disease_type: str,
        current_sae_features: Dict,
        baseline_sae_features: Optional[Dict] = None,
        treatment_history: Optional[List] = None,
        current_drug_class: Optional[str] = None,
        # MM specifics
        mutations: Optional[List[Dict]] = None,
        cytogenetics: Optional[Dict[str, bool]] = None,
        return_object: bool = False
    ) -> Any:
        """
        Main Entry Point: Predict resistance risk.
        Returns Legacy-Shimmed Dictionary.
        """
        
        # 1. Baseline Handling
        if baseline_sae_features:
            baseline = baseline_sae_features
            baseline_source = "patient_specific"
            baseline_penalty = False
        else:
            baseline = get_population_baseline()
            baseline_source = "population_average"
            baseline_penalty = True
            
        # 2. Naive Gate Check
        is_naive = not has_prior_therapy(treatment_history)
        if is_naive:
            logger.info(f"Patient {patient_id} is treatment naive.")
            naive_pred = self._build_naive_response(baseline_source)
            return serialize_to_legacy(naive_pred)

        # 3. Signal Detection
        signals: List[ResistanceSignalData] = []
        disease_norm = disease_type.lower()
        
        if "ovarian" in disease_norm or "ov" == disease_norm:
            signals.append(await detect_restoration(current_sae_features, baseline))
            signals.append(await detect_escape(current_sae_features, baseline, current_drug_class))
            signals.append(await detect_genomic_resistance(mutations, current_drug_class))
            
        elif "myeloma" in disease_norm or "mm" in disease_norm:
            signals.append(await detect_mm_high_risk_genes(mutations, current_drug_class))
            signals.append(await detect_mm_cytogenetics(cytogenetics, current_drug_class))
            
        detected_signals = [s for s in signals if s.detected]
        signal_count = len(detected_signals)
        
        # 4. Engine Calculation (Pure Logic) - Initial Pass
        has_ca125 = any(s.signal_type == ResistanceSignal.CA125_KINETICS for s in signals)

        pred = calculate_resistance_prediction(
            signals=signals,
            treatment_history=treatment_history,
            baseline_source=baseline_source,
            baseline_penalty=baseline_penalty,
            full_ca125_history_available=has_ca125,
            playbook_next_lines=[] # Empty initially
        )

        # 5. Playbook Enrichment (Orchestration Layer)
        if self.playbook_service and pred.risk_level != ResistanceRiskLevel.LOW:
            # Helper to extract keys for playbook from *detected* signals
            detected_keys = []
            for sig in pred.signals_detected:
                if not sig.detected: continue
                
                if sig.signal_type == ResistanceSignal.DNA_REPAIR_RESTORATION:
                    detected_keys.append(ResistanceSignal.DNA_REPAIR_RESTORATION.value)
                elif sig.signal_type == ResistanceSignal.PATHWAY_ESCAPE:
                    detected_keys.append(ResistanceSignal.PATHWAY_ESCAPE.value)
                elif sig.signal_type == ResistanceSignal.GENE_LEVEL_RESISTANCE:
                     if sig.provenance.get("detected_genes"):
                         detected_keys.extend([g["gene"] for g in sig.provenance["detected_genes"]])
            
            if detected_keys:
                pb_result = await self.playbook_service.get_next_line_options(
                    disease=disease_type,
                    detected_resistance=detected_keys,
                    current_drug_class=current_drug_class,
                    treatment_line=len(treatment_history) + 1 if treatment_history else 1
                )
                pred.next_line_options = [
                    {"drug": alt.drug, "rationale": alt.rationale, "priority": alt.priority} 
                    for alt in pb_result.alternatives
                ]
        
        # 6. Return Legacy Dict
        if return_object:
            return pred
        return serialize_to_legacy(pred)


# Singleton Instance
_resistance_prophet_service = None

def get_resistance_prophet_service(
    sae_service=None,
    ca125_service=None,
    treatment_line_service=None,
    resistance_playbook_service=None
) -> ResistanceProphetService:
    global _resistance_prophet_service
    if _resistance_prophet_service is None:
        _resistance_prophet_service = ResistanceProphetService(
            sae_service, ca125_service, treatment_line_service, resistance_playbook_service
        )
    return _resistance_prophet_service
