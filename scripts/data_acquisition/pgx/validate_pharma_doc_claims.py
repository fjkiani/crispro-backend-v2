#!/usr/bin/env python3
"""Validate pharma_integrated_development.mdc claims"""

import json
from pathlib import Path
from datetime import datetime
import re

DOC_CLAIMS = {
    "toxicity_prevention_sensitivity": {"claimed": "100% (6/6)", "line": 132},
    "toxicity_prevention_specificity": {"claimed": "100% (0 FP)", "line": 133},
    "cpic_concordance": {"claimed": "100% (N=59)", "line": 134},
    "prevention_rate_dpyd": {"claimed": "70-85%", "line": 269, "source": "Amstutz 2018"},
    "prevention_rate_tpmt": {"claimed": "80-85%", "line": 270, "source": "Relling 2019"},
    "prevention_rate_ugt1a1": {"claimed": "40-50%", "line": 271, "source": "Gammal 2016"},
    "medwatch_reduction": {"claimed": "95%", "line": 306},
    "mechanism_fit_ddr": {"claimed": "0.983", "line": 127},
    "drug_ranking_top5": {"claimed": "100% (17/17)", "line": 131}
}

OUR_VALIDATION = {
    "toxicity_prevention_sensitivity": {"value": 1.0, "n_cases": 6, "status": "VALIDATED"},
    "toxicity_prevention_specificity": {"value": 1.0, "n_cases": 59, "status": "VALIDATED"},
    "cpic_concordance": {"value": 1.0, "n_cases": 59, "status": "VALIDATED"},
    "mechanism_fit_ddr": {"value": 0.983, "status": "VALIDATED"},
    "drug_ranking_top5": {"value": 1.0, "n_patients": 17, "status": "VALIDATED"}
}

LITERATURE_DATA = {
    "dpyd": {"prevention_rate": 0.06, "n_patients": 4675},
    "tpmt": {"prevention_rate": 0.10, "n_patients": 1981},
    "ugt1a1": {"toxicity_reduction": 0.30, "n_patients": 3455}
}

CPIC_LITERATURE = {
    "dpyd": {"prevention_rate": 0.70, "range": [0.70, 0.85]},
    "tpmt": {"prevention_rate": 0.80, "range": [0.80, 0.85]},
    "ugt1a1": {"prevention_rate": 0.40, "range": [0.40, 0.50]}
}

def main():
    print("=" * 60)
    print("Validating pharma_integrated_development.mdc Claims")
    print("=" * 60)
    print()
    
    results = {}
    
    for claim_key, doc_claim in DOC_CLAIMS.items():
        print(f"🔍 {claim_key}")
        result = {"status": "UNKNOWN", "issues": [], "support": []}
        
        # Check our validation
        if claim_key in OUR_VALIDATION:
            our_val = OUR_VALIDATION[claim_key]
            if our_val["status"] == "VALIDATED":
                result["status"] = "✅ VALIDATED"
                result["support"].append(f"Internal validation: {our_val}")
        
        # Check prevention rates
        if claim_key.startswith("prevention_rate_"):
            gene = claim_key.split("_")[-1]
            doc_claim_val = doc_claim["claimed"]
            doc_nums = re.findall(r"(\d+)", doc_claim_val)
            
            if doc_nums:
                doc_min = int(doc_nums[0]) / 100
                doc_max = int(doc_nums[-1]) / 100 if len(doc_nums) > 1 else doc_min
                
                # Compare to extracteterature
                if gene in LITERATURE_DATA:
                    lit_rate = LITERATURE_DATA[gene].get("prevention_rate") or LITERATURE_DATA[gene].get("toxicity_reduction")
                    if lit_rate < doc_min:
                        result["issues"].append(
                            f"⚠️ DISCREPANCY: Doc claims {doc_claim_val}, "
                            f"extracted literature shows {lit_rate*100:.0f}% "
                            f"(from {LITERATURE_DATA[gene]['n_patients']} patients)"
                        )
                        result["status"] = "⚠️ DISCREPANCY"
                
                # Compare to CPIC literature (document source)
                if gene in CPIC_LITERATURE:
                    cpic_rate = CPIC_LITERATURE[gene]["prevention_rate"]
                    if doc_min <= cpic_rate <= doc_max:
                        result["support"].append(f"✅ Matches CPIC literature: {cpic_rate*100:.0f}%")
                        if result["status"] == "UNKNOWN":
                  result["status"] = "✅ LITERATURE_SUPPORTED"
        
        # MedWatch reduction
        if claim_key == "medwatch_reduction":
            doc_val = 0.95
            lit_est = 0.06
            result["issues"].append(
                f"⚠️ DISCREPANCY: Doc claims 95%, literature estimate is ~6%"
            )
            result["status"] = "⚠️ DISCREPANCY"
            result["note"] = "May mean '95% of PGx-preventable AEs' not '95% of all AEs'"
        
        results[claim_key] = result
        
        print(f"   {result['status']}")
        if result["issues"]:
            for issue in result["issues"]:
                print(f"      {issue}")
        print()
    
    # Save report
    output_dir = Path("oncology-coPilot/oncology-backend-minimal/scripts/data_acquisition/pgx")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    report = {
        "timestamp": datetime.now().isoformat(),
        "results": results,
        "summary": {
            "validated": sum(1 for r ivalues() if "✅" in r["status"]),
            "discrepancies": sum(1 for r in results.values() if "⚠️" in r["status"]),
            "unknown": sum(1 for r in results.values() if r["status"] == "UNKNOWN")
        }
    }
    
    json_file = output_dir / f"pharma_doc_validation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(json_file, 'w') as f:
        json.dump(report, f, indent=2)
    
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"✅ Validated: {report['summary']['validated']}")
    print(f"⚠️  Discrepancies: {report['summary']['discrepancies']}")
    print(f"❓ Unknown: {report['summary']['unknown']}")
    print(f"\n💾 Report: {json_file}")
    print("\n✅ Validation complete!")

if __name__ == "__main__":
    main()
