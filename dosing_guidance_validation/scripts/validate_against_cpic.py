#!/usr/bin/env python3
"""
CPIC Guideline Concordance Validator

Validates our dosing guidance recommendations against CPIC published guidelines.
CPIC = Clinical Pharmacogenetics Implementation Consortium (consensus of 30+ experts)

This provides "gold standard" concordance without needing individual SME review.

Usage:
    python validate_against_cpic.py --input extraction_all_genes_auto_curated.json
    python validate_against_cpic.py --input extraction_all_genes_curated.json --output cpic_concordance_report.json

Author: Zo (Agent)
Date: January 2025
"""

import json
import argparse
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime

# ============================================================================
# CPIC GUIDELINES DATABASE
# Source: https://cpicpgx.org/guidelines/
# ============================================================================

CPIC_GUIDELINES = {
    # -------------------------------------------------------------------------
    # DPYD + Fluoropyrimidines (5-FU, Capecitabine, Tegafur)
    # Reference: Amstutz et al. Clin Pharmacol Ther. 2018;103(2):210-216
    # -------------------------------------------------------------------------
    "DPYD": {
        "variants": {
            # Activity Score 0 (No function)
            "*2A/*2A": {"activity_score": 0, "phenotype": "Poor Metabolizer", "recommendation": "AVOID"},
            "c.1905+1G>A homozygous": {"activity_score": 0, "phenotype": "Poor Metabolizer", "recommendation": "AVOID"},
            "*13/*13": {"activity_score": 0, "phenotype": "Poor Metabolizer", "recommendation": "AVOID"},
            "c.1679T>G homozygous": {"activity_score": 0, "phenotype": "Poor Metabolizer", "recommendation": "AVOID"},
            "DEFICIENCY": {"activity_score": 0, "phenotype": "Poor Metabolizer", "recommendation": "AVOID"},
            "DPD DEFICIENCY": {"activity_score": 0, "phenotype": "Poor Metabolizer", "recommendation": "AVOID"},
            
            # Activity Score 0.5-1.0 (Intermediate - one no-function allele)
            "*1/*2A": {"activity_score": 1.0, "phenotype": "Intermediate Metabolizer", "recommendation": "REDUCE_50"},
            "*1/*13": {"activity_score": 1.0, "phenotype": "Intermediate Metabolizer", "recommendation": "REDUCE_50"},
            "c.1905+1G>A heterozygous": {"activity_score": 1.0, "phenotype": "Intermediate Metabolizer", "recommendation": "REDUCE_50"},
            "c.1679T>G heterozygous": {"activity_score": 1.0, "phenotype": "Intermediate Metabolizer", "recommendation": "REDUCE_50"},
            
            # Activity Score 1.0-1.5 (Intermediate - decreased function)
            "*1/*D949V": {"activity_score": 1.0, "phenotype": "Intermediate Metabolizer", "recommendation": "REDUCE_50"},
            "c.2846A>T": {"activity_score": 1.0, "phenotype": "Intermediate Metabolizer", "recommendation": "REDUCE_50"},
            "c.2846A>T heterozygous": {"activity_score": 1.0, "phenotype": "Intermediate Metabolizer", "recommendation": "REDUCE_50"},
            "*1/*HapB3": {"activity_score": 1.5, "phenotype": "Intermediate Metabolizer", "recommendation": "REDUCE_25"},
            "c.1129-5923C>G": {"activity_score": 1.5, "phenotype": "Intermediate Metabolizer", "recommendation": "REDUCE_25"},
            "c.1236G>A": {"activity_score": 1.5, "phenotype": "Intermediate Metabolizer", "recommendation": "REDUCE_25"},
            "c.1903A>G": {"activity_score": 1.0, "phenotype": "Intermediate Metabolizer", "recommendation": "REDUCE_50"},
            
            # Activity Score 2.0 (Normal)
            "*1/*1": {"activity_score": 2.0, "phenotype": "Normal Metabolizer", "recommendation": "FULL_DOSE"},
            "NORMAL": {"activity_score": 2.0, "phenotype": "Normal Metabolizer", "recommendation": "FULL_DOSE"},
            "NO VARIANT": {"activity_score": 2.0, "phenotype": "Normal Metabolizer", "recommendation": "FULL_DOSE"},
        },
        "drugs": ["5-fluorouracil", "5-fu", "capecitabine", "tegafur", "fluoropyrimidine"],
        "source": "CPIC Guideline for DPYD and Fluoropyrimidines (2017 Update)",
        "pmid": "29152729"
    },
    
    # -------------------------------------------------------------------------
    # TPMT + Thiopurines (6-MP, Azathioprine)
    # Reference: Relling et al. Clin Pharmacol Ther. 2019;105(5):1095-1105
    # -------------------------------------------------------------------------
    "TPMT": {
        "variants": {
            # Poor Metabolizer (deficient)
            "*3A/*3A": {"activity_score": 0, "phenotype": "Poor Metabolizer", "recommendation": "REDUCE_90_OR_AVOID"},
            "*3A/*3C": {"activity_score": 0, "phenotype": "Poor Metabolizer", "recommendation": "REDUCE_90_OR_AVOID"},
            "*3B/*3B": {"activity_score": 0, "phenotype": "Poor Metabolizer", "recommendation": "REDUCE_90_OR_AVOID"},
            "*3C/*3C": {"activity_score": 0, "phenotype": "Poor Metabolizer", "recommendation": "REDUCE_90_OR_AVOID"},
            "*2/*2": {"activity_score": 0, "phenotype": "Poor Metabolizer", "recommendation": "REDUCE_90_OR_AVOID"},
            "*2/*3A": {"activity_score": 0, "phenotype": "Poor Metabolizer", "recommendation": "REDUCE_90_OR_AVOID"},
            "DEFICIENCY": {"activity_score": 0, "phenotype": "Poor Metabolizer", "recommendation": "REDUCE_90_OR_AVOID"},
            
            # Intermediate Metabolizer
            "*1/*2": {"activity_score": 1, "phenotype": "Intermediate Metabolizer", "recommendation": "REDUCE_30_70"},
            "*1/*3A": {"activity_score": 1, "phenotype": "Intermediate Metabolizer", "recommendation": "REDUCE_30_70"},
            "*1/*3B": {"activity_score": 1, "phenotype": "Intermediate Metabolizer", "recommendation": "REDUCE_30_70"},
            "*1/*3C": {"activity_score": 1, "phenotype": "Intermediate Metabolizer", "recommendation": "REDUCE_30_70"},
            "*3A": {"activity_score": 1, "phenotype": "Intermediate Metabolizer", "recommendation": "REDUCE_30_70"},  # Heterozygous assumed
            
            # Normal Metabolizer
            "*1/*1": {"activity_score": 2, "phenotype": "Normal Metabolizer", "recommendation": "FULL_DOSE"},
            "NORMAL": {"activity_score": 2, "phenotype": "Normal Metabolizer", "recommendation": "FULL_DOSE"},
            "NO VARIANT": {"activity_score": 2, "phenotype": "Normal Metabolizer", "recommendation": "FULL_DOSE"},
        },
        "drugs": ["6-mercaptopurine", "6-mp", "mercaptopurine", "azathioprine", "thioguanine"],
        "source": "CPIC Guideline for TPMT/NUDT15 and Thiopurines (2018 Update)",
        "pmid": "30447069"
    },
    
    # -------------------------------------------------------------------------
    # UGT1A1 + Irinotecan
    # Reference: Gammal et al. Clin Pharmacol Ther. 2016;99(4):363-369
    # -------------------------------------------------------------------------
    "UGT1A1": {
        "variants": {
            # Poor Metabolizer (homozygous *28 or *6)
            "*28/*28": {"activity_score": 0, "phenotype": "Poor Metabolizer", "recommendation": "REDUCE_30_PLUS"},
            "*6/*6": {"activity_score": 0, "phenotype": "Poor Metabolizer", "recommendation": "REDUCE_30_PLUS"},
            "*6/*28": {"activity_score": 0, "phenotype": "Poor Metabolizer", "recommendation": "REDUCE_30_PLUS"},
            "(TA)7/(TA)7": {"activity_score": 0, "phenotype": "Poor Metabolizer", "recommendation": "REDUCE_30_PLUS"},
            
            # Intermediate Metabolizer (heterozygous)
            "*1/*28": {"activity_score": 1, "phenotype": "Intermediate Metabolizer", "recommendation": "FULL_OR_REDUCE"},
            "*1/*6": {"activity_score": 1, "phenotype": "Intermediate Metabolizer", "recommendation": "FULL_OR_REDUCE"},
            "(TA)6/(TA)7": {"activity_score": 1, "phenotype": "Intermediate Metabolizer", "recommendation": "FULL_OR_REDUCE"},
            
            # Normal Metabolizer
            "*1/*1": {"activity_score": 2, "phenotype": "Normal Metabolizer", "recommendation": "FULL_DOSE"},
            "(TA)6/(TA)6": {"activity_score": 2, "phenotype": "Normal Metabolizer", "recommendation": "FULL_DOSE"},
            "NORMAL": {"activity_score": 2, "phenotype": "Normal Metabolizer", "recommendation": "FULL_DOSE"},
            "NO VARIANT": {"activity_score": 2, "phenotype": "Normal Metabolizer", "recommendation": "FULL_DOSE"},
        },
        "drugs": ["irinotecan", "cpt-11"],
        "source": "CPIC Guideline for UGT1A1 and Irinotecan (2016)",
        "pmid": "26818858"
    }
}

