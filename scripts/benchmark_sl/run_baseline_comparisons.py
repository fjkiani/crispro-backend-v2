#!/usr/bin/env python3
"""Baseline comparison script for synthetic lethality benchmark.

Doctrine-aligned outputs:
- Standard report schema: {provenance, summary, cases[]}
- Metrics separated:
  - Positives: Class@1 and Drug@1
  - Negatives: PARP false-positive rate
- Identical denominators across Random / Rule / S/P/E (cache-misses count as wrong)

Compares:
1) Random baseline
2) Rule baseline: IF DDR gene THEN PARP
3) S/P/E model: top drug from cached /api/efficacy/predict responses (cache-first)
"""

import json
import os
import random
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Drug candidates (include some non-PARP mechanisms so the hard-set can be meaningful)
DRUG_CANDIDATES = [
    "Olaparib",
    "Niraparib",
    "Rucaparib",
    "Talazoparib",
    "Ceralasertib",  # ATR
    "Adavosertib",  # WEE1
    "Trametinib",   # MEK (MAPK)
]

# DDR genes that trigger PARP recommendation in the baseline
DDR_GENES = [
    "BRCA1",
    "BRCA2",
    "ATM",
    "ATR",
    "CHEK1",
    "CHEK2",
    "PALB2",
    "RAD51C",
    "RAD51D",
    "MBD4",
]

