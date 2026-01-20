#!/usr/bin/env python3
"""
Risk-Benefit Composition Validation Script

Validates the deterministic composition logic for combining
efficacy scores with toxicity tiers into a unified risk-benefit score.

TRANSPARENCY NOTICE:
This script validates LOGIC CORRECTNESS only.
It does NOT validate clinical outcomes or policy optimality.

Usage:
    python3 validate_composition.py

Output:
    ../reports/composition_report.json
    ../reports/COMPOSITION_REPORT.md
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict

# ============================================================================
# COMPOSITION POLICY (The Logic Being Validated)
# ============================================================================

def compose_risk_benefit(
    efficacy_score: float,
    toxicity_tier: Optional[str],
    adjustment_factor: Optional[float]
) -> Tuple[float, str]:
    """
    Deterministic composition of efficacy and toxicity.
    
    Policy (EC2-aligned):
    - HIGH toxicity → Hard veto (score=0, AVOID)
    - MODERATE toxicity → Penalized (score × adjustment_factor)
    - LOW/None toxicity → Full score
    
    Args:
        efficacy_score: From S/P/E framework (0.0 - 1.0)
        toxicity_tier: From PGx screening ("LOW", "MODERATE", "HIGH", or None)
        adjustment_factor: From PGx screening (0.0 - 1.0, where 1.0 = no adjustment)
    
    Returns:
        (composite_score, action_label)
    """
    # Handle missing PGx data
    if toxicity_tier is None or adjustment_factor is None:
        return efficacy_score, "PREFERRED (PGx UNSCREENED)"
    
    # Hard veto for HIGH toxicity or contraindicated
    if toxicity_tier == "HIGH" or adjustment_factor <= 0.1:
        return 0.0, "AVOID / HIGH-RISK"
    
    # Penalized for MODERATE toxicity
    if toxicity_tier == "MODERATE" or adjustment_factor < 0.8:
        composite = round(efficacy_score * adjustment_factor, 3)
        return composite, "CONSIDER WITH MONITORING"
    
    # No concerns - full efficacy
    return efficacy_score, "PREFERRED"


# ============================================================================
# VALIDATION LOGIC
# ============================================================================

@dataclass
class CaseResult:
    """Result for a single test case."""
    case_id: str
    group: str
    description: str
    passed: bool
    expected_composite: float
    actual_composite: float
    expected_label: str
    actual_label: str
    composite_match: bool
    label_match: bool
    notes: str = ""


def validate_case(case: Dict[str, Any]) -> CaseResult:
    """Validate a single test case."""
    inputs = case["inputs"]
    expected = case["expected"]
    
    # Run composition
    actual_composite, actual_label = compose_risk_benefit(
        efficacy_score=inputs["efficacy_score"],
        toxicity_tier=inputs.get("toxicity_tier"),
        adjustment_factor=inputs.get("adjustment_factor")
    )
    
    # Compare results
    expected_composite = expected["composite_score"]
    expected_label = expected["action_label"]
    
    # Allow small floating point tolerance
    composite_match = abs(actual_composite - expected_composite) < 0.001
    label_match = actual_label == expected_label
    passed = composite_match and label_match
    
    notes = ""
    if not composite_match:
        notes += f"Composite mismatch: expected {expected_composite}, got {actual_composite}. "
    if not label_match:
        notes += f"Label mismatch: expected '{expected_label}', got '{actual_label}'. "
    
    return CaseResult(
        case_id=case["case_id"],
        group=case["group"],
        description=case["description"],
        passed=passed,
        expected_composite=expected_composite,
        actual_composite=actual_composite,
        expected_label=expected_label,
        actual_label=actual_label,
        composite_match=composite_match,
        label_match=label_match,
        notes=notes.strip()
    )


def run_validation(cases: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Run validation on all cases and generate report."""
    results = []
    
    for case in cases:
        result = validate_case(case)
        results.append(result)
    
    # Compute statistics
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    failed = total - passed
    pass_rate = (passed / total * 100) if total > 0 else 0.0
    
    # Group statistics
    group_stats = {}
    for r in results:
        group = r.group
        if group not in group_stats:
            group_stats[group] = {"total": 0, "passed": 0}
        group_stats[group]["total"] += 1
        if r.passed:
            group_stats[group]["passed"] += 1
    
    for group in group_stats:
        stats = group_stats[group]
        stats["rate"] = (stats["passed"] / stats["total"] * 100) if stats["total"] > 0 else 0.0
    
    # Build report
    report = {
        "validation_suite": "risk_benefit_composition",
        "version": "1.0",
        "timestamp": datetime.now().isoformat(),
        "summary": {
            "total_cases": total,
            "passed": passed,
            "failed": failed,
            "pass_rate": pass_rate,
            "status": "PASS" if failed == 0 else "FAIL"
        },
        "group_statistics": group_stats,
        "transparency_notice": {
            "what_this_proves": [
                "Composition logic is deterministically correct",
                "All toxicity tiers handled as specified",
                "Edge cases handled gracefully"
            ],
            "what_this_does_not_prove": [
                "The policy improves patient outcomes",
                "The weights are optimal",
                "The system generalizes to unseen patients"
            ]
        },
        "detailed_results": [asdict(r) for r in results],
        "failed_cases": [asdict(r) for r in results if not r.passed]
    }
    
    return report


