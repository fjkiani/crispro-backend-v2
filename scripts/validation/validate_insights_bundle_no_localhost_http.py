#!/usr/bin/env python3
"""
Ring-1 deterministic validator: insights bundle extraction requires NO localhost HTTP.

Scope:
- Calls `complete_care_universal._extract_insights_bundle()` directly (in-process)
- Sets API_BASE_URL to a bogus value to ensure we don't accidentally try HTTP
- Asserts returned bundle shape + value ranges

Outputs:
- `scripts/validation/out/insights_bundle_no_http_v1/report.json` (copy-on-write)
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

OUT_DIR = Path(__file__).resolve().parent / "out" / "insights_bundle_no_http_v1"


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


async def _run() -> Dict[str, Any]:
    # Force bogus base to catch accidental HTTP usage.
    os.environ["API_BASE_URL"] = "http://does-not-exist.invalid:9999"

    from api.routers.complete_care_universal import _extract_insights_bundle  # noqa: WPS433
    import httpx  # noqa: WPS433

    # "Ayesha-like" mutation (truncation should drive deterministic bundle values)
    somatic_mutations = [
        {"gene": "MBD4", "hgvs_p": "p.Ile413Serfs*2", "consequence": "frameshift_variant"},
        {"gene": "TP53", "hgvs_p": "p.Arg175His", "consequence": "missense_variant"},
    ]

    async with httpx.AsyncClient() as client:
        bundle = await _extract_insights_bundle(client, somatic_mutations, api_base=os.environ["API_BASE_URL"])

    # Shape + range assertions
    for k in ("functionality", "chromatin", "essentiality", "regulatory"):
        _assert(k in bundle, f"Missing key: {k}")
        _assert(isinstance(bundle[k], (int, float)), f"{k} must be numeric")
        _assert(0.0 <= float(bundle[k]) <= 1.0, f"{k} out of range: {bundle[k]}")

    return {
        "bundle": bundle,
        "api_base": os.environ.get("API_BASE_URL"),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    timestamped_report_path = OUT_DIR / f"report_{timestamp}.json"
    canonical_report_path = OUT_DIR / "report.json"

    try:
        result = asyncio.run(_run())
        report = {
            "validator": "validate_insights_bundle_no_localhost_http",
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "status": "PASSED",
            "result": result,
            "errors": [],
        }
        timestamped_report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        canonical_report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"✅ Insights bundle validator PASSED. Wrote: {canonical_report_path}")
        raise SystemExit(0)
    except Exception as e:
        report = {
            "validator": "validate_insights_bundle_no_localhost_http",
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "status": "FAILED",
            "errors": [f"{type(e).__name__}: {e}"],
        }
        timestamped_report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        canonical_report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"❌ Insights bundle validator FAILED. Wrote: {canonical_report_path}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()

































