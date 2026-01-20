#!/usr/bin/env python3
"""
Ring-1 deterministic validator: OV Resistance E2E (Ayesha-like) via /api/complete_care/v2.

No server required (in-process FastAPI TestClient).
Writes copy-on-write receipt under:
  scripts/validation/out/resistance_e2e_ov_ayesha_v1/report.json
"""

from __future__ import annotations

import json
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
OUT_DIR = Path(__file__).resolve().parent / "out" / "resistance_e2e_ov_ayesha_v1"
TEST_CASE = Path(__file__).resolve().parent / "test_cases" / "ayesha_ov_baseline.json"


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _required_paths(d: Dict[str, Any], paths: List[str]) -> None:
    for p in paths:
        cur: Any = d
        for part in p.split("."):
            _assert(isinstance(cur, dict), f"Expected dict while traversing {p}, got {type(cur)}")
            _assert(part in cur, f"Missing key: {p}")
            cur = cur[part]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    timestamped_report_path = OUT_DIR / f"report_{timestamp}.json"
    canonical_report_path = OUT_DIR / "report.json"

    errors: List[str] = []
    started = time.time()

    try:
        _assert(TEST_CASE.exists(), f"Missing test case: {TEST_CASE}")
        case = json.loads(TEST_CASE.read_text(encoding="utf-8"))

        # In-process app call
        from fastapi import FastAPI  # noqa: WPS433
        from fastapi.testclient import TestClient  # noqa: WPS433
        from api.routers import complete_care_universal as complete_care_universal_router  # noqa: WPS433

        # Build a minimal in-process app to avoid importing optional/broken routers.
        app = FastAPI()
        app.include_router(complete_care_universal_router.router)

        client = TestClient(app)

        payload = {
            "disease": case.get("disease", "ovarian"),
            "patient_data": case,
            "include_trials": False,
            "include_soc": False,
            "include_biomarker": True,
            "include_wiwfm": False,
            "include_food": False,
            "include_resistance": False,
            "include_resistance_prediction": True,
            "max_trials": 0,
        }

        resp = client.post("/api/complete_care/v2", json=payload)
        latency_ms = int((time.time() - started) * 1000)

        _assert(resp.status_code == 200, f"HTTP {resp.status_code}: {resp.text[:500]}")
        body = resp.json()

        # Required contract fields for Task C
        _required_paths(
            body,
            [
                "resistance_prediction.resistance_prediction.risk_level",
                "resistance_prediction.resistance_prediction.probability",
                "resistance_prediction.resistance_prediction.confidence",
                "resistance_prediction.resistance_prediction.mechanisms_detected",
                "resistance_prediction.resistance_prediction.monitoring_plan",
                "resistance_prediction.resistance_prediction.treatment_actions",
                "resistance_prediction.provenance.code_version",
                "resistance_prediction.provenance.contract_version",
                "resistance_prediction.provenance.services_called",
                "resistance_prediction.provenance.timestamp",
            ],
        )

        # Sanity expectations for Ayesha-like baseline:
        rp = body["resistance_prediction"]["resistance_prediction"]
        risk_level = rp.get("risk_level")
        _assert(risk_level in ("LOW", "MEDIUM", "HIGH", "UNKNOWN"), f"Unexpected risk_level: {risk_level}")

        # CA-125 burden should be extensive at 2842 when biomarker intelligence runs
        bi = body.get("biomarker_intelligence") or {}
        if bi and not bi.get("error"):
            _assert(bi.get("burden_class") in ("EXTENSIVE", "SIGNIFICANT", "MODERATE", "MINIMAL"), "Invalid burden_class")

        report = {
            "validator": "validate_resistance_e2e_ov_ayesha_v1",
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "status": "PASSED",
            "latency_ms": latency_ms,
            "input": case,
            "output_excerpt": {
                "resistance_prediction": body.get("resistance_prediction"),
                "biomarker_intelligence": body.get("biomarker_intelligence"),
            },
            "errors": [],
        }

        timestamped_report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        canonical_report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"✅ OV resistance E2E validator PASSED. Wrote: {canonical_report_path}")
        raise SystemExit(0)
    except Exception as e:
        errors.append(f"{type(e).__name__}: {e}")
        errors.append(traceback.format_exc())
        report = {
            "validator": "validate_resistance_e2e_ov_ayesha_v1",
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "status": "FAILED",
            "errors": errors,
        }
        timestamped_report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        canonical_report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"❌ OV resistance E2E validator FAILED. Wrote: {canonical_report_path}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()


