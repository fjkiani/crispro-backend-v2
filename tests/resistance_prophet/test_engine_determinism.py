"""
Test Suite: Resistance Prophet Engine Determinism
Phase 7 Validation: Ensures pure logic mapper invariants hold across edge cases.
"""

import pytest
from api.services.resistance_prophet.engine import calculate_resistance_prediction
from api.services.resistance_prophet.schemas import (
    ResistanceSignalData, ResistanceSignal, ResistanceRiskLevel
)
from api.services.resistance_prophet.constants import HIGH_RISK_PROBABILITY

# --- Fixtures ---

@pytest.fixture
def signal_restoration_detected():
    return ResistanceSignalData(
        signal_type=ResistanceSignal.DNA_REPAIR_RESTORATION,
        detected=True, probability=0.95, confidence=0.85, 
        rationale="Delta > Threshold", provenance={"delta": 0.4}
    )

@pytest.fixture
def signal_genomic_driver():
    return ResistanceSignalData(
        signal_type=ResistanceSignal.GENE_LEVEL_RESISTANCE,
        detected=True, probability=0.30, confidence=0.0,
        rationale="Genomic Driver Detected", 
        provenance={
            "resistance_genes": [{"gene": "CCNE1", "variant": "Amp", "mechanism": "Replication Stress"}]
        }
    )

@pytest.fixture
def signal_genomic_driver_only():
    """Genomic driver alone usually doesn't trigger HIGH probability in V2 logic unless weighted heavily."""
    return ResistanceSignalData(
        signal_type=ResistanceSignal.GENE_LEVEL_RESISTANCE,
        detected=True, probability=0.55, confidence=0.9,
        rationale="Driver Detected", 
        provenance={
             "resistance_genes": [{"gene": "CCNE1", "variant": "Amp"}]
        }
    )

@pytest.fixture
def treatment_history():
    return [{"drug": "Carbo/Taxol"}]

# --- Tests ---

def test_invariant_orthogonality_071_case(signal_genomic_driver_only, treatment_history):
    """
    Case: '0.71 + 1 signal source'.
    Probability >= 0.70 (simulated via fixture override if needed) but only 1 signal.
    Expected: Risk MEDIUM, but Driver Alert populated.
    """
    # Force probability to 0.71 by mocking aggregation or providing enough signal weight
    # Or just constructing signals such that prob comes out high.
    # In V2 aggregation, 1 signal usually limits confidence unless very strong.
    # Let's pass a signal with prob=0.75 manually.
    signal_genomic_driver_only.probability = 0.75 
    
    signals = [signal_genomic_driver_only]
    
    pred = calculate_resistance_prediction(
        signals=signals,
        treatment_history=treatment_history,
        baseline_source="patient",
        baseline_penalty=False
    )
    
    # Assertions
    assert pred.risk_level == ResistanceRiskLevel.MEDIUM, "Risk should be MEDIUM (only 1 signal)"
    assert len(pred.driver_alerts) == 1, "Driver alert should be present"
    assert pred.driver_alerts[0].gene == "CCNE1"
    
def test_invariant_safety_cap_no_ca125(signal_restoration_detected, treatment_history):
    """
    Case: '2 signals but no CA-125'.
    Risk would be HIGH, but capped to MEDIUM.
    """
    # 2 strong signals
    sig1 = signal_restoration_detected
    sig2 = ResistanceSignalData(
        signal_type=ResistanceSignal.PATHWAY_ESCAPE,
        detected=True, probability=0.80, confidence=0.80,
        rationale="Escape", provenance={}
    )
    
    pred = calculate_resistance_prediction(
        signals=[sig1, sig2],
        treatment_history=treatment_history,
        baseline_source="patient",
        baseline_penalty=False,
        full_ca125_history_available=False # Missing Data -> Trigger Cap
    )
    
    assert pred.risk_level == ResistanceRiskLevel.MEDIUM, "Risk should be capped to MEDIUM"
    assert pred.confidence_cap == "MEDIUM"
    assert "Risk capped" in str(pred.warnings)