def generate_markdown_report(report: Dict[str, Any]) -> str:
    """Generate human-readable markdown report."""
    summary = report["summary"]
    
    md = f"""# Risk-Benefit Composition Validation Report

**Generated:** {report["timestamp"]}  
**Status:** {"✅ PASS" if summary["status"] == "PASS" else "❌ FAIL"}

---

## 📊 Summary

| Metric | Value |
|--------|-------|
| **Total Cases** | {summary["total_cases"]} |
| **Passed** | {summary["passed"]} |
| **Failed** | {summary["failed"]} |
| **Pass Rate** | **{summary["pass_rate"]:.1f}%** |

"""

    # Progress bar
    bar_length = 20
    filled = int(summary["pass_rate"] / 100 * bar_length)
    empty = bar_length - filled
    md += f"""### Pass Rate
```
[{"█" * filled}{"░" * empty}] {summary["pass_rate"]:.1f}%
```

"""

    # Group statistics
    md += "## 📈 Results by Group\n\n"
    md += "| Group | Total | Passed | Rate |\n"
    md += "|-------|-------|--------|------|\n"
    for group, stats in report["group_statistics"].items():
        status = "✅" if stats["rate"] == 100 else "❌"
        md += f"| {group} | {stats['total']} | {stats['passed']} | {status} {stats['rate']:.0f}% |\n"
    md += "\n"

    # Detailed results
    md += "## 📋 Detailed Results\n\n"
    
    # Passed cases
    md += "### ✅ Passed Cases\n\n"
    md += "| Case | Group | Expected Score | Actual Score | Label |\n"
    md += "|------|-------|----------------|--------------|-------|\n"
    for r in report["detailed_results"]:
        if r["passed"]:
            md += f"| {r['case_id']} | {r['group']} | {r['expected_composite']} | {r['actual_composite']} | {r['actual_label']} |\n"
    md += "\n"

    # Failed cases
    if report["failed_cases"]:
        md += "### ❌ Failed Cases\n\n"
        md += "| Case | Group | Expected | Actual | Notes |\n"
        md += "|------|-------|----------|--------|-------|\n"
        for r in report["failed_cases"]:
            md += f"| {r['case_id']} | {r['group']} | {r['expected_composite']} / {r['expected_label']} | {r['actual_composite']} / {r['actual_label']} | {r['notes']} |\n"
        md += "\n"

    # Transparency notice
    md += """## ⚠️ Transparency Notice

### What This PROVES:
"""
    for item in report["transparency_notice"]["what_this_proves"]:
        md += f"- ✅ {item}\n"
    
    md += """
### What This DOES NOT PROVE:
"""
    for item in report["transparency_notice"]["what_this_does_not_prove"]:
        md += f"- ❌ {item}\n"

    md += """
---

## 🔗 Ledger Entry

If all cases pass, add this entry to `VALIDATED_CLAIMS_LEDGER.md`:

```
| **Risk-Benefit Composition** | Deterministic composition logic | 100% pass (N=15 cases) | Synthetic test suite | `risk_benefit_validation/reports/composition_report.json` | `python risk_benefit_validation/scripts/validate_composition.py` | `composition_report.json` |
```

---

*Generated by: validate_composition.py*
"""
    
    return md


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Main entry point."""
    # Determine paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(script_dir, "..", "data")
    reports_dir = os.path.join(script_dir, "..", "reports")
    
    # Ensure reports directory exists
    os.makedirs(reports_dir, exist_ok=True)
    
    # Load test cases
    cases_file = os.path.join(data_dir, "synthetic_cases.json")
    print(f"📂 Loading test cases from: {cases_file}")
    
    with open(cases_file, "r") as f:
        data = json.load(f)
    
    cases = data["cases"]
    print(f"📊 Loaded {len(cases)} test cases")
    
    # Run validation
    print("🔬 Running validation...")
    report = run_validation(cases)
    
    # Save JSON report
    json_path = os.path.join(reports_dir, "composition_report.json")
    with open(json_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"✅ JSON report saved to: {json_path}")
    
    # Save Markdown report
    md_report = generate_markdown_report(report)
    md_path = os.path.join(reports_dir, "COMPOSITION_REPORT.md")
    with open(md_path, "w") as f:
        f.write(md_report)
    print(f"✅ Markdown report saved to: {md_path}")
    
    # Print summary
    summary = report["summary"]
    print("\n" + "=" * 60)
    print("RISK-BENEFIT COMPOSITION VALIDATION RESULTS")
    print("=" * 60)
    print(f"Total cases: {summary['total_cases']}")
    print(f"Passed: {summary['passed']}")
    print(f"Failed: {summary['failed']}")
    print(f"Pass rate: {summary['pass_rate']:.1f}%")
    print("=" * 60)
    
    if summary["status"] == "PASS":
        print("\n🎉 ALL TESTS PASSED!")
        print("Composition logic is deterministically correct.")
        print("\n📝 Next step: Add receipt to VALIDATED_CLAIMS_LEDGER.md")
    else:
        print("\n❌ VALIDATION FAILED")
        print("Review failed cases in the report.")
        for r in report["failed_cases"]:
            print(f"  - {r['case_id']}: {r['notes']}")
    
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    exit(main())

