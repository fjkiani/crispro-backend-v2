#!/usr/bin/env python3
"""Recompute sporadic gate effects from the scenario suite (deterministic).

This is **non-outcome validation**: it validates that the gate policy behaves as intended
and that the implementation matches a naive reference implementation.

Outputs:
- receipts/benchmark_gate_effects.json
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Tuple

# Ensure backend package import works when executed from repo root.
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(PROJECT_ROOT))

from api.services.efficacy_orchestrator.sporadic_gates import apply_sporadic_gates


def clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def _is_parp(drug_class: str) -> bool:
    dc = (drug_class or "").lower()
    return "parp" in dc


def _is_io(drug_class: str) -> bool:
    dc = (drug_class or "").lower().replace(" ", "_")
    return ("checkpoint" in dc) or ("checkpoint_inhibitor" in dc)


def naive_apply(
    *,
    drug_name: str,
    drug_class: str,
    moa: str,
    efficacy_score: float,
    confidence: float,
    germline_status: str,
    tumor_context: Dict[str, Any] | None,
) -> Tuple[float, float]:
    """Naive reference implementation of the policy (mirrors prod rules)."""

    tc = tumor_context or {}
    eff = float(efficacy_score)
    conf = float(confidence)

    # Gate 1: PARP penalty / HRD rescue
    if _is_parp(drug_class):
        germ = (germline_status or "unknown").lower()
        hrd = tc.get("hrd_score")

        if germ == "positive":
            factor = 1.0
        elif germ == "negative":
            if hrd is None:
                factor = 0.8
            else:
                factor = 1.0 if float(hrd) >= 42.0 else 0.6
        else:
            factor = 0.8

        eff *= factor

    # Gate 2: IO boost (mutually exclusive precedence)
    if _is_io(drug_class):
        tmb = tc.get("tmb")
        msi = (tc.get("msi_status") or "").strip()

        boost = 1.0
        if tmb is not None and float(tmb) >= 20.0:
            boost = 1.35
        elif msi.lower() in {"msi-high", "msi_high", "msi high"}:
            boost = 1.30
        elif tmb is not None and float(tmb) >= 10.0:
            boost = 1.25

        eff *= boost

    # Gate 3: confidence caps by completeness
    comp = tc.get("completeness_score")
    if comp is not None:
        c = float(comp)
        if c < 0.3:
            conf = min(conf, 0.4)
        elif c < 0.7:
            conf = min(conf, 0.6)

    return clamp01(eff), clamp01(conf)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--scenario",
        type=str,
        default=None,
        help="Path to scenario suite JSON (default: data/scenario_suite_25_20251231_080940.json)",
    )
    ap.add_argument(
        "--out",
        type=str,
        default=None,
        help="Output path (default: receipts/benchmark_gate_effects.json)",
    )
    args = ap.parse_args(argv)

    base = Path(__file__).resolve().parents[1]
    scenario_path = Path(args.scenario).resolve() if args.scenario else (base / "data" / "scenario_suite_25_20251231_080940.json")
    out_path = Path(args.out).resolve() if args.out else (base / "receipts" / "benchmark_gate_effects.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    suite = json.loads(scenario_path.read_text(encoding="utf-8"))
    cases = suite.get("cases") or []

    changed_eff = 0
    changed_conf = 0
    agree_eff = 0
    agree_conf = 0
    n = 0

    case_checks = []

    for c in cases:
        n += 1
        inp = c.get("input") or {}
        prev_eff = float(inp.get("efficacy_score") or 0.0)
        prev_conf = float(inp.get("confidence") or 0.0)

        eff_sys, conf_sys, _rationale = apply_sporadic_gates(
            drug_name=inp.get("drug_name") or "",
            drug_class=inp.get("drug_class") or "",
            moa=inp.get("moa") or "",
            efficacy_score=prev_eff,
            confidence=prev_conf,
            germline_status=inp.get("germline_status") or "unknown",
            tumor_context=inp.get("tumor_context") or {},
        )

        eff_ref, conf_ref = naive_apply(
            drug_name=inp.get("drug_name") or "",
            drug_class=inp.get("drug_class") or "",
            moa=inp.get("moa") or "",
            efficacy_score=prev_eff,
            confidence=prev_conf,
            germline_status=inp.get("germline_status") or "unknown",
            tumor_context=inp.get("tumor_context") or {},
        )

        if abs(float(eff_sys) - prev_eff) > 1e-9:
            changed_eff += 1
        if abs(float(conf_sys) - prev_conf) > 1e-9:
            changed_conf += 1

        if abs(float(eff_sys) - float(eff_ref)) <= 1e-9:
            agree_eff += 1
        if abs(float(conf_sys) - float(conf_ref)) <= 1e-9:
            agree_conf += 1

        stored_out = c.get("output") or {}
        stored_eff = stored_out.get("efficacy_score")
        stored_conf = stored_out.get("confidence")

        case_checks.append(
            {
                "case_id": c.get("case_id"),
                "label": c.get("label"),
                "baseline": {"efficacy": prev_eff, "confidence": prev_conf},
                "system": {"efficacy": float(eff_sys), "confidence": float(conf_sys)},
                "naive": {"efficacy": float(eff_ref), "confidence": float(conf_ref)},
                "matches_stored_output": {
                    "efficacy": (stored_eff is None) or (abs(float(stored_eff) - float(eff_sys)) <= 1e-9),
                    "confidence": (stored_conf is None) or (abs(float(stored_conf) - float(conf_sys)) <= 1e-9),
                },
            }
        )

    receipt = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scenario_path": str(scenario_path),
        "stats": {
            "n_cases": n,
            "changed_eff_cases": changed_eff,
            "changed_conf_cases": changed_conf,
            "agreement_naive_vs_system_eff": agree_eff,
            "agreement_naive_vs_system_conf": agree_conf,
        },
        "case_checks": case_checks,
        "notes": {
            "scope": "non-outcome validation (policy behavior + reference conformance)",
        },
    }

    out_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(f"✅ wrote: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
