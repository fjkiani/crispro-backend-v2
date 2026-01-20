#!/usr/bin/env python3
"""Validation Runner (CI/Demo-friendly)

Runs deterministic offline validations that back our demo claims:
- TRUE SAE diamonds contracts + single-feature AUROC floors (+ optional multifeature if sklearn installed)
- OV NF1 playbook correctness (separate NF1 fixture)
- Existing mechanism validators (trial matching + resistance prophet)

Run:
  python scripts/validation/run_validations.py
"""

import subprocess
import sys
from pathlib import Path

VALIDATORS = [
    "validate_true_sae_diamonds.py",
    "validate_ov_nf1_playbook.py",
    "validate_092_mechanism_fit_claim.py",
    # existing validators already in repo
    "validate_mbd4_tp53_mechanism_capabilities.py",
    "validate_mechanism_trial_matching.py",
    "validate_mechanism_resistance_prediction.py",
]


def main() -> int:
    base = Path(__file__).resolve().parent
    repo_root = base.parent.parent  # oncology-backend-minimal/

    failures = []
    for v in VALIDATORS:
        path = base / v
        if not path.exists():
            failures.append((v, 2))
            print(f"❌ Missing validator: {path}")
            continue

        print("\n" + "=" * 80)
        print(f"RUNNING: {v}")
        print("=" * 80)

        proc = subprocess.run([sys.executable, str(path)], cwd=str(repo_root))
        if proc.returncode != 0:
            failures.append((v, proc.returncode))

    print("\n" + "=" * 80)
    if not failures:
        print("✅ ALL VALIDATIONS PASSED")
        return 0

    print("❌ VALIDATIONS FAILED")
    for v, code in failures:
        print(f"- {v}: exit {code}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
