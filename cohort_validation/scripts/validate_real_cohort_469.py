#!/usr/bin/env python3
"""
REAL VALIDATION: 469 TCGA Ovarian Cancer Patients with Platinum Response
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple
from dataclasses import dataclass

# DDR genes for proxy pathway computation
DDR_GENES = {
    'BRCA1', 'BRCA2', 'ATM', 'ATR', 'CHEK1', 'CHEK2', 'RAD51', 'PALB2',
    'MBD4', 'MLH1', 'MSH2', 'MSH6', 'PMS2', 'TP53', 'RAD50', 'NBN',
    'FANCA', 'FANCD2', 'BLM', 'WRN', 'RECQL4'
}

@dataclass
class PatientProfile:
    patient_id: str
    platinum_response: str
    mutations: List[str]
    ddr_score: float
    mechanism_vector: List[float]


def compute_proxy_mechanism(mutations: List[Dict]) -> Tuple[float, List[float]]:
    genes = {m.get('gene', '').upper() for m in mutations}
    ddr_hits = len(genes & DDR_GENES)
    ddr_score = min(1.0, ddr_hits / 3.0)
    mechanism_vector = [ddr_score, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    return ddr_score, mechanism_vector


def load_cohort() -> List[PatientProfile]:
    data_path = Path("/Users/fahadkiani/Desktop/development/crispr-assistant-main/data/validation/sae_cohort/tcga_ov_platinum_with_mutations.json")
    with open(data_path) as f:
        data = json.load(f)
    
    patients = []
    for p in data:
        ddr_score, mech_vec = compute_proxy_mechanism(p.get('mutations', []))
        profile = PatientProfile(
            patient_id=p.get('tcga_patient_id', 'unknown'),
            platinum_response=p.get('platinum_response', 'unknown'),
            mutations=[m.get('gene', '') for m in p.get('mutations', [])],
            ddr_score=ddr_score,
            mechanism_vector=mech_vec
        )
        patients.append(profile)
    return patients


def main():
    print("="*60)
    print("REAL VALIDATION: 469 TCGA Ovarian Cancer Patients")
    print("Ground Truth: Platinum Response Labels")
    print("="*60)
    
    patients = load_cohort()
    print(f"\n✅ Loaded {len(patients)} patients")
    
    # Outcome distribution
    outcomes = {}
    for p in patients:
        outcomes[p.platinum_response] = outcomes.get(p.platinum_response, 0) + 1
    print("\nOutcome distribution:")
    for k, v in sorted(outcomes.items()):
        print(f"  {k}: {v} ({v/len(patients)*100:.1f}%)")
    
    # VALIDATION 1: DDR vs Response
    print("\n" + "="*60)
    print("VALIDATION 1: DDR Score vs Platinum Response")
    print("="*60)
    
    ddr_high = [p for p in patients if p.ddr_score >= 0.5]
    ddr_low = [p for p in patients if p.ddr_score < 0.5]
    
    high_sens = sum(1 for p in ddr_high if p.platinum_response == 'sensitive') / len(ddr_high) if ddr_high else 0
    low_sens = sum(1 for p in ddr_low if p.platinum_response == 'sensitive') / len(ddr_low) if ddr_low else 0
    
    print(f"\nDDR-HIGH (≥0.5): {len(ddr_high)} patients, {high_sens:.1%} sensitive")
    print(f"DDR-LOW (<0.5):  {len(ddr_low)} patients, {low_sens:.1%} sensitive")
    
    lift = (high_sens - low_sens) / low_sens if low_sens > 0 else 0
    print(f"\n📊 Sensitivity lift: {lift:+.1%}")
    
    v1_passed = high_sens > low_sens
    print(f"{'✅ PASSED' if v1_passed else '❌ FAILED'}: DDR-high {'shows' if v1_passed else 'does not show'} better response")
    
    # VALIDATION 2: Quintile Analysis
    print("\n" + "="*60)
    print("VALIDATION 2: Response by DDR Quintile")
    print("="*60)
    
    sorted_patients = sorted(patients, key=lambda p: p.ddr_score)
    n = len(sorted_patients)
    
    print("\nQuintile | N   | Avg DDR | Sensitivity")
    print("---------+-----+---------+------------")
    
    q_sens = []
    for i in range(5):
        start = i * (n // 5)
        end = start + (n // 5) if i < 4 else n
        q = sorted_patients[start:end]
        sens = sum(1 for p in q if p.platinum_response == 'sensitive') / len(q)
        avg_ddr = sum(p.ddr_score for p in q) / len(q)
        q_sens.append(sens)
        print(f"   Q{i+1}    | {len(q):3d} |  {avg_ddr:.2f}   |   {sens:.1%}")
    
    gradient = q_sens[4] - q_sens[0]
    v2_passed = gradient > 0
    print(f"\n📊 Q5-Q1 gradient: {gradient:+.1%}")
    print(f"{'✅ PASSED' if v2_passed else '❌ FAILED'}: {'Positive' if v2_passed else 'Negative'} dose-response")
    
    # VALIDATION 3: Resistant vs Sensitive profiles
    print("\n" + "="*60)
    print("VALIDATION 3: Resistant vs Sensitive Profiles")
    print("="*60)
    
    sensitive = [p for p in patients if p.platinum_response == 'sensitive']
    resistant = [p for p in patients if p.platinum_response in ['resistant', 'refractory']]
    
    sens_ddr = sum(p.ddr_score for p in sensitive) / len(sensitive) if sensitive else 0
    res_ddr = sum(p.ddr_score for p in resistant) / len(resistant) if resistant else 0
    
    print(f"\nSensitive (n={len(sensitive)}): Avg DDR = {sens_ddr:.3f}")
    print(f"Resistant (n={len(resistant)}): Avg DDR = {res_ddr:.3f}")
    
    ddr_diff = sens_ddr - res_ddr
    v3_passed = ddr_diff > 0
    print(f"\n📊 DDR difference: {ddr_diff:+.3f}")
    print(f"{'✅ PASSED' if v3_passed else '❌ FAILED'}: Sensitive {'has' if v3_passed else 'does not have'} higher DDR")
    
    # SUMMARY
    print("\n" + "="*60)
    print("VALIDATION SUMMARY")
    print("="*60)
    
    passed = sum([v1_passed, v2_passed, v3_passed])
    
    print(f"\n{'✅' if v1_passed else '❌'} V1: DDR-high sensitivity lift")
    print(f"{'✅' if v2_passed else '❌'} V2: Quintile dose-response")
    print(f"{'✅' if v3_passed else '❌'} V3: Resistant profile difference")
    
    print(f"\n📊 OVERALL: {passed}/3 validations passed")
    
    print("\n" + "="*60)
    print("KEY REAL METRICS (Not Inflated)")
    print("="*60)
    print(f"  Sensitivity lift (DDR-high vs DDR-low): {lift:+.1%}")
    print(f"  Quintile gradient (Q5 - Q1): {gradient:+.1%}")
    print(f"  DDR difference (sens - res): {ddr_diff:+.3f}")
    
    # Save report
    report = {
        "cohort_size": len(patients),
        "outcome_distribution": outcomes,
        "v1_sensitivity_lift": lift,
        "v2_quintile_gradient": gradient,
        "v3_ddr_difference": ddr_diff,
        "validations_passed": passed,
        "validations_total": 3
    }
    
    report_path = Path(__file__).parent / "real_validation_report.json"
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2, default=str)
    print(f"\nReport: {report_path}")
    
    return 0 if passed >= 2 else 1


if __name__ == "__main__":
    sys.exit(main())
