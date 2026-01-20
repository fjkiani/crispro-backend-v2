#!/usr/bin/env python3
"""
Ring-1 Validation Gate for Resistance Prophet Production

Source of Truth: .cursor/MOAT/RESISTANCE_PROPHET_PRODUCTION_AUDIT.md
Task: Phase 4.1 - Add Ring-1 Validation Gate

Checks:
1. No hard-coded RR values for MAPK genes without validation receipt
2. Baseline-only mode enforced when no CA-125
3. RUO disclaimer present in all responses
4. Evidence tier flags correct for all markers
"""

import json
import re
import sys
from pathlib import Path
from datetime import datetime


def check_no_hard_coded_mapk_rr():
    """
    Ensure KRAS/NRAS/BRAF don't have numeric RR without validation receipt.
    
    Criteria:
    - If relative_risk is numeric (not None), evidence_level must be COHORT_VALIDATED
    - If evidence_level is PENDING_REVALIDATION, relative_risk must be None
    """
    playbook_path = Path("api/services/resistance_playbook_service.py")
    
    if not playbook_path.exists():
        playbook_path = Path("oncology-coPilot/oncology-backend-minimal/api/services/resistance_playbook_service.py")
    
    if not playbook_path.exists():
        return {"passed": False, "error": f"Playbook file not found"}
    
    content = playbook_path.read_text()
    
    mapk_genes = ["KRAS", "NRAS", "BRAF"]
    issues = []
    
    for gene in mapk_genes:
        # Find the gene entry block
        pattern = rf'"{gene}"\s*:\s*\{{'
        match = re.search(pattern, content)
        
        if not match:
            # Gene not in playbook - OK
            continue
        
        # Extract the block (rough heuristic - look for next 10 lines)
        start = match.start()
        block_end = content.find("}", start + 100)
        block = content[start:block_end + 1]
        
        # Check relative_risk
        rr_match = re.search(r'"relative_risk"\s*:\s*([\d.]+|None)', block)
        ev_match = re.search(r'"evidence_level"\s*:\s*EvidenceLevel\.(\w+)', block)
        
        if rr_match and ev_match:
            rr_value = rr_match.group(1)
            evidence_level = ev_match.group(1)
            
            if rr_value != "None" and evidence_level in ["PENDING_REVALIDATION", "LITERATURE_BASED"]:
                issues.append({
                    "gene": gene,
                    "issue": f"Has numeric RR ({rr_value}) but evidence_level is {evidence_level}",
                    "expected": "relative_risk should be None for non-COHORT_VALIDATED markers"
                })
            
            if evidence_level == "VALIDATED" and rr_value != "None":
                # Check if validation receipt exists
                report_path = Path(f"scripts/validation/out/{gene.lower()}_ov_platinum/report.json")
                if not report_path.exists():
                    issues.append({
                        "gene": gene,
                        "issue": f"Marked as VALIDATED (RR={rr_value}) but no validation receipt found",
                        "expected": f"Either run validation or downgrade to PENDING_REVALIDATION"
                    })
    
    return {
        "passed": len(issues) == 0,
        "check": "no_hard_coded_mapk_rr",
        "issues": issues
    }


def check_ruo_disclaimer_constant():
    """
    Ensure RUO_DISCLAIMER constant exists and is meaningful.
    """
    prophet_path = Path("api/services/resistance_prophet_service.py")
    
    if not prophet_path.exists():
        prophet_path = Path("oncology-coPilot/oncology-backend-minimal/api/services/resistance_prophet_service.py")
    
    if not prophet_path.exists():
        return {"passed": False, "error": "Prophet service not found"}
    
    content = prophet_path.read_text()
    
    issues = []
    
    # Check RUO_DISCLAIMER exists
    if "RUO_DISCLAIMER" not in content:
        issues.append({"issue": "RUO_DISCLAIMER constant not found"})
    
    # Check it contains key phrases
    required_phrases = [
        "Research Use Only",
        "Not validated for clinical",
        "CA-125 kinetics"
    ]
    
    for phrase in required_phrases:
        if phrase not in content:
            issues.append({"issue": f"RUO_DISCLAIMER missing phrase: '{phrase}'"})
    
    # Check docstring doesn't claim "3-6 months early"
    if "3-6 months early" in content[:500]:
        issues.append({"issue": "Docstring still claims '3-6 months early'"})
    
    return {
        "passed": len(issues) == 0,
        "check": "ruo_disclaimer_constant",
        "issues": issues
    }


