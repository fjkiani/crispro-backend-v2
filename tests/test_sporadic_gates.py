"""
Test Sporadic Cancer Scoring Gates (Day 2 - Module M3)

Tests PARP penalty, HRD rescue, IO boosts, and confidence capping
using Agent Jr's test scenarios.
"""
import pytest
from api.services.efficacy_orchestrator.sporadic_gates import apply_sporadic_gates


def test_parp_penalty_germline_negative():
    """Test Case 2 (L1): PARP inhibitor with germline-negative should get penalty"""
    efficacy_score, confidence, rationale = apply_sporadic_gates(
        drug_name="Olaparib",
        drug_class="PARP inhibitor",
        moa="PARP1/2 inhibition",
        efficacy_score=0.70,
        confidence=0.65,
        germline_status="negative",
        tumor_context={"hrd_score": 25.0, "completeness_score": 0.5}  # Below HRD threshold (42), Level 1
    )
    
    # Expected: 0.6x penalty, confidence capped at 0.6 (Level 1)
    assert efficacy_score == pytest.approx(0.42, abs=0.01), f"Expected 0.42 (0.70 * 0.6), got {efficacy_score}"
    assert confidence == pytest.approx(0.6, abs=0.01), f"Expected 0.6 (capped at L1), got {confidence}"
    assert any("PARP" in r.get("gate", "") for r in rationale), "Should have PARP gate"
    assert any("Germline negative" in r.get("reason", "") for r in rationale), "Should mention germline negative"
    print(f"✅ PARP penalty test passed: {efficacy_score:.2f} (0.70 → 0.42), confidence={confidence:.2f}")


def test_hrd_rescue_parp():
    """Test Case 2 (L1): HRD ≥42 should rescue PARP penalty"""
    efficacy_score, confidence, rationale = apply_sporadic_gates(
        drug_name="Olaparib",
        drug_class="PARP inhibitor",
        moa="PARP1/2 inhibition",
        efficacy_score=0.70,
        confidence=0.65,
        germline_status="negative",
        tumor_context={"hrd_score": 50.0, "completeness_score": 0.5}  # Above HRD threshold (42), Level 1
    )
    
    # Expected: No penalty due to HRD rescue, confidence capped at 0.6 (Level 1)
    assert efficacy_score == pytest.approx(0.70, abs=0.01), f"Expected 0.70 (no penalty), got {efficacy_score}"
    assert confidence == pytest.approx(0.6, abs=0.01), f"Expected 0.6 (capped at L1), got {confidence}"
    assert any("RESCUE" in r.get("gate", "") for r in rationale), "Should have HRD rescue gate"
    assert any("50" in r.get("reason", "") for r in rationale), "Should mention HRD score 50"
    print(f"✅ HRD rescue test passed: {efficacy_score:.2f} (0.70 → 0.70, no penalty), confidence={confidence:.2f}")


def test_tmb_high_boost():
    """Test Case 3 (L2): TMB ≥20 should boost checkpoint inhibitors"""
    efficacy_score, confidence, rationale = apply_sporadic_gates(
        drug_name="Pembrolizumab",
        drug_class="checkpoint_inhibitor",
        moa="PD-1 inhibition",
        efficacy_score=0.60,
        confidence=0.70,
        germline_status="negative",
        tumor_context={"tmb": 25.0, "msi_status": "MSI-Stable", "completeness_score": 0.9}  # TMB ≥20, Level 2
    )
    
    # Expected: 1.3x boost for TMB-high
    assert efficacy_score == pytest.approx(0.78, abs=0.01), f"Expected 0.78 (0.60 * 1.3), got {efficacy_score}"
    assert confidence == pytest.approx(0.70, abs=0.01), "Confidence should not change"
    assert any("TMB" in r.get("gate", "") for r in rationale), "Should have TMB boost gate"
    assert any("25" in r.get("reason", "") for r in rationale), "Should mention TMB score 25"
    print(f"✅ TMB boost test passed: {efficacy_score:.2f} (0.60 → 0.78)")


def test_msi_high_boost():
    """Test Case 3 (L2): MSI-High should boost checkpoint inhibitors"""
    efficacy_score, confidence, rationale = apply_sporadic_gates(
        drug_name="Nivolumab",
        drug_class="checkpoint_inhibitor",
        moa="PD-1 inhibition",
        efficacy_score=0.60,
        confidence=0.70,
        germline_status="negative",
        tumor_context={"tmb": 5.0, "msi_status": "MSI-High", "completeness_score": 0.9}  # MSI-High, Level 2
    )
    
    # Expected: 1.3x boost for MSI-High
    assert efficacy_score == pytest.approx(0.78, abs=0.01), f"Expected 0.78 (0.60 * 1.3), got {efficacy_score}"
    assert confidence == pytest.approx(0.70, abs=0.01), "Confidence should not change"
    assert any("MSI" in r.get("gate", "") for r in rationale), "Should have MSI boost gate"
    assert any("MSI-High" in r.get("reason", "") for r in rationale), "Should mention MSI-High"
    print(f"✅ MSI boost test passed: {efficacy_score:.2f} (0.60 → 0.78)")


