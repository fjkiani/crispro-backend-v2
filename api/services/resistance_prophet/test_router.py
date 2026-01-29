"""
TestRouter Engine
Deterministic mapping from Resistance Prophet signals to NextTestAction recommendations.

V1 Catalog:
1. CA125_SERIES (Enable Signal 3)
2. BASELINE_NGS (Enable Signal 1/2 Precision)
3. LIQUID_BIOPSY (Confirm Restoration/Escape)
4. IMAGING_ESCALATE (Locate Escape)
5. TISSUE_HRD (Gold Standard Confirmation)
"""

from typing import List, Dict, Optional, Tuple
from datetime import datetime
from dataclasses import asdict

from .schemas import (
    ResistancePrediction,
    NextTestAction,
    LogicStep
)

class TestRouter:
    """Deterministic engine for ordering tests based on resistance intelligence."""
    
    def route_tests(
        self,
        prediction: ResistancePrediction,
        last_known_test_timeline: Optional[Dict] = None
    ) -> Tuple[List[NextTestAction], List[LogicStep]]:
        """
        Derive test plan from resistance prediction.
        
        Args:
            prediction: The ResistanceProphet output
            last_known_test_timeline: Optional context about recent tests
        
        Returns:
            Tuple of (recommended_tests, logic_steps)
        """
        steps: List[LogicStep] = []
        tests: List[NextTestAction] = []
        
        # Helper logging
        def log(event: str, because: str, severity: str = "INFO", provenance: str = "TestRouter"):
            steps.append(LogicStep(
                ts=datetime.utcnow().isoformat() + "Z",
                severity=severity,
                event=event,
                because=because,
                provenance={"module": provenance}
            ))
        
        log("ROUTER_START", f"Processing risk level: {prediction.risk_level.value}")
        
        # ------------------------------------------------------------------
        # 1. CA-125 KINETICS (Signal 3 Enabler)
        # Trigger: INSUFFICIENT_CA125_DATA warning in prediction
        # ------------------------------------------------------------------
        ca125_warning = next((w for w in prediction.warnings if "CA-125" in w), None)
        
        if ca125_warning:
            log("GAP_DETECTED", f"CA-125 Intelligence Missing: {ca125_warning}", "WARNING")
            
            tests.append(NextTestAction(
                test_id="CA125_SERIES",
                priority="HIGH",
                frequency="WEEKLY",
                duration="x3",
                why="Enable CA-125 kinetics Signal 3 (currently skipped due to insufficient history).",
                enables_signals=["CA125_KINETICS"],
                triggered_by=["INSUFFICIENT_CA125_DATA"],
                expected_effect={"confidence_cap_change": "may remove MEDIUM cap"}
            ))
            log("ORDER_GENERATED", "Ordered CA125_SERIES (Weekly x3)", "INFO")
        
        # ------------------------------------------------------------------
        # 2. BASELINE CAPTURE (Signal 1/2 Precision)
        # Trigger: Baseline Penalty Applied (using population average)
        # ------------------------------------------------------------------
        if prediction.baseline_penalty_applied:
            log("GAP_DETECTED", f"Baseline SAE missing (Source: {prediction.baseline_source}). Penalty applied.", "WARNING")
            
            tests.append(NextTestAction(
                test_id="BASELINE_NGS",
                priority="HIGH",
                frequency="ONCE",
                duration="x1",
                why="Capture patient-specific baseline to remove population-average penalty.",
                enables_signals=["DNA_REPAIR_RESTORATION", "PATHWAY_ESCAPE"],
                triggered_by=["MISSING_BASELINE"],
                expected_effect={"confidence_gap_reduction": "0.20"}
            ))
            log("ORDER_GENERATED", "Ordered BASELINE_NGS (Immediate)", "INFO")

        # ------------------------------------------------------------------
        # 3. LIQUID BIOPSY / ctDNA (Mechanism Hunter)
        # Trigger: Restoration (Signal 1) or Escape (Signal 2) detected
        # ------------------------------------------------------------------
        restoration_signal = next((s for s in prediction.signals_detected 
                                   if s.signal_type == "DNA_REPAIR_RESTORATION" and s.detected), None)
        escape_signal = next((s for s in prediction.signals_detected 
                              if s.signal_type == "PATHWAY_ESCAPE" and s.detected), None)
        
        if restoration_signal or escape_signal:
            signals = []
            triggers = []
            if restoration_signal: 
                signals.append("DNA_REPAIR_RESTORATION")
                triggers.append("RESTORATION_DETECTED")
                log("SIGNAL_ACTION", f"Restoration Signal detected (Prob: {restoration_signal.probability:.2f})", "CRITICAL")
            
            if escape_signal:
                signals.append("PATHWAY_ESCAPE")
                triggers.append("ESCAPE_DETECTED")
                log("SIGNAL_ACTION", f"Escape Signal detected (Prob: {escape_signal.probability:.2f})", "CRITICAL")
            
            tests.append(NextTestAction(
                test_id="LIQUID_BIOPSY",
                priority="IMMEDIATE",
                frequency="ONCE",
                duration="x1",
                why="Confirm specific mechanism of resistance (Reversion or New Mutation).",
                enables_signals=signals,
                triggered_by=triggers,
                expected_effect={"action": "Switch therapy if confirmed"}
            ))
            log("ORDER_GENERATED", "Ordered LIQUID_BIOPSY (Immediate)", "INFO")
            
            # Nuclear Option: Tissue HRD Confirmation
            # Trigger: Very High Probability Restoration
            if restoration_signal and restoration_signal.probability > 0.80:
                log("ESCALATION", "Restoration probability > 80%. Taping Tissue Re-Test.", "CRITICAL")
                tests.append(NextTestAction(
                    test_id="TISSUE_HRD",
                    priority="IMMEDIATE",
                    frequency="ONCE",
                    duration="x1",
                    why="Gold-standard confirmation of phenotypic reversion (Risk > 80%).",
                    enables_signals=["DNA_REPAIR_RESTORATION"],
                    triggered_by=["HIGH_PROB_RESTORATION"],
                    expected_effect={"decision": "Definitive PARP Stop"}
                ))


        # ------------------------------------------------------------------
        # 4. IMAGING ESCALATION (Lesion Hunter)
        # Trigger: High Risk Level
        # ------------------------------------------------------------------
        if prediction.risk_level == "HIGH":
            log("RISK_ACTION", "Risk Level is HIGH. Examining radiographic burden.", "WARNING")
            
            # Check if we already have recent imaging? (Mock check)
            # For V1, we just optimize for safety -> Order Scan.
            tests.append(NextTestAction(
                test_id="IMAGING_ESCALATE",
                priority="IMMEDIATE",
                frequency="ONCE",
                duration="x1",
                why="Locate potential progression or escape lesions given High Resistance Risk.",
                enables_signals=["RADIOGRAPHIC_PROGRESSION"],
                triggered_by=["HIGH_RISK_LEVEL"],
                expected_effect={"action": "RECIST Evaluation"}
            ))
            log("ORDER_GENERATED", "Ordered IMAGING_ESCALATE (Immediate)", "INFO")
            
        
        log("ROUTER_COMPLETE", f"Generated {len(tests)} test orders.")
        
        return tests, steps
