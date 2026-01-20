#!/usr/bin/env python3
"""
Extract Real Mutation Frequencies from TCGA for Universal Disease Database

Takes gene-pathway mappings and computes actual alteration frequencies
from TCGA data via cBioPortal API.

Output: mutation_frequencies.json (real weights for each pathway)
"""

import sys
from pathlib import Path
import pandas as pd
import json
import time
from typing import Dict, List, Any
from datetime import datetime

# Add pyBioPortal to path - reuse from existing script
pybioportal_parent = Path("/Users/fahadkiani/Desktop/development/crispr-assistant-main/oncology-coPilot/oncology-backend/tests/pyBioPortal-master")
if str(pybioportal_parent) not in sys.path:
    sys.path.insert(0, str(pybioportal_parent))

from pybioportal import molecular_profiles as mp
from pybioportal import sample_lists as sl
from pybioportal import mutations as mut

# Load gene-pathway mappings
MAPPINGS_FILE = Path(__file__).parent / "gene_pathway_mappings.json"
OUTPUT_FILE = Path(__file__).parent / "mutation_frequencies.json"
PARTIAL_OUTPUT = Path(__file__).parent / "mutation_frequencies_partial.json"

# Study IDs for top 10 cancers
STUDIES = {
    "ovarian_cancer_hgs": "ov_tcga_pan_can_atlas_2018",
    "breast_cancer": "brca_tcga_pan_can_atlas_2018",
    "lung_cancer": "luad_tcga_pan_can_atlas_2018",
    "colorectal_cancer": "coadread_tcga_pan_can_atlas_2018",
    "melanoma": "skcm_tcga_pan_can_atlas_2018",
    "prostate_cancer": "prad_tcga_pan_can_atlas_2018",
    "pancreatic_cancer": "paad_tcga_pan_can_atlas_2018",
    "glioblastoma": "gbm_tcga_pan_can_atlas_2018",
    "multiple_myeloma": "mmrf_commpass_ia14",  # Updated: mmrf_commpass not found, using ia14 version
    "leukemia": "laml_tcga_pan_can_atlas_2018"
}


