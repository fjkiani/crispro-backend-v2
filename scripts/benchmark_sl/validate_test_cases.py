#!/usr/bin/env python3
"""Test case validator - validates schema, PMIDs, ground truth."""
import json
from pathlib import Path

def validate_test_cases(test_file: str = "test_cases_100.json"):
    """Validate all test cases."""
    print(f"Validating {test_file}...")
    with open(test_file, 'r') as f:
        test_cases = json.load(f)
    
    errors = []
    for case in test_cases:
        case_id = case.get("case_id", "unknown")
        if "case_id" not in case:
            errors.append(f"{case_id}: Missing case_id")
        if "ground_truth" not in case:
            errors.append(f"{case_id}: Missing ground_truth")
        elif "pmid" in str(case.get("ground_truth", {}).get("clinical_evidence", {})):
            pmid = case["ground_truth"]["clinical_evidence"].get("pmid")
            if pmid:
                try:
                    int(pmid)
                except:
                    errors.append(f"{case_id}: Invalid PMID: {pmid}")
    
    stats = {
        "total": len(test_cases),
        "positive": sum(1 for c in test_cases if c.get("ground_truth", {}).get("synthetic_lethality_detected")),
        "with_pmids": sum(1 for c in test_cases if c.get("ground_truth", {}).get("clinical_evidence", {}).get("pmid"))
    }
    
    print("=" * 60)
    if not errors:
        print("✅ All test cases passed validation!")
    else:
        print(f"❌ Found {len(errors)} errors")
    print(f"📊 Total: {stats['total']}, Positive: {stats['positive']}, With PMIDs: {stats['with_pmids']}")
    
    Path("results").mkdir(exist_ok=True)
    with open("results/validation_report.json", 'w') as f:
        json.dump({"valid": len(errors) == 0, "errors": errors, "stats": stats}, f, indent=2)
    print("✅ Report saved to results/validation_report.json")

if __name__ == "__main__":
    import sys
    test_file = sys.argv[1] if len(sys.argv) > 1 else "test_cases_100.json"
    validate_test_cases(test_file)
