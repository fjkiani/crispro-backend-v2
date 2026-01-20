#!/usr/bin/env python3
"""
PI3K Pathway Validation for OV Platinum Resistance
Computes actual RR from TCGA-OV cohort

Source of Truth: .cursor/MOAT/RESISTANCE_PROPHET_PRODUCTION_AUDIT.md
Task: Phase 2.2 - Create PI3K Validation Script

Claim from docs: PI3K RR = 1.39, p=0.02
Issue: Not found in code - need to verify
"""

import json
import numpy as np
from scipy import stats
from pathlib import Path
from datetime import datetime

# PI3K gene set
PI3K_GENES = {"PIK3CA", "PIK3CB", "PIK3R1", "AKT1", "AKT2", "PTEN"}


def load_tcga_ov_cohort(cohort_path: str) -> list:
    """Load TCGA-OV cohort with platinum response labels"""
    with open(cohort_path) as f:
        return json.load(f)


def has_pi3k_mutation(patient: dict) -> bool:
    """Check if patient has any PI3K pathway mutation"""
    mutations = patient.get("mutations", [])
    patient_genes = {m.get("gene", "").upper() for m in mutations}
    return bool(patient_genes & PI3K_GENES)


def get_pi3k_genes_in_patient(patient: dict) -> set:
    """Get which PI3K genes are mutated in patient"""
    mutations = patient.get("mutations", [])
    patient_genes = {m.get("gene", "").upper() for m in mutations}
    return patient_genes & PI3K_GENES


def compute_contingency_table(cohort: list) -> dict:
    """Compute 2x2 contingency table"""
    pi3k_resistant = 0
    pi3k_sensitive = 0
    wt_resistant = 0
    wt_sensitive = 0
    
    pi3k_genes_found = set()
    
    for patient in cohort:
        response = patient.get("platinum_response", "").lower()
        is_resistant = response in ["resistant", "refractory"]
        
        is_pi3k = has_pi3k_mutation(patient)
        
        if is_pi3k:
            pi3k_genes_found.update(get_pi3k_genes_in_patient(patient))
        
        if is_pi3k and is_resistant:
            pi3k_resistant += 1
        elif is_pi3k and not is_resistant:
            pi3k_sensitive += 1
        elif not is_pi3k and is_resistant:
            wt_resistant += 1
        else:
            wt_sensitive += 1
    
    return {
        "pi3k_resistant": pi3k_resistant,
        "pi3k_sensitive": pi3k_sensitive,
        "wt_resistant": wt_resistant,
        "wt_sensitive": wt_sensitive,
        "pi3k_genes_found": list(pi3k_genes_found)
    }


def compute_relative_risk(table: dict) -> dict:
    """Compute RR with 95% CI"""
    a = table["pi3k_resistant"]
    b = table["pi3k_sensitive"]
    c = table["wt_resistant"]
    d = table["wt_sensitive"]
    
    n_pi3k = a + b
    n_wt = c + d
    
    if n_pi3k == 0:
        return {
            "error": "No PI3K mutations found in cohort",
            "n_pi3k": 0,
            "n_wt": n_wt,
            "action": "CANNOT_VALIDATE"
        }
    
    if n_wt == 0:
        return {"error": "No wildtype patients", "action": "CANNOT_VALIDATE"}
    
    risk_pi3k = a / n_pi3k if n_pi3k > 0 else 0
    risk_wt = c / n_wt if n_wt > 0 else 0
    
    if risk_wt == 0:
        return {
            "error": "Zero resistance rate in wildtype",
            "n_pi3k": n_pi3k,
            "n_wt": n_wt,
            "risk_pi3k": risk_pi3k,
            "risk_wt": risk_wt,
            "action": "CANNOT_VALIDATE"
        }
    
    rr = risk_pi3k / risk_wt
    
    # 95% CI using log method
    try:
        if a > 0 and c > 0:
            log_rr = np.log(rr)
            se_log_rr = np.sqrt((1/a - 1/n_pi3k) + (1/c - 1/n_wt))
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
    except Exception:
        chi2 = 0
        p_value = 1.0
    
    significant = p_value < 0.05
    target_rr_met = rr >= 1.3  # Lower threshold for PI3K (claimed RR=1.39)
    
    return {
        "relative_risk": round(rr, 3),
        "ci_lower": round(ci_lower, 3) if ci_lower != float('inf') else None,
        "ci_upper": round(ci_upper, 3) if ci_upper != float('inf') else None,
        "p_value": round(p_value, 4),
        "chi2": round(chi2, 3),
        "n_pi3k": n_pi3k,
        "n_wt": n_wt,
        "risk_pi3k": round(risk_pi3k, 4),
        "risk_wt": round(risk_wt, 4),
        "significant": significant,
        "target_rr_met": target_rr_met,
        "action": "COHORT_VALIDATED" if (significant and target_rr_met) else (
            "TREND" if (not significant and rr >= 1.2 and p_value < 0.15) else "LITERATURE_BASED"
        )
    }


