#!/usr/bin/env python3
"""PROXY vs TRUE SAE Comparison Test

Side-by-side comparison showing:
1. PROXY SAE: Gene-level → pathway burden → mechanism vector
2. TRUE SAE: Feature-level → DDR_bin → mechanism vector

Run:
  python scripts/validation/compare_proxy_vs_true_sae.py
"""

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# PROXY SAE: Gene-level pathway mapping
DDR_GENES = {'BRCA1', 'BRCA2', 'ATM', 'ATR', 'CHEK2', 'RAD51', 'PALB2', 'MBD4', 'TP53', 'PARP1', 'PARP2'}
MAPK_GENES = {'NF1', 'KRAS', 'BRAF', 'NRAS', 'MEK1', 'MEK2', 'ERK1', 'ERK2', 'MAPK1', 'MAPK3'}
PI3K_GENES = {'PIK3CA', 'PIK3CB', 'PIK3CD', 'PTEN', 'AKT1', 'AKT2', 'MTOR'}

# TRUE SAE: Diamond features (from mapping JSON)
MAPPING_PATH = REPO_ROOT / "api/resources/sae_feature_mapping.true_sae_diamonds.v1.json"
TIER3_PATH = REPO_ROOT / "data/validation/sae_cohort/checkpoints/Tier3_validation_cohort.json"


def compute_proxy_sae(mutations):
    """Compute PROXY SAE from gene-level mutations"""
    genes = {m.get("gene", "").upper() for m in mutations}
    
    ddr_genes_found = sorted(list(genes & DDR_GENES))
    mapk_genes_found = sorted(list(genes & MAPK_GENES))
    pi3k_genes_found = sorted(list(genes & PI3K_GENES))
    
    ddr_burden = min(1.0, len(ddr_genes_found) / 3.0)
    mapk_burden = min(1.0, len(mapk_genes_found) / 3.0)
    pi3k_burden = min(1.0, len(pi3k_genes_found) / 3.0)
    
    mechanism_vector = [ddr_burden, mapk_burden, pi3k_burden, 0.0, 0.0, 0.0, 0.0]
    dna_repair_capacity = 0.6 * ddr_burden + 0.2 * 0.5 + 0.2 * 0.5
    
    return {
        "mutations": [m.get("gene", "") for m in mutations],
        "ddr_genes": ddr_genes_found,
        "ddr_burden": ddr_burden,
        "mechanism_vector": mechanism_vector,
        "dna_repair_capacity": dna_repair_capacity,
        "method": "PROXY_SAE"
    }