# ============================================================================
# RECOMMENDATION MAPPING
# Maps our system's output to CPIC categories
# ============================================================================

def normalize_recommendation(our_rec: Dict) -> str:
    """
    Normalize our system's recommendation to CPIC categories.
    """
    if our_rec is None:
        return "UNKNOWN"
    
    # Check for AVOID/contraindicated
    if our_rec.get("should_avoid", False):
        return "AVOID"
    
    # Check adjustment factor
    adj_factor = our_rec.get("adjustment_factor", 1.0)
    risk_level = our_rec.get("risk_level", "").upper()
    
    if adj_factor <= 0.1:
        return "REDUCE_90_OR_AVOID"
    elif adj_factor <= 0.25:
        return "REDUCE_75"
    elif adj_factor <= 0.5:
        return "REDUCE_50"
    elif adj_factor <= 0.75:
        return "REDUCE_25"
    elif adj_factor >= 0.95:
        return "FULL_DOSE"
    else:
        return "REDUCE_MODERATE"


def cpic_recommendation_matches(cpic_rec: str, our_rec: str) -> Tuple[bool, str]:
    """
    Check if our recommendation matches CPIC guideline.
    
    Returns: (is_concordant, match_type)
    match_type: "EXACT", "CONSERVATIVE", "LESS_CONSERVATIVE", "MISMATCH"
    """
    # Define recommendation hierarchy (lower = more conservative)
    hierarchy = {
        "AVOID": 0,
        "REDUCE_90_OR_AVOID": 1,
        "REDUCE_75": 2,
        "REDUCE_50": 3,
        "REDUCE_30_70": 3,  # Same level as 50%
        "REDUCE_30_PLUS": 3,
        "REDUCE_25": 4,
        "REDUCE_MODERATE": 4,
        "FULL_OR_REDUCE": 5,
        "FULL_DOSE": 6,
        "UNKNOWN": -1
    }
    
    cpic_level = hierarchy.get(cpic_rec, -1)
    our_level = hierarchy.get(our_rec, -1)
    
    if cpic_level == -1 or our_level == -1:
        return False, "UNKNOWN"
    
    if cpic_level == our_level:
        return True, "EXACT"
    elif our_level < cpic_level:
        # We are more conservative (lower = more reduction)
        return True, "MORE_CONSERVATIVE"
    else:
        # We are less conservative (higher = less reduction)
        return False, "LESS_CONSERVATIVE"


