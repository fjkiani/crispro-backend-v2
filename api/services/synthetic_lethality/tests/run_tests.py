#!/usr/bin/env python3
"""
Test runner for Synthetic Lethality Agent.

Runs integration and E2E tests.
"""
import sys
import os
import asyncio

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from api.services.synthetic_lethality.tests.test_integration import (
    test_agent_basic_functionality,
    test_agent_multi_mutation,
    test_pathway_mapping,
    test_drug_recommendations,
    test_error_handling
)

from api.services.synthetic_lethality.tests.test_e2e import (
    test_api_health_check,
    test_api_endpoint,
    test_api_error_handling,
    test_orchestrator_integration,
    test_full_pipeline
)


async def run_integration_tests():
    """Run integration tests."""
    print("=" * 60)
    print("🧪 INTEGRATION TESTS")
    print("=" * 60)
    
    tests = [
        ("Basic Functionality", test_agent_basic_functionality),
        ("Multi-Mutation", test_agent_multi_mutation),
        ("Pathway Mapping", test_pathway_mapping),
        ("Drug Recommendations", test_drug_recommendations),
        ("Error Handling", test_error_handling),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        try:
            print(f"\n📋 Running: {name}")
            await test_func()
            passed += 1
            print(f"✅ {name}: PASSED")
        except Exception as e:
            failed += 1
            print(f"❌ {name}: FAILED - {e}")
            import traceback
            traceback.print_exc()
    
    print(f"\n{'=' * 60}")
    print(f"Integration Tests: {passed} passed, {failed} failed")
    print(f"{'=' * 60}\n")
    
    return passed, failed


async def run_e2e_tests():
    """Run end-to-end tests."""
    print("=" * 60)
    print("🌐 END-TO-END TESTS")
    print("=" * 60)
    
    tests = [
        ("API Health Check", test_api_health_check),
        ("API Endpoint", test_api_endpoint),
        ("API Error Handling", test_api_error_handling),
        ("Orchestrator Integration", test_orchestrator_integration),
        ("Full Pipeline", test_full_pipeline),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        try:
            print(f"\n📋 Running: {name}")
            await test_func()
            passed += 1
            print(f"✅ {name}: PASSED")
        except Exception as e:
            failed += 1
            print(f"❌ {name}: FAILED - {e}")
            import traceback
            traceback.print_exc()
    
    print(f"\n{'=' * 60}")
    print(f"E2E Tests: {passed} passed, {failed} failed")
    print(f"{'=' * 60}\n")
    
    return passed, failed


async def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("🚀 SYNTHETIC LETHALITY AGENT - TEST SUITE")
    print("=" * 60 + "\n")
    
    # Run integration tests
    int_passed, int_failed = await run_integration_tests()
    
    # Run E2E tests
    e2e_passed, e2e_failed = await run_e2e_tests()
    
    # Summary
    total_passed = int_passed + e2e_passed
    total_failed = int_failed + e2e_failed
    
    print("=" * 60)
    print("📊 TEST SUMMARY")
    print("=" * 60)
    print(f"Integration Tests: {int_passed} passed, {int_failed} failed")
    print(f"E2E Tests:         {e2e_passed} passed, {e2e_failed} failed")
    print(f"Total:             {total_passed} passed, {total_failed} failed")
    print("=" * 60)
    
    if total_failed == 0:
        print("\n✅ ALL TESTS PASSED!")
        return 0
    else:
        print(f"\n❌ {total_failed} TEST(S) FAILED")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)


