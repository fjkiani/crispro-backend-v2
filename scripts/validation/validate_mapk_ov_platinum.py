#!/usr/bin/env python3
"""
MAPK Pathway Validation for OV Platinum Resistance
Computes actual RR from TCGA-OV cohort (not hard-coded)

Source of Truth: .cursor/MOAT/RESISTANCE_PROPHET_PRODUCTION_AUDIT.md
Task: Phase 2.1 - Create MAPK Validation Script

MAPK gene set: KRAS, NRAS, BRAF, NF1, MAP2K1, MAP2K2
"""

import json
import numpy as np
from scipy import stats
from pathlib import Path
from datetime import datetime

# MAPK gene set (from audit)
MAPK_GENES = {"KRAS", "NRAS", "BRAF", "NF1", "MAP2K1", "MAP2K2"}

# Note: NF1 is validated separately with RR=2.10
# This script validates the FULL MAPK pathway as a group


def load_tcga_ov_cohort(cohort_path: str) -> list:
    """Load TCGA-OV cohort with platinum response labels"""
    with open(cohort_path) as f:
        return json.load(f)


def has_mapk_mutation(patient: dict, exclude_nf1: bool = False) -> bool:
    """
    Check if patient has any MAPK pathway mutation
    
    Args:
        patient: Patient dict with mutations list
        exclude_nf1: If True, exclude NF1 (already validated separately)
    """
    mutations = patient.get("mutations", [])
    patient_genes = {m.get("gene", "").upper() for m in mutations}
    
    gene_set = MAPK_GENES.copy()
    if exclude_nf1:
        gene_set.discard("NF1")
    
    return bool(patient_genes & gene_set)


def get_mapk_genes_in_patient(patient: dict) -> set:
    """Get which MAPK genes are mutated in patient"""
    mutations = patient.get("mutations", [])
    patient_genes = {m.get("gene", "").upper() for m in mutations}
    return patient_genes & MAPK_GENES


def compute_contingency_table(cohort: list, exclude_nf1: bool = False) -> dict:
    """Compute 2x2 contingency table"""
    mapk_resistant = 0
    mapk_sensitive = 0
    wt_resistant = 0
    wt_sensitive = 0
    
    mapk_genes_found = set()
    
    for patient in cohort:
        # Determine resistance status
        response = patient.get("platinum_response", "").lower()
        is_resistant = response in ["resistant", "refractory"]
        
        is_mapk = has_mapk_mutation(patient, exclude_nf1=exclude_nf1)
        
        if is_mapk:
            mapk_genes_found.update(get_mapk_genes_in_patient(patient))
        
        if is_mapk and is_resistant:
            mapk_resistant += 1
        elif is_mapk and not is_resistant:
            mapk_sensitive += 1
        elif not is_mapk and is_resistant:
            wt_resistant += 1
        else:
            wt_sensitive += 1
    
    return {
        "mapk_resistant": mapk_resistant,
        "mapk_sensitive": mapk_sensitive,
        "wt_resistant": wt_resistant,
        "wt_sensitive": wt_sensitive,
        "mapk_genes_found": list(mapk_genes_found)
    }


def compute_relative_risk(table: dict) -> dict:
    """Compute RR with 95% CI"""
    a = table["mapk_resistant"]
    b = table["mapk_sensitive"]
    c = table["wt_resistant"]
    d = table["wt_sensitive"]
    
    n_mapk = a + b
    n_wt = c + d
    
    if n_mapk == 0:
        return {
            "error": "No MAPK mutations found in cohort",
            "n_mapk": 0,
            "n_wt": n_wt,
            "action": "CANNOT_VALIDATE"
        }
    
    if n_wt == 0:
        return {"error": "No wildtype patients", "action": "CANNOT_VALIDATE"}
    
    risk_mapk = a / n_mapk if n_mapk > 0 else 0
    risk_wt = c / n_wt if n_wt > 0 else 0
    
    if risk_wt == 0:
        return {
            "error": "Zero resistance rate in wildtype (cannot compute RR)",
            "n_mapk": n_mapk,
            "n_wt": n_wt,
            "risk_mapk": risk_mapk,
            "risk_wt": risk_wt,
            "action": "CANNOT_VALIDATE"
        }
    
    rr = risk_mapk / risk_wt
    
    # 95% CI using log method
    try:
        if a > 0 and c > 0:
            log_rr = np.log(rr)
            se_log_rr = np.sqrt((1/a - 1/n_mapk) + (1/c - 1/n_wt))
            ci_lower = np.exp(log_rr - 1.96 * se_log_rr)
            ci_upper = np.exp(log_rr + 1.96 * se_log_rr)
        else:
            ci_lower = 0
            ci_upper = float('inf')
    except Exception:
        ci_lower = 0
        ci_upper = float('inf')
    
    # Chi-square test
    try:
        contingency = [[a, b], [c, d]]
        chi2, p_value, dof, expected = stats.chi2_contingency(contingency)
    except Exception as e:
        chi2 = 0
        p_value = 1.0
    
    significant = p_value < 0.05
    target_rr_met = rr >= 1.5
    
    return {
        "relative_risk": round(rr, 3),
        "ci_lower": round(ci_lower, 3) if ci_lower != float('inf') else None,
        "ci_upper": round(ci_upper, 3) if ci_upper != float('inf') else None,
        "p_value": round(p_value, 4),
        "chi2": round(chi2, 3),
        "n_mapk": n_mapk,
        "n_wt": n_wt,
        "risk_mapk": round(risk_mapk, 4),
        "risk_wt": round(risk_wt, 4),
        "significant": significant,
        "target_rr_met": target_rr_met,
        "action": "COHORT_VALIDATED" if (significant and target_rr_met) else "LITERATURE_BASED"
    }


