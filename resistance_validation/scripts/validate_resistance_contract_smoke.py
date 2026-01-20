"""
Ring-1 deterministic validator: ResistanceContract smoke.

Purpose:
- Prevent schema drift for the canonical resistance contract that the UI should consume.
- No server required. No network calls. Deterministic output.

Output:
- Writes `report.json` under `scripts/validation/out/resistance_contract_smoke/`.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from api.contracts.resistance_builders import contract_from_playbook_result
from api.services.resistance_playbook_service import get_resistance_playbook_service
from api.services.input_completeness import compute_input_completeness


OUT_DIR = Path(__file__).resolve().parent / "out" / "resistance_contract_smoke"


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _required_contract_keys() -> List[str]:
    return [
        "mechanisms",
        "actions",
        "receipts",
        "provenance",
        "warnings",
    ]


def _required_provenance_keys() -> List[str]:
    return [
        "service_version",
        "run_id",
        "generated_at",
        "disease_original",
        "disease_normalized",
        "code_version",
        "contract_version",
        "inputs_snapshot_hash",
        "flags",
    ]


def validate_contract_dict(contract_dict: Dict[str, Any]) -> Dict[str, Any]:
    # Required top-level keys
    for k in _required_contract_keys():
        _assert(k in contract_dict, f"Missing contract key: {k}")

    prov = contract_dict.get("provenance") or {}
    _assert(isinstance(prov, dict), "contract.provenance must be a dict")
    for k in _required_provenance_keys():
        _assert(k in prov, f"Missing provenance key: {k}")

    # Actions should carry evidence tiers when evidence_level is present
    actions = contract_dict.get("actions") or []
    _assert(isinstance(actions, list), "contract.actions must be a list")
    for i, action in enumerate(actions):
        _assert(isinstance(action, dict), f"contract.actions[{i}] must be a dict")
        if action.get("evidence_level") is not None:
            _assert("evidence_tier" in action, f"Missing evidence_tier on contract.actions[{i}]")

    # Sprint 2: contract flags must include an input level marker
    flags = (prov.get("flags") or [])
    _assert(isinstance(flags, list), "provenance.flags must be a list")
    _assert(
        any(f in ("INPUT_LEVEL_L0", "INPUT_LEVEL_L1", "INPUT_LEVEL_L2") for f in flags),
        "provenance.flags must include an INPUT_LEVEL_* marker",
    )

    return {
        "passed": True,
        "action_count": len(actions),
        "mechanism_count": len(contract_dict.get("mechanisms") or []),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Deterministic “fixture-like” input.
    # NOTE: The playbook itself is deterministic based on detected genes + disease key.
    patient_id = "fixture-ov-contract-001"
    disease_original = "ovarian_cancer_hgs"
    disease_normalized = "ovarian_cancer_hgs"

    detected_genes = ["NF1"]  # validated action-utility target in OV playbook validators
    playbook_disease = "ovarian"

    svc = get_resistance_playbook_service()
    # This call is async in the service; we run it via asyncio here.
    import asyncio

    playbook_result = asyncio.run(
        svc.get_next_line_options(
            disease=playbook_disease,
            detected_resistance=detected_genes,
            current_regimen=None,
            current_drug_class=None,
            treatment_line=1,
            prior_therapies=None,
            cytogenetics=None,
            patient_id=patient_id,
        )
    )

    completeness = compute_input_completeness(
        tumor_context={"somatic_mutations": [{"gene": g} for g in detected_genes]},
        ca125_history=None,
    )

    contract = contract_from_playbook_result(
        endpoint="/api/care/resistance_playbook_v2",
        disease_canonical=disease_normalized,
        tumor_context={"somatic_mutations": [{"gene": g} for g in detected_genes]},
        playbook_disease_key=playbook_disease,
        playbook_result=playbook_result,
        warnings=list(completeness.warnings or []),
        receipts=[],
    )

    contract_dict = contract.model_dump()
    contract_validation = validate_contract_dict(contract_dict)

    report = {
        "validator": "validate_resistance_contract_smoke",
        "version": "v1",
        "generated_at": datetime.utcnow().isoformat(),
        "inputs": {
            "patient_id": patient_id,
            "disease_original": disease_original,
            "disease_normalized": disease_normalized,
            "playbook_disease": playbook_disease,
            "detected_genes": detected_genes,
        },
        "results": {
            "contract_validation": contract_validation,
        },
        "artifacts": {
            "contract_json": "contract.json",
        },
        "env": {
            "CI": os.environ.get("CI"),
        },
    }

    # Copy-on-write: write timestamped, then copy to canonical
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    timestamped_report_path = OUT_DIR / f"report_{timestamp}.json"
    canonical_report_path = OUT_DIR / "report.json"
    
    (OUT_DIR / "contract.json").write_text(json.dumps(contract_dict, indent=2, sort_keys=True), encoding="utf-8")
    timestamped_report_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    canonical_report_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")


if __name__ == "__main__":
    main()


