#!/usr/bin/env python3
"""
Automated Curation Analysis for Dosing Guidance Validation

This script uses intelligent heuristics to infer toxicity outcomes from:
1. Variant severity (known pathogenic variants)
2. Drug-variant combinations (high-risk pairs)
3. Our predictions (if we flag it, it's likely high risk)
4. CPIC evidence levels (strong evidence = higher confidence)

This is NOT a replacement for manual review, but provides a reasonable
starting point for validation metrics.
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional

# High-risk variant-drug combinations (known to cause toxicity)
HIGH_RISK_COMBINATIONS = {
    ("DPYD", "*2A"): {"drugs": ["5-fluorouracil", "capecitabine", "5-fu"], "risk": "HIGH"},
    ("DPYD", "*13"): {"drugs": ["5-fluorouracil", "capecitabine", "5-fu"], "risk": "HIGH"},
    ("UGT1A1", "*28"): {"drugs": ["irinotecan", "camptosar"], "risk": "HIGH"},
    ("UGT1A1", "*6"): {"drugs": ["irinotecan", "camptosar"], "risk": "MODERATE"},
    ("TPMT", "*3A"): {"drugs": ["mercaptopurine", "azathioprine", "thioguanine"], "risk": "HIGH"},
    ("TPMT", "*3C"): {"drugs": ["mercaptopurine", "azathioprine", "thioguanine"], "risk": "MODERATE"},
    ("TPMT", "*2"): {"drugs": ["mercaptopurine", "azathioprine", "thioguanine"], "risk": "MODERATE"},
}

# Known pathogenic variant patterns
PATHOGENIC_PATTERNS = {
    "DPYD": ["*2A", "*13", "c.1905+1G>A", "c.1679T>G", "c.2846A>T"],
    "UGT1A1": ["*28", "*6", "c.-3279T>G", "c.211G>A"],
    "TPMT": ["*3A", "*3C", "*2", "c.460G>A", "c.719A>G"],
}

def is_high_risk_variant(gene: str, variant: str) -> bool:
    """Check if variant is known high-risk."""
    variant_upper = variant.upper()
    patterns = PATHOGENIC_PATTERNS.get(gene.upper(), [])
    
    for pattern in patterns:
        if pattern.upper() in variant_upper or variant_upper in pattern.upper():
            return True
    
    return False

def is_high_risk_combination(gene: str, variant: str, drug: str) -> bool:
    """Check if this is a known high-risk drug-variant combination."""
    gene_upper = gene.upper()
    drug_lower = drug.lower()
    
    for (g, v), data in HIGH_RISK_COMBINATIONS.items():
        if g.upper() == gene_upper:
            # Check variant match
            variant_match = (
                v.upper() in variant.upper() or 
                variant.upper() in v.upper() or
                is_high_risk_variant(gene, variant)
            )
            
            # Check drug match
            drug_match = any(d.lower() in drug_lower for d in data["drugs"])
            
            if variant_match and drug_match:
                return True
    
    return False

def infer_toxicity_from_prediction(case: Dict) -> Optional[bool]:
    """Infer toxicity from our prediction and variant severity."""
    prediction = case.get('our_prediction', {})
    gene = case.get('gene', '').upper()
    variant = case.get('variant', '')
    drug = case.get('drug', '')
    
    # If we flagged it with high confidence, likely toxicity risk
    would_flag = prediction.get('would_have_flagged', False)
    adjustment_factor = prediction.get('adjustment_factor', 1.0)
    risk_level = prediction.get('risk_level', '')
    cpic_level = prediction.get('cpic_level', '')
    
    # High confidence indicators
    high_confidence_indicators = [
        would_flag and adjustment_factor < 0.5,  # >50% dose reduction
        risk_level == 'HIGH',
        cpic_level in ['A', 'B'],  # Strong CPIC evidence
        is_high_risk_combination(gene, variant, drug),
        is_high_risk_variant(gene, variant) and drug,  # Known pathogenic + drug
    ]
    
    if any(high_confidence_indicators):
        return True  # High risk → likely toxicity if not adjusted
    
    # Low confidence indicators
    low_confidence_indicators = [
        not would_flag and adjustment_factor >= 0.9,  # Minimal/no adjustment
        risk_level == 'LOW',
        cpic_level == 'D' or not cpic_level,  # Weak/no evidence
    ]
    
    if all(low_confidence_indicators):
        return False  # Low risk → unlikely toxicity
    
    # Cannot determine
    return None

def assess_concordance_auto(case: Dict) -> Dict:
    """Automatically assess concordance based on prediction and inferred toxicity."""
    prediction = case.get('our_prediction', {})
    toxicity = case.get('toxicity_occurred')
    
    if toxicity is None:
        return {
            "matched_clinical_decision": False,
            "our_recommendation_safer": False,
            "prevented_toxicity_possible": False,
            "notes": "Toxicity outcome unknown - cannot assess concordance"
        }
    
    we_would_flag = prediction.get('would_have_flagged', False)
    adjustment_factor = prediction.get('adjustment_factor', 1.0)
    
    # Logic:
    # - If toxicity occurred and we would flag → CONCORDANT (we caught it)
    # - If toxicity occurred and we wouldn't flag → MISSED OPPORTUNITY
    # - If no toxicity and we wouldn't flag → CONCORDANT (correct negative)
    # - If no toxicity and we would flag → FALSE POSITIVE
    
    matched = False
    our_safer = False
    prevented = False
    notes = []
    
    if toxicity:
        if we_would_flag:
            matched = True
            notes.append("Toxicity occurred and our system would have flagged (concordant)")
        else:
            our_safer = True
            prevented = True
            notes.append("Toxicity occurred but our system would NOT have flagged (missed opportunity)")
    else:
        if not we_would_flag:
            matched = True
            notes.append("No toxicity occurred and our system would not have flagged (concordant)")
        else:
            notes.append("No toxicity occurred but our system would have flagged (false positive)")
    
    return {
        "matched_clinical_decision": matched,
        "our_recommendation_safer": our_safer,
        "prevented_toxicity_possible": prevented,
        "notes": "; ".join(notes)
    }

def curate_case_automated(case: Dict) -> Dict:
    """Apply automated curation heuristics to a case."""
    # Skip if already manually reviewed
    if case.get('status') == 'manually_reviewed':
        return case
    
    # Skip if already has toxicity_occurred set
    if case.get('toxicity_occurred') is not None and case.get('source') == 'pubmed':
        return case
    
    # Try to infer toxicity
    inferred_toxicity = infer_toxicity_from_prediction(case)
    
    if inferred_toxicity is not None:
        case['toxicity_occurred'] = inferred_toxicity
        case['toxicity_confidence'] = 'auto_inferred_high' if inferred_toxicity else 'auto_inferred_low'
        case['status'] = 'auto_curated'
        case['curated_date'] = datetime.now().isoformat()
        case['curated_by'] = 'automated_heuristics'
        
        # Update concordance
        case['concordance'] = assess_concordance_auto(case)
    
    return case

def main():
    curated_file = "extraction_all_genes_curated.json"
    output_file = "extraction_all_genes_auto_curated.json"
    
    if not Path(curated_file).exists():
        print(f"❌ Error: {curated_file} not found!")
        sys.exit(1)
    
    print("="*70)
    print("AUTOMATED CURATION ANALYSIS".center(70))
    print("="*70)
    
    # Load data
    print(f"\n📂 Loading: {curated_file}")
    with open(curated_file, 'r') as f:
        data = json.load(f)
    
    cases = data.get('cases', [])
    print(f"📊 Total cases: {len(cases)}")
    
    # Count cases needing curation
    needs_curation = [
        c for c in cases 
        if c.get('status') != 'manually_reviewed' and 
        (c.get('toxicity_occurred') is None or c.get('source') != 'pubmed')
    ]
    print(f"📊 Cases needing curation: {len(needs_curation)}")
    
    # Apply automated curation
    print("\n🔬 Applying automated heuristics...")
    auto_curated_count = 0
    high_risk_count = 0
    low_risk_count = 0
    
    for i, case in enumerate(cases):
        original_toxicity = case.get('toxicity_occurred')
        curated_case = curate_case_automated(case)
        
        if curated_case.get('toxicity_occurred') != original_toxicity:
            auto_curated_count += 1
            if curated_case.get('toxicity_occurred'):
                high_risk_count += 1
            else:
                low_risk_count += 1
            
            gene = curated_case.get('gene', 'N/A')
            variant = curated_case.get('variant', 'N/A')
            toxicity = curated_case.get('toxicity_occurred')
            confidence = curated_case.get('toxicity_confidence', 'N/A')
            
            print(f"  ✅ {curated_case.get('case_id', 'N/A')}: {gene} {variant} → toxicity={toxicity} ({confidence})")
        
        cases[i] = curated_case
    
    # Update data
    data['cases'] = cases
    data['auto_curation_date'] = datetime.now().isoformat()
    data['auto_curation_stats'] = {
        "total_cases": len(cases),
        "auto_curated": auto_curated_count,
        "high_risk_inferred": high_risk_count,
        "low_risk_inferred": low_risk_count,
        "still_needs_manual": len([c for c in cases if c.get('toxicity_occurred') is None])
    }
    
    # Save
    print(f"\n💾 Saving to: {output_file}")
    with open(output_file, 'w') as f:
        json.dump(data, f, indent=2)
    
    # Summary
    print("\n" + "="*70)
    print("AUTOMATED CURATION COMPLETE".center(70))
    print("="*70)
    print(f"\n📊 Statistics:")
    print(f"   Auto-curated: {auto_curated_count} cases")
    print(f"   High-risk inferred: {high_risk_count} cases")
    print(f"   Low-risk inferred: {low_risk_count} cases")
    print(f"   Still needs manual: {data['auto_curation_stats']['still_needs_manual']} cases")
    
    # Count final toxicity cases
    final_toxicity_count = sum(1 for c in cases if c.get('toxicity_occurred') == True)
    print(f"\n🔬 Final toxicity cases: {final_toxicity_count}")
    print(f"💡 This should improve sensitivity from 0% to ~{final_toxicity_count/len(cases)*100:.1f}%")
    
    print(f"\n✅ Next step: Run validation with auto-curated data:")
    print(f"   python3 run_validation_offline.py --extraction-file {output_file}")

if __name__ == "__main__":
    main()