def main():
    """Main validation runner"""
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
        
        output_dir = Path("scripts/validation/out/pi3k_ov_platinum")
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
    
    output_dir = Path("scripts/validation/out/pi3k_ov_platinum")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"\n=== PI3K Pathway Validation ===")
    table = compute_contingency_table(cohort)
    result = compute_relative_risk(table)
    
    print(f"  PI3K genes found: {table.get('pi3k_genes_found', [])}")
    print(f"  Contingency table:")
    print(f"    PI3K+ Resistant: {table['pi3k_resistant']}")
    print(f"    PI3K+ Sensitive: {table['pi3k_sensitive']}")
    print(f"    WT Resistant: {table['wt_resistant']}")
    print(f"    WT Sensitive: {table['wt_sensitive']}")
    
    if "error" not in result:
        print(f"\n  Results:")
        print(f"    RR: {result.get('relative_risk')} [{result.get('ci_lower')}, {result.get('ci_upper')}]")
        print(f"    p-value: {result.get('p_value')}")
        print(f"    Significant (p<0.05): {result.get('significant')}")
        print(f"    Target RR ≥ 1.3: {result.get('target_rr_met')}")
        print(f"    Action: {result.get('action')}")
        
        # Compare to claim
        claimed_rr = 1.39
        claimed_p = 0.02
        print(f"\n  Comparison to Documentation Claim:")
        print(f"    Claimed RR: {claimed_rr}, Computed RR: {result.get('relative_risk')}")
        print(f"    Claimed p: {claimed_p}, Computed p: {result.get('p_value')}")
        
        if abs(result.get('relative_risk', 0) - claimed_rr) < 0.2:
            print(f"    ✓ RR is close to claimed value")
        else:
            print(f"    ⚠ RR differs significantly from claim")
    else:
        print(f"\n  Error: {result.get('error')}")
        print(f"  Action: {result.get('action')}")
    
    report = {
        "endpoint_contract": "ov_platinum_response_tcga_style",
        "cohort_path": cohort_path_used,
        "cohort_size": len(cohort),
        "gene_set": list(PI3K_GENES),
        "timestamp": datetime.now().isoformat(),
        
        "contingency_table": {k: v for k, v in table.items() if k != 'pi3k_genes_found'},
        "pi3k_genes_found": table.get('pi3k_genes_found', []),
        "result": result,
        
        "documented_claim": {
            "relative_risk": 1.39,
            "p_value": 0.02,
            "source": "02_RESISTANCE_PREDICTION.md"
        },
        
        "acceptance": {
            "target_rr": 1.3,
            "target_p": 0.05,
            "passed": result.get("action") == "COHORT_VALIDATED"
        },
        
        "recommendation": {
            "action": result.get("action", "LITERATURE_BASED"),
            "add_to_playbook": result.get("action") == "COHORT_VALIDATED",
            "relative_risk_to_use": result.get("relative_risk") if result.get("action") == "COHORT_VALIDATED" else None,
            "note": "If COHORT_VALIDATED, add PIK3CA to resistance_playbook_service.py OV section. Otherwise remove claim from docs."
        }
    }
    
    with open(output_dir / "report.json", "w") as f:
        json.dump(report, f, indent=2)
    
    print(f"\n✓ Report saved to: {output_dir / 'report.json'}")
    print(f"\n=== FINAL RECOMMENDATION ===")
    print(f"  Action: {report['recommendation']['action']}")
    print(f"  Add to playbook: {report['recommendation']['add_to_playbook']}")


if __name__ == "__main__":
    main()

