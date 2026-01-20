#!/usr/bin/env python3
"""
ADC Resistance Auto-Labeling Pipeline for Yale T-DXd Project

Generates resistance labels WITHOUT manual curation based on:
1. Mutation patterns (TP53, PIK3CA, ERBB2, etc.)
2. Gene expression levels (HER2, TROP2, SLFN11)
3. Pathway disruptions (DDR, drug efflux, HER2 bypass)

Label Categories:
- ADC_RESISTANCE_RISK: HIGH / MEDIUM / LOW
- SG_CROSS_RESISTANCE_RISK: HIGH / MEDIUM / LOW (sacituzumab govitecan)
- ENDOCRINE_SENSITIVITY: HIGH / MEDIUM / LOW
- ERIBULIN_SENSITIVITY: HIGH / MEDIUM / LOW

Output: brca_adc_resistance_cohort.csv (ready for model training)
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple
from datetime import datetime

# Paths - direct absolute paths
DATA_DIR = Path("/Users/fahadkiani/Desktop/development/crispr-assistant-main/oncology-coPilot/oncology-backend-minimal/data/yale_tdzd_project")
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

# Labeling thresholds (will refine based on literature)
THRESHOLDS = {
    # Expression percentiles for "low"
    "ERBB2_LOW": 25,  # <25th percentile = HER2-low
    "TACSTD2_LOW": 25,  # <25th percentile = TROP2-low (SG resistance)
    "SLFN11_LOW": 25,  # <25th percentile = DDR-low (ADC resistance)
    
    # Expression percentiles for "high"
    "ERBB2_HIGH": 75,  # >75th percentile = HER2-high
    "TACSTD2_HIGH": 75,  # >75th percentile = TROP2-high (SG sensitivity)
    "SLFN11_HIGH": 75,  # >75th percentile = DDR-high (ADC sensitivity)
    
    # Efflux pump overexpression threshold
    "ABCB1_HIGH": 75,
    "ABCG2_HIGH": 75,
}


def load_mutations(study_id: str) -> pd.DataFrame:
    """Load mutation data for a study"""
    mut_file = RAW_DIR / f"{study_id}_mutations.csv"
    if not mut_file.exists():
        print(f"⚠️  Mutations file not found: {mut_file}")
        return pd.DataFrame()
    
    df = pd.read_csv(mut_file)
    print(f"✅ Loaded {len(df)} mutations from {study_id}")
    return df


def load_clinical(study_id: str) -> pd.DataFrame:
    """Load clinical data for a study"""
    clin_file = RAW_DIR / f"{study_id}_clinical.csv"
    if not clin_file.exists():
        print(f"⚠️  Clinical file not found: {clin_file}")
        return pd.DataFrame()
    
    df = pd.read_csv(clin_file)
    print(f"✅ Loaded clinical data for {study_id}")
    return df


def load_expression(study_id: str) -> pd.DataFrame:
    """Load expression data for a study (if available)"""
    expr_file = RAW_DIR / f"{study_id}_expression.csv"
    if not expr_file.exists():
        print(f"⚠️  Expression file not found: {expr_file} (will use mutation-only labels)")
        return pd.DataFrame()
    
    df = pd.read_csv(expr_file)
    print(f"✅ Loaded expression data from {study_id}")
    return df


def create_patient_mutation_matrix(df_mutations: pd.DataFrame) -> pd.DataFrame:
    """
    Create patient × gene mutation matrix
    
    Returns DataFrame with:
    - Rows: patient IDs
    - Columns: genes
    - Values: 1 if mutated, 0 if wild-type
    """
    if df_mutations.empty:
        return pd.DataFrame()
    
    # Get gene column name
    gene_col = [c for c in df_mutations.columns if 'hugo' in c.lower() or c == 'gene'][0]
    
    # Get patient/sample ID
    if 'patientId' in df_mutations.columns:
        id_col = 'patientId'
    elif 'sampleId' in df_mutations.columns:
        id_col = 'sampleId'
    else:
        id_col = df_mutations.columns[0]
    
    # Create binary matrix
    df_pivot = df_mutations.groupby([id_col, gene_col]).size().reset_index(name='count')
    df_pivot['mutated'] = 1
    df_matrix = df_pivot.pivot_table(
        index=id_col, 
        columns=gene_col, 
        values='mutated', 
        fill_value=0
    )
    
    print(f"✅ Created mutation matrix: {df_matrix.shape[0]} patients × {df_matrix.shape[1]} genes")
    return df_matrix


def label_adc_resistance(patient_muts: Dict[str, int], patient_expr: Dict[str, float] = None) -> Tuple[str, int, List[str]]:
    """
    Label ADC resistance risk for a single patient
    
    Scoring:
    - TP53 mutation: +3 points
    - HER2 low expression: +3 points
    - PIK3CA mutation: +2 points
    - SLFN11 low: +2 points (DDR deficiency)
    - ABCB1/ABCG2 high: +2 points (efflux pumps)
    
    Classification:
    - HIGH_RISK: ≥7 points
    - MEDIUM_RISK: 4-6 points
    - LOW_RISK: 0-3 points
    
    Returns: (risk_label, score, rationale_list)
    """
    score = 0
    rationale = []
    
    # Mutation-based scoring
    if patient_muts.get("TP53", 0) > 0:
        score += 3
        rationale.append("TP53 mutation (impaired DNA damage response)")
    
    if patient_muts.get("PIK3CA", 0) > 0:
        score += 2
        rationale.append("PIK3CA mutation (bypass HER2 signaling)")
    
    if patient_muts.get("ERBB2", 0) > 0:
        score += 2
        rationale.append("ERBB2 mutation (may reduce ADC binding)")
    
    # Expression-based scoring (if available)
    if patient_expr:
        # HER2 low
        if patient_expr.get("ERBB2", 50) < THRESHOLDS["ERBB2_LOW"]:
            score += 3
            rationale.append("HER2-low expression (<25th percentile)")
        
        # SLFN11 low (DDR marker)
        if patient_expr.get("SLFN11", 50) < THRESHOLDS["SLFN11_LOW"]:
            score += 2
            rationale.append("SLFN11-low (DNA damage resistance)")
        
        # Efflux pumps high
        if patient_expr.get("ABCB1", 50) > THRESHOLDS["ABCB1_HIGH"]:
            score += 2
            rationale.append("ABCB1 overexpression (drug efflux)")
        
        if patient_expr.get("ABCG2", 50) > THRESHOLDS["ABCG2_HIGH"]:
            score += 2
            rationale.append("ABCG2 overexpression (drug efflux)")
    
    # Classify
    if score >= 7:
        risk = "HIGH_RISK"
    elif score >= 4:
        risk = "MEDIUM_RISK"
    else:
        risk = "LOW_RISK"
    
    return risk, score, rationale


def label_sg_cross_resistance(patient_muts: Dict[str, int], patient_expr: Dict[str, float] = None) -> Tuple[str, int, List[str]]:
    """
    Label sacituzumab govitecan (SG) cross-resistance risk
    
    T-DXd and SG both target TOP1 (topoisomerase I) pathway
    Key markers:
    - TROP2 low expression: +3 points
    - SLFN11 low: +2 points
    - TOP1 mutation: +2 points
    - Prior T-DXd exposure: +3 points (not available yet)
    
    Classification:
    - HIGH_RISK: ≥5 points (likely <3mo rwPFS on SG)
    - MEDIUM_RISK: 3-4 points
    - LOW_RISK: 0-2 points
    
    Returns: (risk_label, score, rationale_list)
    """
    score = 0
    rationale = []
    
    # Mutation-based
    if patient_muts.get("TOP1", 0) > 0:
        score += 2
        rationale.append("TOP1 mutation (payload target disrupted)")
    
    if patient_muts.get("TOP2A", 0) > 0:
        score += 1
        rationale.append("TOP2A mutation")
    
    # Expression-based (if available)
    if patient_expr:
        # TROP2 low
        if patient_expr.get("TACSTD2", 50) < THRESHOLDS["TACSTD2_LOW"]:
            score += 3
            rationale.append("TROP2-low expression (<25th percentile)")
        
        # SLFN11 low (cross-resistance via DDR)
        if patient_expr.get("SLFN11", 50) < THRESHOLDS["SLFN11_LOW"]:
            score += 2
            rationale.append("SLFN11-low (DDR resistance, cross-resistance likely)")
    
    # Classify
    if score >= 5:
        risk = "HIGH_RISK"
    elif score >= 3:
        risk = "MEDIUM_RISK"
    else:
        risk = "LOW_RISK"
    
    return risk, score, rationale


def label_endocrine_sensitivity(patient_muts: Dict[str, int], patient_expr: Dict[str, float] = None, subtype: str = None) -> Tuple[str, int, List[str]]:
    """
    Label endocrine therapy sensitivity
    
    Scoring:
    - ESR1 wild-type: +3 points
    - PIK3CA mutation: +2 points (PI3K inhibitor candidate)
    - HR+ subtype: +3 points
    - HER2 heterogeneity: +1 point
    
    Classification:
    - HIGH: ≥6 points (likely >6mo rwPFS)
    - MEDIUM: 3-5 points
    - LOW: 0-2 points
    
    Returns: (sensitivity_label, score, rationale_list)
    """
    score = 0
    rationale = []
    
    # Subtype
    if subtype and "HR+" in subtype:
        score += 3
        rationale.append("HR+ subtype")
    
    # Mutations
    if patient_muts.get("ESR1", 0) == 0:
        score += 3
        rationale.append("ESR1 wild-type (no endocrine resistance)")
    else:
        score -= 2
        rationale.append("ESR1 mutation (endocrine resistance)")
    
    if patient_muts.get("PIK3CA", 0) > 0:
        score += 2
        rationale.append("PIK3CA mutation (PI3K inhibitor candidate)")
    
    if patient_muts.get("PTEN", 0) > 0:
        score -= 1
        rationale.append("PTEN loss (endocrine resistance)")
    
    # Classify
    if score >= 6:
        sensitivity = "HIGH"
    elif score >= 3:
        sensitivity = "MEDIUM"
    else:
        sensitivity = "LOW"
    
    return sensitivity, score, rationale


def label_eribulin_sensitivity(patient_muts: Dict[str, int], patient_expr: Dict[str, float] = None) -> Tuple[str, int, List[str]]:
    """
    Label eribulin sensitivity
    
    Eribulin = microtubule inhibitor
    
    Scoring:
    - TP53 wild-type: +2 points
    - No tubulin mutations: +2 points
    - Prior anthracycline exposure: -1 point (not available yet)
    
    Classification:
    - HIGH: ≥3 points
    - MEDIUM: 1-2 points
    - LOW: ≤0 points
    
    Returns: (sensitivity_label, score, rationale_list)
    """
    score = 0
    rationale = []
    
    # TP53 status
    if patient_muts.get("TP53", 0) == 0:
        score += 2
        rationale.append("TP53 wild-type (better microtubule targeting)")
    
    # Tubulin genes (rarely mutated, but check)
    tubulin_genes = ["TUBA1A", "TUBB", "TUBB3"]
    has_tubulin_mut = any(patient_muts.get(g, 0) > 0 for g in tubulin_genes)
    if not has_tubulin_mut:
        score += 2
        rationale.append("No tubulin mutations detected")
    
    # Classify
    if score >= 3:
        sensitivity = "HIGH"
    elif score >= 1:
        sensitivity = "MEDIUM"
    else:
        sensitivity = "LOW"
    
    return sensitivity, score, rationale


def process_cohort(study_id: str) -> pd.DataFrame:
    """Process a single cohort and generate labels"""
    
    print(f"\n{'='*80}")
    print(f"PROCESSING: {study_id}")
    print(f"{'='*80}\n")
    
    # Load data
    df_muts = load_mutations(study_id)
    df_clin = load_clinical(study_id)
    df_expr = load_expression(study_id)  # May be empty
    
    if df_muts.empty:
        print(f"❌ No mutation data available for {study_id}, skipping")
        return pd.DataFrame()
    
    # Create mutation matrix
    df_mut_matrix = create_patient_mutation_matrix(df_muts)
    
    if df_mut_matrix.empty:
        print(f"❌ Failed to create mutation matrix for {study_id}")
        return pd.DataFrame()
    
    # Process each patient
    labeled_data = []
    
    for patient_id in df_mut_matrix.index:
        patient_muts = df_mut_matrix.loc[patient_id].to_dict()
        patient_expr = None  # TODO: Add expression data when available
        
        # Generate labels
        adc_risk, adc_score, adc_rationale = label_adc_resistance(patient_muts, patient_expr)
        sg_risk, sg_score, sg_rationale = label_sg_cross_resistance(patient_muts, patient_expr)
        endo_sens, endo_score, endo_rationale = label_endocrine_sensitivity(patient_muts, patient_expr)
        erib_sens, erib_score, erib_rationale = label_eribulin_sensitivity(patient_muts, patient_expr)
        
        labeled_data.append({
            'patient_id': patient_id,
            'study_id': study_id,
            
            # Mutation counts
            'tp53_mut': patient_muts.get('TP53', 0),
            'pik3ca_mut': patient_muts.get('PIK3CA', 0),
            'erbb2_mut': patient_muts.get('ERBB2', 0),
            'esr1_mut': patient_muts.get('ESR1', 0),
            'brca1_mut': patient_muts.get('BRCA1', 0),
            'brca2_mut': patient_muts.get('BRCA2', 0),
            'top1_mut': patient_muts.get('TOP1', 0),
            
            # Labels
            'adc_resistance_risk': adc_risk,
            'adc_resistance_score': adc_score,
            'adc_resistance_rationale': "; ".join(adc_rationale),
            
            'sg_cross_resistance_risk': sg_risk,
            'sg_cross_resistance_score': sg_score,
            'sg_cross_resistance_rationale': "; ".join(sg_rationale),
            
            'endocrine_sensitivity': endo_sens,
            'endocrine_sensitivity_score': endo_score,
            'endocrine_sensitivity_rationale': "; ".join(endo_rationale),
            
            'eribulin_sensitivity': erib_sens,
            'eribulin_sensitivity_score': erib_score,
            'eribulin_sensitivity_rationale': "; ".join(erib_rationale),
        })
    
    df_labeled = pd.DataFrame(labeled_data)
    
    print(f"\n✅ Labeled {len(df_labeled)} patients")
    print(f"\nADC Resistance Distribution:")
    print(df_labeled['adc_resistance_risk'].value_counts())
    print(f"\nSG Cross-Resistance Distribution:")
    print(df_labeled['sg_cross_resistance_risk'].value_counts())
    
    return df_labeled


def main():
    """Main labeling pipeline"""
    
    print("=" * 80)
    print("🏷️  ADC RESISTANCE AUTO-LABELING PIPELINE")
    print("=" * 80)
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Process each cohort
    cohorts = [
        "brca_tcga_pan_can_atlas_2018",
        "brca_metabric"
    ]
    
    all_labeled = []
    
    for study_id in cohorts:
        df_labeled = process_cohort(study_id)
        if not df_labeled.empty:
            all_labeled.append(df_labeled)
    
    if not all_labeled:
        print("\n❌ No data to label. Run extract_tcga_brca.py first.")
        return
    
    # Combine all cohorts
    df_combined = pd.concat(all_labeled, ignore_index=True)
    
    # Save
    output_file = PROCESSED_DIR / "brca_adc_resistance_cohort.csv"
    df_combined.to_csv(output_file, index=False)
    
    print(f"\n{'='*80}")
    print("✅ LABELING COMPLETE")
    print(f"{'='*80}")
    print(f"Total patients labeled: {len(df_combined)}")
    print(f"Output file: {output_file}")
    print(f"\nNext step: Train prediction models using train_adc_models.py")
    print(f"End time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()

