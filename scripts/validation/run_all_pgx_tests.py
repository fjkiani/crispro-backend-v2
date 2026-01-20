#!/usr/bin/env python3
"""
PGx Integration - Master Test Runner

Runs all PGx test suites:
1. E2E Tests (real patient data)
2. Failure Scenarios (edge cases, errors)
3. Integration Failures (service failures)
4. Data Validation (data sanitization)

Research Use Only - Not for Clinical Decision Making
"""

import asyncio
import subprocess
import sys
from pathlib import Path
from datetime import datetime
import json

# Test suites
TEST_SUITES = [
    {
        "name": "E2E Tests",
        "file": "test_pgx_e2e_simple.py",
        "description": "End-to-end tests with real patient data"
    },
    {
        "name": "Failure Scenarios",
        "file": "test_pgx_failure_scenarios.py",
        "description": "Edge cases, errors, and failure scenarios"
    },
    {
        "name": "Integration Failures",
        "file": "test_pgx_integration_failures.py",
        "description": "Service failures and integration issues"
    },
    {
        "name": "Data Validation",
        "file": "test_pgx_data_validation.py",
        "description": "Data validation and sanitization"
    }
]


def run_test_suite(suite_file: str) -> dict:
    """Run a single test suite."""
    script_path = Path(__file__).parent / suite_file
    
    if not script_path.exists():
        return {
            "status": "skipped",
            "error": f"Test file not found: {suite_file}"
        }
    
    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout per suite
        )
        
        return {
            "status": "completed",
            "exit_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "success": result.returncode == 0
        }
    except subprocess.TimeoutExpired:
        return {
            "status": "timeout",
            "error": "Test suite timed out after 5 minutes"
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }


def main():
    """Run all test suites."""
    print("\n" + "=" * 80)
    print("PGX INTEGRATION - MASTER TEST RUNNER")
    print("=" * 80)
    print()
    print(f"Running {len(TEST_SUITES)} test suites...")
    print()
    
    results = {}
    total_passed = 0
    total_failed = 0
    
    for suite in TEST_SUITES:
        print(f"📋 {suite['name']}")
        print(f"   {suite['description']}")
        print(f"   File: {suite['file']}")
        print()
        
        result = run_test_suite(suite['file'])
        results[suite['name']] = result
        
        if result['status'] == 'completed':
            if result['success']:
                print(f"   ✅ PASSED")
                total_passed += 1
            else:
                print(f"   ❌ FAILED (exit code: {result['exit_code']})")
                total_failed += 1
                if result['stderr']:
                    print(f"   Error: {result['stderr'][:200]}")
        elif result['status'] == 'timeout':
            print(f"   ⏱️  TIMEOUT")
            total_failed += 1
        elif result['status'] == 'skipped':
            print(f"   ⏭️  SKIPPED: {result.get('error', 'Unknown reason')}")
        else:
            print(f"   ❌ ERROR: {result.get('error', 'Unknown error')}")
            total_failed += 1
        
        print()
    
    # Summary
    print("=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"✅ Passed: {total_passed}")
    print(f"❌ Failed: {total_failed}")
    print(f"Total: {len(TEST_SUITES)}")
    print()
    
    # Production readiness
    print("=" * 80)
    print("PRODUCTION READINESS")
    print("=" * 80)
    if total_failed == 0:
        print("✅ All test suites passed - System is production ready")
        production_ready = True
    else:
        print(f"⚠️  {total_failed} test suite(s) failed - Review before production")
        production_ready = False
    print()
    
    # Save results
    output_file = Path(__file__).parent / "pgx_master_test_results.json"
    with open(output_file, "w") as f:
        json.dump({
            "test_timestamp": datetime.now().isoformat(),
            "total_suites": len(TEST_SUITES),
            "passed": total_passed,
            "failed": total_failed,
            "production_ready": production_ready,
            "results": results
        }, f, indent=2)
    
    print(f"📄 Results saved to: {output_file}")
    print()
    
    return production_ready


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

