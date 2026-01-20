#!/usr/bin/env python3
"""TRUE SAE Diamonds Validation (Tier-3)

What this validates (regression gates):
- Tier-3 cohort + results artifacts are present and consistent
- Label contract: positive class == resistant + refractory
- Diamond features list is stable (direction=higher_in_resistant)
- Always-on: single-feature AUROC for a few diamonds stays above a floor
- Optional (if sklearn installed): recompute multi-feature CV AUROC and compare to stored baseline

Run:
  python scripts/validation/validate_true_sae_diamonds.py
"""

import json
import sys
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]

TIER3_PATH = REPO_ROOT / "data/validation/sae_cohort/checkpoints/Tier3_validation_cohort.json"
RESULTS_PATH = REPO_ROOT / "data/validation/sae_cohort/checkpoints/sae_validation_results.json"
BASELINE_PATH = REPO_ROOT / "data/validation/sae_cohort/checkpoints/true_sae_diamonds_baseline.v1.json"
MAPPING_PATH = REPO_ROOT / "api/resources/sae_feature_mapping.true_sae_diamonds.v1.json"

REPORT_DIR = Path(__file__).resolve().parent


@dataclass
class CheckResult:
    name: str
    passed: bool
    details: str
    metrics: Dict[str, Any]


def _load_json(path: Path) -> Any:
    with open(path, "r") as f:
        return json.load(f)


def _assert(cond: bool, msg: str):
    if not cond:
        raise AssertionError(msg)


def _patient_feature_value(pdata: Dict[str, Any], feat_idx: int) -> float:
    """Aggregate feature value across all variants for a patient (sum)."""
    s = 0.0
    for v in pdata.get("variants", []) or []:
        for tf in v.get("top_features", []) or []:
            if tf.get("index") == feat_idx:
                s += float(tf.get("value", 0.0) or 0.0)
    return s


def _auc_roc(y_true: List[int], scores: List[float]) -> float:
    """AUROC via Mann–Whitney U (handles ties)."""
    pairs = list(zip(scores, y_true))
    pairs.sort(key=lambda x: x[0])

    n_pos = sum(y_true)
    n_neg = len(y_true) - n_pos
    _assert(n_pos > 0 and n_neg > 0, "Need both positive and negative samples for AUROC")

    ranks = [0.0] * len(pairs)
    i = 0
    r = 1
    while i < len(pairs):
        j = i
        while j < len(pairs) and pairs[j][0] == pairs[i][0]:
            j += 1
        avg_rank = (r + (r + (j - i) - 1)) / 2.0
        for k in range(i, j):
            ranks[k] = avg_rank
        r += (j - i)
        i = j

    sum_ranks_pos = sum(rank for rank, (_, y) in zip(ranks, pairs) if y == 1)
    u = sum_ranks_pos - (n_pos * (n_pos + 1) / 2.0)
    return float(u / (n_pos * n_neg))


def _prepare_ids_labels(patients: Dict[str, Any]) -> Tuple[List[str], List[int]]:
    ids: List[str] = []
    y: List[int] = []
    for pid, pdata in patients.items():
        out = pdata.get("outcome")
        if out not in ("sensitive", "resistant", "refractory"):
            continue
        ids.append(pid)
        y.append(1 if out in ("resistant", "refractory") else 0)
    return ids, y


def _try_recompute_multifeature_auc(patients: Dict[str, Any], feature_list: List[int], y: List[int]) -> Dict[str, Any]:
    """Optional: recompute multi-feature AUROC via sklearn if available."""
    try:
        import numpy as np
        from sklearn.linear_model import LogisticRegression
        from sklearn.model_selection import StratifiedKFold
        from sklearn.metrics import roc_auc_score
    except Exception as e:
        return {"status": "skipped", "reason": f"sklearn unavailable: {e}"}

    ids, _ = _prepare_ids_labels(patients)
    X = []
    for pid in ids:
        pdata = patients[pid]
        X.append([_patient_feature_value(pdata, fidx) for fidx in feature_list])

    X = np.asarray(X, dtype=float)
    y_np = np.asarray(y, dtype=int)

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    aucs: List[float] = []
    fold_meta: List[Dict[str, Any]] = []

    for fold, (train_idx, test_idx) in enumerate(cv.split(X, y_np), start=1):
        model = LogisticRegression(max_iter=3000, class_weight="balanced", random_state=42)
        model.fit(X[train_idx], y_np[train_idx])
        prob = model.predict_proba(X[test_idx])[:, 1]
        auc = float(roc_auc_score(y_np[test_idx], prob))
        aucs.append(auc)
        fold_meta.append({"fold": fold, "test_size": int(len(test_idx)), "test_positive": int(y_np[test_idx].sum()), "auroc": auc})

    return {
        "status": "computed",
        "mean_auroc": float(sum(aucs) / len(aucs)),
        "fold_auroc": aucs,
        "fold_meta": fold_meta,
    }


