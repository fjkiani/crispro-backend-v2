#!/usr/bin/env python3
"""
Ring-1 deterministic validator: Synthetic Lethality pilot benchmark receipt.

Sprint 3 deliverable (RESISTANCE_VALIDATION_PLAN.md):
- Emit a stable `report.json` for `sl_pilot_drug_match_v1`
- Report Evo2 usage rate explicitly
- Guardrail: ensure we are validating the *Evo2-backed* benchmark artifact (not rules-only GUIDANCE_FAST bypass)

No server required. No network calls. Reads pinned artifact(s) from repo.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict


REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = Path(__file__).resolve().parent / "out" / "sl_pilot_drug_match_v1"


PINNED_BENCHMARK = (
    REPO_ROOT
    / "scripts"
    / "benchmark_sl"
    / "results"
    / "benchmark_efficacy_20251203_210907.json"
)


EXPECTED = {
    "benchmark_type": "efficacy_predict",
    "num_cases": 10,
    "drug_accuracy": 0.5,
    "evo2_usage_rate": 1.0,
}


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    # Copy-on-write: write timestamped, then copy to canonical
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    timestamped_report_path = OUT_DIR / f"report_{timestamp}.json"
    canonical_report_path = OUT_DIR / "report.json"

    errors = []
    try:
        _assert(PINNED_BENCHMARK.exists(), f"Missing pinned benchmark artifact: {PINNED_BENCHMARK}")
        j = _load_json(PINNED_BENCHMARK)

        _assert(j.get("benchmark_type") == EXPECTED["benchmark_type"], "benchmark_type mismatch (guardrail)")
        _assert(int(j.get("num_cases", -1)) == EXPECTED["num_cases"], "num_cases mismatch")

        agg = j.get("aggregate_metrics") or {}
        drug_acc = float(agg.get("drug_accuracy", -1.0))
        evo2_rate = float(agg.get("evo2_usage_rate", -1.0))

        # Use tight tolerances (this is a pinned artifact).
        _assert(abs(drug_acc - EXPECTED["drug_accuracy"]) < 1e-9, "drug_accuracy mismatch")
        _assert(abs(evo2_rate - EXPECTED["evo2_usage_rate"]) < 1e-9, "evo2_usage_rate mismatch")

        # Guardrail: ensure this was not a rules-only run (GUIDANCE_FAST bypass).
        # The pinned artifact must come from the efficacy benchmark that calls /api/efficacy/predict.
        rules_only_bypass_detected = j.get("benchmark_type") != "efficacy_predict"
        _assert(rules_only_bypass_detected is False, "rules-only bypass detected (unexpected benchmark_type)")

        report = {
            "validator": "validate_synthetic_lethality_pilot_benchmark",
            "timestamp": datetime.utcnow().isoformat(),
            "status": "PASSED",
            "run_meta": {
                "contract": "sl_pilot_drug_match_v1",
                "pinned_benchmark_path": str(PINNED_BENCHMARK),
                "expected": EXPECTED,
            },
            "metrics": {
                "drug_accuracy": drug_acc,
                "evo2_usage_rate": evo2_rate,
                "avg_confidence": float(agg.get("avg_confidence", 0.0)),
                "num_cases": int(j.get("num_cases", 0)),
            },
            "guardrails": {
                "rules_only_bypass_detected": False,
            },
            "errors": [],
        }
        # Copy-on-write: write timestamped, then copy to canonical
        timestamped_report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        canonical_report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"✅ SL pilot benchmark validator PASSED. Wrote: {canonical_report_path} (timestamped: {timestamped_report_path})")
        raise SystemExit(0)
    except Exception as e:
        errors.append(f"{type(e).__name__}: {e}")
        report = {
            "validator": "validate_synthetic_lethality_pilot_benchmark",
            "timestamp": datetime.utcnow().isoformat(),
            "status": "FAILED",
            "run_meta": {
                "contract": "sl_pilot_drug_match_v1",
                "pinned_benchmark_path": str(PINNED_BENCHMARK),
                "expected": EXPECTED,
            },
            "errors": errors,
        }
        timestamped_report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        canonical_report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"❌ SL pilot benchmark validator FAILED. Wrote: {canonical_report_path} (timestamped: {timestamped_report_path})")
        raise SystemExit(1)


if __name__ == "__main__":
    main()