def main():
    """Main validation runner"""
    # Try multiple possible cohort paths
    possible_paths = [
        "data/validation/tcga_ov_platinum_response_with_genomics.json",
        "tools/benchmarks/tcga_ov_platinum_response_with_genomics.json",
        "data/validation/tcga_ov_469_with_hrd.json",
        "../data/validation/tcga_ov_platinum_response_with_genomics.json"
    ]
    
    cohort = None
    cohort_path_used = None
    
    for path in possible_paths:
        try:
            cohort = load_tcga_ov_cohort(path)
            cohort_path_used = path
            print(f"✓ Loaded cohort from: {path}")
            break
        except FileNotFoundError:
            continue
    
    if cohort is None:
        print("❌ ERROR: Could not find TCGA-OV cohort file")
        print("   Checked paths:")
        for p in possible_paths:
            print(f"     - {p}")
        
        # Create empty report indicating data not found
        output_dir = Path("scripts/validation/out/mapk_ov_platinum")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        report = {
            "status": "DATA_NOT_FOUND",
            "error": "TCGA-OV cohort file not found",
            "paths_checked": possible_paths,
            "action": "CANNOT_VALIDATE",
            "timestamp": datetime.now().isoformat()
        }
        
        with open(output_dir / "report.json", "w") as f:
            json.dump(report, f, indent=2)
        
        return
    
    output_dir = Path("scripts/validation/out/mapk_ov_platinum")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Run full MAPK validation
    print(f"\n=== MAPK Pathway Validation (Full) ===")
    table = compute_contingency_table(cohort, exclude_nf1=False)
    result = compute_relative_risk(table)
    
    print(f"  MAPK genes found: {table.get('mapk_genes_found', [])}")
    print(f"  Contingency table:")
    print(f"    MAPK+ Resistant: {table['mapk_resistant']}")
    print(f"    MAPK+ Sensitive: {table['mapk_sensitive']}")
    print(f"    WT Resistant: {table['wt_resistant']}")
    print(f"    WT Sensitive: {table['wt_sensitive']}")
    
    if "error" not in result:
        print(f"\n  Results:")
        print(f"    RR: {result.get('relative_risk')} [{result.get('ci_lower')}, {result.get('ci_upper')}]")
        print(f"    p-value: {result.get('p_value')}")
        print(f"    Significant (p<0.05): {result.get('significant')}")
        print(f"    Target RR ≥ 1.5: {result.get('target_rr_met')}")
        print(f"    Action: {result.get('action')}")
    else:
        print(f"\n  Error: {result.get('error')}")
        print(f"  Action: {result.get('action')}")
    
    # Run MAPK excluding NF1 (since NF1 is validated separately)
    print(f"\n=== MAPK Pathway Validation (Excluding NF1) ===")
    table_no_nf1 = compute_contingency_table(cohort, exclude_nf1=True)
    result_no_nf1 = compute_relative_risk(table_no_nf1)
    
    print(f"  MAPK genes found (no NF1): {[g for g in table_no_nf1.get('mapk_genes_found', []) if g != 'NF1']}")
    print(f"  n_mapk (no NF1): {result_no_nf1.get('n_mapk', 0)}")
    
    if "error" not in result_no_nf1 and result_no_nf1.get('n_mapk', 0) > 0:
        print(f"  RR (no NF1): {result_no_nf1.get('relative_risk')}")
        print(f"  p-value: {result_no_nf1.get('p_value')}")
        print(f"  Action: {result_no_nf1.get('action')}")
    else:
        print(f"  Not enough non-NF1 MAPK mutations for separate validation")
    
    # Generate report
    report = {
        "endpoint_contract": "ov_platinum_response_tcga_style",
        "cohort_path": cohort_path_used,
        "cohort_size": len(cohort),
        "gene_set": list(MAPK_GENES),
        "timestamp": datetime.now().isoformat(),
        
        "full_mapk": {
            "contingency_table": {k: v for k, v in table.items() if k != 'mapk_genes_found'},
            "mapk_genes_found": table.get('mapk_genes_found', []),
            "result": result
        },
        
        "mapk_excluding_nf1": {
            "contingency_table": {k: v for k, v in table_no_nf1.items() if k != 'mapk_genes_found'},
            "mapk_genes_found": [g for g in table_no_nf1.get('mapk_genes_found', []) if g != 'NF1'],
            "result": result_no_nf1
        },
        
        "acceptance": {
            "target_rr": 1.5,
            "target_p": 0.05,
            "full_mapk_passed": result.get("action") == "COHORT_VALIDATED",
            "mapk_no_nf1_passed": result_no_nf1.get("action") == "COHORT_VALIDATED"
        },
        
        "recommendation": {
            "for_kras_entry": result.get("action", "LITERATURE_BASED"),
            "relative_risk_to_use": result.get("relative_risk") if result.get("action") == "COHORT_VALIDATED" else None,
            "note": "If COHORT_VALIDATED, update resistance_playbook_service.py KRAS entry. Otherwise keep as LITERATURE_BASED with relative_risk=None"
        }
    }
    
    with open(output_dir / "report.json", "w") as f:
        json.dump(report, f, indent=2)
    
    print(f"\n✓ Report saved to: {output_dir / 'report.json'}")
    print(f"\n=== FINAL RECOMMENDATION ===")
    print(f"  Action for KRAS entry: {report['recommendation']['for_kras_entry']}")
    if report['recommendation']['relative_risk_to_use']:
        print(f"  Use RR: {report['recommendation']['relative_risk_to_use']}")
    else:
        print(f"  Keep relative_risk: None (not validated)")


if __name__ == "__main__":
    main()

