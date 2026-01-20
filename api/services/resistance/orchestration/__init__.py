"""
Orchestration modules for resistance prediction.

These modules handle the aggregation of signals into overall predictions:
- Probability computation (weighted average of signals)
- Risk stratification (HIGH/MEDIUM/LOW)
- Confidence computation (with penalties and caps)
- Action determination (urgency and recommended actions)
- Treatment line adjustment (clone evolution, cross-resistance)
- Rationale building (human-readable explanations)
- Baseline provider (population averages when missing)
"""

from .resistance_probability_computer import ResistanceProbabilityComputer
from .risk_stratifier import RiskStratifier
from .confidence_computer import ConfidenceComputer
from .action_determiner import ActionDeterminer
from .treatment_line_adjuster import TreatmentLineAdjuster
from .rationale_builder import RationaleBuilder
from .baseline_provider import BaselineProvider
from .resistance_prophet_orchestrator import ResistanceProphetOrchestrator

__all__ = [
    "ResistanceProbabilityComputer",
    "RiskStratifier",
    "ConfidenceComputer",
    "ActionDeterminer",
    "TreatmentLineAdjuster",
    "RationaleBuilder",
    "BaselineProvider",
    "ResistanceProphetOrchestrator",
]
