"""
Comprehensive Validation Test Suite for Sporadic Cancer Gates (Mission 3)

Tests all 25 test scenarios from Agent Jr against Zo's sporadic_gates.py module.
Validates PARP penalties, HRD rescue, IO boosts, and confidence capping.
"""
import pytest
import json
from pathlib import Path
from typing import Dict, Any, List, Tuple
from api.services.efficacy_orchestrator.sporadic_gates import apply_sporadic_gates

# Path to test scenarios directory (from project root)
# Test file is at: oncology-coPilot/oncology-backend-minimal/tests/test_sporadic_gates_full_suite.py
# Project root is 4 levels up
TEST_FILE = Path(__file__).resolve()
PROJECT_ROOT = TEST_FILE.parent.parent.parent.parent
REPO_ROOT = PROJECT_ROOT.parent
TEST_SCENARIOS_DIR = REPO_ROOT / '.cursor' / 'ayesha' / 'test_scenarios'

# Verify path exists
if not TEST_SCENARIOS_DIR.exists():
    raise FileNotFoundError(
        f"Test scenarios directory not found: {TEST_SCENARIOS_DIR}\n"
        f"Test file: {TEST_FILE}\n"
        f"Project root: {PROJECT_ROOT}"
    )

# All 25 test scenario files
ALL_SCENARIOS = [
    "test_case_1_level_0.json",
    "test_case_2_level_1.json",
    "test_case_3_level_2.json",
    "test_case_4_edge_case.json",
    "test_case_5_ayesha.json",
    "test_case_6_prostate_l0.json",
    "test_case_7_prostate_l1.json",
    "test_case_8_melanoma_l0.json",
    "test_case_9_melanoma_l1.json",
    "test_case_10_bladder_l0.json",
    "test_case_11_bladder_l1.json",
    "test_case_12_endometrial_l0.json",
    "test_case_13_endometrial_l1.json",
    "test_case_14_gastric_l0.json",
    "test_case_15_gastric_l1.json",
    "test_case_16_esophageal_l0.json",
    "test_case_17_esophageal_l1.json",
    "test_case_18_headneck_l0.json",
    "test_case_19_headneck_l1.json",
    "test_case_20_glioblastoma_l0.json",
    "test_case_21_glioblastoma_l1.json",
    "test_case_22_renal_l0.json",
    "test_case_23_renal_l1.json",
    "test_case_24_leukemia_l0.json",
    "test_case_25_leukemia_l1.json",
]


def load_scenario(scenario_file: str) -> Dict[str, Any]:
    """Load a test scenario JSON file."""
    scenario_path = TEST_SCENARIOS_DIR / scenario_file
    if not scenario_path.exists():
        pytest.skip(f"Scenario file not found: {scenario_file}")
    
    with open(scenario_path, 'r') as f:
        return json.load(f)


