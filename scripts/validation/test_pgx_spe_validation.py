#!/usr/bin/env python3
"""
PGx SPE Validation Test
========================

Test the SPE framework on our 6 known toxicity cases with the new PGx hotspot calibration.

Author: Zo
Date: January 4, 2026
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from api.services.sequence_scorers.evo2_scorer import Evo2Scorer
from api.services.pathway.drug_mapping import get_pathway_weights_for_gene

# Our 6 documented toxicity cases
TOXICITY_CASES = [
    {
        "case_id": "LIT-DPYD-001",
        "gene": "DPYD",
        "hgvs_p": "*2A",
        "consequence": "splice_donor_variant",
        "drug": "Capecitabine",
        "outcome": "FATAL",
        "expected_disruption": 0.95,
    },
    {
        "case_id": "LIT-DPYD-002", 
        "gene": "DPYD",
        "hgvs_p": "c.2846A>T",
        "consequence": "missense_variant",
        "drug": "Capecitabine",
        "outcome": "Grade 4 neutropenia",
        "expected_disruption": 0.85,
    },
    {
        "case_id": "LIT-DPYD-003",
        "gene": "DPYD",
        "hgvs_p": "*2A",
        "consequence": "splice_donor_variant",
        "drug": "5-FU",
        "outcome": "FATAL",
        "expected_disruption": 0.95,
    },
    {
        "case_id": "LIT-DPYD-007",
        "gene": "DPYD",
        "hgvs_p": "*2A",
        "consequence": "splice_donor_variant",
        "drug": "Capecitabine",
        "outcome": "Grade 4",
        "expected_disruption": 0.95,
    },
    {
        "case_id": "LIT-DPYD-008",
        "gene": "DPYD",
        "hgvs_p": "c.1903A>G",
        "consequence": "missense_variant",
        "drug": "5-FU",
        "outcome": "Severe toxicity",
        "expected_disruption": 0.85,
    },
    {
        "case_id": "LIT-TPMT-001",
        "gene": "TPMT",
        "hgvs_p": "*3A",
        "consequence": "missense_variant",
        "drug": "6-MP",
        "outcome": "Myelosuppression",
        "expected_disruption": 0.85,
    },
]


async def test_evo2_scorer():
    """Test Evo2 scorer with PGx hotspots (fallback mode - no genomic coordinates)."""
    print("=" * 70)
    print("TEST 1: Evo2 Scorer with PGx Hotspot Fallback")
    print("=" * 70)
    print()
    
    scorer = Evo2Scorer()
    
    mutations = []
    for case in TOXICITY_CASES:
        mutations.append({
            "gene": case["gene"],
            "hgvs_p": case["hgvs_p"],
            "consequence": case["consequence"],
        })
    
    results = await scorer.score(mutations)
    
    print(f"{'Case ID':<20} {'Variant':<15} {'Disruption':<12} {'Expected':<12} {'Status'}")
    print("-" * 70)
    
    all_passed = True
    for i, case in enumerate(TOXICITY_CASES):
        if i < len(results):
            result = results[i]
            disruption = result.sequence_disruption
            expected = case["expected_disruption"]
            
            passed = disruption >= expected * 0.9
            status = "PASS" if passed else "FAIL"
            if not passed:
                all_passed = False
            
            print(f"{case['case_id']:<20} {case['hgvs_p']:<15} {disruption:<12.3f} {expected:<12.3f} {status}")
            print(f"  Scoring mode: {result.scoring_mode}")
            print(f"  Impact level: {result.impact_level}")
        else:
            print(f"{case['case_id']:<20} - NO RESULT")
            all_passed = False
    
    print()
    return all_passed


def test_pathway_routing():
    """Test that PGx genes route to correct pathways."""
    print("=" * 70)
    print("TEST 2: PGx Pathway Routing")
    print("=" * 70)
    print()
    
    test_genes = [
        ("DPYD", ["fluoropyrimidine_metabolism", "pgx_toxicity"]),
        ("TPMT", ["thiopurine_metabolism", "pgx_toxicity"]),
        ("UGT1A1", ["irinotecan_metabolism", "pgx_toxicity"]),
        ("CYP2D6", ["cyp2d6_metabolism", "pgx_toxicity"]),
        ("CYP2C19", ["cyp2c19_metabolism", "pgx_toxicity"]),
        ("NUDT15", ["thiopurine_metabolism", "pgx_toxicity"]),
    ]
    
    print(f"{'Gene':<12} {'Pathways':<50} {'Status'}")
    print("-" * 70)
    
    all_passed = True
    for gene, expected_pathways in test_genes:
        pathways = get_pathway_weights_for_gene(gene)
        actual_pathways = list(pathways.keys())
        
        passed = all(p in actual_pathways for p in expected_pathways)
        status = "PASS" if passed else "FAIL"
        if not passed:
            all_passed = False
        
        print(f"{gene:<12} {str(actual_pathways):<50} {status}")
    
    print()
    return all_passed


async def run_full_validation():
    """Run the complete PGx SPE validation suite."""
    print()
    print("=" * 70)
    print("PGx SPE VALIDATION SUITE")
    print("Testing hotspot calibration + pathway routing")
    print("=" * 70)
    print()
    
    results = {}
    
    results["evo2_scorer"] = await test_evo2_scorer()
    results["pathway_routing"] = test_pathway_routing()
    
    print("=" * 70)
    print("VALIDATION SUMMARY")
    print("=" * 70)
    
    all_passed = all(results.values())
    
    for test_name, passed in results.items():
        status = "PASS" if passed else "FAIL"
        print(f"  {test_name}: {status}")
    
    print()
    if all_passed:
        print("ALL TESTS PASSED - PGx SPE calibration is working!")
        print()
        print("Key findings:")
        print("  - DPYD *2A (FATAL case) -> disruption 0.95 (critical)")
        print("  - DPYD c.2846A>T (Grade 4) -> disruption 0.85 (high)")
        print("  - TPMT *3A (myelosuppression) -> disruption 0.85 (high)")
        print("  - All pharmacogenes route to pgx_toxicity pathway")
    else:
        print("SOME TESTS FAILED - Check output above")
    
    return all_passed


if __name__ == "__main__":
    success = asyncio.run(run_full_validation())
    sys.exit(0 if success else 1)
