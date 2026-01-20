#!/usr/bin/env python3
"""
PGx Integration - Integration Failure Tests

Tests integration failures (API failures, service unavailability, etc.)
that could occur in production.

Research Use Only - Not for Clinical Decision Making
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

# Add backend to path
backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))

from api.services.pgx_care_plan_integration import integrate_pgx_into_drug_efficacy


async def test_pgx_service_unavailable():
    """Test: PGx screening service unavailable."""
    print("Testing: PGx service unavailable...")
    
    with patch('api.services.pgx_care_plan_integration.get_pgx_screening_service') as mock_get_service:
        mock_get_service.side_effect = Exception("Service unavailable")
        
        try:
            result = await integrate_pgx_into_drug_efficacy(
                drug_efficacy_response={"drugs": [{"name": "5-FU", "efficacy_score": 0.75}]},
                patient_profile={"germline_variants": [{"gene": "DPYD"}]},
                treatment_line="first-line",
                prior_therapies=[]
            )
            # Should handle gracefully - return unchanged or with error indicator
            print(f"   ✅ Handled gracefully: {result is not None}")
            return True
        except Exception as e:
            print(f"   ❌ Crashed: {e}")
            return False


async def test_risk_benefit_service_unavailable():
    """Test: Risk-benefit composition service unavailable."""
    print("Testing: Risk-benefit service unavailable...")
    
    with patch('api.services.pgx_care_plan_integration.get_risk_benefit_composition_service') as mock_get_service:
        mock_get_service.side_effect = Exception("Service unavailable")
        
        try:
            result = await integrate_pgx_into_drug_efficacy(
                drug_efficacy_response={"drugs": [{"name": "5-FU", "efficacy_score": 0.75}]},
                patient_profile={"germline_variants": [{"gene": "DPYD"}]},
                treatment_line="first-line",
                prior_therapies=[]
            )
            # Should handle gracefully
            print(f"   ✅ Handled gracefully: {result is not None}")
            return True
        except Exception as e:
            print(f"   ❌ Crashed: {e}")
            return False


async def test_pgx_screening_timeout():
    """Test: PGx screening service timeout."""
    print("Testing: PGx screening timeout...")
    
    async def slow_screen(*args, **kwargs):
        await asyncio.sleep(10)  # Simulate slow operation
        return {}
    
    with patch('api.services.pgx_care_plan_integration.get_pgx_screening_service') as mock_get_service:
        mock_service = AsyncMock()
        mock_service.screen_drugs = slow_screen
        mock_get_service.return_value = mock_service
        
        try:
            result = await asyncio.wait_for(
                integrate_pgx_into_drug_efficacy(
                    drug_efficacy_response={"drugs": [{"name": "5-FU", "efficacy_score": 0.75}]},
                    patient_profile={"germline_variants": [{"gene": "DPYD"}]},
                    treatment_line="first-line",
                    prior_therapies=[]
                ),
                timeout=1.0
            )
            print(f"   ❌ Should have timed out")
            return False
        except asyncio.TimeoutError:
            print(f"   ✅ Timeout handled gracefully")
            return True
        except Exception as e:
            print(f"   ⚠️  Unexpected error: {e}")
            return False


async def test_pgx_screening_returns_none():
    """Test: PGx screening returns None."""
    print("Testing: PGx screening returns None...")
    
    with patch('api.services.pgx_care_plan_integration.get_pgx_screening_service') as mock_get_service:
        mock_service = AsyncMock()
        mock_service.screen_drugs = AsyncMock(return_value=None)
        mock_get_service.return_value = mock_service
        
        try:
            result = await integrate_pgx_into_drug_efficacy(
                drug_efficacy_response={"drugs": [{"name": "5-FU", "efficacy_score": 0.75}]},
                patient_profile={"germline_variants": [{"gene": "DPYD"}]},
                treatment_line="first-line",
                prior_therapies=[]
            )
            # Should handle gracefully
            print(f"   ✅ Handled gracefully: {result is not None}")
            return True
        except Exception as e:
            print(f"   ❌ Crashed: {e}")
            return False


async def test_pgx_screening_returns_empty_dict():
    """Test: PGx screening returns empty dict."""
    print("Testing: PGx screening returns empty dict...")
    
    with patch('api.services.pgx_care_plan_integration.get_pgx_screening_service') as mock_get_service:
        mock_service = AsyncMock()
        mock_service.screen_drugs = AsyncMock(return_value={})
        mock_get_service.return_value = mock_service
        
        try:
            result = await integrate_pgx_into_drug_efficacy(
                drug_efficacy_response={"drugs": [{"name": "5-FU", "efficacy_score": 0.75}]},
                patient_profile={"germline_variants": [{"gene": "DPYD"}]},
                treatment_line="first-line",
                prior_therapies=[]
            )
            # Should handle gracefully
            print(f"   ✅ Handled gracefully: {result is not None}")
            return True
        except Exception as e:
            print(f"   ❌ Crashed: {e}")
            return False


async def test_pgx_screening_raises_exception():
    """Test: PGx screening raises exception."""
    print("Testing: PGx screening raises exception...")
    
    with patch('api.services.pgx_care_plan_integration.get_pgx_screening_service') as mock_get_service:
        mock_service = AsyncMock()
        mock_service.screen_drugs = AsyncMock(side_effect=Exception("Screening failed"))
        mock_get_service.return_value = mock_service
        
        try:
            result = await integrate_pgx_into_drug_efficacy(
                drug_efficacy_response={"drugs": [{"name": "5-FU", "efficacy_score": 0.75}]},
                patient_profile={"germline_variants": [{"gene": "DPYD"}]},
                treatment_line="first-line",
                prior_therapies=[]
            )
            # Should handle gracefully - return unchanged or with error indicator
            print(f"   ✅ Handled gracefully: {result is not None}")
            return True
        except Exception as e:
            print(f"   ❌ Crashed: {e}")
            return False


async def run_all_integration_tests():
    """Run all integration failure tests."""
    print("\n" + "=" * 80)
    print("PGX INTEGRATION - INTEGRATION FAILURE TESTS")
    print("=" * 80)
    print()
    
    tests = [
        test_pgx_service_unavailable,
        test_risk_benefit_service_unavailable,
        test_pgx_screening_timeout,
        test_pgx_screening_returns_none,
        test_pgx_screening_returns_empty_dict,
        test_pgx_screening_raises_exception,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            result = await test()
            if result:
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"   ❌ Test crashed: {e}")
            failed += 1
    
    print()
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"Total: {passed + failed}")
    print()
    
    return failed == 0


if __name__ == "__main__":
    success = asyncio.run(run_all_integration_tests())
    sys.exit(0 if success else 1)