def validate_parp_gates_for_scenario(scenario_file: str) -> Tuple[bool, Dict[str, Any]]:
    """
    Test PARP inhibitor gates for a scenario.
    
    Returns:
        (passed, results_dict) where results_dict contains:
        - scenario_name
        - expected_penalty_factor
        - actual_penalty_factor
        - expected_efficacy
        - actual_efficacy
        - passed
        - error_message (if failed)
    """
    scenario = load_scenario(scenario_file)
    
    # Extract inputs
    patient = scenario["patient"]
    tumor_context = scenario["expected_tumor_context"]
    expected_gates = scenario["expected_gates"]
    expected_confidence = scenario["expected_confidence"]
    
    # Test all PARP scenarios (including HRD rescue cases where penalty_applied=false but factor=1.0)
    # Only skip if this is not a PARP-relevant scenario (but all scenarios should test PARP gates)
    
    # Base efficacy score (using 0.70 as standard)
    base_efficacy = 0.70
    base_confidence = 0.80  # High base to test capping
    
    # Run sporadic gates for PARP inhibitor
    # JSON null already converts to Python None, so we can use tumor_context directly
    actual_efficacy, actual_confidence, rationale = apply_sporadic_gates(
        drug_name="Olaparib",
        drug_class="PARP inhibitor",
        moa="PARP1/2 inhibition",
        efficacy_score=base_efficacy,
        confidence=base_confidence,
        germline_status=patient["germline_status"],
        tumor_context=tumor_context
    )
    
    # Calculate expected efficacy
    expected_penalty_factor = expected_gates["parp_penalty_factor"]
    expected_efficacy = base_efficacy * expected_penalty_factor
    
    # Calculate expected confidence (capped)
    expected_confidence_cap = expected_confidence.get("cap")
    if expected_confidence_cap is not None:
        expected_conf = min(base_confidence, expected_confidence_cap)
    else:
        expected_conf = base_confidence
    
    # Validate
    efficacy_match = abs(actual_efficacy - expected_efficacy) < 0.01
    confidence_match = abs(actual_confidence - expected_conf) < 0.01
    
    passed = efficacy_match and confidence_match
    
    return passed, {
        "scenario_name": scenario["scenario_name"],
        "scenario_file": scenario_file,
        "test_type": "PARP",
        "cancer_type": patient.get("cancer_type", "unknown"),
        "level": tumor_context.get("level", "unknown"),
        "germline_status": patient["germline_status"],
        "hrd_score": tumor_context.get("hrd_score"),
        "base_efficacy": base_efficacy,
        "expected_penalty_factor": expected_penalty_factor,
        "expected_efficacy": expected_efficacy,
        "actual_efficacy": actual_efficacy,
        "efficacy_match": efficacy_match,
        "base_confidence": base_confidence,
        "expected_confidence_cap": expected_confidence_cap,
        "expected_confidence": expected_conf,
        "actual_confidence": actual_confidence,
        "confidence_match": confidence_match,
        "passed": passed,
        "rationale": [r.get("reason", "") for r in rationale if "reason" in r]
    }


def validate_io_boost_for_scenario(scenario_file: str) -> Tuple[bool, Dict[str, Any]]:
    """
    Test IO boost gates for a scenario.
    
    Returns:
        (passed, results_dict)
    """
    scenario = load_scenario(scenario_file)
    
    # Extract inputs
    patient = scenario["patient"]
    tumor_context = scenario["expected_tumor_context"]
    expected_gates = scenario["expected_gates"]
    expected_confidence = scenario["expected_confidence"]
    
    # Skip if IO boost not expected
    if not expected_gates.get("io_boost_applied", False):
        return True, {
            "scenario_name": scenario["scenario_name"],
            "test_type": "IO",
            "skipped": True,
            "reason": "IO boost not expected for this scenario"
        }
    
    # Base efficacy score
    base_efficacy = 0.60
    base_confidence = 0.80
    
    # Run sporadic gates for checkpoint inhibitor
    # JSON null already converts to Python None, so we can use tumor_context directly
    actual_efficacy, actual_confidence, rationale = apply_sporadic_gates(
        drug_name="Pembrolizumab",
        drug_class="checkpoint_inhibitor",
        moa="PD-1 inhibition",
        efficacy_score=base_efficacy,
        confidence=base_confidence,
        germline_status=patient["germline_status"],
        tumor_context=tumor_context
    )
    
    # Calculate expected efficacy
    expected_boost_factor = expected_gates["io_boost_factor"]
    expected_efficacy = base_efficacy * expected_boost_factor
    # Clamp to [0, 1]
    expected_efficacy = min(1.0, max(0.0, expected_efficacy))
    
    # Calculate expected confidence (capped)
    expected_confidence_cap = expected_confidence.get("cap")
    if expected_confidence_cap is not None:
        expected_conf = min(base_confidence, expected_confidence_cap)
    else:
        expected_conf = base_confidence
    
    # Validate
    efficacy_match = abs(actual_efficacy - expected_efficacy) < 0.01
    confidence_match = abs(actual_confidence - expected_conf) < 0.01
    
    passed = efficacy_match and confidence_match
    
    return passed, {
        "scenario_name": scenario["scenario_name"],
        "scenario_file": scenario_file,
        "test_type": "IO",
        "cancer_type": patient.get("cancer_type", "unknown"),
        "level": tumor_context.get("level", "unknown"),
        "tmb": tumor_context.get("tmb"),
        "msi_status": tumor_context.get("msi_status"),
        "base_efficacy": base_efficacy,
        "expected_boost_factor": expected_boost_factor,
        "expected_efficacy": expected_efficacy,
        "actual_efficacy": actual_efficacy,
        "efficacy_match": efficacy_match,
        "base_confidence": base_confidence,
        "expected_confidence_cap": expected_confidence_cap,
        "expected_confidence": expected_conf,
        "actual_confidence": actual_confidence,
        "confidence_match": confidence_match,
        "passed": passed,
        "rationale": [r.get("reason", "") for r in rationale if "reason" in r]
    }