def normalize_variant(variant: str, gene: str) -> str:
    """
    Normalize variant string for lookup in CPIC database.
    """
    if not variant:
        return "NO VARIANT"
    
    v = variant.upper().strip()
    
    # Handle deficiency mentions
    if "DEFICIENC" in v:
        return "DEFICIENCY"
    
    # Handle specific DPYD variants
    if gene == "DPYD":
        if "C.2846A>T" in v or "D949V" in v:
            return "c.2846A>T"
        if "C.1905+1G>A" in v or "*2A" in v:
            if "HOMOZYGOUS" in v or "/*2A" in v:
                return "*2A/*2A"
            return "*1/*2A"
        if "C.1679T>G" in v or "*13" in v:
            return "*1/*13"
        if "C.1903A>G" in v:
            return "c.1903A>G"
    
    # Handle TPMT variants
    if gene == "TPMT":
        if "*3A/*3A" in v:
            return "*3A/*3A"
        if "*3A" in v:
            return "*3A"  # Heterozygous assumed
        if "*1/*3A" in v:
            return "*1/*3A"
    
    # Handle UGT1A1 variants
    if gene == "UGT1A1":
        if "*28/*28" in v or "(TA)7/(TA)7" in v:
            return "*28/*28"
        if "*28" in v:
            return "*1/*28"
    
    return v


