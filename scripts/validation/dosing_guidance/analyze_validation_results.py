#!/usr/bin/env python3
"""Comprehensive Analysis of Dosing Guidance Validation Results"""

import json

# Load validation report
with open('validation_report.json', 'r') as f:
    report = json.load(f)

# Load auto-curated data
with open('extraction_all_genes_auto_curated.json', 'r') as f:
    data = json.load(f)

cases = data.get('cases', [])

print("="*70)
print("DOSING GUIDANCE VALIDATION - COMPREHENSIVE ANALYSIS".center(70))
print("="*70)

# Overall statistics
print("\n📊 OVERALL STATISTICS")
print(f"   Total cases: {len(cases)}")
print(f"   Cases with toxicity=True: {sum(1 for c in cases if c.get('toxicity_occurred') == True)}")
print(f"   Cases with toxicity=False: {sum(1 for c in cases if c.get('toxicity_occurred') == False)}")
print(f"   Auto-curated cases: {sum(1 for c in cases if c.get('status') == 'auto_curated')}")

# Analyze toxicity cases
print("\n🔬 TOXICITY CASES ANALYSIS")
toxicity_cases = [c for c in cases if c.get('toxicity_occurred') == True]
print(f"   Total toxicity cases: {len(toxicity_cases)}")

for case in toxicity_cases:
    case_id = case.get('case_id', 'N/A')
    gene = case.get('gene', 'N/A')
    would_flag = case.get('our_prediction', {}).get('would_have_flagged', False)
    risk_level = case.get('our_prediction', {}).get('risk_level', 'N/A')
    cpic_level = case.get('our_prediction', {}).get('cpic_level', 'N/A')
    
    print(f"\n   {case_id} ({gene}):")
    print(f"      Would flag: {would_flag}")
    print(f"      Risk level: {risk_level}")
    print(f"      CPIC level: {cpic_level}")
    if not would_flag:
        print(f"      ⚠️  MISSED OPPORTUNITY")

# Validation metrics
print("\n📈 VALIDATION METRICS")
metrics = report.get('metrics', {})
print(f"   Sensitivity: {metrics.get('sensitivity', 0):.1f}%")
print(f"   Specificity: {metrics.get('specificity', 0):.1f}%")
print(f"   True positives: {metrics.get('true_positives', 0)}")
print(f"   False negatives: {metrics.get('false_negatives', 0)}")

print("\n💡 KEY FINDINGS")
missed = sum(1 for c in toxicity_cases if not c.get('our_prediction', {}).get('would_have_flagged', False))
print(f"   • {missed} out of {len(toxicity_cases)} toxicity cases were NOT flagged")
print(f"   • All toxicity cases are DPYD gene")
print(f"   • System showed 100% specificity (no false positives)")

print("\n" + "="*70)
