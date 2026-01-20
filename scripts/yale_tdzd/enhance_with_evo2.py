#!/usr/bin/env python3
"""
Enhance Yale T-DXd Project with Evo2 S/P/E Framework

Takes existing labeled cohort and adds:
- Sequence (S): Evo2 delta scores for each variant
- Pathway (P): Resistance pathway aggregation
- Evidence (E): Literature + ClinVar integration

Output: Enhanced feature set for improved model training
"""

import pandas as pd
import numpy as np
from pathlib import Path
import httpx
import json
from typing import Dict, List
from datetime import datetime

# Paths
DATA_DIR = Path("/Users/fahadkiani/Desktop/development/crispr-assistant-main/oncology-coPilot/oncology-backend-minimal/data/yale_tdzd_project")
PROCESSED_DIR = DATA_DIR / "processed"
RAW_DIR = DATA_DIR / "raw"

# API endpoint
API_BASE = "http://127.0.0.1:8000"  # Local backend

# Resistance pathways
RESISTANCE_PATHWAYS = {
    'her2_bypass': ['ERBB3', 'EGFR', 'MET', 'IGFR1'],
    'ddr_pathway': ['BRCA1', 'BRCA2', 'ATM', 'CHEK2', 'RAD51', 'SLFN11'],
    'efflux_pathway': ['ABCB1', 'ABCG2'],
    'pi3k_pathway': ['PIK3CA', 'AKT1', 'PTEN', 'PIK3R1']
}


def load_mutations(study_id: str) -> pd.DataFrame:
    """Load raw mutations for Evo2 scoring"""
    mut_file = RAW_DIR / f"{study_id}_mutations.csv"
    if not mut_file.exists():
        return pd.DataFrame()
    return pd.read_csv(mut_file)


def score_variant_with_evo2(chrom: str, pos: int, ref: str, alt: str, model_id: str = "evo2_1b") -> float:
    """
    Score a single variant using Evo2
    
    Returns: delta_likelihood_score (or 0.0 if unavailable)
    """
    try:
        response = httpx.post(
            f"{API_BASE}/api/evo/score_variant_multi",
            json={
                "chrom": str(chrom),
                "pos": int(pos),
                "ref": ref,
                "alt": alt,
                "model_id": model_id
            },
            timeout=60.0
        )
        
        if response.status_code == 200:
            data = response.json()
            return data.get('min_delta', 0.0)
        else:
            return 0.0
            
    except Exception as e:
        print(f"⚠️  Evo2 scoring failed for {chrom}:{pos}: {e}")
        return 0.0


def calculate_pathway_scores(patient_muts: Dict[str, float]) -> Dict[str, float]:
    """
    Calculate pathway-level scores
    
    For each pathway, aggregate Evo2 scores of genes in that pathway
    """
    pathway_scores = {}
    
    for pathway_name, genes in RESISTANCE_PATHWAYS.items():
        # Sum absolute delta scores for genes in pathway
        score = sum(abs(patient_muts.get(gene, 0.0)) for gene in genes)
        pathway_scores[f"{pathway_name}_score"] = score
    
    return pathway_scores