def validate_confidence_cap_for_scenario(scenario_file: str) -> Tuple[bool, Dict[str, Any]]:
    """
    Test confidence capping for a scenario (using a non-PARP, non-IO drug).
    
    Returns:
        (passed, results_dict)
    """
    scenario = load_scenario(scenario_file)
    
    # Extract inputs
    patient = scenario["patient"]
    tumor_context = scenario["expected_tumor_context"]
    expected_confidence = scenario["expected_confidence"]
    
    # Base efficacy and confidence
    base_efficacy = 0.75
    base_confidence = 0.85  # High base to test capping
    
    # Run sporadic gates for a standard drug (not PARP, not IO)
    # JSON null already converts to Python None, so we can use tumor_context directly
    actual_efficacy, actual_confidence, rationale = apply_sporadic_gates(
        drug_name="Carboplatin",
        drug_class="platinum",
        moa="DNA crosslinking",
        efficacy_score=base_efficacy,
        confidence=base_confidence,
        germline_status=patient["germline_status"],
        tumor_context=tumor_context
    )
    
    # Calculate expected confidence (capped)
    expected_confidence_cap = expected_confidence.get("cap")
    if expected_confidence_cap is not None:
        expected_conf = min(base_confidence, expected_confidence_cap)
    else:
        expected_conf = base_confidence
    
    # Validate
    confidence_match = abs(actual_confidence - expected_conf) < 0.01
    efficacy_unchanged = abs(actual_efficacy - base_efficacy) < 0.01  # Should not change for non-PARP, non-IO
    
    passed = confidence_match and efficacy_unchanged
    
    return passed, {
        "scenario_name": scenario["scenario_name"],
        "scenario_file": scenario_file,
        "test_type": "CONFIDENCE",
        "cancer_type": patient.get("cancer_type", "unknown"),
        "level": tumor_context.get("level", "unknown"),
        "completeness_score": tumor_context.get("completeness_score"),
        "base_confidence": base_confidence,
        "expected_confidence_cap": expected_confidence_cap,
        "expected_confidence": expected_conf,
        "actual_confidence": actual_confidence,
        "confidence_match": confidence_match,
        "base_efficacy": base_efficacy,
        "actual_efficacy": actual_efficacy,
        "efficacy_unchanged": efficacy_unchanged,
        "passed": passed,
        "rationale": [r.get("reason", "") for r in rationale if "reason" in r]
    }


# Parametrized tests for all scenarios
@pytest.mark.parametrize("scenario_file", ALL_SCENARIOS)
def test_parp_gates(scenario_file: str):
    """Test PARP gates for each scenario."""
    passed, results = validate_parp_gates_for_scenario(scenario_file)
    
    if results.get("skipped"):
        pytest.skip(results["reason"])
    
    assert passed, (
        f"PARP gates failed for {results['scenario_name']}:\n"
        f"  Expected efficacy: {results['expected_efficacy']:.3f}, Actual: {results['actual_efficacy']:.3f}\n"
        f"  Expected confidence: {results['expected_confidence']:.3f}, Actual: {results['actual_confidence']:.3f}\n"
        f"  Rationale: {results.get('rationale', [])}"
    )


