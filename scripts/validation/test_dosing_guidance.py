#!/usr/bin/env python3
"""
Dosing Guidance Validation Script

Tests the complete dosing guidance pipeline:
1. PharmGKB metabolizer status (DPYD, TPMT, UGT1A1)
2. Dosing guidance service
3. Cumulative toxicity detection
4. API endpoint

Run: python scripts/validation/test_dosing_guidance.py
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../'))

from api.routers.pharmgkb import get_metabolizer_status, get_dose_adjustments
from api.services.dosing_guidance_service import DosingGuidanceService, check_cumulative_toxicity
from api.schemas.dosing import DosingGuidanceRequest
import asyncio


def test_pharmgkb_dpyd():
    """Test DPYD metabolizer status and dose adjustments"""
    print("\n=== Test 1: DPYD Poor Metabolizer (*2A/*2A) ===")
    
    # Test Poor Metabolizer
    result = get_metabolizer_status('DPYD', '*2A/*2A')
    assert result['status'] == 'Poor Metabolizer', f"Expected Poor Metabolizer, got {result['status']}"
    assert result['adjustment_factor'] == 0.0, f"Expected adjustment_factor 0.0, got {result['adjustment_factor']}"
    assert result['confidence'] == 0.95, f"Expected confidence 0.95, got {result['confidence']}"
    print(f"✅ DPYD *2A/*2A → {result['status']}, adjustment_factor: {result['adjustment_factor']}")
    
    # Test dose adjustments
    adjustments = get_dose_adjustments('DPYD', 'Poor Metabolizer')
    assert len(adjustments) >= 2, f"Expected at least 2 adjustments, got {len(adjustments)}"
    print(f"✅ Found {len(adjustments)} dose adjustments for DPYD Poor Metabolizer")
    for adj in adjustments:
        print(f"   - {adj['drug']}: {adj['adjustment'][:60]}...")
    
    # Test Intermediate Metabolizer
    result2 = get_metabolizer_status('DPYD', '*1/*2A')
    assert result2['status'] == 'Intermediate Metabolizer', f"Expected Intermediate, got {result2['status']}"
    assert result2['adjustment_factor'] == 0.5, f"Expected adjustment_factor 0.5, got {result2['adjustment_factor']}"
    print(f"✅ DPYD *1/*2A → {result2['status']}, adjustment_factor: {result2['adjustment_factor']}")
    
    return True


def test_pharmgkb_tpmt():
    """Test TPMT metabolizer status and dose adjustments"""
    print("\n=== Test 2: TPMT Poor Metabolizer (*3A/*3A) ===")
    
    result = get_metabolizer_status('TPMT', '*3A/*3A')
    assert result['status'] == 'Poor Metabolizer', f"Expected Poor Metabolizer, got {result['status']}"
    assert result['adjustment_factor'] == 0.1, f"Expected adjustment_factor 0.1, got {result['adjustment_factor']}"
    print(f"✅ TPMT *3A/*3A → {result['status']}, adjustment_factor: {result['adjustment_factor']}")
    
    adjustments = get_dose_adjustments('TPMT', 'Poor Metabolizer')
    assert len(adjustments) >= 2, f"Expected at least 2 adjustments, got {len(adjustments)}"
    print(f"✅ Found {len(adjustments)} dose adjustments for TPMT Poor Metabolizer")
    
    return True


def test_pharmgkb_ugt1a1():
    """Test UGT1A1 metabolizer status and dose adjustments"""
    print("\n=== Test 3: UGT1A1 Poor Metabolizer (*28/*28) ===")
    
    result = get_metabolizer_status('UGT1A1', '*28/*28')
    assert result['status'] == 'Poor Metabolizer', f"Expected Poor Metabolizer, got {result['status']}"
    assert result['adjustment_factor'] == 0.7, f"Expected adjustment_factor 0.7, got {result['adjustment_factor']}"
    print(f"✅ UGT1A1 *28/*28 → {result['status']}, adjustment_factor: {result['adjustment_factor']}")
    
    adjustments = get_dose_adjustments('UGT1A1', 'Poor Metabolizer')
    assert len(adjustments) >= 1, f"Expected at least 1 adjustment, got {len(adjustments)}"
    print(f"✅ Found {len(adjustments)} dose adjustments for UGT1A1 Poor Metabolizer")
    
    return True


def test_cumulative_toxicity():
    """Test cumulative toxicity detection"""
    print("\n=== Test 4: Cumulative Toxicity Detection ===")
    
    # Test anthracycline cumulative toxicity
    result1 = check_cumulative_toxicity('doxorubicin', ['epirubicin'])
    assert result1 is not None, "Expected alert for anthracycline cumulative toxicity"
    assert 'CUMULATIVE TOXICITY ALERT' in result1, "Expected alert message"
    assert 'anthracycline' in result1.lower(), "Expected anthracycline mention"
    print(f"✅ Anthracycline cumulative toxicity detected: {result1[:80]}...")
    
    # Test platinum cumulative toxicity
    result2 = check_cumulative_toxicity('cisplatin', ['carboplatin'])
    assert result2 is not None, "Expected alert for platinum cumulative toxicity"
    assert 'platinum' in result2.lower(), "Expected platinum mention"
    print(f"✅ Platinum cumulative toxicity detected: {result2[:80]}...")
    
    # Test taxane cumulative toxicity
    result3 = check_cumulative_toxicity('paclitaxel', ['docetaxel'])
    assert result3 is not None, "Expected alert for taxane cumulative toxicity"
    assert 'taxane' in result3.lower(), "Expected taxane mention"
    print(f"✅ Taxane cumulative toxicity detected: {result3[:80]}...")
    
    # Test no prior therapy (should return None)
    result4 = check_cumulative_toxicity('cisplatin', [])
    assert result4 is None, "Expected None when no prior therapies"
    print(f"✅ No alert when no prior therapies (correct)")
    
    return True


async def test_dosing_guidance_service():
    """Test the unified dosing guidance service"""
    print("\n=== Test 5: Dosing Guidance Service (DPYD + 5-FU) ===")
    
    service = DosingGuidanceService()
    
    request = DosingGuidanceRequest(
        gene="DPYD",
        variant="*2A/*2A",
        drug="5-fluorouracil",
        standard_dose="1000 mg/m² IV daily x 5 days",
        treatment_line=1,
        prior_therapies=[],
        disease="colorectal cancer"
    )
    
    response = await service.get_dosing_guidance(request)
    
    assert len(response.recommendations) > 0, "Expected at least 1 recommendation"
    assert response.contraindicated == True, "Expected contraindicated=True for DPYD Poor + 5-FU"
    assert response.confidence >= 0.7, f"Expected confidence >= 0.7, got {response.confidence}"
    
    rec = response.recommendations[0]
    assert rec.gene == "DPYD", f"Expected gene DPYD, got {rec.gene}"
    assert rec.drug == "5-fluorouracil", f"Expected drug 5-fluorouracil, got {rec.drug}"
    assert rec.adjustment_type.value == "avoid", f"Expected adjustment_type 'avoid', got {rec.adjustment_type.value}"
    assert rec.adjustment_factor == 0.0, f"Expected adjustment_factor 0.0, got {rec.adjustment_factor}"
    assert len(rec.monitoring) > 0, "Expected monitoring requirements"
    assert len(rec.alternatives) > 0, "Expected alternative drugs"
    
    print(f"✅ Dosing guidance returned:")
    print(f"   - Gene: {rec.gene}")
    print(f"   - Drug: {rec.drug}")
    print(f"   - Phenotype: {rec.phenotype}")
    print(f"   - Adjustment Type: {rec.adjustment_type.value}")
    print(f"   - Adjustment Factor: {rec.adjustment_factor}")
    print(f"   - CPIC Level: {rec.cpic_level}")
    print(f"   - Monitoring: {len(rec.monitoring)} requirements")
    print(f"   - Alternatives: {len(rec.alternatives)} drugs")
    print(f"   - Contraindicated: {response.contraindicated}")
    print(f"   - Confidence: {response.confidence:.2f}")
    
    return True


async def test_dosing_guidance_with_cumulative_toxicity():
    """Test dosing guidance with cumulative toxicity"""
    print("\n=== Test 6: Dosing Guidance with Cumulative Toxicity ===")
    
    service = DosingGuidanceService()
    
    request = DosingGuidanceRequest(
        gene="DPYD",
        variant="*1/*1",  # Normal metabolizer
        drug="doxorubicin",
        standard_dose="60 mg/m² IV every 3 weeks",
        treatment_line=2,
        prior_therapies=["epirubicin"],  # Prior anthracycline
        disease="breast cancer"
    )
    
    response = await service.get_dosing_guidance(request)
    
    assert response.cumulative_toxicity_alert is not None, "Expected cumulative toxicity alert"
    assert 'anthracycline' in response.cumulative_toxicity_alert.lower(), "Expected anthracycline mention"
    
    print(f"✅ Cumulative toxicity alert detected:")
    print(f"   {response.cumulative_toxicity_alert[:100]}...")
    
    return True


async def run_all_tests():
    """Run all validation tests"""
    print("=" * 70)
    print("DOSING GUIDANCE VALIDATION TEST SUITE")
    print("=" * 70)
    
    tests = [
        ("PharmGKB DPYD", test_pharmgkb_dpyd),
        ("PharmGKB TPMT", test_pharmgkb_tpmt),
        ("PharmGKB UGT1A1", test_pharmgkb_ugt1a1),
        ("Cumulative Toxicity", test_cumulative_toxicity),
        ("Dosing Guidance Service", test_dosing_guidance_service),
        ("Dosing Guidance + Cumulative Toxicity", test_dosing_guidance_with_cumulative_toxicity),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            if asyncio.iscoroutinefunction(test_func):
                await test_func()
            else:
                test_func()
            passed += 1
        except AssertionError as e:
            print(f"❌ {test_name} FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"❌ {test_name} ERROR: {e}")
            failed += 1
    
    print("\n" + "=" * 70)
    print("TEST RESULTS")
    print("=" * 70)
    print(f"✅ Passed: {passed}/{len(tests)}")
    print(f"❌ Failed: {failed}/{len(tests)}")
    
    if failed == 0:
        print("\n🎉 ALL TESTS PASSED - Dosing Guidance Implementation Validated!")
        return 0
    else:
        print(f"\n⚠️  {failed} test(s) failed - Review implementation")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(run_all_tests())
    sys.exit(exit_code)