def get_cpic_recommendation(gene: str, variant: str, drug: str = None) -> Optional[Dict]:
    """
    Get CPIC guideline recommendation for a variant.
    """
    gene = gene.upper()
    
    if gene not in CPIC_GUIDELINES:
        return None
    
    guideline = CPIC_GUIDELINES[gene]
    normalized_variant = normalize_variant(variant, gene)
    
    # Look up variant
    if normalized_variant in guideline["variants"]:
        cpic_data = guideline["variants"][normalized_variant]
        return {
            "gene": gene,
            "variant": normalized_variant,
            "phenotype": cpic_data["phenotype"],
            "activity_score": cpic_data["activity_score"],
            "recommendation": cpic_data["recommendation"],
            "source": guideline["source"],
            "pmid": guideline["pmid"]
        }
    
    # Try to find partial match
    for var_key, var_data in guideline["variants"].items():
        if normalized_variant in var_key or var_key in normalized_variant:
            return {
                "gene": gene,
                "variant": var_key,
                "phenotype": var_data["phenotype"],
                "activity_score": var_data["activity_score"],
                "recommendation": var_data["recommendation"],
                "source": guideline["source"],
                "pmid": guideline["pmid"],
                "partial_match": True
            }
    
    return None


def validate_against_cpic(cases: List[Dict]) -> Dict:
    """
    Validate our recommendations against CPIC guidelines.
    
    Args:
        cases: List of validation cases with our predictions
        
    Returns:
        Concordance report with detailed results
    """
    results = {
        "total_cases": len(cases),
        "cases_with_cpic_match": 0,
        "concordance_results": [],
        "concordance_rate": 0.0,
        "exact_matches": 0,
        "conservative_matches": 0,
        "less_conservative": 0,
        "unknown_cases": 0,
        "by_gene": {},
        "by_recommendation": {},
        "timestamp": datetime.now().isoformat()
    }
    
    for case in cases:
        case_id = case.get("case_id", case.get("pmid", "unknown"))
        gene = case.get("gene", "").upper()
        variant = case.get("variant", "")
        drug = case.get("drug", "")
        our_prediction = case.get("our_prediction", {})
        
        # Get CPIC recommendation
        cpic = get_cpic_recommendation(gene, variant, drug)
        
        if cpic is None:
            results["concordance_results"].append({
                "case_id": case_id,
                "gene": gene,
                "variant": variant,
                "cpic_recommendation": None,
                "our_recommendation": normalize_recommendation(our_prediction),
                "concordant": None,
                "match_type": "NO_CPIC_DATA",
                "notes": f"No CPIC guideline found for {gene} {variant}"
            })
            results["unknown_cases"] += 1
            continue
        
        results["cases_with_cpic_match"] += 1
        
        # Normalize our recommendation
        our_rec_normalized = normalize_recommendation(our_prediction)
        
        # Check concordance
        is_concordant, match_type = cpic_recommendation_matches(
            cpic["recommendation"], 
            our_rec_normalized
        )
        
        result = {
            "case_id": case_id,
            "gene": gene,
            "variant": variant,
            "drug": drug,
            "cpic_phenotype": cpic["phenotype"],
            "cpic_recommendation": cpic["recommendation"],
            "our_recommendation": our_rec_normalized,
            "concordant": is_concordant,
            "match_type": match_type,
            "cpic_source": cpic["source"],
            "cpic_pmid": cpic["pmid"]
        }
        
        results["concordance_results"].append(result)
        
        # Update counts
        if match_type == "EXACT":
            results["exact_matches"] += 1
        elif match_type == "MORE_CONSERVATIVE":
            results["conservative_matches"] += 1
        elif match_type == "LESS_CONSERVATIVE":
            results["less_conservative"] += 1
        
        # Track by gene
        if gene not in results["by_gene"]:
            results["by_gene"][gene] = {"total": 0, "concordant": 0}
        results["by_gene"][gene]["total"] += 1
        if is_concordant:
            results["by_gene"][gene]["concordant"] += 1
    
    # Calculate concordance rate
    cases_evaluated = results["cases_with_cpic_match"]
    if cases_evaluated > 0:
        concordant_count = results["exact_matches"] + results["conservative_matches"]
        results["concordance_rate"] = concordant_count / cases_evaluated
        results["strict_concordance_rate"] = results["exact_matches"] / cases_evaluated
    
    # Calculate per-gene concordance
    for gene, stats in results["by_gene"].items():
        if stats["total"] > 0:
            stats["concordance_rate"] = stats["concordant"] / stats["total"]
    
    return results


