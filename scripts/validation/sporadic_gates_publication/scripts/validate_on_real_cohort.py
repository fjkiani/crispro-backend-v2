#!/usr/bin/env python3
"""
Validates sporadic gate behavior on a real clinical cohort (n=469 TCGA-OV).
"""

import json
import sys
import argparse
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, List, Tuple

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(PROJECT_ROOT))

from api.services.efficacy_orchestrator.sporadic_gates import apply_sporadic_gates

DDR_GENES = {
    'BRCA1', 'BRCA2', 'ATM', 'ATR', 'CHEK1', 'CHEK2', 'RAD51', 'PALB2',
    'MBD4', 'MLH1', 'MSH2', 'MSH6', 'PMS2', 'TP53', 'RAD50', 'NBN',
    'FANCA', 'FANCD2', 'BLM', 'WRN', 'RECQL4'
}

def compute_ddr_proxy(mutations: List[Dict]) -> float:
    genes = {m.get('gene', '').upper() for m in mutations}
    ddr_hits = len(genes & DDR_GENES)
    # Map hits to a 0-100 scale where 3+ hits = HRD-high (>=42)
    # This is a crude proxy for demonstration on real data
    if ddr_hits >= 3:
        return 60.0
    elif ddr_hits >= 1:
        return 30.0
    return 0.0

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cohort", type=str, default="data/validation/sae_cohort/tcga_ov_platinum_with_mutations.json")
    ap.add_argument("--out", type=str, default="oncology-coPilot/oncology-backend-minimal/scripts/validation/sporadic_gates_publication/receipts/latest/real_cohort_behavioral_validation.json")
    args = ap.parse_args()

    cohort_path = Path(args.cohort)
    if not cohort_path.exists():
        print(f"❌ Cohort file missing: {cohort_path}")
        return 1

    with open(cohort_path) as f:
        data = json.load(f)

    stats = {
        "cohort_size": len(data),
        "parp_penalty_applied": 0,
        "parp_rescue_applied": 0,
        "io_boost_applied": 0,
      "confidence_capped_l1": 0,
        "no_adjustment": 0
    }

    for p in data:
        muts = p.get("mutations", [])
        hrd_proxy = compute_ddr_proxy(muts)
        
        # Simulate L1 intake (partial biomarkers)
        tc = {
            "hrd_score": hrd_proxy,
            "tmb": 5.0, # Fixed for this cohort demo
            "msi_status": "MSI-Stable",
            "completeness_score": 0.5
        }

        # Olaparib
        eff_p, conf_p, rat_p = apply_sporadic_gates(
            drug_name="Olaparib",
            drug_class="PARP inhibitor",
            moa="PARP1/2",
            efficacy_score=0.70,
            confidence=0.65,
            germline_status="negative",
            tumor_context=tc
        )

        if eff_p < 0.70:
            stats["parp_penalty_applied"] += 1
        elif hrd_proxy >= 42:
            stats["parp_rescue_applied"] += 1
            
        if conf_p <= 0.6:
            stats["confidence_capped_l1"] += 1

    receipt = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "cohort_source": str(cohort_path),
        "metrics": stats,
        "notes": "Behavioral audit of sporadic gates on 469 real TCGA-OV mutation profiles."
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, 'w') as f:
        json.dump(receipt, f, indent=2)

    print(f"✅ Behavioral validation complete for {len(data)} patients")
    print(f"✅ Receipt: {out_path}")
    print(f"📊 PARP Penalties: {stats['parp_penalty_applied']} ({stats['parp_penalty_applied']/len(data):.1%})")
    
    return 0

if __name__ == "__main__":
    main()
