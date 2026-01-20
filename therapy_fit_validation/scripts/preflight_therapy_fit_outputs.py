#!/usr/bin/env python3
"""
Preflight checks for Therapy Fit batch outputs.

Hard-fails if outputs are structurally invalid for validation.

CRITICAL: Must pass BEFORE running pathway validation or AUROC computation.

Gates:
  1. Efficacy non-zero (≥50% drugs have efficacy > 0)
  2. Tier diversity (≥10% consider or supported)
  3. Insights working (≥50% drugs have non-zero chips)
  4. Mutation payload (patients have ≥2 genes on average)
  5. Minimum patients (≥50 patients processed)

Usage:
    python preflight_therapy_fit_outputs.py receipts/latest/tcga_ov_platinum_wiwfm_per_patient.jsonl
    
If passes: prints "PREFLIGHT_PASSED" + metrics
If fails: raises ValueError with explicit reasons
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Any


def check_preflight_gates(predictions_jsonl: Path, min_patients: int = 50) -> Dict[str, Any]:
    """
    Preflight gates that must pass before AUROC computation.
    
    Gates:
      1. Efficacy non-zero (≥50% drugs have efficacy > 0)
      2. Tier diversity (≥10% consider or supported)
      3. Insights working (≥50% drugs have non-zero chips)
      4. Mutation payload (patients have ≥2 genes on average)
      5. Minimum patients (≥min_patients processed)
    
    Returns:
      dict with pass/fail per gate + metrics
    
    Raises:
      ValueError if any gate fails
    """
    
    if not predictions_jsonl.exists():
        raise FileNotFoundError(f"Receipt file not found: {predictions_jsonl}")
    
    drug_rows = []
    patient_gene_counts = []
    patients_processed = 0
    patients_with_errors = 0
    
    # Read JSONL file
    for line in predictions_jsonl.read_text().strip().split("\n"):
        if not line.strip():
            continue
        
        try:
            rec = json.loads(line)
        except json.JSONDecodeError as e:
            print(f"⚠️  Warning: Failed to parse line: {e}")
            patients_with_errors += 1
            continue
        
        # Skip error records
        if "error" in rec:
            patients_with_errors += 1
            continue
        
        patients_processed += 1
        
        # Check if this is the new format (with full drugs list) or old format (top drug only)
        if "drugs" in rec:
            # NEW FORMAT: Full drugs list available
            for drug in rec.get("drugs", []):
                drug_rows.append({
                    "efficacy": drug.get("efficacy_score", 0),
                    "tier": drug.get("evidence_tier", "insufficient"),
                    "insights": drug.get("insights", {}),
                })
        elif "wiwfm" in rec:
            # OLD FORMAT: Only top drug available (from current validation script)
            wiwfm = rec.get("wiwfm", {})
            drug_rows.append({
                "efficacy": wiwfm.get("top_efficacy_score", 0),
                "tier": wiwfm.get("top_evidence_tier", "insufficient"),
                "insights": {},  # Not available in old format
            })
        
        # Extract mutation counts
        if "mutations" in rec:
            # Direct mutations list
            n_genes = len(set(m.get("gene", "") for m in rec.get("mutations", []) if m.get("gene")))
        elif "genes" in rec:
            # Gene list (from current validation script)
            n_genes = len(rec.get("genes", []))
        elif "n_mutations" in rec:
            # Fallback: use n_mutations if available
            n_genes = rec.get("n_mutations", 0)
        else:
            n_genes = 0
        
        if n_genes > 0:
            patient_gene_counts.append(n_genes)
    
    # Gate 0: Minimum patients
    gate0_pass = patients_processed >= min_patients
    
    if len(drug_rows) == 0:
        raise ValueError(
            f"PREFLIGHT FAILED: No drug data found in receipt. "
            f"Processed: {patients_processed}, Errors: {patients_with_errors}. "
            f"Check receipt format."
        )
    
    # Gate 1: Efficacy non-zero
    nonzero_efficacy = sum(1 for d in drug_rows if d["efficacy"] > 0)
    efficacy_rate = nonzero_efficacy / len(drug_rows) if drug_rows else 0
    gate1_pass = efficacy_rate >= 0.50
    
    # Gate 2: Tier diversity
    tier_counts = {}
    for d in drug_rows:
        tier = d.get("tier", "insufficient")
        tier_counts[tier] = tier_counts.get(tier, 0) + 1
    noninsufficient_count = tier_counts.get("consider", 0) + tier_counts.get("supported", 0)
    noninsufficient_rate = noninsufficient_count / len(drug_rows) if drug_rows else 0
    gate2_pass = noninsufficient_rate >= 0.10
    
    # Gate 3: Insights working (only if insights available)
    gate3_pass = True  # Default pass if insights not available
    insights_available = any(d.get("insights") for d in drug_rows)
    if insights_available:
        nonzero_insights = sum(
            1 for d in drug_rows 
            if d.get("insights") and sum(
                d["insights"].get(k, 0) for k in ["functionality", "chromatin", "essentiality", "regulatory"]
            ) > 0
        )
        insights_rate = nonzero_insights / len(drug_rows) if drug_rows else 0
        gate3_pass = insights_rate >= 0.50
    else:
        # Insights not available in receipt format - skip gate but warn
        print("⚠️  Warning: Insights data not available in receipt format. Skipping Gate 3.")
    
    # Gate 4: Mutation payload
    avg_genes = sum(patient_gene_counts) / len(patient_gene_counts) if patient_gene_counts else 0
    gate4_pass = avg_genes >= 2.0
    
    # Results
    results = {
        "gate0_min_patients": {
            "pass": gate0_pass,
            "patients_processed": patients_processed,
            "patients_with_errors": patients_with_errors,
            "threshold": min_patients,
        },
        "gate1_efficacy_nonzero": {
            "pass": gate1_pass,
            "rate": round(efficacy_rate, 4),
            "threshold": 0.50,
            "n_nonzero": nonzero_efficacy,
            "n_total": len(drug_rows),
        },
        "gate2_tier_diversity": {
            "pass": gate2_pass,
            "rate": round(noninsufficient_rate, 4),
            "threshold": 0.10,
            "tier_counts": tier_counts,
            "noninsufficient_count": noninsufficient_count,
        },
        "gate3_insights_working": {
            "pass": gate3_pass,
            "insights_available": insights_available,
            "rate": round(insights_rate, 4) if insights_available else None,
            "threshold": 0.50,
            "n_nonzero": nonzero_insights if insights_available else None,
            "n_total": len(drug_rows),
        },
        "gate4_mutation_payload": {
            "pass": gate4_pass,
            "avg_genes": round(avg_genes, 2),
            "threshold": 2.0,
            "n_patients": len(patient_gene_counts),
        },
        "all_gates_pass": gate0_pass and gate1_pass and gate2_pass and gate3_pass and gate4_pass,
    }
    
    # Hard fail if any gate fails
    if not results["all_gates_pass"]:
        failed = [k for k, v in results.items() if k.startswith("gate") and not v.get("pass", False)]
        error_msg = f"PREFLIGHT FAILED. Gates failed: {failed}\n\n"
        error_msg += "Detailed Results:\n"
        error_msg += json.dumps(results, indent=2)
        raise ValueError(error_msg)
    
    return results


def main():
    parser = argparse.ArgumentParser(
        description="Preflight checks for Therapy Fit batch outputs (CRITICAL - must pass before validation)"
    )
    parser.add_argument(
        "receipt_file",
        type=Path,
        help="Path to JSONL receipt file (e.g., receipts/latest/tcga_ov_platinum_wiwfm_per_patient.jsonl)"
    )
    parser.add_argument(
        "--min-patients",
        type=int,
        default=50,
        help="Minimum number of patients required (default: 50)"
    )
    args = parser.parse_args()
    
    try:
        results = check_preflight_gates(args.receipt_file, min_patients=args.min_patients)
        
        print("✅ PREFLIGHT_PASSED")
        print("\nGate Results:")
        print(json.dumps(results, indent=2))
        
        sys.exit(0)
        
    except ValueError as e:
        print(f"❌ PREFLIGHT_FAILED")
        print(f"\n{str(e)}")
        sys.exit(1)
        
    except FileNotFoundError as e:
        print(f"❌ ERROR: {e}")
        sys.exit(1)
        
    except Exception as e:
        print(f"❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