def test_tmb_msi_double_boost():
    """Test Case 3 (L2): TMB-high + MSI-High should get 1.5x boost"""
    efficacy_score, confidence, rationale = apply_sporadic_gates(
        drug_name="Pembrolizumab",
        drug_class="checkpoint_inhibitor",
        moa="PD-1 inhibition",
        efficacy_score=0.60,
        confidence=0.70,
        germline_status="negative",
        tumor_context={"tmb": 25.0, "msi_status": "MSI-High", "completeness_score": 0.9}  # Both! Level 2
    )
    
    # Expected: 1.69x boost (1.3 * 1.3) for both, BUT clamped at 1.0
    # Calculation: 0.60 * 1.3 * 1.3 = 1.014 → clamped to 1.0
    assert efficacy_score == pytest.approx(1.0, abs=0.01), f"Expected 1.0 (clamped from 1.014), got {efficacy_score}"
    assert confidence == pytest.approx(0.70, abs=0.01), "Confidence should not change"
    assert any("TMB" in r.get("gate", "") or "MSI" in r.get("gate", "") for r in rationale), "Should have IO boost gates"
    assert any("25" in r.get("reason", "") for r in rationale) or any("MSI-High" in r.get("reason", "") for r in rationale), "Should mention biomarkers"
    print(f"✅ Double boost test passed: {efficacy_score:.2f} (0.60 → 1.0, clamped)")


def test_confidence_cap_level0():
    """Test Case 1 (L0): Minimal data should cap confidence at 0.4"""
    efficacy_score, confidence, rationale = apply_sporadic_gates(
        drug_name="Carboplatin",
        drug_class="platinum",
        moa="DNA crosslinking",
        efficacy_score=0.75,
        confidence=0.80,  # High confidence input
        germline_status="unknown",
        tumor_context={"completeness_score": 0.2}  # Level 0 (< 0.3)
    )
    
    # Expected: Confidence capped at 0.4
    assert efficacy_score == pytest.approx(0.75, abs=0.01), "Efficacy should not change"
    assert confidence == pytest.approx(0.4, abs=0.01), f"Expected 0.4 (capped from 0.80), got {confidence}"
    assert any("CONFIDENCE_CAP" in r.get("gate", "") for r in rationale), "Should have confidence cap gate"
    assert any("0.2" in r.get("reason", "") for r in rationale), "Should mention completeness 0.2"
    print(f"✅ Level 0 confidence cap test passed: {confidence:.2f} (0.80 → 0.40)")


def test_confidence_cap_level1():
    """Test Case 2 (L1): Partial data should cap confidence at 0.6"""
    efficacy_score, confidence, rationale = apply_sporadic_gates(
        drug_name="Olaparib",
        drug_class="PARP inhibitor",
        moa="PARP1/2 inhibition",
        efficacy_score=0.70,
        confidence=0.80,  # High confidence input
        germline_status="negative",
        tumor_context={"completeness_score": 0.5, "hrd_score": 50.0}  # Level 1 (0.3-0.7)
    )
    
    # Expected: Confidence capped at 0.6
    assert confidence == pytest.approx(0.6, abs=0.01), f"Expected 0.6 (capped from 0.80), got {confidence}"
    assert any("CONFIDENCE_CAP" in r.get("gate", "") for r in rationale), "Should have confidence cap gate"
    assert any("0.5" in r.get("reason", "") for r in rationale), "Should mention completeness 0.5"
    print(f"✅ Level 1 confidence cap test passed: {confidence:.2f} (0.80 → 0.60)")


def test_no_confidence_cap_level2():
    """Test Case 3 (L2): Full NGS should NOT cap confidence"""
    efficacy_score, confidence, rationale = apply_sporadic_gates(
        drug_name="Pembrolizumab",
        drug_class="checkpoint_inhibitor",
        moa="PD-1 inhibition",
        efficacy_score=0.80,
        confidence=0.85,
        germline_status="negative",
        tumor_context={"completeness_score": 0.9, "tmb": 25.0, "msi_status": "MSI-High"}  # Level 2 (≥ 0.7)
    )
    
    # Expected: Confidence NOT capped, but note IO boosts were applied
    # Efficacy: 0.80 * 1.3 (TMB) * 1.3 (MSI) = 1.352 → clamped to 1.0
    assert efficacy_score == pytest.approx(1.0, abs=0.01), f"Expected 1.0 (clamped), got {efficacy_score}"
    assert confidence == pytest.approx(0.85, abs=0.01), f"Expected 0.85 (no cap), got {confidence}"
    assert not any("CAP_L2" in r.get("gate", "") for r in rationale), "Should not cap Level 2 confidence"
    print(f"✅ Level 2 (no cap) test passed: confidence={confidence:.2f} (0.85 → 0.85, no cap)")


if __name__ == "__main__":
    print("\n⚔️ RUNNING SPORADIC GATES TESTS (DAY 2 - MODULE M3) ⚔️\n")
    
    # Run all tests
    test_parp_penalty_germline_negative()
    test_hrd_rescue_parp()
    test_tmb_high_boost()
    test_msi_high_boost()
    test_tmb_msi_double_boost()
    test_confidence_cap_level0()
    test_confidence_cap_level1()
    test_no_confidence_cap_level2()
    
    print("\n⚔️ ALL SPORADIC GATES TESTS PASSED! DAY 2 COMPLETE! ⚔️\n")