PARP_DRUGS = {"olaparib", "niraparib", "rucaparib", "talazoparib"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _env_flags() -> Dict[str, str]:
    keys = [
        "DISABLE_LITERATURE",
        "DISABLE_FUSION",
        "EVO_FORCE_MODEL",
        "EVO_USE_DELTA_ONLY",
        "GUIDANCE_FAST",
    ]
    return {k: os.getenv(k, "") for k in keys}


def drug_class(drug_name: Optional[str]) -> str:
    if not drug_name:
        return "none"
    d = drug_name.strip().lower()
    if d in PARP_DRUGS:
        return "parp"
    if d == "ceralasertib":
        return "atr"
    if d == "adavosertib":
        return "wee1"
    if d == "trametinib":
        return "mapk"
    # fallback
    return "other"


def random_baseline(_: List[Dict[str, Any]]) -> str:
    return random.choice(DRUG_CANDIDATES)


def rule_based_baseline(mutations: List[Dict[str, Any]]) -> str:
    genes = [(m.get("gene") or "").strip().upper() for m in mutations]
    if any(g in DDR_GENES for g in genes):
        return "Olaparib"
    return random.choice(DRUG_CANDIDATES)


def load_cache(cache_file: Path = Path("cache/mock_responses.json")) -> Dict[str, Any]:
    if cache_file.exists():
        with open(cache_file, "r") as f:
            return json.load(f)
    return {}


def get_spe_prediction(case_id: str, cache: Dict[str, Any]) -> Dict[str, Any]:
    """Return {drug, confidence, cache_hit}.

    Cache schema: {case_id: {drugs:[{name, confidence, ...}], ...}}
    """
    if case_id not in cache:
        return {"drug": None, "confidence": 0.0, "cache_hit": False}

    pred = cache[case_id] or {}
    drugs = pred.get("drugs") or []
    if not drugs:
        return {"drug": None, "confidence": 0.0, "cache_hit": True}

    top = max(drugs, key=lambda d: float(d.get("confidence", 0) or 0))
    return {
        "drug": top.get("name"),
        "confidence": float(top.get("confidence", 0) or 0),
        "cache_hit": True,
    }


def _lower_list(xs: List[str]) -> List[str]:
    return [x.lower() for x in xs if isinstance(x, str) and x]


def run_baseline_comparisons(test_file: str = "test_cases_pilot.json", use_cache: bool = True) -> Dict[str, Any]:
    with open(test_file, "r") as f:
        test_cases = json.load(f)

    cache = load_cache() if use_cache else {}

    run_id = str(uuid.uuid4())

    # Aggregate counters
    pos_n = 0
    neg_n = 0

    agg = {
        "random": {"pos_class_correct": 0, "pos_drug_correct": 0, "neg_parp_fp": 0, "spe_cache_miss": 0},
        "rule": {"pos_class_correct": 0, "pos_drug_correct": 0, "neg_parp_fp": 0, "spe_cache_miss": 0},
        "spe": {"pos_class_correct": 0, "pos_drug_correct": 0, "neg_parp_fp": 0, "spe_cache_miss": 0},
    }

    cases_out: List[Dict[str, Any]] = []

    for case in test_cases:
        case_id = case.get("case_id") or ""
        mutations = case.get("mutations") or []
        gt = case.get("ground_truth") or {}

        gt_drugs = _lower_list(gt.get("effective_drugs") or [])
        is_positive = bool(gt_drugs)

        if is_positive:
            pos_n += 1
        else:
            neg_n += 1

        gt_classes = sorted({drug_class(d) for d in gt_drugs if d})

        # Predictions
        pred_random = random_baseline(mutations)
        pred_rule = rule_based_baseline(mutations)

        spe = get_spe_prediction(case_id, cache) if use_cache else {"drug": None, "confidence": 0.0, "cache_hit": False}
        pred_spe = spe.get("drug")

        # For denominator fairness: if S/P/E missing for a positive, it counts as wrong
        if is_positive and not pred_spe:
            agg["spe"]["spe_cache_miss"] += 1

        preds = {
            "random": {"drug": pred_random, "class": drug_class(pred_random)},
            "rule": {"drug": pred_rule, "class": drug_class(pred_rule)},
            "spe": {"drug": pred_spe, "class": drug_class(pred_spe), "confidence": spe.get("confidence", 0.0), "cache_hit": spe.get("cache_hit", False)},
        }

        evals: Dict[str, Any] = {}

        for model_key in ("random", "rule", "spe"):
            pred_drug = preds[model_key].get("drug")
            pred_drug_l = (pred_drug or "").lower() if pred_drug else ""
            pred_cls = preds[model_key].get("class")

            if is_positive:
                class_correct = pred_cls in gt_classes if pred_cls else False
                drug_correct = pred_drug_l in gt_drugs if pred_drug_l else False

                agg[model_key]["pos_class_correct"] += int(class_correct)
                agg[model_key]["pos_drug_correct"] += int(drug_correct)

                evals[model_key] = {"class_at1": class_correct, "drug_at1": drug_correct}
            else:
                # Negative controls: we track PARP false positives explicitly
                parp_fp = pred_cls == "parp"
                agg[model_key]["neg_parp_fp"] += int(parp_fp)
                evals[model_key] = {"neg_parp_fp": parp_fp}

        cases_out.append(
            {
                "case_id": case_id,
                "disease": case.get("disease"),
                "label": {
                    "is_positive": is_positive,
                    "effective_drugs": gt.get("effective_drugs") or [],
                    "effective_classes": gt_classes,
                },
                "predictions": preds,
                "eval": evals,
            }
        )

    def rate(num: int, den: int) -> float:
        return (num / den) if den else 0.0

    metrics = {}
    for model_key in ("random", "rule", "spe"):
        metrics[model_key] = {
            "positive": {
                "n": pos_n,
                "class_at1": rate(agg[model_key]["pos_class_correct"], pos_n),
                "drug_at1": rate(agg[model_key]["pos_drug_correct"], pos_n),
            },
            "negative": {
                "n": neg_n,
                "parp_fp_rate": rate(agg[model_key]["neg_parp_fp"], neg_n),
            },
        }
        if model_key == "spe":
            metrics[model_key]["positive"]["cache_miss_rate"] = rate(agg[model_key]["spe_cache_miss"], pos_n)
            metrics[model_key]["cache"]= {"enabled": bool(use_cache), "size": len(cache)}

    report = {
        "provenance": {
            "run_id": run_id,
            "created_at": _now_iso(),
            "script": "run_baseline_comparisons.py",
            "dataset": test_file,
            "flags": _env_flags(),
        },
        "summary": {
            "n_total": len(test_cases),
            "n_positive": pos_n,
            "n_negative": neg_n,
            "metrics": metrics,
        },
        "cases": cases_out,
    }

    out_path = Path("results/baseline_comparison_cached.json")
    out_path.parent.mkdir(exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(report, f, indent=2)

    # Print a concise summary
    print("=" * 60)
    print("Baseline Comparison Results (Doctrine Schema)")
    print("=" * 60)
    for k in ("random", "rule", "spe"):
        pos = report["summary"]["metrics"][k]["positive"]
        neg = report["summary"]["metrics"][k]["negative"]
        extra = ""
        if k == "spe":
            extra = f" | cache_miss={pos.get('cache_miss_rate', 0):.1%}"
        print(
            f"{k.upper():<6} pos(Class@1={pos['class_at1']:.1%}, Drug@1={pos['drug_at1']:.1%}) | "
            f"neg(PARP_FP={neg['parp_fp_rate']:.1%}){extra}"
        )
    print(f"\n✅ Results saved to {out_path}")

    return report


if __name__ == "__main__":
    import sys

    test_file = sys.argv[1] if len(sys.argv) > 1 else "test_cases_pilot.json"
    run_baseline_comparisons(test_file, use_cache=True)
