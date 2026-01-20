#!/usr/bin/env python3
"""Publication suite runner for SL benchmark (doctrine-aligned).

What this produces
- Baselines: random + DDR→PARP rule
- Model: SP vs SPE (via /api/efficacy/predict) using deterministic fast-mode
- Optional ablations: S, P, E, SP, SE, PE, SPE

Outputs
- results/publication_suite_<timestamp>.json
- results/publication_suite_<timestamp>.md

Notes
- Uses Class@1 / Drug@1 on positives.
- Uses PARP FP rate on negatives.
- Includes bootstrap CIs for the above metrics.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx


PARP_DRUGS = {"olaparib", "niraparib", "rucaparib", "talazoparib"}
DDR_GENES = {
    "BRCA1",
    "CA2",
    "ATM",
    "ATR",
    "CHEK1",
    "CHEK2",
    "PALB2",
    "RAD51C",
    "RAD51D",
    "MBD4",
    "CDK12",
    "ARID1A",
}

DRUG_CANDIDATES = [
    "Olaparib",
    "Niraparib",
    "Rucaparib",
    "Talazoparib",
    "Ceralasertib",
    "Adavosertib",
    "Trametinib",
    "Bevacizumab",
    "Pembrolizumab",
]


def drug_class(drug: Optional[str]) -> str:
    d = (drug or "").lower().strip()
    if not d:
        return ""
    if d in PARP_DRUGS or "parp" in d:
        return "parp"
    if ("atr" in d) or ("ceralasertib" in d):
        return "atr"
    if "wee1" in d or "adavosertib" in d:
        return "wee1"
    if "mek" in d or "trametinib" in d:
        return "mek"
    if "vegf" in d or "bevacizumab" in d:
        return "vegf"
    if "pd-1" in d or "pembro" in d or "pembrolizumab" in d:
        return "io"
    if "platinum" in d or d in {"carboplatin", "cisplatin"}:
        return "platinum"
    return d


def _lower_list(xs: List[str]) -> List[str]:
    return [str(x).lower().strip() for x in xs if x]


def evaluate_case(case: Dict[str, Any], top_drug: Optional[str]) -> Dict[str, Any]:
    gt = case.get("ground_truth") or {}
    gt_drugs = _lower_list(gt.get("effective_drugs") or [])
    is_positive = bool(gt.get("synthetic_lethality_detected", False))

    gt_classes = sorted({drug_class(d) for d in gt_drugs if d})
    pred_cls = drug_class(top_drug)
    pred_drug_l = (top_drug or "").lower().strip() if top_drug else ""

    if is_positive:
        return {
            "is_positive": True,
            "gt_drugs": gt.get("effective_drugs") or [],
            "gt_classes": gt_classes,
            "class_at1": bool(pred_cls and pred_cls in gt_classes),
            "drug_at1": bool(pred_drug_l and pred_drug_l in gt_drugs),
        }

    return {
        "is_positive": False,
        "gt_drugs": [],
        "gt_classes": [],
        "neg_parp_fp": pred_cls == "parp",
    }


def bootstrap_ci(values: List[int], n_boot: int = 2000, seed: int = 1337) -> Tuple[float, float]:
    """Bootstrap 95% CI for a proportion-like metric (values are 0/1)."""
    if not values:
        return (0.0, 0.0)
    rng = random.Random(seed)
    n = len(values)
    stats = []
    for _ in range(n_boot):
        samp = [values[rng.randrange(n)] for _ in range(n)]
        stats.append(sum(samp) / n)
    stats.sort()
    lo = stats[int(0.025 * n_boot)]
    hi = stats[int(0.975 * n_boot)]
    return lo, hi


async def call_efficacy(
    client: httpx.AsyncClient,
    *,
    api_root: str,
    model_id: str,
    case: Dict[str, Any],
    ablation_mode: str,
    timeout_s: float,
) -> Dict[str, Any]:
    payload = {
        "model_id": model_id,
        "mutations": case.get("mutations") or [],
        "disease": case.get("disease", "ovarian_cancer"),
        "ablation_mode": ablation_mode,
        "options": {
            "adaptive": True,
            "ensemble": False,
            "fast": True,
            "panel_id": "sl_publication",
        },
    }
    resp = await client.post(f"{api_root}/api/efficacy/predict", json=payload, timeout=timeout_s)
    resp.raise_for_status()
    return resp.json()


def top_drug_from_prediction(pred: Dict[str, Any]) -> Tuple[Optional[str], float, Optional[str]]:
    drugs = pred.get("drugs") or []
    if not drugs:
        return None, 0.0, None

    # Deterministic tie-break: sort by (confidence desc, name asc)
    def key(d: Dict[str, Any]):
        return (-float(d.get("confidence", 0.0) or 0.0), str(d.get("name", "")).lower())

    top = sorted(drugs, key=key)[0]
    return top.get("name"), float(top.get("confidence", 0.0) or 0.0), top.get("moa")


def baseline_random() -> str:
    return random.choice(DRUG_CANDIDATES)


def baseline_rule_ddr_to_parp(muts: List[Dict[str, Any]]) -> str:
    genes = {(m.get("gene") or "").upper() for m in (muts or [])}
    if any(g in DDR_GENES for g in genes):
        return "Olaparib"
    return random.choice(DRUG_CANDIDATES)


async def run_method_api(
    *,
    name: str,
    cases: List[Dict[str, Any]],
    api_root: str,
    model_id: str,
    ablation_mode: str,
    timeout_s: float,
    max_concurrent: int,
) -> Dict[str, Any]:
    sem = asyncio.Semaphore(max_concurrent)

    async def one(case: Dict[str, Any]) -> Dict[str, Any]:
        async with sem:
            async with httpx.AsyncClient() as client:
                pred = await call_efficacy(
                    client,
                    api_root=api_root,
                    model_id=model_id,
                    case=case,
                    ablation_mode=ablation_mode,
                    timeout_s=timeout_s,
                )
        top_name, top_conf, top_moa = top_drug_from_prediction(pred)
        ev = evaluate_case(case, top_name)
        return {
            "case_id": case.get("case_id"),
            "disease": case.get("disease"),
            "prediction": {"top_drug": top_name, "top_class": drug_class(top_name), "confidence": top_conf, "moa": top_moa},
            "eval": ev,
        }

    rows = await asyncio.gather(*[one(c) for c in cases])
    return {"name": name, "ablation_mode": ablation_mode, "cases": rows}


def summarize(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    pos = [r for r in rows if r["eval"].get("is_positive")]
    neg = [r for r in rows if not r["eval"].get("is_positive")]

    pos_class = [1 if r["eval"].get("class_at1") else 0 for r in pos]
    pos_drug = [1 if r["eval"].get("drug_at1") else 0 for r in pos]
    neg_parp = [1 if r["eval"].get("neg_parp_fp") else 0 for r in neg]

    def rate(xs: List[int]) -> float:
        return (sum(xs) / len(xs)) if xs else 0.0

    return {
        "n_total": len(rows),
        "n_positive": len(pos),
        "n_negative": len(neg),
        "positive": {
            "class_at1": rate(pos_class),
            "drug_at1": rate(pos_drug),
            "class_at1_ci95": bootstrap_ci(pos_class),
            "drug_at1_ci95": bootstrap_ci(pos_drug),
        },
        "negative": {
            "parp_fp_rate": rate(neg_parp),
            "parp_fp_rate_ci95": bootstrap_ci(neg_parp),
        },
    }


def render_md(report: Dict[str, Any]) -> str:
    lines = []
    lines.append("## Publication suite results (100-case dataset)\n")
    lines.append(f"- **Dataset**: `{report['dataset_file']}`\n")
    lines.append(f"- **API**: `{report['api_root']}`\n")
    lines.append(f"- **Model**: `{report['model_id']}`\n")
    lines.append(f"- **Fast-mode**: True (no evidence calls)\n")
    lines.append("\n")

    lines.append("### Summary (positives + negatives)\n")
    lines.append("| Method | Pos Class@1 | 95% CI | Pos Drug@1 | 95% CI | Neg PARP FP | 95% CI |\n")
    lines.append("|---|---:|---:|---:|---:|---:|---:|\n")

    for m in report["methods"]:
        s = m["summary"]
        pc = s["positive"]["class_at1"]
        pcc = s["positive"]["class_at1_ci95"]
        pd = s["positive"]["drug_at1"]
        pdc = s["positive"]["drug_at1_ci95"]
        nf = s["negative"]["parp_fp_rate"]
        nfc = s["negative"]["parp_fp_rate_ci95"]
        lines.append(
            "| {name} | {pc:.1%} | [{pcl:.1%}, {pch:.1%}] | {pd:.1%} | [{pdl:.1%}, {pdh:.1%}] | {nf:.1%} | [{nfl:.1%}, {nfh:.1%}] |\n".format(
                name=m["name"],
                pc=pc,
                pcl=pcc[0],
                pch=pcc[1],
                pd=pd,
                pdl=pdc[0],
                pdh=pdc[1],
                nf=nf,
                nfl=nfc[0],
                nfh=nfc[1],
            )
        )

    lines.append("\n")
    return "".join(lines)


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--test-file", default="test_cases_100.json")
    ap.add_argument("--api-root", default="http://127.0.0.1:8000")
    ap.add_argument("--model-id", default="evo2_1b")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--max-concurrent", type=int, default=2)
    ap.add_argument("--timeout", type=float, default=120.0)
    ap.add_argument("--with-ablations", action="store_true")
    ap.add_argument("--seed", type=int, default=1337)
    args = ap.parse_args()

    random.seed(args.seed)

    test_path = Path(args.test_file)
    if not test_path.exists():
        raise SystemExit(f"Missing test file: {test_path}")

    cases = json.loads(test_path.read_text(encoding="utf-8"))
    if args.limit and args.limit > 0:
        cases = cases[: args.limit]

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    methods: List[Dict[str, Any]] = []

    # Baselines (deterministic seed)
    baseline_rows = []
    for c in cases:
        pred = baseline_random()
        ev = evaluate_case(c, pred)
        baseline_rows.append({
            "case_id": c.get("case_id"),
            "disease": c.get("disease"),
            "prediction": {"top_drug": pred, "top_class": drug_class(pred), "confidence": None, "moa": None},
            "eval": ev,
        })
    methods.append({"name": "Random", "kind": "baseline", "cases": baseline_rows})

    rule_rows = []
    for c in cases:
        pred = baseline_rule_ddr_to_parp(c.get("mutations") or [])
        ev = evaluate_case(c, pred)
        rule_rows.append({
            "case_id": c.get("case_id"),
            "disease": c.get("disease"),
            "prediction": {"top_drug": pred, "top_class": drug_class(pred), "confidence": None, "moa": None},
            "eval": ev,
        })
    methods.append({"name": "Rule (DDR→PARP)", "kind": "baseline", "cases": rule_rows})

    # Model profiles
    sp = await run_method_api(
        name="Model SP",
        cases=cases,
        api_root=args.api_root,
        model_id=args.model_id,
        ablation_mode="SP",
        timeout_s=args.timeout,
        max_concurrent=args.max_concurrent,
    )
    methods.append({"name": sp["name"], "kind": "model", "ablation_mode": "SP", "cases": sp["cases"]})

    spe = await run_method_api(
        name="Model SPE",
        cases=cases,
        api_root=args.api_root,
        model_id=args.model_id,
        ablation_mode="SPE",
        timeout_s=args.timeout,
        max_concurrent=args.max_concurrent,
    )
    methods.append({"name": spe["name"], "kind": "model", "ablation_mode": "SPE", "cases": spe["cases"]})

    if args.with_ablations:
        for mode in ["S", "P", "E", "SP", "SE", "PE", "SPE"]:
            r = await run_method_api(
                name=f"Ablation {mode}",
                cases=cases,
                api_root=args.api_root,
                model_id=args.model_id,
                ablation_mode=mode,
                timeout_s=args.timeout,
                max_concurrent=args.max_concurrent,
            )
            methods.append({"name": r["name"], "kind": "ablation", "ablation_mode": mode, "cases": r["cases"]})

    # Attach summaries
    for m in methods:
        m["summary"] = summarize(m["cases"])

    report = {
        "run_id": ts,
        "dataset_file": str(test_path),
        "api_root": args.api_root,
        "model_id": args.model_id,
        "seed": args.seed,
        "methods": methods,
    }

    out_dir = Path("results")
    out_dir.mkdir(exist_ok=True)
    out_json = out_dir / f"publication_suite_{ts}.json"
    out_md = out_dir / f"publication_suite_{ts}.md"

    out_json.write_text(json.dumps(report, indent=2), encoding="utf-8")
    out_md.write_text(render_md(report), encoding="utf-8")

    print(f"✅ wrote {out_json}")
    print(f"✅ wrote {out_md}")

    # Print a small console summary
    for m in methods[:4]:
        s = m["summary"]
        print(
            f"{m['name']}: pos(class@1={s['positive']['class_at1']:.1%}, drug@1={s['positive']['drug_at1']:.1%}) "
            f"neg(parp_fp={s['negative']['parp_fp_rate']:.1%})"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