def extract_mutations_with_retry(study_id: str, genes: List[str], max_retries: int = 3) -> pd.DataFrame:
    """Extract somatic mutations with retry logic"""
    print(f"📊 Extracting mutations from {study_id}...")
    
    for attempt in range(max_retries):
        try:
            # Get mutation profile
            df_prof = mp.get_all_molecular_profiles_in_study(study_id)
            profile_id = None
            
            if isinstance(df_prof, pd.DataFrame) and "molecularProfileId" in df_prof.columns:
                cand = df_prof["molecularProfileId"].astype(str).tolist()
                for pid in cand:
                    if pid.endswith("_mutations"):
                        profile_id = pid
                        break
            
            if not profile_id:
                print(f"❌ No mutation profile found for {study_id}")
                return pd.DataFrame()
            
            # Get sample list
            df_lists = sl.get_all_sample_lists_in_study(study_id)
            sample_list_id = None
            
            if isinstance(df_lists, pd.DataFrame) and "sampleListId" in df_lists.columns:
                c2 = df_lists["sampleListId"].astype(str).tolist()
                for sid in c2:
                    if sid.endswith("_all"):
                        sample_list_id = sid
                        break
                if sample_list_id is None and c2:
                    sample_list_id = c2[0]
            
            # Extract mutations
            print(f"   Using profile: {profile_id}, sample list: {sample_list_id}")
            df_muts = mut.get_muts_in_mol_prof_by_sample_list_id(
                profile_id, 
                sample_list_id, 
                projection="DETAILED", 
                pageSize=10000
            )
            
            if not isinstance(df_muts, pd.DataFrame) or df_muts.empty:
                print(f"❌ No mutations found")
                return pd.DataFrame()
            
            # Filter to target genes
            gene_col = [c for c in df_muts.columns if 'hugo' in c.lower() or c == 'gene'][0]
            df_filtered = df_muts[df_muts[gene_col].str.upper().isin([g.upper() for g in genes])]
            
            print(f"✅ Extracted {len(df_filtered)} mutations in {df_filtered[gene_col].nunique()} genes from {df_filtered['sampleId'].nunique()} samples")
            
            return df_filtered
            
        except Exception as e:
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # Exponential backoff
                print(f"⚠️  Error (attempt {attempt + 1}/{max_retries}): {e}")
                print(f"   Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                print(f"❌ Error extracting mutations after {max_retries} attempts: {e}")
                return pd.DataFrame()
    
    return pd.DataFrame()


def calculate_pathway_frequency(
    df_mutations: pd.DataFrame, 
    pathway_genes: List[str],
    total_samples: int
) -> float:
    """
    Calculate what % of samples have alterations in pathway genes.
    
    Args:
        df_mutations: Mutations dataframe
        pathway_genes: List of genes in pathway
        total_samples: Total samples in study
        
    Returns:
        Frequency (0.0-1.0)
    """
    if df_mutations.empty or total_samples == 0:
        return 0.0
    
    # Get gene column name (might be 'Hugo_Symbol', 'gene', 'hugoGeneSymbol')
    gene_col = [c for c in df_mutations.columns if 'hugo' in c.lower() or c.lower() == 'gene'][0]
    
    # Count unique samples with mutations in any pathway gene
    pathway_mutations = df_mutations[
        df_mutations[gene_col].str.upper().isin([g.upper() for g in pathway_genes])
    ]
    
    if pathway_mutations.empty:
        return 0.0
    
    unique_samples = pathway_mutations['sampleId'].nunique()
    frequency = unique_samples / total_samples
    
    return round(frequency, 3)


def extract_for_cancer(cancer_type: str, study_id: str, mappings: Dict) -> Dict[str, Any]:
    """Extract mutation frequencies for one cancer type"""
    print(f"\n{'='*80}")
    print(f"🎯 Extracting: {cancer_type} ({study_id})")
    print(f"{'='*80}")
    
    cancer_mappings = mappings.get(cancer_type, {})
    if not cancer_mappings:
        print(f"⚠️  No pathway mappings found for {cancer_type}")
        return {}
    
    # Get all genes needed for this cancer
    all_genes = []
    for pathway_genes in cancer_mappings.values():
        if isinstance(pathway_genes, list):
            all_genes.extend(pathway_genes)
    all_genes = list(set(all_genes))  # Deduplicate
    
    print(f"📊 Target genes: {len(all_genes)} genes")
    print(f"📊 Target pathways: {len(cancer_mappings)} pathways")
    
    # Extract mutations with retry
    df_mutations = extract_mutations_with_retry(study_id, all_genes)
    
    if df_mutations.empty:
        print(f"❌ No mutations extracted for {study_id}")
        return {}
    
    total_samples = df_mutations['sampleId'].nunique()
    print(f"✅ Extracted mutations from {total_samples} samples")
    
    # Calculate frequency for each pathway
    pathway_frequencies = {}
    for pathway_name, pathway_genes in cancer_mappings.items():
        if not isinstance(pathway_genes, list):
            continue
            
        frequency = calculate_pathway_frequency(
            df_mutations, 
            pathway_genes, 
            total_samples
        )
        
        # Determine extraction type
        extraction_type = "mutation"
        if pathway_name in ["alk_ros1", "tmprss2_erg"]:
            extraction_type = "mutation_proxy"  # Fusions
        elif pathway_name in ["pd1_immune", "pd_l1_immune", "immune_checkpoint"]:
            extraction_type = "mutation_proxy"  # Expression markers
        elif pathway_name in ["androgen_receptor", "er_pr_signaling"]:
            extraction_type = "mutation_proxy"  # Expression-driven
        
        pathway_frequencies[pathway_name] = {
            "weight": frequency,
            "source": f"TCGA ({int(frequency*100)}% altered, n={total_samples})",
            "genes": pathway_genes,
            "samples_altered": int(frequency * total_samples),
            "total_samples": total_samples,
            "extraction_type": extraction_type,
            "extracted_at": datetime.now().isoformat()
        }
        
        print(f"  ✓ {pathway_name}: {frequency:.3f} ({int(frequency*100)}% altered) [{extraction_type}]")
    
    return pathway_frequencies


def save_partial_results(all_frequencies: Dict):
    """Save partial results after each cancer"""
    PARTIAL_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with open(PARTIAL_OUTPUT, 'w') as f:
        json.dump(all_frequencies, f, indent=2)
    print(f"💾 Saved partial results: {PARTIAL_OUTPUT}")


def main():
    """Main extraction pipeline"""
    
    print("=" * 80)
    print("🎯 TCGA MUTATION FREQUENCY EXTRACTION")
    print("=" * 80)
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Load gene-pathway mappings
    if not MAPPINGS_FILE.exists():
        print(f"❌ Mappings file not found: {MAPPINGS_FILE}")
        print(f"   Create it using Step 1 instructions in doctrine")
        return
    
    with open(MAPPINGS_FILE) as f:
        mappings = json.load(f)
    
    print(f"✅ Loaded mappings for {len(mappings)} cancer types")
    print()
    
    # Extract for each cancer (with rate limiting)
    all_frequencies = {}
    
    for idx, (cancer_type, study_id) in enumerate(STUDIES.items(), 1):
        try:
            frequencies = extract_for_cancer(cancer_type, study_id, mappings)
            if frequencies:
                all_frequencies[cancer_type] = frequencies
                # Save partial results after each cancer
                save_partial_results(all_frequencies)
            
            # Rate limiting: sleep between studies (except last one)
            if idx < len(STUDIES):
                time.sleep(1)
                
        except Exception as e:
            print(f"❌ Error extracting {cancer_type}: {e}")
            import traceback
            traceback.print_exc()
            continue
    
    # Save final results
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(all_frequencies, f, indent=2)
    
    print(f"\n{'='*80}")
    print("✅ EXTRACTION COMPLETE")
    print(f"{'='*80}")
    print(f"Output: {OUTPUT_FILE}")
    print(f"Cancers extracted: {len(all_frequencies)}/{len(STUDIES)}")
    print(f"End time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    print("📝 Next step: Run update_universal_database.py to merge into universal database")


if __name__ == "__main__":
    main()


