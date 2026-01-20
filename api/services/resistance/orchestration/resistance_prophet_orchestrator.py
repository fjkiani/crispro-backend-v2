"""
Resistance Prophet Orchestrator.

Slim orchestrator that coordinates validated resistance detectors and orchestration modules.
Replaces the monolithic ResistanceProphetService with a modular, event-driven architecture.

Uses ONLY validated detectors:
- Signal 1: DNA Repair Restoration (predictive)
- Signal 4: MM High-Risk Genes (prognostic)
- Signal 7: Post-Treatment Pathway Profiling (prognostic)
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime
import logging
import asyncio

from ..models import (
    ResistancePrediction,
    ResistanceSignalData,
    ResistanceRiskLevel,
    UrgencyLevel,
)
from ..biomarkers.predictive.dna_repair_restoration import DNARepairRestorationDetector
from ..biomarkers.prognostic.mm_high_risk import MMHighRiskGeneDetector
from ..biomarkers.prognostic.pathway_post_treatment import PostTreatmentPathwayDetector

from .resistance_probability_computer import ResistanceProbabilityComputer
from .risk_stratifier import RiskStratifier
from .confidence_computer import ConfidenceComputer
from .action_determiner import ActionDeterminer
from .treatment_line_adjuster import TreatmentLineAdjuster
from .rationale_builder import RationaleBuilder
from .baseline_provider import BaselineProvider

from ..events.resistance_event_dispatcher import ResistanceEventDispatcher

logger = logging.getLogger(__name__)


class ResistanceProphetOrchestrator:
    """
    Slim orchestrator for resistance prediction.
    
    Coordinates validated detectors and orchestration modules to produce
    resistance predictions. Uses event-driven architecture for extensibility.
    """
    
    def __init__(
        self,
        sae_service=None,
        ca125_service=None,
        resistance_playbook_service=None,
        mm_pathway_service=None,
        enable_events: bool = True
    ):
        """
        Initialize orchestrator with services and detectors.
        
        Args:
            sae_service: SAE feature service
            ca125_service: CA-125 intelligence service (optional)
            resistance_playbook_service: Resistance playbook service
            mm_pathway_service: MM pathway service (optional)
            enable_events: Enable event-driven architecture (default: True)
        """
        self.sae_service = sae_service
        self.ca125_service = ca125_service
        self.resistance_playbook_service = resistance_playbook_service
        self.mm_pathway_service = mm_pathway_service
        
        # Initialize event dispatcher
        self.event_dispatcher = ResistanceEventDispatcher() if enable_events else None
        
        # Initialize validated detectors
        self.dna_repair_detector = DNARepairRestorationDetector(
            event_emitter=self.event_dispatcher
        )
        self.mm_high_risk_detector = MMHighRiskGeneDetector(
            event_emitter=self.event_dispatcher
        )
        self.post_treatment_pathway_detector = PostTreatmentPathwayDetector(
            event_emitter=self.event_dispatcher
        )
        
        # Initialize orchestration modules
        self.probability_computer = ResistanceProbabilityComputer()
        self.risk_stratifier = RiskStratifier()
        self.confidence_computer = ConfidenceComputer()
        self.action_determiner = ActionDeterminer()
        self.treatment_line_adjuster = TreatmentLineAdjuster()
        self.rationale_builder = RationaleBuilder()
        self.baseline_provider = BaselineProvider()
        
        logger.info("ResistanceProphetOrchestrator initialized with validated detectors")
    
    async def predict_resistance(
        self,
        current_sae_features: Dict,
        baseline_sae_features: Optional[Dict] = None,
        ca125_history: Optional[List[Dict]] = None,
        treatment_history: Optional[List[Dict]] = None,
        current_drug_class: Optional[str] = None,
        mutations: Optional[List[Dict]] = None,
        treatment_line: int = 1,
        prior_therapies: Optional[List[str]] = None,
        disease: str = "ovarian",
        expression_data: Optional[Dict[str, float]] = None  # For Post-Treatment Pathway Profiling
    ) -> ResistancePrediction:
        """
        Predict treatment resistance risk using validated detectors.
        
        Args:
            current_sae_features: Current SAE mechanism vector + DNA repair capacity
            baseline_sae_features: Baseline SAE features (pre-treatment if available)
            ca125_history: List of CA-125 measurements (optional)
            treatment_history: Patient treatment history (optional)
            current_drug_class: Current drug being assessed
            mutations: List of mutations (for MM detection)
            treatment_line: Treatment line (1, 2, 3+)
            prior_therapies: List of prior drug classes
            disease: Disease type ("ovarian" or "myeloma")
            
        Returns:
            ResistancePrediction with risk level, signals, actions
        """
        logger.info("=== RESISTANCE PROPHET ORCHESTRATOR: Starting prediction ===")
        
        signals_detected: List[ResistanceSignalData] = []
        warnings: List[str] = []
        
        # Track baseline handling
        baseline_source = "patient_baseline"
        baseline_penalty_applied = False
        
        # Manager Q16: Handle missing baseline
        if baseline_sae_features is None:
            logger.warning("Baseline SAE features missing - using population average")
            warnings.append("INSUFFICIENT_BASELINE_DATA")
            baseline_sae_features = self.baseline_provider.get_population_baseline()
            baseline_source = "population_average"
            baseline_penalty_applied = True
        
        # Run validated detectors in parallel
        detector_tasks = []
        
        # Signal 1: DNA Repair Restoration (OV-specific)
        if disease.lower() in ["ovarian", "ov"]:
            detector_tasks.append(
                self.dna_repair_detector.detect(
                    current_sae=current_sae_features,
                    baseline_sae=baseline_sae_features,
                    baseline_source=baseline_source
                )
            )
        
        # Signal 4: MM High-Risk Genes (MM-specific)
        if disease.lower() in ["myeloma", "mm"] and mutations:
            detector_tasks.append(
                self.mm_high_risk_detector.detect(
                    mutations=mutations,
                    drug_class=current_drug_class
                )
            )
        
        # Signal 7: Post-Treatment Pathway Profiling (requires expression data)
        if expression_data:
            detector_tasks.append(
                self.post_treatment_pathway_detector.detect(
                    expression_data=expression_data,
                    pfi_days=None
                )
            )
        
        # Execute detectors in parallel
        detector_results = await asyncio.gather(*detector_tasks, return_exceptions=True)
        
        # Process detector results
        for i, result in enumerate(detector_results):
            if isinstance(result, Exception):
                logger.error(f"Detector {i} failed: {result}")
                warnings.append(f"DETECTOR_ERROR_{i}")
            elif isinstance(result, ResistanceSignalData):
                signals_detected.append(result)
            else:
                logger.warning(f"Unexpected detector result type: {type(result)}")
        
        # Count positive signals
        signal_count = sum(1 for sig in signals_detected if sig.detected)
        
        # Compute overall resistance probability
        probability = self.probability_computer.compute(signals_detected)
        
        # Apply treatment line adjustment (if MM or treatment line > 1)
        if disease.lower() in ["myeloma", "mm"] or treatment_line > 1:
            probability, adjustment_details = self.treatment_line_adjuster.adjust(
                base_probability=probability,
                treatment_line=treatment_line,
                prior_therapies=prior_therapies,
                current_drug_class=current_drug_class
            )
        else:
            adjustment_details = None
        
        # Check if CA-125 is available
        ca125_available = ca125_history is not None and len(ca125_history) >= 2
        
        # Manager Q9: Stratify risk level
        risk_level = self.risk_stratifier.stratify(
            probability=probability,
            signal_count=signal_count,
            has_ca125=ca125_available
        )
        
        # Compute confidence with penalty tracking
        confidence, confidence_cap = self.confidence_computer.compute(
            signals=signals_detected,
            baseline_source=baseline_source,
            has_ca125=ca125_available,
            signal_count=signal_count
        )
        
        # Manager Q10: Determine urgency and actions
        urgency, actions = self.action_determiner.determine(
            risk_level=risk_level,
            signal_count=signal_count,
            signals=signals_detected,
            disease=disease
        )
        
        # Emit ActionRequired event if dispatcher available
        if self.event_dispatcher and urgency == UrgencyLevel.CRITICAL:
            self.event_dispatcher.emit_action_required(
                risk_level=risk_level,
                urgency=urgency,
                actions=actions,
                signal_count=signal_count,
                probability=probability
            )
        
        # Manager Q11: Get next-line options from ResistancePlaybookService
        next_line_options = []
        downstream_handoffs = {}
        
        if self.resistance_playbook_service and risk_level != ResistanceRiskLevel.LOW:
            try:
                # Extract detected genes for MM
                detected_genes = []
                if disease.lower() in ["myeloma", "mm"]:
                    for sig in signals_detected:
                        if sig.provenance.get("detected_genes"):
                            detected_genes.extend([g["gene"] for g in sig.provenance["detected_genes"]])
                
                # Get playbook recommendations
                playbook_result = await self.resistance_playbook_service.get_next_line_options(
                    disease=disease,
                    detected_resistance=detected_genes if detected_genes else None,
                    current_regimen=None,
                    current_drug_class=current_drug_class,
                    treatment_line=treatment_line,
                    prior_therapies=prior_therapies,
                    patient_id=None
                )
                
                # Convert alternatives to dict format
                if hasattr(playbook_result, 'alternatives'):
                    next_line_options = [
                        {
                            "drug": alt.drug,
                            "drug_class": alt.drug_class,
                            "rationale": alt.rationale,
                            "evidence_level": alt.evidence_level.value if hasattr(alt.evidence_level, 'value') else str(alt.evidence_level),
                            "priority": alt.priority,
                            "source_gene": alt.source_gene if hasattr(alt, 'source_gene') else None
                        }
                        for alt in playbook_result.alternatives
                    ]
                
                # Capture downstream handoffs
                if hasattr(playbook_result, 'downstream_handoffs'):
                    downstream_handoffs = {
                        agent: {
                            "agent": handoff.agent,
                            "action": handoff.action,
                            "payload": handoff.payload
                        }
                        for agent, handoff in playbook_result.downstream_handoffs.items()
                    }
            except Exception as e:
                logger.error(f"Failed to fetch next-line options: {e}")
                warnings.append("PLAYBOOK_SERVICE_UNAVAILABLE")
        
        # Build rationale
        if disease.lower() in ["myeloma", "mm"]:
            rationale = self.rationale_builder.build_mm_rationale(
                signals_detected=signals_detected,
                probability=probability,
                risk_level=risk_level
            )
        else:
            rationale = self.rationale_builder.build(
                signals_detected=signals_detected,
                probability=probability,
                risk_level=risk_level
            )
        
        # Add treatment line info to rationale if applicable
        if adjustment_details:
            rationale.append(f"Treatment line adjustment: {treatment_line}L (×{adjustment_details['final_multiplier']:.2f})")
            if adjustment_details.get("cross_resistance_applied"):
                rationale.append(f"Cross-resistance detected: prior {current_drug_class} exposure")
        
        # Build provenance
        provenance = {
            "model_version": "resistance_prophet_orchestrator_v1.0",
            "phase": "phase2_modularized",
            "timestamp": datetime.utcnow().isoformat(),
            "architecture": "modular_event_driven",
            "validated_detectors_used": [
                "DNA_REPAIR_RESTORATION",
                "MM_HIGH_RISK_GENE",
                "POST_TREATMENT_PATHWAY_PROFILING"
            ],
            "signals_used": [sig.signal_type.value for sig in signals_detected],
            "ca125_available": ca125_available,
            "baseline_available": baseline_source == "patient_baseline",
            "baseline_source": baseline_source,
            "baseline_penalty_applied": baseline_penalty_applied,
            "disease": disease,
            "treatment_line": treatment_line
        }
        
        # Create prediction
        prediction = ResistancePrediction(
            risk_level=risk_level,
            probability=probability,
            confidence=confidence,
            signals_detected=signals_detected,
            signal_count=signal_count,
            urgency=urgency,
            recommended_actions=actions,
            next_line_options=next_line_options,
            rationale=rationale,
            provenance=provenance,
            warnings=warnings,
            baseline_source=baseline_source,
            baseline_penalty_applied=baseline_penalty_applied,
            confidence_cap=confidence_cap
        )
        
        # Emit prediction complete event
        if self.event_dispatcher:
            self.event_dispatcher.emit_prediction_complete(prediction)
        
        logger.info(
            f"=== RESISTANCE PROPHET ORCHESTRATOR: Prediction complete - "
            f"Risk={risk_level.value}, Probability={probability:.2f}, Signals={signal_count} ==="
        )
        
        return prediction
    
    def register_event_handler(self, event_type: str, handler):
        """
        Register an event handler.
        
        Args:
            event_type: Event type (e.g., "ResistanceSignalDetected", "ActionRequired")
            handler: Callable that handles the event
        """
        if self.event_dispatcher:
            self.event_dispatcher.register_handler(event_type, handler)
        else:
            logger.warning("Event dispatcher not enabled - cannot register handler")