def generate_cpic_concordance_report(results: Dict) -> str:
    """
    Generate a markdown report of CPIC concordance.
    """
    report = []
    report.append("# CPIC Guideline Concordance Report")
    report.append("")
    report.append(f"**Generated:** {results['timestamp']}")
    report.append(f"**Total Cases Evaluated:** {results['total_cases']}")
    report.append(f"**Cases with CPIC Match:** {results['cases_with_cpic_match']}")
    report.append("")
    
    report.append("## 📊 Overall Concordance")
    report.append("")
    concordance_pct = results['concordance_rate'] * 100
    strict_pct = results.get('strict_concordance_rate', 0) * 100
    
    report.append(f"| Metric | Value |")
    report.append(f"|--------|-------|")
    report.append(f"| **Overall Concordance** | **{concordance_pct:.1f}%** |")
    report.append(f"| Exact Matches | {results['exact_matches']} ({strict_pct:.1f}%) |")
    report.append(f"| More Conservative | {results['conservative_matches']} |")
    report.append(f"| Less Conservative | {results['less_conservative']} |")
    report.append(f"| Unknown/No CPIC Data | {results['unknown_cases']} |")
    report.append("")
    
    # Concordance visual
    report.append("### Concordance Breakdown")
    report.append("```")
    total_concordant = results['exact_matches'] + results['conservative_matches']
    if results['cases_with_cpic_match'] > 0:
        bar_filled = int(concordance_pct / 5)
        bar_empty = 20 - bar_filled
        report.append(f"[{'█' * bar_filled}{'░' * bar_empty}] {concordance_pct:.1f}% CPIC Concordant")
    report.append("```")
    report.append("")
    
    # Per-gene breakdown
    report.append("## 📈 Concordance by Gene")
    report.append("")
    report.append("| Gene | Total Cases | Concordant | Rate |")
    report.append("|------|-------------|------------|------|")
    for gene, stats in results["by_gene"].items():
        rate_pct = stats.get('concordance_rate', 0) * 100
        report.append(f"| {gene} | {stats['total']} | {stats['concordant']} | {rate_pct:.1f}% |")
    report.append("")
    
    # Detailed case results
    report.append("## 📋 Detailed Case Results")
    report.append("")
    
    # Group by match type
    exact_cases = [c for c in results['concordance_results'] if c.get('match_type') == 'EXACT']
    conservative_cases = [c for c in results['concordance_results'] if c.get('match_type') == 'MORE_CONSERVATIVE']
    less_conservative_cases = [c for c in results['concordance_results'] if c.get('match_type') == 'LESS_CONSERVATIVE']
    no_data_cases = [c for c in results['concordance_results'] if c.get('match_type') == 'NO_CPIC_DATA']
    
    if exact_cases:
        report.append("### ✅ Exact Matches")
        report.append("")
        report.append("| Case | Gene | Variant | CPIC | Ours |")
        report.append("|------|------|---------|------|------|")
        for c in exact_cases[:10]:
            report.append(f"| {c['case_id'][:20]} | {c['gene']} | {c['variant'][:20]} | {c['cpic_recommendation']} | {c['our_recommendation']} |")
        if len(exact_cases) > 10:
            report.append(f"| ... | ... | ... | ... | ... |")
            report.append(f"| *({len(exact_cases)} total)* | | | | |")
        report.append("")
    
    if conservative_cases:
        report.append("### 🔼 More Conservative (Acceptable)")
        report.append("")
        report.append("| Case | Gene | Variant | CPIC | Ours |")
        report.append("|------|------|---------|------|------|")
        for c in conservative_cases[:10]:
            report.append(f"| {c['case_id'][:20]} | {c['gene']} | {c['variant'][:20]} | {c['cpic_recommendation']} | {c['our_recommendation']} |")
        report.append("")
    
    if less_conservative_cases:
        report.append("### 🔽 Less Conservative (ATTENTION NEEDED)")
        report.append("")
        report.append("| Case | Gene | Variant | CPIC | Ours | Notes |")
        report.append("|------|------|---------|------|------|-------|")
        for c in less_conservative_cases:
            report.append(f"| {c['case_id'][:20]} | {c['gene']} | {c['variant'][:20]} | {c['cpic_recommendation']} | {c['our_recommendation']} | Review needed |")
        report.append("")
    
    if no_data_cases:
        report.append("### ❓ No CPIC Data Available")
        report.append("")
        report.append("| Case | Gene | Variant | Notes |")
        report.append("|------|------|---------|-------|")
        for c in no_data_cases[:10]:
            notes = c.get('notes', 'No CPIC guideline')
            report.append(f"| {c['case_id'][:20]} | {c['gene']} | {c['variant'][:20]} | {notes[:40]} |")
        report.append("")
    
    # Summary
    report.append("## 🎯 Summary")
    report.append("")
    if concordance_pct >= 90:
        report.append(f"✅ **EXCELLENT:** {concordance_pct:.1f}% concordance with CPIC guidelines")
        report.append("")
        report.append("Our dosing guidance system is well-aligned with CPIC expert consensus.")
    elif concordance_pct >= 75:
        report.append(f"✅ **GOOD:** {concordance_pct:.1f}% concordance with CPIC guidelines")
        report.append("")
        report.append("Our system shows good alignment with CPIC. Review less conservative cases.")
    else:
        report.append(f"⚠️ **NEEDS REVIEW:** {concordance_pct:.1f}% concordance with CPIC guidelines")
        report.append("")
        report.append("Some recommendations may need adjustment to better align with CPIC.")
    
    report.append("")
    report.append("---")
    report.append("")
    report.append("**CPIC References:**")
    report.append("1. DPYD: Amstutz et al. Clin Pharmacol Ther. 2018;103(2):210-216 (PMID: 29152729)")
    report.append("2. TPMT: Relling et al. Clin Pharmacol Ther. 2019;105(5):1095-1105 (PMID: 30447069)")
    report.append("3. UGT1A1: Gammal et al. Clin Pharmacol Ther. 2016;99(4):363-369 (PMID: 26818858)")
    
    return "\n".join(report)


