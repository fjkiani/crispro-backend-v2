#!/usr/bin/env python3
"""
Resistance Validation Suite Runner (Ring 0/1)

Purpose
-------
Operationalize `.cursor/MOAT/RESISTANCE_VALIDATION_PLAN.md`:
- Ring 0: fast deterministic unit tests (no server, no network)
- Ring 1: deterministic validators that emit report.json

This runner is intentionally conservative:
- It does NOT require a running FastAPI server.
- It does NOT hit the network.

Usage
-----
python oncology-coPilot/oncology-backend-minimal/scripts/validation/run_resistance_validation_suite.py --ring0
python oncology-coPilot/oncology-backend-minimal/scripts/validation/run_resistance_validation_suite.py --ring1
python oncology-coPilot/oncology-backend-minimal/scripts/validation/run_resistance_validation_suite.py --ring0 --ring1
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any


REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass
class StepResult:
    name: str
    passed: bool
    details: str
    meta: Dict[str, Any]

def _has_pytest() -> bool:
    try:
        import pytest  # noqa: F401
        return True
    except Exception:
        return False


def run_cmd(name: str, cmd: List[str], cwd: Path) -> StepResult:
    p = subprocess.run(
        cmd,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    ok = p.returncode == 0
    return StepResult(
        name=name,
        passed=ok,
        details=p.stdout[-4000:],  # keep tail for readability
        meta={"returncode": p.returncode, "cmd": cmd},
    )


def run_ring0() -> List[StepResult]:
    """
    Ring 0: unit tests only (no server required).
    """
    results: List[StepResult] = []

    if not _has_pytest():
        return [
            StepResult(
                name="ring0:pytest_missing",
                passed=False,
                details="pytest is not installed in this environment. Re-run with --skip-missing-pytest to treat this as SKIPPED, or install dev deps to enforce Ring-0 locally/CI.",
                meta={"action": "install pytest or use --skip-missing-pytest"},
            )
        ]

    # Limit to deterministic unit tests relevant to resistance capability.
    test_files = [
        "tests/test_resistance_playbook.py",
        "tests/test_biomarker_intelligence_universal.py",
        "tests/test_safety_service.py",
        "tests/test_safety_api.py",
    ]

    for tf in test_files:
        results.append(
            run_cmd(
                name=f"pytest:{tf}",
                cmd=[sys.executable, "-m", "pytest", "-q", tf],
                cwd=REPO_ROOT,
            )
        )

    return results


def run_ring1() -> List[StepResult]:
    """
    Ring 1: deterministic validators that emit report.json.
    """
    results: List[StepResult] = []

    # OV NF1 playbook regression gate (no network)
    validator = "scripts/validation/validate_ov_nf1_playbook.py"
    results.append(
        run_cmd(
            name=f"validator:{validator}",
            cmd=[sys.executable, validator],
            cwd=REPO_ROOT,
        )
    )

    # Canonical ResistanceContract smoke (prevents schema drift)
    contract_validator = "scripts/validation/validate_resistance_contract_smoke.py"
    results.append(
        run_cmd(
            name=f"validator:{contract_validator}",
            cmd=[sys.executable, contract_validator],
            cwd=REPO_ROOT,
        )
    )

    # Synthetic Lethality pilot benchmark receipt (deterministic; no network)
    sl_validator = "scripts/validation/validate_synthetic_lethality_pilot_benchmark.py"
    results.append(
        run_cmd(
            name=f"validator:{sl_validator}",
            cmd=[sys.executable, sl_validator],
            cwd=REPO_ROOT,
        )
    )

    # Resistance E2E fixture-driven validation (Task A, Deliverable 4)
    e2e_fixture_validator = "scripts/validation/validate_resistance_e2e_fixtures.py"
    results.append(
        run_cmd(
            name=f"validator:{e2e_fixture_validator}",
            cmd=[sys.executable, e2e_fixture_validator],
            cwd=REPO_ROOT,
        )
    )

    # Insights bundle extraction must not require localhost HTTP (Task B, Deliverable 10)
    insights_validator = "scripts/validation/validate_insights_bundle_no_localhost_http.py"
    results.append(
        run_cmd(
            name=f"validator:{insights_validator}",
            cmd=[sys.executable, insights_validator],
            cwd=REPO_ROOT,
        )
    )

    # Task C: E2E OV resistance (Ayesha-like) via /api/complete_care/v2 (in-process)
    ov_e2e_validator = "scripts/validation/validate_resistance_e2e_ov_ayesha_v1.py"
    results.append(
        run_cmd(
            name=f"validator:{ov_e2e_validator}",
            cmd=[sys.executable, ov_e2e_validator],
            cwd=REPO_ROOT,
        )
    )

    # Guardrail: ensure key receipt exists (precomputed report from prior runs).
    receipt = "scripts/validation/out/ddr_bin_ov_platinum_TRUE_SAE_v2/report.json"
    receipt_path = REPO_ROOT / receipt
    if not receipt_path.exists():
        results.append(
            StepResult(
                name=f"receipt_exists:{receipt}",
                passed=False,
                details="Missing expected receipt file. If this is a fresh checkout, regenerate receipts or update the plan.",
                meta={"path": str(receipt_path)},
            )
        )
    else:
        try:
            j = json.loads(receipt_path.read_text())
            ok = isinstance(j, dict) and "run_meta" in j and ("platinum_response" in j or "os" in j)
            results.append(
                StepResult(
                    name=f"receipt_parse:{receipt}",
                    passed=ok,
                    details="Parsed receipt JSON and found expected keys.",
                    meta={"path": str(receipt_path), "keys": sorted(list(j.keys()))[:30]},
                )
            )
        except Exception as e:
            results.append(
                StepResult(
                    name=f"receipt_parse:{receipt}",
                    passed=False,
                    details=f"Failed to parse receipt JSON: {type(e).__name__}: {e}",
                    meta={"path": str(receipt_path)},
                )
            )

    return results


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ring0", action="store_true", help="Run fast deterministic unit tests")
    ap.add_argument("--ring1", action="store_true", help="Run deterministic validators (no network)")
    ap.add_argument(
        "--skip-missing-pytest",
        action="store_true",
        help="If pytest is missing, mark Ring-0 as skipped (non-failing). Use --strict to force failure.",
    )
    ap.add_argument(
        "--strict",
        action="store_true",
        help="Fail the suite if any Ring-0 prerequisite is missing (e.g., pytest not installed).",
    )
    ap.add_argument(
        "--out",
        default="scripts/validation/out/resistance_validation_suite/report.json",
        help="Where to write the consolidated suite report (relative to oncology-backend-minimal)",
    )
    args = ap.parse_args()

    if args.strict and args.skip_missing_pytest:
        ap.error("--strict and --skip-missing-pytest are mutually exclusive")

    if not args.ring0 and not args.ring1:
        ap.error("Must specify at least one of --ring0 or --ring1")

    steps: List[StepResult] = []
    if args.ring0:
        ring0 = run_ring0()
        # Optionally treat pytest-missing as skipped (non-failing)
        if args.skip_missing_pytest and ring0 and ring0[0].name == "ring0:pytest_missing":
            steps.append(
                StepResult(
                    name="ring0:pytest_missing",
                    passed=True,
                    details="SKIPPED: pytest is not installed in this environment (non-strict mode).",
                    meta={"skipped": True},
                )
            )
        else:
            steps.extend(ring0)
    if args.ring1:
        steps.extend(run_ring1())

    overall = all(s.passed for s in steps)

    out_path = REPO_ROOT / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "timestamp": datetime.utcnow().isoformat(),
        "runner": "run_resistance_validation_suite",
        "ring0": bool(args.ring0),
        "ring1": bool(args.ring1),
        "overall_passed": overall,
        "steps": [asdict(s) for s in steps],
    }
    out_path.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    print(f"\nWrote consolidated report: {out_path}")

    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())