@pytest.mark.parametrize("scenario_file", ALL_SCENARIOS)
def test_io_boost(scenario_file: str):
    """Test IO boost gates for each scenario."""
    passed, results = validate_io_boost_for_scenario(scenario_file)
    
    if results.get("skipped"):
        pytest.skip(results["reason"])
    
    assert passed, (
        f"IO boost failed for {results['scenario_name']}:\n"
        f"  Expected efficacy: {results['expected_efficacy']:.3f}, Actual: {results['actual_efficacy']:.3f}\n"
        f"  Expected confidence: {results['expected_confidence']:.3f}, Actual: {results['actual_confidence']:.3f}\n"
        f"  Rationale: {results.get('rationale', [])}"
    )


@pytest.mark.parametrize("scenario_file", ALL_SCENARIOS)
def test_confidence_cap(scenario_file: str):
    """Test confidence capping for each scenario."""
    passed, results = validate_confidence_cap_for_scenario(scenario_file)
    
    assert passed, (
        f"Confidence cap failed for {results['scenario_name']}:\n"
        f"  Expected confidence: {results['expected_confidence']:.3f}, Actual: {results['actual_confidence']:.3f}\n"
        f"  Expected cap: {results['expected_confidence_cap']}\n"
        f"  Rationale: {results.get('rationale', [])}"
    )


# Main execution function to generate results summary
def run_full_validation() -> Dict[str, Any]:
    """
    Run full validation suite and return results summary.
    
    Returns:
        Dictionary with:
        - total_scenarios: int
        - parp_tests: List[Dict]
        - io_tests: List[Dict]
        - confidence_tests: List[Dict]
        - summary: Dict with pass/fail counts
    """
    all_parp_results = []
    all_io_results = []
    all_confidence_results = []
    
    for scenario_file in ALL_SCENARIOS:
        # Test PARP gates
        parp_passed, parp_results = validate_parp_gates_for_scenario(scenario_file)
        all_parp_results.append(parp_results)
        
        # Test IO boost
        io_passed, io_results = validate_io_boost_for_scenario(scenario_file)
        all_io_results.append(io_results)
        
        # Test confidence cap
        conf_passed, conf_results = validate_confidence_cap_for_scenario(scenario_file)
        all_confidence_results.append(conf_results)
    
    # Calculate summary
    parp_passed = sum(1 for r in all_parp_results if r.get("passed", False) or r.get("skipped", False))
    io_passed = sum(1 for r in all_io_results if r.get("passed", False) or r.get("skipped", False))
    conf_passed = sum(1 for r in all_confidence_results if r.get("passed", False))
    
    return {
        "total_scenarios": len(ALL_SCENARIOS),
        "parp_tests": all_parp_results,
        "io_tests": all_io_results,
        "confidence_tests": all_confidence_results,
        "summary": {
            "parp_passed": parp_passed,
            "parp_total": len(all_parp_results),
            "io_passed": io_passed,
            "io_total": len(all_io_results),
            "confidence_passed": conf_passed,
            "confidence_total": len(all_confidence_results)
        }
    }


if __name__ == "__main__":
    print("\n⚔️ RUNNING FULL VALIDATION SUITE - 25 TEST SCENARIOS ⚔️\n")
    
    results = run_full_validation()
    
    print(f"Total Scenarios: {results['total_scenarios']}")
    print(f"PARP Tests: {results['summary']['parp_passed']}/{results['summary']['parp_total']} passed")
    print(f"IO Tests: {results['summary']['io_passed']}/{results['summary']['io_total']} passed")
    print(f"Confidence Tests: {results['summary']['confidence_passed']}/{results['summary']['confidence_total']} passed")
    
    print("\n⚔️ VALIDATION COMPLETE! ⚔️\n")