def main():
    parser = argparse.ArgumentParser(description="Validate dosing guidance against CPIC guidelines")
    parser.add_argument("--input", "-i", required=True, help="Input JSON file with validation cases")
    parser.add_argument("--output", "-o", help="Output JSON file for concordance report")
    parser.add_argument("--report", "-r", help="Output markdown report file")
    args = parser.parse_args()
    
    # Load cases
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"❌ Error: Input file not found: {input_path}")
        sys.exit(1)
    
    print(f"📂 Loading cases from: {input_path}")
    with open(input_path) as f:
        data = json.load(f)
    
    # Handle different input formats
    if isinstance(data, list):
        cases = data
    elif isinstance(data, dict) and "cases" in data:
        cases = data["cases"]
    else:
        cases = [data]
    
    print(f"📊 Loaded {len(cases)} cases")
    
    # Run validation
    print("🔬 Validating against CPIC guidelines...")
    results = validate_against_cpic(cases)
    
    # Print summary
    print("")
    print("=" * 60)
    print("CPIC CONCORDANCE RESULTS")
    print("=" * 60)
    print(f"Total cases: {results['total_cases']}")
    print(f"Cases with CPIC match: {results['cases_with_cpic_match']}")
    print(f"Concordance rate: {results['concordance_rate']*100:.1f}%")
    print(f"  - Exact matches: {results['exact_matches']}")
    print(f"  - More conservative: {results['conservative_matches']}")
    print(f"  - Less conservative: {results['less_conservative']}")
    print(f"  - Unknown/No data: {results['unknown_cases']}")
    print("=" * 60)
    
    # Save JSON output
    output_path = args.output or input_path.with_name("cpic_concordance_report.json")
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\n✅ Concordance report saved to: {output_path}")
    
    # Generate and save markdown report
    report_path = args.report or input_path.with_name("CPIC_CONCORDANCE_REPORT.md")
    report = generate_cpic_concordance_report(results)
    with open(report_path, 'w') as f:
        f.write(report)
    print(f"✅ Markdown report saved to: {report_path}")
    
    # Return concordance status
    if results['concordance_rate'] >= 0.90:
        print("\n🎉 EXCELLENT: ≥90% CPIC concordance achieved!")
        return 0
    elif results['concordance_rate'] >= 0.75:
        print("\n✅ GOOD: ≥75% CPIC concordance achieved")
        return 0
    else:
        print("\n⚠️ WARNING: Concordance below 75% - review needed")
        return 1


if __name__ == "__main__":
    sys.exit(main())