def test_invariant_baseline_penalty(treatment_history):
    """
    Case: Baseline missing -> penalty applied.
    """
    pred = calculate_resistance_prediction(
        signals=[],
        treatment_history=treatment_history,
        baseline_source="population_average",
        baseline_penalty=True
    )
    
    assert pred.baseline_penalty_applied is True
    assert pred.baseline_source == "population_average"

def test_invariant_driver_alert_preservation(signal_genomic_driver, treatment_history):
    """
    Case: Risk Low/Medium, but Driver Alert persists.
    """
    signal_genomic_driver.probability = 0.20 # Low prob
    
    pred = calculate_resistance_prediction(
        signals=[signal_genomic_driver],
        treatment_history=treatment_history,
        baseline_source="patient",
        baseline_penalty=False
    )
    
    assert pred.risk_level == ResistanceRiskLevel.LOW
    assert len(pred.driver_alerts) == 1
    assert pred.driver_alerts[0].gene == "CCNE1"

def test_contract_snapshot_deployment_ready(treatment_history):
    """
    Final Contract Snapshot verify:
    1. Thresholds: 0.70 high, 0.50 medium.
    2. High Risk requires 2 signals (clinical-relevant count).
    3. Missing CA-125 triggers Cap to MEDIUM.
    4. Provenance contains explicit probability components.
    """
    # Setup: 2 Strong Clinical Signals (Each Prob 0.8 -> Avg 0.8)
    sig1 = ResistanceSignalData(
        signal_type=ResistanceSignal.DNA_REPAIR_RESTORATION,
        detected=True, probability=0.80, confidence=1.0, 
        rationale="Strong Restoration", provenance={}
    )
    sig2 = ResistanceSignalData(
        signal_type=ResistanceSignal.PATHWAY_ESCAPE,
        detected=True, probability=0.80, confidence=1.0,
        rationale="Strong Escape", provenance={}
    )
    
    # CASE 1: Full Data (CA-125 available) -> HIGH Risk
    pred_full = calculate_resistance_prediction(
        signals=[sig1, sig2],
        treatment_history=treatment_history,
        baseline_source="patient",
        baseline_penalty=False,
        full_ca125_history_available=True 
    )
    
    assert pred_full.risk_level == ResistanceRiskLevel.HIGH
    assert pred_full.probability >= 0.70
    assert pred_full.provenance["probability_components"]["blended"] >= 0.70
    assert pred_full.confidence_cap is None
    
    # CASE 2: Missing CA-125 -> CAPPED to MEDIUM
    pred_missing_ca125 = calculate_resistance_prediction(
        signals=[sig1, sig2],
        treatment_history=treatment_history,
        baseline_source="patient",
        baseline_penalty=False,
        full_ca125_history_available=False
    )
    
    assert pred_missing_ca125.risk_level == ResistanceRiskLevel.MEDIUM
    assert pred_missing_ca125.probability >= 0.70 # Prob is high...
    assert pred_missing_ca125.risk_level != ResistanceRiskLevel.HIGH # But Risk Capped
    assert pred_missing_ca125.confidence_cap == "MEDIUM"

    # CASE 3: Medium Threshold Check (1 Signal, Prob 0.55)
    sig_med = ResistanceSignalData(
        signal_type=ResistanceSignal.DNA_REPAIR_RESTORATION,
        detected=True, probability=0.55, confidence=1.0,
        rationale="Mid Restoration", provenance={}
    )
    pred_med = calculate_resistance_prediction(
        signals=[sig_med],
        treatment_history=treatment_history,
        baseline_source="patient",
        baseline_penalty=False
    )
    assert pred_med.risk_level == ResistanceRiskLevel.MEDIUM
    assert pred_med.probability >= 0.50

