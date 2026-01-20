#!/usr/bin/env python3
"""
Verify the 469-patient validation claims from RESISTANCE_PREDICTION_VALIDATED.md
"""

import json
import sys
from pathlib import Path

# MAPK genes
MAPK_GENES = {'KRAS', 'NRAS', 'BRAF', 'NF1', 'MAP2K1', 'MAP2K2'}

# Load 469-patient dataset with mutations
path = Path("data/validation/tcga_ov_469_with_hrd.json")
if not path.exists():
    # Try relative to script location
    path = Path(__file__).parent.parent.parent.parent / "data" / "validation" / "tcga_ov_469_with_hrd.json"

with open(path) as f:
    data = json.load(f)

patients = data if isinstance(data, list) else data.get('patients', [])

print(f"Total patients: {len(patients)}")

# Count MAPK and NF1
mapk_resistant = 0
mapk_sensitive = 0
wt_resistant = 0
wt_sensitive = 0
nf1_resistant = 0
nf1_sensitive = 0
total_resistant = 0
total_sensitive = 0
mapk_count = 0
nf1_count = 0

for p in patients:
    # Get mutations
    mutations = p.get('mutations', [])
    
    # Extract genes
    genes = set()
    for m in mutations:
        if isinstance(m, dict):
            gene = m.get('gene', '').upper()
            if gene:
                genes.add(gene)
        elif isinstance(m, str):
            genes.add(m.upper())
    
    # Get response - handle dict structure
    response = ""
    if 'platinum_response' in p:
        resp_val = p['platinum_response']
        if isinstance(resp_val, str):
            response = resp_val.lower()
        elif isinstance(resp_val, dict):
            response = resp_val.get('response_category', '').lower()
    elif 'treatment_response' in p:
        resp_val = p['treatment_response']
        if isinstance(resp_val, str):
            response = resp_val.lower()
        elif isinstance(resp_val, dict):
            response = resp_val.get('response_category', '').lower()
    
    is_resistant = response in ['resistant', 'refractory']
    is_sensitive = response == 'sensitive'
    
    if is_resistant:
        total_resistant += 1
    elif is_sensitive:
        total_sensitive += 1
    
    has_mapk = bool(genes & MAPK_GENES)
    has_nf1 = 'NF1' in genes
    
    if has_mapk:
        mapk_count += 1
        if is_resistant:
            mapk_resistant += 1
        elif is_sensitive:
            mapk_sensitive += 1
    
    if has_nf1:
        nf1_count += 1
        if is_resistant:
            nf1_resistant += 1
        elif is_sensitive:
            nf1_sensitive += 1
    
    if not has_mapk:
        if is_resistant:
            wt_resistant += 1
        elif is_sensitive:
            wt_sensitive += 1

print(f"\n=== Response Distribution ===")
print(f"Resistant: {total_resistant}")
print(f"Sensitive: {total_sensitive}")

print(f"\n=== MAPK Counts ===")
print(f"MAPK+ patients: {mapk_count}")
print(f"MAPK+ Resistant: {mapk_resistant}")
print(f"MAPK+ Sensitive: {mapk_sensitive}")
print(f"WT Resistant: {wt_resistant}")
print(f"WT Sensitive: {wt_sensitive}")

# Calculate RR
if (mapk_resistant + mapk_sensitive) > 0 and (wt_resistant + wt_sensitive) > 0:
    risk_mapk = mapk_resistant / (mapk_resistant + mapk_sensitive) if (mapk_resistant + mapk_sensitive) > 0 else 0
    risk_wt = wt_resistant / (wt_resistant + wt_sensitive) if (wt_resistant + wt_sensitive) > 0 else 0
    if risk_wt > 0:
        rr_mapk = risk_mapk / risk_wt
        print(f"\nMAPK Relative Risk: {rr_mapk:.2f}x")
        print(f"  MAPK risk: {risk_mapk:.3f} ({mapk_resistant}/{mapk_resistant + mapk_sensitive})")
        print(f"  WT risk: {risk_wt:.3f} ({wt_resistant}/{wt_resistant + wt_sensitive})")
        print(f"  Claimed: 2.7x (1.97x in ledger)")
        match_mapk = abs(rr_mapk - 2.7) < 0.5 or abs(rr_mapk - 1.97) < 0.3
        print(f"  Match: {'✅ YES' if match_mapk else '❌ NO'}")
    else:
        print(f"\nMAPK Relative Risk: Cannot compute (WT risk = 0)")

print(f"\n=== NF1 Counts ===")
print(f"NF1+ patients: {nf1_count}")
print(f"NF1+ Resistant: {nf1_resistant}")
print(f"NF1+ Sensitive: {nf1_sensitive}")

if total_resistant > 0 and total_sensitive > 0:
    nf1_pct_resistant = (nf1_resistant / total_resistant * 100)
    nf1_pct_sensitive = (nf1_sensitive / total_sensitive * 100)
    nf1_enrichment = nf1_pct_resistant / nf1_pct_sensitive if nf1_pct_sensitive > 0 else 0
    print(f"\nNF1 % in Resistant: {nf1_pct_resistant:.1f}% ({nf1_resistant}/{total_resistant})")
    print(f"NF1 % in Sensitive: {nf1_pct_sensitive:.1f}% ({nf1_sensitive}/{total_sensitive})")
    print(f"NF1 Enrichment: {nf1_enrichment:.2f}x")
    
    # Compare to claim
    print(f"\n=== Comparison to Claim ===")
    print(f"Claimed: 16.1% in resistant, 4.5% in sensitive, 3.5x enrichment")
    print(f"Actual: {nf1_pct_resistant:.1f}% in resistant, {nf1_pct_sensitive:.1f}% in sensitive, {nf1_enrichment:.2f}x enrichment")
    match = abs(nf1_pct_resistant - 16.1) < 2 and abs(nf1_pct_sensitive - 4.5) < 2 and abs(nf1_enrichment - 3.5) < 0.5
    print(f"Match: {'✅ YES' if match else '❌ NO'}")
    
    # Also calculate NF1 resistance rate
    if nf1_count > 0:
        nf1_resistance_rate = (nf1_resistant / nf1_count * 100) if nf1_count > 0 else 0
        wt_count = len(patients) - nf1_count
        wt_resistance_rate = (wt_resistant / wt_count * 100) if wt_count > 0 else 0
        nf1_rr = nf1_resistance_rate / wt_resistance_rate if wt_resistance_rate > 0 else 0
        print(f"\n=== NF1 Resistance Rate ===")
        print(f"NF1-mutant resistance rate: {nf1_resistance_rate:.1f}% ({nf1_resistant}/{nf1_count})")
        print(f"WT resistance rate: {wt_resistance_rate:.1f}% ({wt_resistant}/{wt_count})")
        print(f"NF1 Relative Risk (resistance rate): {nf1_rr:.2f}x")
        print(f"Claimed: 2.1x (30.8% vs 14.7%)")
        match_rr = abs(nf1_rr - 2.1) < 0.3
        print(f"Match: {'✅ YES' if match_rr else '❌ NO'}")
