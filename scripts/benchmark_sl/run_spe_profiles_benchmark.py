#!/usr/bin/env python3
"""Run S/P/E orchestrator on a dataset in two profiles (SP vs SPE).

This is the doctrine-aligned harness for proving lift.

Default behavior:
- Calls a running API at --api-root (http://127.0.0.1:8000)
- Limits cases unless --limit is increased (to control cost)

Outputs doctrine schema:
{ provenance, summary, cases[] }
"""

import argparse
import asyncio
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx


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


def _lower_list(xs: List[str]) -> List[str]:
    return [x.lower() for x in xs if isinstance(x, str) and x]


def drug_class(drug_name: Optional[str]) -> str:
    if not drug_name:
        return "none"
    d = drug_name.strip().lower()
    if d in {"olaparib", "niraparib", "rucaparib", "talazoparib"}:
        return "parp"
    if d == "ceralasertib":
        return "atr"
    if d == "adavosertib":
        return "wee1"
    if d == "trametinib":
        return "mapk"
    return "other"


def _top_drug(prediction: Dict[str, Any]) -> Tuple[Optional[str], float, Optional[str]]:
    drugs = prediction.get("drugs") or []
    if not drugs:
        return None, 0.0, None
    top = max(drugs, key=lambda d: float(d.get("confidence", 0) or 0))
    return top.get("name"), float(top.get("confidence", 0) or 0), top.get("moa")


def _evaluate_case(case: Dict[str, Any], top_drug: Optional[str]) -> Dict[str, Any]:
    gt = case.get("ground_truth") or {}
    gt_drugs = _lower_list(gt.get("effective_drugs") or [])
    is_positive = bool(gt_drugs)
    gt_classes = sorted({drug_class(d) for d in gt_drugs if d})

    pred_cls = drug_class(top_drug)
    pred_drug_l = (top_drug or "").lower() if top_drug else ""

    if is_positive:
        return {
            "is_positive": True,
            "gt_drugs": gt.get("effective_drugs") or [],
            "gt_classes": gt_classes,
            "class_at1": bool(pred_cls and pred_cls in gt_classes),
            "drug_at1": bool(pred_drug_l and pred_drug_l in gt_drugs),
        }

    # negatives
    return {
        "is_positive": False,
        "gt_drugs": [],
        "gt_classes": [],
        "neg_parp_fp": pred_cls == "parp",
    }


async def _call_efficacy(
    client: httpx.AsyncClient,
    *,
    api_root: str,
    model_id: str,
    case: Dict[str, Any],
    profile: str,
    timeout_s: float,
) -> Dict[str, Any]:
    payload = {
        "model_id": model_id,
        "mutations": case.get("mutations") or [],
        "disease": case.get("disease", "ovarian_cancer"),
        # IMPORTANT: ablation_mode is a top-level request field expected by the orchestrator.
        # Putting it inside options will be ignored and SP vs SPE becomes meaningless.
        "ablation_mode": profile,
        "options": {
            "adaptive": True,
            "ensemble": False,
            "fast": True,
        },
    }

    resp = await client.post(f"{api_root}/api/efficacy/predict", json=payload, timeout=timeout_s)
    resp.raise_for_status()
    return resp.json()


async def run_profile(
    *,
    api_root: str,
    test_cases: List[Dict[str, Any]],
    profile: str,
    model_id: str,
    limit: Optional[int],
    timeout_s: float,
    max_concurrent: int,
    include_raw: bool,
) -> Dict[str, Any]:
    run_id = str(uuid.uuid4())

    cases = test_cases[:limit] if limit else test_cases

    sem = asyncio.Semaphore(max_concurrent)

    async def process_one(case: Dict[str, Any]) -> Dict[str, Any]:
        async with sem:
            async with httpx.AsyncClient() as client:
                pred = await _call_efficacy(
                    client,
                    api_root=api_root,
                    model_id=model_id,
                    case=case,
                    profile=profile,
                    timeout_s=timeout_s,
                )

            top_name, top_conf, top_moa = _top_drug(pred)
            ev = _evaluate_case(case, top_name)
            out = {
                "case_id": case.get("case_id"),
                "disease": case.get("disease"),
                "profile": profile,
                "prediction": {
                    "top_drug": top_name,
                    "top_class": drug_class(top_name),
                    "confidence": top_conf,
                    "moa": top_moa,
                },
                "eval": ev,
            }
            if include_raw:
                out["raw_response"] = pred
            return out

    results = await asyncio.gather(*[process_one(c) for c in cases])

    pos = [r for r in results if r["eval"].get("is_positive")]
    neg = [r for r in results if not r["eval"].get("is_positive")]

    def rate(n: int, d: int) -> float:
        return (n / d) if d else 0.0

    pos_class = sum(1 for r in pos if r["eval"].get("class_at1"))
    pos_drug = sum(1 for r in pos if r["eval"].get("drug_at1"))
    neg_parp_fp = sum(1 for r in neg if r["eval"].get("neg_parp_fp"))

    report = {
        "provenance": {
            "run_id": run_id,
            "created_at": _now_iso(),
            "script": "run_spe_profiles_benchmark.py",
            "api_root": api_root,
            "model_id": model_id,
            "profile": profile,
            "flags": _env_flags(),
        },
        "summary": {
            "n_total": len(results),
            "n_positive": len(pos),
            "n_negative": len(neg),
            "positive": {
                "class_at1": rate(pos_class, len(pos)),
                "drug_at1": rate(pos_drug, len(pos)),
            },
            "negative": {
                "parp_fp_rate": rate(neg_parp_fp, len(neg)),
            },
        },
        "cases": results,
    }

    return report


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("test_file", help="JSON dataset (list of cases)")
    ap.add_argument("--api-root", default="http://127.0.0.1:8000")
    ap.add_argument("--model-id", default=os.getenv("EVO_FORCE_MODEL") or "evo2_1b")
    ap.add_argument("--limit", type=int, default=12, help="Limit number of cases (cost control)")
    ap.add_argument("--timeout", type=float, default=180.0)
    ap.add_argument("--max-concurrent", type=int, default=2)
    ap.add_argument("--include-raw", action="store_true")
    args = ap.parse_args()

    test_path = Path(args.test_file)
    cases = json.loads(test_path.read_text())

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    for profile in ("SP", "SPE"):
        print("=" * 70)
        print(f"Running profile={profile} cases={min(len(cases), args.limit)} api={args.api_root} model={args.model_id}")
        print("=" * 70)

        try:
            report = await run_profile(
                api_root=args.api_root,
                test_cases=cases,
                profile=profile,
                model_id=args.model_id,
                limit=args.limit,
                timeout_s=args.timeout,
                max_concurrent=args.max_concurrent,
                include_raw=args.include_raw,
            )
        except Exception as e:
            print(f"❌ Failed profile={profile}: {e}")
            return 1

        out = Path("results") / f"profile_{profile}_{test_path.stem}_{ts}.json"
        out.parent.mkdir(exist_ok=True)
        out.write_text(json.dumps(report, indent=2))

        s = report["summary"]
        print(
            f"✅ {profile} pos(Class@1={s['positive']['class_at1']:.1%}, Drug@1={s['positive']['drug_at1']:.1%}) "
            f"neg(PARP_FP={s['negative']['parp_fp_rate']:.1%}) -> {out}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
