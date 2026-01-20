#!/usr/bin/env python3
"""Mechanism Fit Claim Validator (Demo-Safe)

Validates the *mechanism fit* claim for a DDR-high patient:
- DDR-targeting trials (ddr > 0.5 in `trial_moa_vectors.json`) should have **high** mechanism fit
- Non-DDR trials should have **low** mechanism fit

Why this exists:
- We use this as an offline, deterministic check that our cosine-similarity ranker
  is behaving sanely and supports demo messaging like "DDR-high → DDR trials fit well".

NOTE:
- This validates **mechanism_fit_score** from `MechanismFitRanker`.
- It does NOT validate TRUE-SAE DDR_bin scores (separate concept).

Run:
  python scripts/validation/validate_092_mechanism_fit_claim.py
"""

import json
import os
import statistics
import sys
from pathlib import Path

# Add oncology-backend-minimal/ to sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

try:
    from api.services.mechanism_fit_ranker import MechanismFitRanker
    from api.services.pathway_to_mechanism_vector import convert_moa_dict_to_vector
except ImportError as e:
    print(f"❌ Import failed: {e}")
    raise SystemExit(2)


def summarize(name: str, values: list[float]) -> str:
    if not values:
        return f"{name}: EMPTY"
    return (
        f"{name}: n={len(values)} mean={sum(values)/len(values):.3f} "
        f"median={statistics.median(values):.3f} min={min(values):.3f} max={max(values):.3f}"
    )


def main() -> int:
    script_dir = Path(__file__).resolve().parent
    moa_path = script_dir.parent.parent / "api" / "resources" / "trial_moa_vectors.json"

    if not moa_path.exists():
        print(f"❌ Trial MoA vectors file not found: {moa_path}")
        return 2

    trial_moa_vectors = json.loads(moa_path.read_text())

    print("=" * 60)
    print("MECHANISM FIT VALIDATION: DDR-high patient")
    print("=" * 60)

    # DDR-high patient mechanism vector (7D): [DDR, MAPK, PI3K, VEGF, HER2, IO, Efflux]
    # This is intentionally deterministic and offline.
    patient_mechanism_vector = [0.88, 0.12, 0.05, 0.02, 0.0, 0.0, 0.0]
    print(f"Patient Mechanism Vector: {patient_mechanism_vector}")
    print(f"Total Trials with MoA Vectors: {len(trial_moa_vectors)}")

    ranker = MechanismFitRanker(alpha=0.7, beta=0.3)

    # Prepare trials for scoring
    trials = []
    for nct_id, data in trial_moa_vectors.items():
        moa_dict = data.get("moa_vector") or {}
        moa_vector = convert_moa_dict_to_vector(moa_dict, use_7d=True)

        trials.append(
            {
                "nct_id": nct_id,
                # Titles aren't stored in trial_moa_vectors.json (vectors-only resource)
                "title": nct_id,
                # Eligibility is not the point of this validator; keep constant.
                "eligibility_score": 0.85,
                "moa_vector": moa_vector,
            }
        )

    # IMPORTANT: allow min_mechanism_fit=0.0 so we can compare DDR vs non-DDR separation.
    ranked_scores = ranker.rank_trials(
        trials=trials,
        sae_mechanism_vector=patient_mechanism_vector,
        min_eligibility=0.60,
        min_mechanism_fit=0.0,
    )

    # Split by DDR tag in MoA dict
    ddr_scores: list[float] = []
    non_ddr_scores: list[float] = []

    for score in ranked_scores:
        moa_dict = (trial_moa_vectors.get(score.nct_id, {}) or {}).get("moa_vector") or {}
        ddr_value = float(moa_dict.get("ddr", 0.0) or 0.0)
        if ddr_value > 0.5:
            ddr_scores.append(score.mechanism_fit_score)
        else:
            non_ddr_scores.append(score.mechanism_fit_score)

    print()
    print(summarize("DDR trials (ddr>0.5)", ddr_scores))
    print(summarize("Non-DDR trials (ddr<=0.5)", non_ddr_scores))

    if not ddr_scores:
        print("❌ No DDR trials found (ddr>0.5). Check MoA tagging.")
        return 1
    if not non_ddr_scores:
        print("❌ No non-DDR trials found. Check MoA tagging.")
        return 1

    mean_ddr = sum(ddr_scores) / len(ddr_scores)
    mean_non = sum(non_ddr_scores) / len(non_ddr_scores)
    delta = mean_ddr - mean_non

    # Demo-safe acceptance criteria (intentionally loose, but meaningful)
    # - DDR trials should be strongly aligned
    # - Non-DDR should be mostly orthogonal
    # - There should be clear separation
    min_mean_ddr = 0.92
    max_mean_non = 0.20
    min_delta = 0.60

    print()
    print("=" * 60)
    print("CLAIM VERIFICATION")
    print("=" * 60)
    print(f"Mean DDR fit: {mean_ddr:.3f} (target ≥ {min_mean_ddr})")
    print(f"Mean non-DDR fit: {mean_non:.3f} (target ≤ {max_mean_non})")
    print(f"Separation Δ(mean): {delta:.3f} (target ≥ {min_delta})")

    ok = True
    if mean_ddr < min_mean_ddr:
        print(f"❌ FAIL: mean DDR fit {mean_ddr:.3f} < {min_mean_ddr}")
        ok = False
    if mean_non > max_mean_non:
        print(f"❌ FAIL: mean non-DDR fit {mean_non:.3f} > {max_mean_non}")
        ok = False
    if delta < min_delta:
        print(f"❌ FAIL: separation Δ {delta:.3f} < {min_delta}")
        ok = False

    if ok:
        print("✅ PASS: Mechanism fit behaves as expected for DDR-high patient")
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())

