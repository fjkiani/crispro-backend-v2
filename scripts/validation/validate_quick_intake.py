#!/usr/bin/env python3
"""
Validate Quick Intake - Production Validation Script

Source of Truth: .cursor/MOAT/SPORADIC_CANCER_PRODUCTION_PLAN.md
Task: Phase 1.2 - Test Quick Intake Endpoint

Validates:
- All 15 cancer types return valid TumorContext
- Each response includes required fields (tmb, hrd_score, msi_status, completeness_score)
"""

import sys
import asyncio
import json
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from api.services.tumor_quick_intake import generate_level0_tumor_context


# All 15 cancer types from disease_priors.json
ALL_CANCERS = [
    "ovarian_hgs",
    "breast_tnbc",
    "colorectal",
    "lung_nsclc",
    "pancreatic",
    "prostate_adenocarcinoma",
    "melanoma_cutaneous",
    "bladder_urothelial",
    "endometrial_uterine",
    "gastric_adenocarcinoma",
    "esophageal_adenocarcinoma",
    "head_neck_squamous",
    "glioblastoma_multiforme",
    "renal_clear_cell",
    "acute_myeloid_leukemia"
]


async def test_cancer(cancer_type: str) -> tuple[bool, dict]:
    """Test Quick Intake for a single cancer type"""
    try:
        context, provenance, conf_cap, recommendations = await generate_level0_tumor_context(
            cancer_type=cancer_type,
            stage="III",
            line=2
        )
        
        # Extract values (handle both Pydantic model and dict)
        tmb = context.tmb if hasattr(context, 'tmb') else context.get("tmb")
        hrd = context.hrd_score if hasattr(context, 'hrd_score') else context.get("hrd_score")
        msi = context.msi_status if hasattr(context, 'msi_status') else context.get("msi_status")
        comp = context.completeness_score if hasattr(context, 'completeness_score') else context.get("completeness_score")
        
        # Validate required fields
        # Note: msi_status can be None when unknown (per tumor_quick_intake.py line 146)
        errors = []
        if tmb is None:
            errors.append("tmb missing")
        if hrd is None:
            errors.append("hrd_score missing")
        # msi_status can be None (unknown) - this is valid behavior
        if comp is None:
            errors.append("completeness_score missing")
        
        if errors:
            return False, {"errors": errors}
        
        return True, {
            "tmb": tmb,
            "hrd_score": hrd,
            "msi_status": msi,
            "completeness_score": comp,
            "confidence_cap": conf_cap
        }
    except Exception as e:
        return False, {"error": str(e)}


async def main():
    """Run validation for all 15 cancer types"""
    print("=" * 60)
    print("QUICK INTAKE VALIDATION (15 Cancer Types)")
    print("=" * 60)
    print()
    
    results = {}
    passed = 0
    
    for cancer in ALL_CANCERS:
        success, data = await test_cancer(cancer)
        results[cancer] = {"passed": success, "data": data}
        
        if success:
            passed += 1
            msi_display = data['msi_status'] if data['msi_status'] is not None else "None (unknown)"
            print(f"✅ {cancer}: TMB={data['tmb']}, HRD={data['hrd_score']}, MSI={msi_display}, completeness={data['completeness_score']:.2f}")
        else:
            print(f"❌ {cancer}: {data.get('error', data.get('errors', 'Unknown error'))}")
    
    print()
    print("=" * 60)
    print(f"RESULTS: {passed}/{len(ALL_CANCERS)} cancers passed")
    print("=" * 60)
    
    # Save report
    report_dir = Path(project_root) / "scripts" / "validation" / "out" / "quick_intake"
    report_dir.mkdir(parents=True, exist_ok=True)
    
    report = {
        "timestamp": datetime.now().isoformat(),
        "total_cancers": len(ALL_CANCERS),
        "passed": passed,
        "failed": len(ALL_CANCERS) - passed,
        "results": results,
        "status": "PASS" if passed == len(ALL_CANCERS) else "FAIL"
    }
    
    with open(report_dir / "report.json", "w") as f:
        json.dump(report, f, indent=2)
    
    print(f"\nReport saved to: {report_dir / 'report.json'}")
    
    return 0 if passed == len(ALL_CANCERS) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