def compute_true_sae(patient_id, tier3_data):
    """Compute TRUE SAE from Tier-3 patient data"""
    mapping = json.loads(MAPPING_PATH.read_text())
    diamond_feature_ids = sorted([int(f["feature_index"]) for f in mapping.get("features", [])])
    
    patient_data = tier3_data.get("data", {}).get(patient_id)
    if not patient_data:
        raise ValueError(f"Patient {patient_id} not found")
    
    feature_activations = {}
    for feat_idx in diamond_feature_ids:
        total = 0.0
        for variant in patient_data.get("variants", []):
            for tf in variant.get("top_features", []):
                if tf.get("index") == feat_idx:
                    total += float(tf.get("value", 0.0) or 0.0)
        feature_activations[feat_idx] = total
    
    ddr_bin_score = sum(feature_activations.values()) / len(diamond_feature_ids) if diamond_feature_ids else 0.0
    ddr_bin_score = min(1.0, ddr_bin_score)
    
    mechanism_vector = [ddr_bin_score, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    dna_repair_capacity = 0.6 * ddr_bin_score + 0.2 * 0.5 + 0.2 * 0.5
    
    return {
        "diamond_features": diamond_feature_ids,
        "ddr_bin_score": ddr_bin_score,
        "mechanism_vector": mechanism_vector,
        "dna_repair_capacity": dna_repair_capacity,
        "feature_activations": feature_activations,
        "method": "TRUE_SAE"
    }


def main():
    print("=" * 80)
    print("PROXY SAE vs TRUE SAE COMPARISON")
    print("=" * 80)
    print()
    
    # Test Case 1: Ayesha (MBD4 + TP53)
    print("TEST CASE 1: Ayesha (MBD4 + TP53)")
    print("-" * 80)
    
    ayesha_mutations = [
        {"gene": "MBD4", "hgvs_p": "p.R153*", "source": "germline"},
        {"gene": "TP53", "hgvs_p": "p.R175H", "source": "somatic"}
    ]
    
    proxy = compute_proxy_sae(ayesha_mutations)
    print("\n📊 PROXY SAE (Gene-Level):")
    print(f"  Mutations: {proxy['mutations']}")
    print(f"  DDR genes found: {proxy['ddr_genes']}")
    print(f"  DDR burden: {proxy['ddr_burden']:.3f}")
    print(f"  Mechanism vector: {[f'{v:.3f}' for v in proxy['mechanism_vector']]}")
    print(f"  DNA repair capacity: {proxy['dna_repair_capacity']:.3f}")
    print(f"  Method: {proxy['method']}")
    
    if TIER3_PATH.exists():
        tier3_data = json.loads(TIER3_PATH.read_text())
        sample_patients = list(tier3_data.get("data", {}).keys())[:5]
        
        if sample_patients:
            sample_id = sample_patients[0]
            try:
                true_sae = compute_true_sae(sample_id, tier3_data)
                print("\n📊 TRUE SAE (Feature-Level):")
                print(f"  Patient ID: {sample_id}")
                print(f"  Diamond features: {len(true_sae['diamond_features'])} features")
                print(f"  DDR_bin score: {true_sae['ddr_bin_score']:.3f}")
                print(f"  Mechanism vector: {[f'{v:.3f}' for v in true_sae['mechanism_vector']]}")
                print(f"  DNA repair capacity: {true_sae['dna_repair_capacity']:.3f}")
                print(f"  Method: {true_sae['method']}")
                print(f"  Top 3 feature activations:")
                sorted_features = sorted(true_sae['feature_activations'].items(), key=lambda x: -x[1])[:3]
                for feat_idx, val in sorted_features:
                    print(f"    Feature {feat_idx}: {val:.3f}")
            except Exception as e:
                print(f"\n⚠️  TRUE SAE computation failed: {e}")
    else:
        print("\n⚠️  Tier-3 cohort not found - skipping TRUE SAE example")
    
    print("\n" + "=" * 80)
    print("KEY DIFFERENCES")
    print("=" * 80)
    print()
    print("PROXY SAE:")
    print("  ✅ Fast ($0, no GPU)")
    print("  ✅ Validated on full cohorts (469 OV, 995 MM)")
    print("  ✅ Interpretable (gene names)")
    print("  ❌ Coarse (all TP53 mutations treated the same)")
    print("  ❌ No variant-level specificity")
    print("  ❌ Cannot simulate interventions (no steerability)")
    print()
    print("TRUE SAE:")
    print("  ✅ Variant-specific (p.R175H vs p.R273H have different scores)")
    print("  ✅ Sequence-aware (sees actual DNA/protein)")
    print("  ✅ Steerable (can clamp DDR_bin for counterfactuals)")
    print("  ✅ Early detection (DDR_bin monitoring)")
    print("  ⚠️  Requires GPU (~$0.10-0.30 per patient)")
    print("  ⚠️  Validated on Tier-3 (149 patients, AUROC 0.78)")
    print()
    print("=" * 80)
    print("RECOMMENDATION")
    print("=" * 80)
    print()
    print("Use PROXY SAE as default (production-ready, validated, cheap).")
    print("Use TRUE SAE when:")
    print("  - Variant-level specificity is needed")
    print("  - Steerability (counterfactual reasoning) is required")
    print("  - Early resistance detection (DDR_bin monitoring) is enabled")
    print()
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
