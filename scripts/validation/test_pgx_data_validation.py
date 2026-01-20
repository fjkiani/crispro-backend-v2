#!/usr/bin/env python3
"""
PGx Integration - Data Validation Tests

Tests data validation and sanitization to ensure invalid data doesn't
cause crashes or incorrect results.

Research Use Only - Not for Clinical Decision Making
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))

from api.services.pgx_care_plan_integration import integrate_pgx_into_drug_efficacy


async def test_variant_format_validation():
    """Test: Various variant format validations."""
    print("Testing: Variant format validation...")
    
    variant_formats = [
        {"gene": "DPYD", "variant": "c.1905+1G>A"},  # Standard HGVS
        {"gene": "DPYD", "variant": "*2A"},  # Star allele
        {"gene": "DPYD", "variant": "c.1905+1G>A", "hgvs_c": "NM_000110.3:c.1905+1G>A"},  # With HGVS_c
        {"gene": "DPYD", "variant": "c.1905+1G>A", "hgvs_p": "p.?"},  # With HGVS_p
        {"gene": "DPYD", "variant": None},  # None variant
        {"gene": "DPYD", "variant": ""},  # Empty variant
        {"gene": "DPYD"},  # Missing variant
    ]
    
    passed = 0
    for variant in variant_formats:
        try:
            result = await integrate_pgx_into_drug_efficacy(
                drug_efficacy_response={"drugs": [{"name": "5-FU", "efficacy_score": 0.75}]},
                patient_profile={"germline_variants": [variant]},
                treatment_line="first-line",
                prior_therapies=[]
            )
            if result is not None:
                passed += 1
        except Exception as e:
            print(f"   ❌ Failed with variant {variant}: {e}")
            return False
    
    print(f"   ✅ Handled {passed}/{len(variant_formats)} variant formats")
    return passed == len(variant_formats)


async def test_gene_name_validation():
    """Test: Gene name format validation."""
    print("Testing: Gene name validation...")
    
    gene_names = [
        "DPYD",  # Standard
        "dpyd",  # Lowercase
        "Dpyd",  # Mixed case
        "DPYD ",  # With space
        " DPYD",  # Leading space
        "DPYD\n",  # With newline
        "DPYD\t",  # With tab
    ]
    
    passed = 0
    for gene_name in gene_names:
        try:
            result = await integrate_pgx_into_drug_efficacy(
                drug_efficacy_response={"drugs": [{"name": "5-FU", "efficacy_score": 0.75}]},
                patient_profile={"germline_variants": [{"gene": gene_name}]},
                treatment_line="first-line",
                prior_therapies=[]
            )
            if result is not None:
                passed += 1
        except Exception as e:
            print(f"   ❌ Failed with gene {gene_name}: {e}")
            return False
    
    print(f"   ✅ Handled {passed}/{len(gene_names)} gene name formats")
    return passed == len(gene_names)


async def test_drug_name_normalization():
    """Test: Drug name normalization and matching."""
    print("Testing: Drug name normalization...")
    
    # Test various drug name formats that should all match
    drug_name_variants = [
        "5-Fluorouracil",
        "5-fluorouracil",
        "5-FU",
        "5-fu",
        "Fluorouracil",
        "fluorouracil",
        "Capecitabine",
        "capecitabine",
    ]
    
    passed = 0
    for drug_name in drug_name_variants:
        try:
            result = await integrate_pgx_into_drug_efficacy(
                drug_efficacy_response={"drugs": [{"name": drug_name, "efficacy_score": 0.75}]},
                patient_profile={"germline_variants": [{"gene": "DPYD", "variant": "c.1905+1G>A"}]},
                treatment_line="first-line",
                prior_therapies=[]
            )
            if result is not None:
                passed += 1
        except Exception as e:
            print(f"   ❌ Failed with drug name {drug_name}: {e}")
            return False
    
    print(f"   ✅ Handled {passed}/{len(drug_name_variants)} drug name formats")
    return passed == len(drug_name_variants)


async def test_numeric_precision():
    """Test: Numeric precision and overflow handling."""
    print("Testing: Numeric precision...")
    
    extreme_scores = [
        0.0,  # Zero
        1.0,  # Maximum
        1.5,  # Over maximum
        -0.5,  # Negative
        0.0000001,  # Very small
        0.9999999,  # Very close to 1
        float('inf'),  # Infinity
        float('-inf'),  # Negative infinity
        float('nan'),  # NaN
    ]
    
    passed = 0
    for score in extreme_scores:
        try:
            result = await integrate_pgx_into_drug_efficacy(
                drug_efficacy_response={"drugs": [{"name": "5-FU", "efficacy_score": score}]},
                patient_profile={"germline_variants": [{"gene": "DPYD"}]},
                treatment_line="first-line",
                prior_therapies=[]
            )
            if result is not None:
                passed += 1
        except (ValueError, OverflowError, TypeError):
            # Expected for invalid numbers
            passed += 1
        except Exception as e:
            print(f"   ❌ Unexpected error with score {score}: {e}")
            return False
    
    print(f"   ✅ Handled {passed}/{len(extreme_scores)} extreme score values")
    return True


async def test_unicode_handling():
    """Test: Unicode and special character handling."""
    print("Testing: Unicode handling...")
    
    unicode_names = [
        "5-FU",
        "Drug™",
        "Drug®",
        "Drug©",
        "Drug-Name",
        "Drug_Name",
        "Drug Name",
        "Drug/Name",
        "Drug\\Name",
        "Drug\nName",
        "Drug\tName",
    ]
    
    passed = 0
    for name in unicode_names:
        try:
            result = await integrate_pgx_into_drug_efficacy(
                drug_efficacy_response={"drugs": [{"name": name, "efficacy_score": 0.75}]},
                patient_profile={"germline_variants": [{"gene": "DPYD"}]},
                treatment_line="first-line",
                prior_therapies=[]
            )
            if result is not None:
                passed += 1
        except Exception as e:
            print(f"   ❌ Failed with name {name}: {e}")
            return False
    
    print(f"   ✅ Handled {passed}/{len(unicode_names)} unicode/special character names")
    return passed == len(unicode_names)


async def run_all_validation_tests():
    """Run all data validation tests."""
    print("\n" + "=" * 80)
    print("PGX INTEGRATION - DATA VALIDATION TESTS")
    print("=" * 80)
    print()
    
    tests = [
        test_variant_format_validation,
        test_gene_name_validation,
        test_drug_name_normalization,
        test_numeric_precision,
        test_unicode_handling,
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
    success = asyncio.run(run_all_validation_tests())
    sys.exit(0 if success else 1)

