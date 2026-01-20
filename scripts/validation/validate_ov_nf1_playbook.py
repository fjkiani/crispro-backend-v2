#!/usr/bin/env python3
"""OV NF1 Playbook Validation

Regression gates:
- NF1 is present in OV_RESISTANCE_PLAYBOOK with RR=2.10 and TCGA_OV_469 source
- Playbook service returns expected alternatives and monitoring/regimen guidance for NF1

Important: This is a **separate NF1 fixture** (OV-NF1-001). AK/Ayesha should not be assumed NF1+.

Run:
  python scripts/validation/validate_ov_nf1_playbook.py
"""

import asyncio
import json
import os
import sys
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from api.services.resistance_playbook_service import OV_RESISTANCE_PLAYBOOK, get_resistance_playbook_service  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "data/patient_states/OV-NF1-001.json"
REPORT_DIR = Path(__file__).resolve().parent


@dataclass
class CheckResult:
    name: str
    passed: bool
    details: str
    metrics: Dict[str, Any]


def _assert(cond: bool, msg: str):
    if not cond:
        raise AssertionError(msg)


async def main_async() -> int:
    checks: List[CheckResult] = []
    overall = True

    try:
        _assert(FIXTURE_PATH.exists(), f"Missing fixture: {FIXTURE_PATH}")
        fixture = json.loads(FIXTURE_PATH.read_text())

        # Static playbook checks
        nf1 = OV_RESISTANCE_PLAYBOOK.get("NF1")
        _assert(nf1 is not None, "OV_RESISTANCE_PLAYBOOK missing NF1")

        rr = nf1.get("relative_risk")
        validation_source = nf1.get("validation_source")
        alternatives = nf1.get("alternatives", [])

        _assert(rr is not None and abs(float(rr) - 2.10) < 1e-6, f"NF1 RR unexpected: {rr}")
        _assert(validation_source == "TCGA_OV_469", f"NF1 validation_source drifted: {validation_source}")
        _assert(len(alternatives) >= 3, f"Expected >=3 NF1 alternatives, got {len(alternatives)}")

        alt_drugs = {a.get("drug") for a in alternatives}
        _assert("trametinib" in alt_drugs, "NF1 alternatives missing trametinib")
        _assert("bevacizumab" in alt_drugs, "NF1 alternatives missing bevacizumab")
        _assert("olaparib" in alt_drugs, "NF1 alternatives missing olaparib")

        checks.append(CheckResult(
            "nf1_playbook_static",
            True,
            "NF1 playbook entry present with expected RR/source/alternatives",
            {"relative_risk": rr, "validation_source": validation_source, "alt_drugs": sorted(list(alt_drugs))},
        ))

        # Service checks
        service = get_resistance_playbook_service()
        result = await service.get_next_line_options(
            disease="ovarian",
            detected_resistance=["NF1"],
            current_regimen=fixture["patient_profile"].get("current_regimen"),
            current_drug_class="platinum",
            treatment_line=int(fixture["patient_profile"].get("treatment_line", 1)),
            prior_therapies=fixture["patient_profile"].get("prior_therapies") or [],
            patient_id=fixture.get("patient_id"),
        )

        got_alt_drugs = {a.drug.lower() for a in result.alternatives}
        _assert("trametinib" in got_alt_drugs, "Service output missing trametinib")
        _assert("bevacizumab" in got_alt_drugs, "Service output missing bevacizumab")
        _assert("olaparib" in got_alt_drugs, "Service output missing olaparib")
        _assert(result.provenance.get("playbook_source") == "OV_RESISTANCE_PLAYBOOK", "Provenance playbook_source mismatch")

        checks.append(CheckResult(
            "nf1_playbook_service",
            True,
            "Playbook service returns expected NF1 alternatives + provenance",
            {
                "alternatives_count": len(result.alternatives),
                "alt_drugs": sorted(list(got_alt_drugs)),
                "regimen_changes_count": len(result.regimen_changes),
                "monitoring_changes": asdict(result.monitoring_changes),
                "provenance": result.provenance,
            },
        ))

        _assert(len(result.regimen_changes) >= 1, "Expected at least 1 regimen change for NF1")
        _assert(bool(result.monitoring_changes.biomarker_frequency), "Expected biomarker_frequency monitoring change for NF1")

        checks.append(CheckResult(
            "nf1_regimen_monitoring",
            True,
            "NF1 includes regimen change + intensified monitoring guidance",
            {
                "regimen_changes": [asdict(rc) for rc in result.regimen_changes],
                "biomarker_frequency": result.monitoring_changes.biomarker_frequency,
                "imaging_frequency": result.monitoring_changes.imaging_frequency,
            },
        ))

    except Exception as e:
        overall = False
        checks.append(CheckResult("exception", False, f"{type(e).__name__}: {e}", {}))

    report = {
        "timestamp": datetime.utcnow().isoformat(),
        "validator": "validate_ov_nf1_playbook",
        "fixture": str(FIXTURE_PATH),
        "overall_passed": overall,
        "checks": [asdict(c) for c in checks],
    }

    # Copy-on-write: write timestamped, then copy to canonical
    timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    timestamped_path = REPORT_DIR / f"ov_nf1_playbook_report_{timestamp}.json"
    canonical_path = REPORT_DIR / "ov_nf1_playbook_report.json"
    
    timestamped_path.write_text(json.dumps(report, indent=2))
    canonical_path.write_text(json.dumps(report, indent=2))

    print(json.dumps(report, indent=2))
    print(f"\nWrote report: {canonical_path} (timestamped: {timestamped_path})")
    return 0 if overall else 1


def main() -> int:
    return asyncio.run(main_async())


if __name__ == "__main__":
    raise SystemExit(main())