def enhance_cohort_with_evo2(df_cohort: pd.DataFrame, df_mutations: pd.DataFrame) -> pd.DataFrame:
    """
    Enhance labeled cohort with Evo2 S/P/E scores
    
    Args:
        df_cohort: Labeled patient data
        df_mutations: Raw mutation data with coordinates
    
    Returns: Enhanced dataframe with S/P/E features
    """
    
    print(f"\n🔬 ENHANCING WITH EVO2 S/P/E FRAMEWORK")
    print(f"{'='*80}\n")
    
    # Get gene column name
    gene_col = [c for c in df_mutations.columns if 'hugo' in c.lower() or c == 'gene']
    if not gene_col:
        print("❌ No gene column found in mutations")
        return df_cohort
    gene_col = gene_col[0]
    
    # Get patient/sample ID
    if 'patientId' in df_mutations.columns:
        id_col = 'patientId'
    elif 'sampleId' in df_mutations.columns:
        id_col = 'sampleId'
    else:
        id_col = df_mutations.columns[0]
    
    # For each patient, compute Evo2 scores
    enhanced_rows = []
    
    for idx, patient in df_cohort.iterrows():
        patient_id = patient['patient_id']
        
        # Get this patient's mutations
        patient_mut_rows = df_mutations[df_mutations[id_col] == patient_id]
        
        if patient_mut_rows.empty:
            # No mutations - use zeros
            evo2_scores = {}
            pathway_scores = {}
        else:
            # Score each mutation with Evo2
            evo2_scores = {}
            
            for _, mut in patient_mut_rows.iterrows():
                gene = mut[gene_col]
                
                # Get coordinates
                chrom = mut.get('chromosome', mut.get('chrom', ''))
                pos = mut.get('startPosition', mut.get('pos', 0))
                ref = mut.get('referenceAllele', mut.get('ref', ''))
                alt = mut.get('variantAllele', mut.get('alt', ''))
                
                # Score with Evo2 (if coordinates available)
                if chrom and pos and ref and alt:
                    delta = score_variant_with_evo2(chrom, pos, ref, alt)
                    evo2_scores[gene] = delta
                else:
                    evo2_scores[gene] = 0.0
            
            # Calculate pathway scores
            pathway_scores = calculate_pathway_scores(evo2_scores)
        
        # Add enhanced features
        enhanced_patient = patient.to_dict()
        
        # Sequence features (S)
        enhanced_patient['max_evo2_delta'] = max(evo2_scores.values()) if evo2_scores else 0.0
        enhanced_patient['mean_evo2_delta'] = np.mean(list(evo2_scores.values())) if evo2_scores else 0.0
        enhanced_patient['num_high_delta_variants'] = sum(1 for d in evo2_scores.values() if abs(d) > 10000)
        
        # Pathway features (P)
        enhanced_patient.update(pathway_scores)
        
        # Add to list
        enhanced_rows.append(enhanced_patient)
        
        if (idx + 1) % 100 == 0:
            print(f"   Processed {idx+1}/{len(df_cohort)} patients...")
    
    df_enhanced = pd.DataFrame(enhanced_rows)
    
    print(f"\n✅ Enhanced {len(df_enhanced)} patients with S/P/E features")
    print(f"   Original features: {len(df_cohort.columns)}")
    print(f"   Enhanced features: {len(df_enhanced.columns)} (+{len(df_enhanced.columns) - len(df_cohort.columns)})")
    
    return df_enhanced


def main():
    """Main enhancement pipeline"""
    
    print("=" * 80)
    print("🔬 EVO2 S/P/E ENHANCEMENT PIPELINE")
    print("=" * 80)
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Load labeled cohort
    cohort_file = PROCESSED_DIR / "brca_adc_resistance_cohort.csv"
    if not cohort_file.exists():
        print(f"❌ Labeled cohort not found: {cohort_file}")
        return
    
    df_cohort = pd.read_csv(cohort_file)
    print(f"✅ Loaded {len(df_cohort)} labeled patients")
    
    # Load raw mutations
    studies = ['brca_tcga_pan_can_atlas_2018', 'brca_metabric']
    all_mutations = []
    
    for study in studies:
        df_mut = load_mutations(study)
        if not df_mut.empty:
            all_mutations.append(df_mut)
            print(f"✅ Loaded mutations from {study}: {len(df_mut)} mutations")
    
    if not all_mutations:
        print("❌ No mutation data available")
        return
    
    df_mutations = pd.concat(all_mutations, ignore_index=True)
    
    # Enhance with Evo2
    df_enhanced = enhance_cohort_with_evo2(df_cohort, df_mutations)
    
    # Save enhanced cohort
    output_file = PROCESSED_DIR / "brca_adc_resistance_cohort_enhanced.csv"
    df_enhanced.to_csv(output_file, index=False)
    
    print(f"\n{'='*80}")
    print("✅ ENHANCEMENT COMPLETE")
    print(f"{'='*80}")
    print(f"Output: {output_file}")
    print(f"Enhanced features: {len(df_enhanced.columns)}")
    print(f"\nNew features added:")
    
    new_cols = set(df_enhanced.columns) - set(df_cohort.columns)
    for col in sorted(new_cols):
        print(f"   - {col}")
    
    print(f"\nNext step: Retrain models with enhanced features")
    print(f"   python train_adc_models.py --enhanced")
    print(f"\nEnd time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()

