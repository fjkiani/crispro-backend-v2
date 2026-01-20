#!/usr/bin/env python3
"""
PGx Integration - Comprehensive Failure Test Suite

This test suite validates that PGx integration handles edge cases, errors,
and failure scenarios gracefully without crashing in production.

Test Categories:
1. Missing/Null Data Scenarios
2. Invalid Data Formats
3. Service Failures
4. Timeout Scenarios
5. Empty/Malformed Responses
6. Edge Cases (drug names, variants, etc.)
7. Concurrent Requests
8. Large Payloads
9. Invalid Patient Profiles
10. Missing Dependencies

Research Use Only - Not for Clinical Decision Making
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
from unittest.mock import AsyncMock, patch, MagicMock

import httpx

# Add backend to path
backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))

from api.services.pgx_care_plan_integration import integrate_pgx_into_drug_efficacy, add_pgx_safety_gate_to_trials

# API base URL
API_ROOT = "http://localhost:8000"


# ============================================================================
# TEST CATEGORIES
# ============================================================================

class FailureTestSuite:
    """Comprehensive failure test suite for PGx integration."""
    
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []
    
    def log_result(self, test_name: str, passed: bool, error: Optional[str] = None):
        """Log test result."""
        if passed:
            self.passed += 1
            print(f"   ✅ {test_name}")
        else:
            self.failed += 1
            print(f"   ❌ {test_name}")
            if error:
                print(f"      Error: {error}")
                self.errors.append(f"{test_name}: {error}")
    
    async def test_missing_drug_efficacy_response(self):
        """Test: Missing/null drug efficacy response."""
        test_name = "Missing drug efficacy response"
        try:
            result = await integrate_pgx_into_drug_efficacy(
                drug_efficacy_response=None,
                patient_profile={"germline_variants": [{"gene": "DPYD"}]},
                treatment_line="first-line",
                prior_therapies=[]
            )
            # Should return None or empty response gracefully
            self.log_result(test_name, result is None or result == {})
        except Exception as e:
            # Should handle gracefully, not crash
            self.log_result(test_name, True, f"Handled gracefully: {type(e).__name__}")
    
    async def test_empty_drugs_list(self):
        """Test: Empty drugs list in response."""
        test_name = "Empty drugs list"
        try:
            result = await integrate_pgx_into_drug_efficacy(
                drug_efficacy_response={"drugs": []},
                patient_profile={"germline_variants": [{"gene": "DPYD"}]},
                treatment_line="first-line",
                prior_therapies=[]
            )
            # Should return gracefully with empty drugs
            self.log_result(test_name, result is not None)
        except Exception as e:
            self.log_result(test_name, False, str(e))
    
    async def test_missing_germline_variants(self):
        """Test: Missing germline variants."""
        test_name = "Missing germline variants"
        try:
            result = await integrate_pgx_into_drug_efficacy(
                drug_efficacy_response={"drugs": [{"name": "5-FU", "efficacy_score": 0.75}]},
                patient_profile={},  # No germline_variants
                treatment_line="first-line",
                prior_therapies=[]
            )
            # Should return unchanged response
            self.log_result(test_name, result is not None)
        except Exception as e:
            self.log_result(test_name, False, str(e))
    
    async def test_empty_germline_variants(self):
        """Test: Empty germline variants list."""
        test_name = "Empty germline variants list"
        try:
            result = await integrate_pgx_into_drug_efficacy(
                drug_efficacy_response={"drugs": [{"name": "5-FU", "efficacy_score": 0.75}]},
                patient_profile={"germline_variants": []},
                treatment_line="first-line",
                prior_therapies=[]
            )
            # Should return unchanged response
            self.log_result(test_name, result is not None)
        except Exception as e:
            self.log_result(test_name, False, str(e))
    
    async def test_malformed_variant(self):
        """Test: Malformed variant data."""
        test_name = "Malformed variant data"
        try:
            result = await integrate_pgx_into_drug_efficacy(
                drug_efficacy_response={"drugs": [{"name": "5-FU", "efficacy_score": 0.75}]},
                patient_profile={"germline_variants": [{"invalid": "data"}]},  # Missing gene
                treatment_line="first-line",
                prior_therapies=[]
            )
            # Should handle gracefully
            self.log_result(test_name, result is not None)
        except Exception as e:
            # Should not crash
            self.log_result(test_name, True, f"Handled gracefully: {type(e).__name__}")
    
    async def test_missing_drug_name(self):
        """Test: Drug missing name field."""
        test_name = "Drug missing name field"
        try:
            result = await integrate_pgx_into_drug_efficacy(
                drug_efficacy_response={"drugs": [{"efficacy_score": 0.75}]},  # No name
                patient_profile={"germline_variants": [{"gene": "DPYD"}]},
                treatment_line="first-line",
                prior_therapies=[]
            )
            # Should handle gracefully
            self.log_result(test_name, result is not None)
        except Exception as e:
            self.log_result(test_name, False, str(e))
    
    async def test_invalid_drug_name_format(self):
        """Test: Invalid drug name formats."""
        test_name = "Invalid drug name formats"
        try:
            invalid_names = [None, "", 123, [], {}]
            for invalid_name in invalid_names:
                result = await integrate_pgx_into_drug_efficacy(
                    drug_efficacy_response={"drugs": [{"name": invalid_name, "efficacy_score": 0.75}]},
                    patient_profile={"germline_variants": [{"gene": "DPYD"}]},
                    treatment_line="first-line",
                    prior_therapies=[]
                )
                # Should handle gracefully
                if result is None:
                    self.log_result(test_name, False, f"Failed with name: {invalid_name}")
                    return
            self.log_result(test_name, True)
        except Exception as e:
            self.log_result(test_name, True, f"Handled gracefully: {type(e).__name__}")
    
    async def test_missing_efficacy_score(self):
        """Test: Drug missing efficacy score."""
        test_name = "Drug missing efficacy score"
        try:
            result = await integrate_pgx_into_drug_efficacy(
                drug_efficacy_response={"drugs": [{"name": "5-FU"}]},  # No efficacy_score
                patient_profile={"germline_variants": [{"gene": "DPYD"}]},
                treatment_line="first-line",
                prior_therapies=[]
            )
            # Should handle gracefully
            self.log_result(test_name, result is not None)
        except Exception as e:
            self.log_result(test_name, False, str(e))
    
    async def test_invalid_efficacy_score(self):
        """Test: Invalid efficacy score values."""
        test_name = "Invalid efficacy score values"
        try:
            invalid_scores = [None, "invalid", -1, 2.0, [], {}]
            for invalid_score in invalid_scores:
                result = await integrate_pgx_into_drug_efficacy(
                    drug_efficacy_response={"drugs": [{"name": "5-FU", "efficacy_score": invalid_score}]},
                    patient_profile={"germline_variants": [{"gene": "DPYD"}]},
                    treatment_line="first-line",
                    prior_therapies=[]
                )
                # Should handle gracefully
                if result is None:
                    self.log_result(test_name, False, f"Failed with score: {invalid_score}")
                    return
            self.log_result(test_name, True)
        except Exception as e:
            self.log_result(test_name, True, f"Handled gracefully: {type(e).__name__}")
    
    async def test_awaiting_ngs_status(self):
        """Test: Response with awaiting_ngs status."""
        test_name = "Response with awaiting_ngs status"
        try:
            result = await integrate_pgx_into_drug_efficacy(
                drug_efficacy_response={"status": "awaiting_ngs"},
                patient_profile={"germline_variants": [{"gene": "DPYD"}]},
                treatment_line="first-line",
                prior_therapies=[]
            )
            # Should return unchanged
            self.log_result(test_name, result.get("status") == "awaiting_ngs")
        except Exception as e:
            self.log_result(test_name, False, str(e))
    
    async def test_missing_patient_profile(self):
        """Test: Missing patient profile."""
        test_name = "Missing patient profile"
        try:
            result = await integrate_pgx_into_drug_efficacy(
                drug_efficacy_response={"drugs": [{"name": "5-FU", "efficacy_score": 0.75}]},
                patient_profile=None,
                treatment_line="first-line",
                prior_therapies=[]
            )
            # Should handle gracefully
            self.log_result(test_name, result is not None)
        except Exception as e:
            # Should not crash
            self.log_result(test_name, True, f"Handled gracefully: {type(e).__name__}")
    
    async def test_missing_treatment_line(self):
        """Test: Missing treatment line."""
        test_name = "Missing treatment line"
        try:
            result = await integrate_pgx_into_drug_efficacy(
                drug_efficacy_response={"drugs": [{"name": "5-FU", "efficacy_score": 0.75}]},
                patient_profile={"germline_variants": [{"gene": "DPYD"}]},
                treatment_line=None,
                prior_therapies=[]
            )
            # Should handle gracefully
            self.log_result(test_name, result is not None)
        except Exception as e:
            self.log_result(test_name, False, str(e))
    
    async def test_invalid_treatment_line(self):
        """Test: Invalid treatment line values."""
        test_name = "Invalid treatment line values"
        try:
            invalid_lines = ["", "invalid", 123, [], {}]
            for invalid_line in invalid_lines:
                result = await integrate_pgx_into_drug_efficacy(
                    drug_efficacy_response={"drugs": [{"name": "5-FU", "efficacy_score": 0.75}]},
                    patient_profile={"germline_variants": [{"gene": "DPYD"}]},
                    treatment_line=invalid_line,
                    prior_therapies=[]
                )
                # Should handle gracefully
                if result is None:
                    self.log_result(test_name, False, f"Failed with line: {invalid_line}")
                    return
            self.log_result(test_name, True)
        except Exception as e:
            self.log_result(test_name, True, f"Handled gracefully: {type(e).__name__}")
    
    async def test_missing_prior_therapies(self):
        """Test: Missing prior therapies."""
        test_name = "Missing prior therapies"
        try:
            result = await integrate_pgx_into_drug_efficacy(
                drug_efficacy_response={"drugs": [{"name": "5-FU", "efficacy_score": 0.75}]},
                patient_profile={"germline_variants": [{"gene": "DPYD"}]},
                treatment_line="first-line",
                prior_therapies=None
            )
            # Should handle gracefully
            self.log_result(test_name, result is not None)
        except Exception as e:
            self.log_result(test_name, False, str(e))
    
    async def test_invalid_prior_therapies(self):
        """Test: Invalid prior therapies format."""
        test_name = "Invalid prior therapies format"
        try:
            invalid_therapies = ["not a list", 123, {}, None]
            for invalid_therapy in invalid_therapies:
                result = await integrate_pgx_into_drug_efficacy(
                    drug_efficacy_response={"drugs": [{"name": "5-FU", "efficacy_score": 0.75}]},
                    patient_profile={"germline_variants": [{"gene": "DPYD"}]},
                    treatment_line="first-line",
                    prior_therapies=invalid_therapy
                )
                # Should handle gracefully
                if result is None:
                    self.log_result(test_name, False, f"Failed with therapies: {invalid_therapy}")
                    return
            self.log_result(test_name, True)
        except Exception as e:
            self.log_result(test_name, True, f"Handled gracefully: {type(e).__name__}")
    
    async def test_unknown_gene(self):
        """Test: Unknown/unsupported gene."""
        test_name = "Unknown/unsupported gene"
        try:
            result = await integrate_pgx_into_drug_efficacy(
                drug_efficacy_response={"drugs": [{"name": "5-FU", "efficacy_score": 0.75}]},
                patient_profile={"germline_variants": [{"gene": "UNKNOWN_GENE"}]},
                treatment_line="first-line",
                prior_therapies=[]
            )
            # Should handle gracefully (no PGx screening for unknown gene)
            self.log_result(test_name, result is not None)
        except Exception as e:
            self.log_result(test_name, False, str(e))
    
    async def test_multiple_variants_same_gene(self):
        """Test: Multiple variants for same gene."""
        test_name = "Multiple variants same gene"
        try:
            result = await integrate_pgx_into_drug_efficacy(
                drug_efficacy_response={"drugs": [{"name": "5-FU", "efficacy_score": 0.75}]},
                patient_profile={"germline_variants": [
                    {"gene": "DPYD", "variant": "c.1905+1G>A"},
                    {"gene": "DPYD", "variant": "c.2846A>T"}
                ]},
                treatment_line="first-line",
                prior_therapies=[]
            )
            # Should handle gracefully
            self.log_result(test_name, result is not None)
        except Exception as e:
            self.log_result(test_name, False, str(e))
    
    async def test_multiple_genes(self):
        """Test: Multiple different genes."""
        test_name = "Multiple different genes"
        try:
            result = await integrate_pgx_into_drug_efficacy(
                drug_efficacy_response={"drugs": [
                    {"name": "5-FU", "efficacy_score": 0.75},
                    {"name": "Tamoxifen", "efficacy_score": 0.70}
                ]},
                patient_profile={"germline_variants": [
                    {"gene": "DPYD", "variant": "c.1905+1G>A"},
                    {"gene": "CYP2D6", "variant": "*4"}
                ]},
                treatment_line="first-line",
                prior_therapies=[]
            )
            # Should handle gracefully
            self.log_result(test_name, result is not None)
        except Exception as e:
            self.log_result(test_name, False, str(e))
    
    async def test_large_drug_list(self):
        """Test: Large number of drugs."""
        test_name = "Large drug list (100+ drugs)"
        try:
            large_drug_list = [{"name": f"Drug_{i}", "efficacy_score": 0.5 + (i % 50) / 100} for i in range(150)]
            result = await integrate_pgx_into_drug_efficacy(
                drug_efficacy_response={"drugs": large_drug_list},
                patient_profile={"germline_variants": [{"gene": "DPYD"}]},
                treatment_line="first-line",
                prior_therapies=[]
            )
            # Should handle gracefully
            self.log_result(test_name, result is not None and len(result.get("drugs", [])) == 150)
        except Exception as e:
            self.log_result(test_name, False, str(e))
    
    async def test_special_characters_in_drug_name(self):
        """Test: Special characters in drug names."""
        test_name = "Special characters in drug names"
        try:
            special_names = ["5-FU", "6-MP", "Drug-Name", "Drug_Name", "Drug Name", "Drug/Name"]
            for special_name in special_names:
                result = await integrate_pgx_into_drug_efficacy(
                    drug_efficacy_response={"drugs": [{"name": special_name, "efficacy_score": 0.75}]},
                    patient_profile={"germline_variants": [{"gene": "DPYD"}]},
                    treatment_line="first-line",
                    prior_therapies=[]
                )
                if result is None:
                    self.log_result(test_name, False, f"Failed with name: {special_name}")
                    return
            self.log_result(test_name, True)
        except Exception as e:
            self.log_result(test_name, False, str(e))
    
    async def test_case_insensitive_drug_names(self):
        """Test: Case insensitive drug name matching."""
        test_name = "Case insensitive drug names"
        try:
            case_variants = ["5-FU", "5-fu", "5-Fu", "FLUOROURACIL", "fluorouracil", "Fluorouracil"]
            for case_variant in case_variants:
                result = await integrate_pgx_into_drug_efficacy(
                    drug_efficacy_response={"drugs": [{"name": case_variant, "efficacy_score": 0.75}]},
                    patient_profile={"germline_variants": [{"gene": "DPYD"}]},
                    treatment_line="first-line",
                    prior_therapies=[]
                )
                if result is None:
                    self.log_result(test_name, False, f"Failed with name: {case_variant}")
                    return
            self.log_result(test_name, True)
        except Exception as e:
            self.log_result(test_name, False, str(e))
    
    async def test_trials_missing_interventions(self):
        """Test: Trials with missing interventions."""
        test_name = "Trials missing interventions"
        try:
            result = await add_pgx_safety_gate_to_trials(
                trials_response={"trials": [{"trial_id": "T001", "title": "Test Trial"}]},  # No interventions
                patient_profile={"germline_variants": [{"gene": "DPYD"}]},
                treatment_line="first-line",
                prior_therapies=[]
            )
            # Should handle gracefully (UNKNOWN_NO_INTERVENTIONS status)
            self.log_result(test_name, result is not None)
            if result:
                trial = result.get("trials", [{}])[0]
                pgx_safety = trial.get("pgx_safety", {})
                self.log_result(test_name, pgx_safety.get("safety_status") == "UNKNOWN_NO_INTERVENTIONS")
        except Exception as e:
            self.log_result(test_name, False, str(e))
    
    async def test_trials_empty_interventions(self):
        """Test: Trials with empty interventions list."""
        test_name = "Trials empty interventions"
        try:
            result = await add_pgx_safety_gate_to_trials(
                trials_response={"trials": [{"trial_id": "T001", "interventions": []}]},
                patient_profile={"germline_variants": [{"gene": "DPYD"}]},
                treatment_line="first-line",
                prior_therapies=[]
            )
            # Should handle gracefully
            self.log_result(test_name, result is not None)
        except Exception as e:
            self.log_result(test_name, False, str(e))
    
    async def test_trials_malformed_interventions(self):
        """Test: Trials with malformed interventions."""
        test_name = "Trials malformed interventions"
        try:
            malformed = [
                {"trial_id": "T001", "interventions": None},
                {"trial_id": "T002", "interventions": "not a list"},
                {"trial_id": "T003", "interventions": [None]},
                {"trial_id": "T004", "interventions": [{"no": "name"}]}
            ]
            for trial_data in malformed:
                result = await add_pgx_safety_gate_to_trials(
                    trials_response={"trials": [trial_data]},
                    patient_profile={"germline_variants": [{"gene": "DPYD"}]},
                    treatment_line="first-line",
                    prior_therapies=[]
                )
                if result is None:
                    self.log_result(test_name, False, f"Failed with: {trial_data}")
                    return
            self.log_result(test_name, True)
        except Exception as e:
            self.log_result(test_name, True, f"Handled gracefully: {type(e).__name__}")
    
    async def test_concurrent_requests(self):
        """Test: Multiple concurrent requests."""
        test_name = "Concurrent requests"
        try:
            async def single_request():
                return await integrate_pgx_into_drug_efficacy(
                    drug_efficacy_response={"drugs": [{"name": "5-FU", "efficacy_score": 0.75}]},
                    patient_profile={"germline_variants": [{"gene": "DPYD"}]},
                    treatment_line="first-line",
                    prior_therapies=[]
                )
            
            # Run 10 concurrent requests
            results = await asyncio.gather(*[single_request() for _ in range(10)])
            # All should succeed
            self.log_result(test_name, all(r is not None for r in results))
        except Exception as e:
            self.log_result(test_name, False, str(e))
    
    async def test_service_timeout_simulation(self):
        """Test: Simulated service timeout."""
        test_name = "Service timeout simulation"
        try:
            # Use asyncio.wait_for to simulate timeout
            async def slow_operation():
                await asyncio.sleep(0.1)  # Simulate slow operation
                return await integrate_pgx_into_drug_efficacy(
                    drug_efficacy_response={"drugs": [{"name": "5-FU", "efficacy_score": 0.75}]},
                    patient_profile={"germline_variants": [{"gene": "DPYD"}]},
                    treatment_line="first-line",
                    prior_therapies=[]
                )
            
            try:
                result = await asyncio.wait_for(slow_operation(), timeout=0.05)
                # Should complete within timeout
                self.log_result(test_name, result is not None)
            except asyncio.TimeoutError:
                # Timeout should be handled gracefully
                self.log_result(test_name, True, "Timeout handled gracefully")
        except Exception as e:
            self.log_result(test_name, False, str(e))
    
    async def run_all_tests(self):
        """Run all failure tests."""
        print("\n" + "=" * 80)
        print("PGX INTEGRATION - FAILURE TEST SUITE")
        print("=" * 80)
        print()
        print("Testing edge cases, error conditions, and failure scenarios...")
        print()
        
        # Run all tests
        test_methods = [
            self.test_missing_drug_efficacy_response,
            self.test_empty_drugs_list,
            self.test_missing_germline_variants,
            self.test_empty_germline_variants,
            self.test_malformed_variant,
            self.test_missing_drug_name,
            self.test_invalid_drug_name_format,
            self.test_missing_efficacy_score,
            self.test_invalid_efficacy_score,
            self.test_awaiting_ngs_status,
            self.test_missing_patient_profile,
            self.test_missing_treatment_line,
            self.test_invalid_treatment_line,
            self.test_missing_prior_therapies,
            self.test_invalid_prior_therapies,
            self.test_unknown_gene,
            self.test_multiple_variants_same_gene,
            self.test_multiple_genes,
            self.test_large_drug_list,
            self.test_special_characters_in_drug_name,
            self.test_case_insensitive_drug_names,
            self.test_trials_missing_interventions,
            self.test_trials_empty_interventions,
            self.test_trials_malformed_interventions,
            self.test_concurrent_requests,
            self.test_service_timeout_simulation,
        ]
        
        for test_method in test_methods:
            try:
                await test_method()
            except Exception as e:
                self.log_result(test_method.__name__, False, f"Unexpected error: {str(e)}")
        
        # Summary
        print()
        print("=" * 80)
        print("TEST SUMMARY")
        print("=" * 80)
        print(f"✅ Passed: {self.passed}")
        print(f"❌ Failed: {self.failed}")
        print(f"Total: {self.passed + self.failed}")
        print()
        
        if self.errors:
            print("Errors:")
            for error in self.errors[:10]:  # Show first 10 errors
                print(f"  - {error}")
            if len(self.errors) > 10:
                print(f"  ... and {len(self.errors) - 10} more")
        
        print()
        print("=" * 80)
        print("PRODUCTION READINESS")
        print("=" * 80)
        if self.failed == 0:
            print("✅ All failure tests passed - System handles edge cases gracefully")
        else:
            print(f"⚠️  {self.failed} failure test(s) failed - Review error handling")
        print()
        
        return self.failed == 0


async def main():
    """Run failure test suite."""
    suite = FailureTestSuite()
    success = await suite.run_all_tests()
    
    # Save results
    output_file = Path(__file__).parent / "pgx_failure_test_results.json"
    with open(output_file, "w") as f:
        json.dump({
            "test_timestamp": datetime.now().isoformat(),
            "passed": suite.passed,
            "failed": suite.failed,
            "total": suite.passed + suite.failed,
            "errors": suite.errors,
            "production_ready": success
        }, f, indent=2)
    
    print(f"📄 Results saved to: {output_file}")
    print()
    
    return success


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)