def main() -> int:
    checks: List[CheckResult] = []
    overall = True

    try:
        # Presence
        _assert(TIER3_PATH.exists(), f"Missing Tier-3 cohort: {TIER3_PATH}")
        _assert(RESULTS_PATH.exists(), f"Missing Tier-3 results: {RESULTS_PATH}")
        _assert(BASELINE_PATH.exists(), f"Missing baseline JSON: {BASELINE_PATH}")
        _assert(MAPPING_PATH.exists(), f"Missing mapping JSON: {MAPPING_PATH}")

        tier3 = _load_json(TIER3_PATH)
        results = _load_json(RESULTS_PATH)
        baseline = _load_json(BASELINE_PATH)
        mapping = _load_json(MAPPING_PATH)

        patients = tier3.get("data", {})
        _assert(isinstance(patients, dict) and len(patients) > 0, "Tier-3 cohort has no patients")

        ids, y = _prepare_ids_labels(patients)
        expected_total = int(results["cohort_stats"]["total_patients"])
        expected_pos = int(results["cohort_stats"]["resistant"])  # includes refractory
        expected_neg = int(results["cohort_stats"]["sensitive"])

        _assert(len(y) == expected_total, f"Tier-3 usable patients mismatch: got {len(y)} expected {expected_total}")
        _assert(sum(y) == expected_pos, f"Positive class mismatch: got {sum(y)} expected {expected_pos}")
        _assert((len(y) - sum(y)) == expected_neg, f"Negative class mismatch: got {len(y)-sum(y)} expected {expected_neg}")

        checks.append(CheckResult(
            "label_contract",
            True,
            "Tier-3 labels consistent (pos = resistant + refractory)",
            {"total": len(y), "pos": int(sum(y)), "neg": int(len(y) - sum(y))},
        ))

        large_effect = results["analysis"]["large_effect_list"]
        diamonds = [x for x in large_effect if x.get("direction") == "higher_in_resistant"]
        diamond_ids = sorted([int(x["feature_index"]) for x in diamonds])
        mapping_ids = sorted([int(x["feature_index"]) for x in mapping.get("features", [])])

        _assert(len(diamond_ids) == 9, f"Expected 9 higher_in_resistant diamonds, got {len(diamond_ids)}")
        _assert(set(diamond_ids) == set(mapping_ids), "Diamonds list mismatch between results and mapping JSON")

        checks.append(CheckResult(
            "diamond_list",
            True,
            "Diamond feature list stable and matches mapping JSON",
            {"diamond_ids": diamond_ids},
        ))

        # Always-on: single-feature AUROC floors for top 3 diamonds
        # (These are the exact ones we’ve previously quoted as ~0.64–0.65.)
        single_feature_floor = 0.60
        single_results = {}
        for feat in [1407, 27607, 12893]:
            scores = [_patient_feature_value(patients[pid], feat) for pid in ids]
            auc = _auc_roc(y, scores)
            single_results[str(feat)] = {"auroc": auc, "nonzero_patients": int(sum(1 for s in scores if s != 0.0))}
            _assert(auc >= single_feature_floor, f"Single-feature AUROC too low for {feat}: {auc:.3f}")

        checks.append(CheckResult(
            "single_feature_auc",
            True,
            f"Single-feature AUROC clears floor (>= {single_feature_floor})",
            single_results,
        ))

        # Optional: multi-feature AUROC recompute (if sklearn available)
        feature_list = baseline["features"]["feature_list"]
        stored_mean = float(baseline["results"]["mean_auroc"])

        recompute = _try_recompute_multifeature_auc(patients, feature_list, y)
        if recompute.get("status") == "computed":
            new_mean = float(recompute["mean_auroc"])
            _assert(new_mean >= 0.70, f"Multi-feature AUROC gate failed: {new_mean:.3f} < 0.70")
            _assert(abs(new_mean - stored_mean) <= 0.03, f"Multi-feature AUROC drift too large: stored={stored_mean:.3f}, new={new_mean:.3f}")
            checks.append(CheckResult(
                "multifeature_auc",
                True,
                "Multi-feature AUROC recompute matches stored baseline and clears threshold",
                {"stored_mean": stored_mean, **recompute},
            ))
        else:
            checks.append(CheckResult(
                "multifeature_auc",
                True,
                "Skipped (sklearn not installed) — single-feature + contracts still validated",
                recompute,
            ))

    except Exception as e:
        overall = False
        checks.append(CheckResult("exception", False, f"{type(e).__name__}: {e}", {}))

    report = {
        "timestamp": datetime.utcnow().isoformat(),
        "validator": "validate_true_sae_diamonds",
        "overall_passed": overall,
        "checks": [asdict(c) for c in checks],
    }

    out_path = REPORT_DIR / f"true_sae_diamonds_report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
    out_path.write_text(json.dumps(report, indent=2))

    print(json.dumps(report, indent=2))
    print(f"\nWrote report: {out_path}")
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())
