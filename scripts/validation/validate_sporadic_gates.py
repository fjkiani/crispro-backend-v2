#!/usr/bin/env python3
"""
Validate Sporadic Gates - Production Validation Script

Source of Truth: .cursor/MOAT/SPORADIC_CANCER_PRODUCTION_PLAN.md
Task: Phase 1.1 - Run Sporadic Gates Unit Tests

Validates:
- PARP penalty (germline negative + HRD < 42)
- HRD rescue (HRD ≥ 42)
- TMB boost (TMB ≥ 20)
- MSI boost (MSI-High)
- Confidence caps (L0 → 0.4, L1 → 0.6, L2 → no cap)
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from api.services.efficacy_orchestrator.sporadic_gates import apply_sporadic_gates


def test_parp_penalty():
    """Test PARP penalty when germline negative + HRD < 42"""
    efficacy, confidence, rationale = apply_sporadic_gates(
        drug_name="Olaparib",
        drug_class="PARP inhibitor",
        moa="PARP1/2 inhibition",
        efficacy_score=0.70,
        confidence=0.65,
        germline_status="negative",
        tumor_context={"hrd_score": 25.0, "completeness_score": 0.5}
    )
    assert abs(efficacy - 0.42) < 0.02, f"PARP penalty failed: {efficacy} (expected ~0.42)"
    assert confidence <= 0.6, f"L1 confidence cap failed: {confidence} (expected <= 0.6)"
    print("✅ PARP penalty: PASS (0.70 → 0.42, 0.6x penalty)")
    return True


def test_hrd_rescue():
    """Test HRD rescue when HRD ≥ 42"""
    efficacy, confidence, rationale = apply_sporadic_gates(
        drug_name="Olaparib",
        drug_class="PARP inhibitor",
        moa="PARP1/2 inhibition",
        efficacy_score=0.70,
        confidence=0.65,
        germline_status="negative",
        tumor_context={"hrd_score": 50.0, "completeness_score": 0.5}
    )
    assert abs(efficacy - 0.70) < 0.02, f"HRD rescue failed: {efficacy} (expected ~0.70)"
    print("✅ HRD rescue: PASS (0.70 → 0.70, no penalty)")
    return True


def test_tmb_boost():
    """Test TMB boost when TMB ≥ 20"""
    efficacy, confidence, rationale = apply_sporadic_gates(
        drug_name="Pembrolizumab",
        drug_class="checkpoint_inhibitor",
        moa="PD-1 inhibition",
        efficacy_score=0.60,
        confidence=0.70,
        germline_status="negative",
        tumor_context={"tmb": 25.0, "msi_status": "MSI-Stable", "completeness_score": 0.9}
    )
    assert efficacy >= 0.70, f"TMB boost failed: {efficacy} (expected >= 0.70)"
    print(f"✅ TMB boost: PASS (0.60 → {efficacy:.2f}, 1.3x+ boost)")
    return True


def test_msi_boost():
    """Test MSI boost when MSI-High"""
    efficacy, confidence, rationale = apply_sporadic_gates(
        drug_name="Nivolumab",
        drug_class="checkpoint_inhibitor",
        moa="PD-1 inhibition",
        efficacy_score=0.60,
        confidence=0.70,
        germline_status="negative",
        tumor_context={"tmb": 5.0, "msi_status": "MSI-High", "completeness_score": 0.9}
    )
    assert efficacy >= 0.70, f"MSI boost failed: {efficacy} (expected >= 0.70)"
    print(f"✅ MSI boost: PASS (0.60 → {efficacy:.2f}, 1.3x+ boost)")
    return True


def test_tmb_msi_double_boost():
    """Test boost when TMB ≥ 20 AND MSI-High (TMB takes precedence per if-elif l""
    efficacy, confidence, rationale = apply_sporadic_gates(
        drug_name="Pembrolizumab",
        drug_class="checkpoint_inhibitor",
        moa="PD-1 inhibition",
        efficacy_score=0.60,
        confidence=0.70,
        germline_status="negative",
        tumor_context={"tmb": 25.0, "msi_status": "MSI-High", "completeness_score": 0.9}
    )
    # Code uses if-elif chain: TMB ≥20 (1.35x) takes precedence over MSI-High (1.30x)
    # Expected: 0.60 * 1.35 = 0.81
    assert abs(efficacy - 0.81) < 0.02, f"TMB boost failed: {efficacy} (expected ~0.81, TMB takes precedence)"
    print(f"✅ TMB+MSI (TMB precedence): PASS (0.60 → {efficacy:.2f}, 1.35x TMB boost applied)")
    return True


def test_confidence_caps():
    """Test confidence caps by completeness level"""
    # L0 cap (completeness < 0.3)
    _, conf_l0, _ = apply_sporadic_gates(
        drug_name="Test",
        drug_class="other",
        moa="test",
        efficacy_score=0.80,
        confidence=0.90,
        germline_status="negative",
        tumor_context={"completeness_score": 0.2}  # L0
    )
    assert conf_l0 <= 0.4, f"L0 cap failed: {conf_l0} (expected <= 0.4)"
    
    # L1 cap (0.3 ≤ completeness < 0.7)
    _, conf_l1, _ = apply_sporadic_gates(
        drug_name="Test",
        drug_class="other",
        moa="test",
        efficacy_score=0.80,
        confidence=0.90,
        germline_status="negative",
        tumor_context={"completeness_score": 0.5}  # L1
    )
    assert conf_l1 <= 0.6, f"L1 cap failed: {conf_l1} (expected <= 0.6)"
    
    # L2 no cap (completeness ≥ 0.7)
    _, conf_l2, _ = apply_sporadic_gates(
        drug_name="Test",
        drug_class="other",
        moa="test",
        efficacy_score=0.80,
        confidence=0.90,
        germline_status="negative",
        tumor_context={"completeness_score": 0.9}  # L2
    )
    assert conf_l2 >= 0.85, f"L2 no cap failed: {conf_l2} (expected >= 0.85)"
    
    print(f"✅ Confidence caps: PASS (L0={conf_l0:.2f}, L1={conf_l1:.2f}, L2={conf_l2:.2f})")
    return True


def main():
    """Run all validation tests"""
    print("=" * 60)
    print("SPORADIC GATES VALIDATION")
    print("=" * 60)
    print()
    
    tests = [
        test_parp_penalty,
        test_hrd_rescue,
        test_tmb_boost,
        test_msi_boost,
        test_tmb_msi_double_boost,
        test_confidence_caps
    ]
    
    passed = 0
    failed = []
    
    for test in tests:
        try:
            if test():
                passed += 1
        except AssertionError as e:
            print(f"❌ {test.__name__}: FAIL - {e}")
            failed.append(test.__name__)
        except Exception as e:
            print(f"❌ {test.__name__}: ERROR - {e}")
            failed.append(test.__name__)
    
    print()
    print("=" * 60)
    print(f"RESULTS: {passed}/{len(tests)} tests passed")
    if failed:
        print(f"FAILED: {', '.join(failed)}")
    print("=" * 60)
    
    # Save report
    report_dir = Path(project_root) / "scripts" / "validation" / "out" / "sporadic_gates"
    report_dir.mkdir(parents=True, exist_ok=True)
    
    import json
    from datetime import datetime
    
    report = {
        "timestamp": datetime.now().isoformat(),
        "total_tests": len(tests),
        "passed": passed,
        "failed": len(failed),
        "failed_tests": failed,
        "status": "PASS" if passed == len(tests) else "FAIL"
    }
    
    with open(report_dir / "report.json", "w") as f:
        json.dump(report, f, indent=2)
    
    print(f"\nReport saved to: {report_dir / 'report.json'}")
    
    return 0 if passed == len(tests) else 1


if __name__ == "__main__":
    sys.exit(main())