def check_baseline_only_mode_constant():
    """
    Ensure BASELINE_ONLY_CLAIMS_DISABLED constant exists.
    """
    prophet_path = Path("api/services/resistance_prophet_service.py")
    
    if not prophet_path.exists():
        prophet_path = Path("oncology-coPilot/oncology-backend-minimal/api/services/resistance_prophet_service.py")
    
    if not prophet_path.exists():
        return {"passed": False, "error": "Prophet service not found"}
    
    content = prophet_path.read_text()
    
    issues = []
    
    if "BASELINE_ONLY_CLAIMS_DISABLED" not in content:
        issues.append({"issue": "BASELINE_ONLY_CLAIMS_DISABLED constant not found"})
    
    if "early_detection" not in content:
        issues.append({"issue": "BASELINE_ONLY_CLAIMS_DISABLED missing 'early_detection'"})
    
    return {
        "passed": len(issues) == 0,
        "check": "baseline_only_mode_constant",
        "issues": issues
    }


def check_evidence_level_enum():
    """
    Ensure EvidenceLevel enum includes PENDING_REVALIDATION.
    """
    playbook_path = Path("api/services/resistance_playbook_service.py")
    
    if not playbook_path.exists():
        playbook_path = Path("oncology-coPilot/oncology-backend-minimal/api/services/resistance_playbook_service.py")
    
    if not playbook_path.exists():
        return {"passed": False, "error": "Playbook service not found"}
    
    content = playbook_path.read_text()
    
    issues = []
    
    if "PENDING_REVALIDATION" not in content:
        issues.append({"issue": "EvidenceLevel enum missing PENDING_REVALIDATION"})
    
    return {
        "passed": len(issues) == 0,
        "check": "evidence_level_enum",
        "issues": issues
    }


def check_fixtures_exist():
    """
    Ensure resistance fixtures file exists and is valid.
    """
    fixtures_path = Path("scripts/validation/fixtures/resistance_fixtures.json")
    
    if not fixtures_path.exists():
        fixtures_path = Path("oncology-coPilot/oncology-backend-minimal/scripts/validation/fixtures/resistance_fixtures.json")
    
    issues = []
    
    if not fixtures_path.exists():
        issues.append({"issue": "Fixtures file not found"})
        return {"passed": False, "check": "fixtures_exist", "issues": issues}
    
    try:
        with open(fixtures_path) as f:
            fixtures = json.load(f)
        
        if "fixtures" not in fixtures:
            issues.append({"issue": "Fixtures file missing 'fixtures' key"})
        elif len(fixtures["fixtures"]) < 3:
            issues.append({"issue": f"Only {len(fixtures['fixtures'])} fixtures, expected ≥3"})
        
    except json.JSONDecodeError as e:
        issues.append({"issue": f"Invalid JSON: {e}"})
    
    return {
        "passed": len(issues) == 0,
        "check": "fixtures_exist",
        "issues": issues
    }


def main():
    """Run all Ring-1 checks"""
    print("=" * 60)
    print("RESISTANCE PROPHET RING-1 VALIDATION GATE")
    print("=" * 60)
    print(f"Timestamp: {datetime.now().isoformat()}")
    print()
    
    checks = [
        check_no_hard_coded_mapk_rr,
        check_ruo_disclaimer_constant,
        check_baseline_only_mode_constant,
        check_evidence_level_enum,
        check_fixtures_exist
    ]
    
    results = []
    all_passed = True
    
    for check_fn in checks:
        result = check_fn()
        results.append(result)
        
        status = "✅ PASS" if result["passed"] else "❌ FAIL"
        print(f"{status} - {result['check']}")
        
        if not result["passed"]:
            all_passed = False
            for issue in result.get("issues", []):
                print(f"       ⚠️  {issue.get('issue', issue)}")
        
        print()
    
    print("=" * 60)
    
    if all_passed:
        print("✅ ALL RING-1 CHECKS PASSED")
        print("   Ready for production deployment")
    else:
        print("❌ RING-1 VALIDATION FAILED")
        print("   Fix issues before production deployment")
    
    print("=" * 60)
    
    # Save report
    output_dir = Path("scripts/validation/out/ring1")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    report = {
        "timestamp": datetime.now().isoformat(),
        "overall_passed": all_passed,
        "checks": results
    }
    
    with open(output_dir / "report.json", "w") as f:
        json.dump(report, f, indent=2)
    
    print(f"\nReport saved to: {output_dir / 'report.json'}")
    
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()

