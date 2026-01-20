#!/usr/bin/env python3
"""
Ring-1 Validator: Resistance E2E Fixture-Driven Validation

Purpose:
--------
Validates resistance prediction end-to-end using deterministic fixtures.
Proves that:
- L0/L1/L2 input completeness caps confidence appropriately
- Missing inputs are flagged correctly (not errors)
- Expression data is optional (RUO; MVP works without it)

This validator runs WITHOUT a server and WITHOUT network calls.
It uses direct service imports to test the resistance contract generation.

Usage:
------
python3 oncology-coPilot/oncology-backend-minimal/scripts/validation/validate_resistance_e2e_fixtures.py
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

# Ensure repo root (oncology-backend-minimal/) is on sys.path for `from api...` imports
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from api.services.input_completeness import compute_input_completeness, InputCompleteness
from api.services.disease_normalization import validate_disease_type
from api.contracts.resistance_builders import contract_from_playbook_result
from api.services.resistance_playbook_service import get_resistance_playbook_service
import asyncio


FIXTURES_DIR = Path(__file__).parent / "fixtures" / "resistance_e2e"
OUT_DIR = Path(__file__).parent / "out" / "resistance_e2e_fixtures_v1"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def load_fixture(fixture_name: str) -> Dict[str, Any]:
    """Load a fixture JSON file."""
    fixture_path = FIXTURES_DIR / f"{fixture_name}.json"
    if not fixture_path.exists():
        raise FileNotFoundError(f"Fixture not found: {fixture_path}")
    return json.loads(fixture_path.read_text())


def validate_fixture_output(
    fixture: Dict[str, Any],
    contract: Dict[str, Any],
    completeness: InputCompleteness
) -> Dict[str, Any]:
    """Validate that contract output matches fixture expectations."""
    errors: List[str] = []
    warnings: List[str] = []

    # Check input level flag
    expected_level = fixture.get("expected_input_level", "L0")
    flags = contract.get("provenance", {}).get("flags", [])
    level_flags = [f for f in flags if f.startswith("INPUT_LEVEL_")]
    
    if not level_flags:
        errors.append(f"Missing INPUT_LEVEL_* flag in provenance.flags")
    elif level_flags[0] != f"INPUT_LEVEL_{expected_level}":
        errors.append(f"Expected INPUT_LEVEL_{expected_level}, got {level_flags[0]}")

    # Check confidence cap
    expected_cap = fixture.get("expected_confidence_cap", 0.5)
    actual_confidence = contract.get("confidence")
    if actual_confidence is not None and actual_confidence > expected_cap:
        errors.append(
            f"Confidence {actual_confidence:.3f} exceeds expected cap {expected_cap:.3f} "
            f"for {expected_level} completeness"
        )

    # Check expected flags
    expected_flags = set(fixture.get("expected_flags", []))
    actual_flags = set(flags)
    
    missing_flags = expected_flags - actual_flags
    if missing_flags:
        warnings.append(f"Expected flags not present: {missing_flags}")
    
    # Check that expression missing is NOT an error (data gap, not failure)
    if "EXPRESSION_DATA_MISSING" in expected_flags:
        if "EXPRESSION_DATA_MISSING" not in actual_flags:
            warnings.append("Expression missing should be flagged as data gap (not error)")

    return {
        "passed": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "expected_level": expected_level,
        "actual_level": level_flags[0] if level_flags else None,
        "expected_confidence_cap": expected_cap,
        "actual_confidence": actual_confidence,
        "expected_flags": list(expected_flags),
        "actual_flags": list(actual_flags),
    }


async def run_fixture(fixture_name: str) -> Dict[str, Any]:
    """Run a single fixture through the resistance pipeline."""
    fixture = load_fixture(fixture_name)
    patient_profile = fixture["patient_profile"]
    
    # Extract inputs
    disease_original = patient_profile["disease"]
    is_valid, disease_normalized = validate_disease_type(disease_original)
    
    if not is_valid:
        return {
            "fixture": fixture_name,
            "passed": False,
            "error": f"Invalid disease: {disease_original}",
        }

    tumor_context = patient_profile.get("tumor_context", {})
    somatic_mutations = tumor_context.get("somatic_mutations", [])
    ca125_history = patient_profile.get("biomarker_history", {}).get("ca125_history") if patient_profile.get("biomarker_history") else None
    hrd_score = patient_profile.get("hrd_score")

    # Compute input completeness
    completeness = compute_input_completeness(
        tumor_context=tumor_context,
        ca125_history=ca125_history,
    )

    # Get resistance playbook result
    detected_genes = [m.get("gene") for m in somatic_mutations if m.get("gene")]
    playbook_disease = disease_normalized.replace("_cancer_hgs", "").replace("_cancer", "").replace("_", "")
    
    svc = get_resistance_playbook_service()
    playbook_result = await svc.get_next_line_options(
        disease=playbook_disease,
        detected_resistance=detected_genes,
        current_regimen=None,
        current_drug_class=None,
        treatment_line=1,
        prior_therapies=None,
        cytogenetics=None,
        patient_id=patient_profile.get("patient_id"),
    )

    # Build resistance contract
    contract = contract_from_playbook_result(
        endpoint="/api/care/resistance_playbook_v2",
        disease_canonical=disease_normalized,
        tumor_context=tumor_context,
        playbook_disease_key=playbook_disease,
        playbook_result=playbook_result,
        warnings=list(completeness.warnings or []),
        receipts=[],
    )

    contract_dict = contract.model_dump()
    validation_result = validate_fixture_output(fixture, contract_dict, completeness)

    return {
        "fixture": fixture_name,
        "description": fixture.get("description"),
        "validation": validation_result,
        "contract_summary": {
            "risk_level": contract_dict.get("risk_level"),
            "confidence": contract_dict.get("confidence"),
            "mechanism_count": len(contract_dict.get("mechanisms", [])),
            "action_count": len(contract_dict.get("actions", [])),
            "flags": contract_dict.get("provenance", {}).get("flags", []),
        },
    }


async def main() -> None:
    """Run all fixtures and emit report.json."""
    fixture_names = [
        "l0_mutations_only",
        "l1_with_ca125",
        "l2_full_completeness",
        "edge_case_2_of_3_trigger",
        "expression_present_ruo",
    ]

    results = []
    for fixture_name in fixture_names:
        try:
            result = await run_fixture(fixture_name)
            results.append(result)
        except Exception as e:
            results.append({
                "fixture": fixture_name,
                "passed": False,
                "error": str(e),
                "traceback": str(e.__traceback__) if hasattr(e, "__traceback__") else None,
            })

    # Generate report
    all_passed = all(r.get("validation", {}).get("passed", False) if "validation" in r else r.get("passed", False) for r in results)
    
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    report_path = OUT_DIR / f"report_{timestamp}.json"
    canonical_report_path = OUT_DIR / "report.json"

    report = {
        "validator": "validate_resistance_e2e_fixtures",
        "version": "v1",
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "status": "PASSED" if all_passed else "FAILED",
        "fixture_count": len(fixture_names),
        "results": results,
        "summary": {
            "passed": sum(1 for r in results if (r.get("validation", {}).get("passed", False) if "validation" in r else r.get("passed", False))),
            "failed": sum(1 for r in results if not (r.get("validation", {}).get("passed", False) if "validation" in r else r.get("passed", False))),
        },
    }

    # Copy-on-write: write timestamped, then copy to canonical
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    
    with open(canonical_report_path, "w") as f:
        json.dump(report, f, indent=2)

    print(f"✅ Resistance E2E Fixture Validation {'PASSED' if all_passed else 'FAILED'}")
    print(f"   Report: {canonical_report_path}")
    print(f"   Timestamped: {report_path}")
    print(f"   Summary: {report['summary']['passed']}/{len(fixture_names)} fixtures passed")

    if not all_passed:
        print("\n❌ Failures:")
        for r in results:
            if not (r.get("validation", {}).get("passed", False) if "validation" in r else r.get("passed", False)):
                print(f"   - {r['fixture']}: {r.get('validation', {}).get('errors', r.get('error', 'Unknown error'))}")

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    asyncio.run(main())

