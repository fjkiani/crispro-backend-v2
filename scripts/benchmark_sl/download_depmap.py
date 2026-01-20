#!/usr/bin/env python3
"""
Download and process DepMap data for benchmarking.

DepMap requires manual download:
1. Visit: https://depmap.org/portal/download/
2. Download 'CRISPRGeneEffect.csv' (or 'Achilles_gene_effect.csv')
3. Place it in this directory as 'depmap_raw.csv'
4. Run this script to process it
"""
import json
from pathlib import Path
from typing import Dict, Any

# Check if pandas is available
try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

def download_depmap():
    """Process DepMap gene effect scores."""
    print("=" * 60)
    print("DepMap Data Processing")
    print("=" * 60)
    
    raw_file = Path("depmap_raw.csv")
    
    if not raw_file.exists():
        print("\n⚠️  DepMap data not found!")
        print("\n📋 Manual download instructions:")
        print("   1. Visit: https://depmap.org/portal/download/")
        print("   2. Log in (free registration required)")
        print("   3. Download 'CRISPRGeneEffect.csv' (or 'Achilles_gene_effect.csv')")
        print("   4. Save it as 'depmap_raw.csv' in this directory")
        print("   5. Re-run this script")
        print("\n💡 Alternative: Use the DepMap API with credentials")
        
        # Create a placeholder with known values from literature
        print("\n📝 Creating placeholder with literature values...")
        placeholder = create_literature_placeholder()
        
        output_file = Path("depmap_essentiality.json")
        with open(output_file, 'w') as f:
            json.dump(placeholder, f, indent=2)
        print(f"✅ Created placeholder: {output_file}")
        print("⚠️  These are literature estimates, not actual DepMap data!")
        
        return placeholder
    
    if not PANDAS_AVAILABLE:
        print("❌ pandas not installed. Run: pip install pandas")
        return None
    
    print(f"\n✅ Found {raw_file}, processing...")
    
    try:
        df = pd.read_csv(raw_file, index_col=0)
        print(f"   Loaded {len(df)} cell lines, {len(df.columns)} genes")
    except Exception as e:
        print(f"❌ Error loading CSV: {e}")
        return None
    
    # Key genes for synthetic lethality
    key_genes = ['BRCA1', 'BRCA2', 'MBD4', 'TP53', 'PARP1', 'ATR', 'WEE1', 'ATM', 'CHEK2', 'PALB2', 'RAD51C', 'RAD51D', 'ARID1A', 'CDK12', 'KRAS', 'EGFR']
    
    # Try to find cell line info (depends on DepMap format)
    cell_line_info = None
    model_file = Path("depmap_model.csv")
    if model_file.exists():
        try:
            cell_line_info = pd.read_csv(model_file)
        except:
            pass
    
    essentiality_scores = {}
    print("\n📊 Extracting essentiality scores...")
    
    for gene in key_genes:
        # Try different column naming conventions
        gene_col = None
        for col in df.columns:
            if gene in col.upper():
                gene_col = col
                break
        
        if gene_col is None:
            print(f"   ⚠️  {gene}: Not found in data")
            continue
        
        gene_data = df[gene_col].dropna()
        if len(gene_data) == 0:
            print(f"   ⚠️  {gene}: No valid data")
            continue
        
        # DepMap scores: negative = essential, positive = non-essential
        # Convert to 0-1 scale where 1 = highly essential
        mean_score = gene_data.mean()
        essentiality = max(0, min(1, -mean_score))  # Invert and clamp
        
        essentiality_scores[gene] = {
            "depmap_mean_effect": float(mean_score),
            "essentiality_score": float(essentiality),
            "std": float(gene_data.std()),
            "n_cell_lines": int(len(gene_data)),
            "source": "DepMap CRISPR",
        }
        print(f"   {gene}: effect={mean_score:.3f}, essentiality={essentiality:.3f} (n={len(gene_data)})")
    
    output_file = Path("depmap_essentiality.json")
    with open(output_file, 'w') as f:
        json.dump(essentiality_scores, f, indent=2)
    
    print(f"\n✅ Saved to {output_file}")
    return essentiality_scores

def create_literature_placeholder() -> Dict[str, Any]:
    """Create placeholder with known values from literature.
    
    These are NOT real DepMap values - they are estimates from published studies.
    Use actual DepMap data for real benchmarking!
    """
    return {
        "_warning": "These are LITERATURE ESTIMATES, not actual DepMap data!",
        "_source": "Estimated from DepMap publications and cancer dependency studies",
        "BRCA1": {
            "essentiality_score": 0.15,  # Generally not essential in most cells
            "notes": "Essential in HR-proficient cells, not in HR-deficient",
            "source": "literature_estimate"
        },
        "BRCA2": {
            "essentiality_score": 0.12,
            "notes": "Similar to BRCA1, context-dependent",
            "source": "literature_estimate"
        },
        "MBD4": {
            "essentiality_score": 0.08,
            "notes": "Low essentiality, involved in BER pathway",
            "source": "literature_estimate"
        },
        "TP53": {
            "essentiality_score": 0.05,
            "notes": "Tumor suppressor, often lost in cancer",
            "source": "literature_estimate"
        },
        "PARP1": {
            "essentiality_score": 0.25,
            "notes": "Moderate essentiality, higher in BRCA-deficient cells",
            "source": "literature_estimate"
        },
        "ATR": {
            "essentiality_score": 0.45,
            "notes": "Higher essentiality, key DNA damage response",
            "source": "literature_estimate"
        },
        "WEE1": {
            "essentiality_score": 0.35,
            "notes": "Moderate essentiality, cell cycle checkpoint",
            "source": "literature_estimate"
        },
        "ATM": {
            "essentiality_score": 0.20,
            "notes": "DNA damage sensor, moderate essentiality",
            "source": "literature_estimate"
        },
        "CHEK2": {
            "essentiality_score": 0.15,
            "notes": "Checkpoint kinase, low-moderate essentiality",
            "source": "literature_estimate"
        }
    }

if __name__ == "__main__":
    download_depmap()
