"""
Test IO Pathway Integration (GSE91061, AUC = 0.780)

Tests pathway-based IO prediction integration into sporadic_gates.py
Validates compute_io_pathway_scores() and logistic_regression_composite()

CRITICAL: Includes real GSE91061 data validation to ensure coefficients are correct.
"""
import pytest
import pandas as pd
import numpy as np
import os
from api.services.efficacy_orchestrator.sporadic_gates import (
    apply_io_boost,
    apply_sporadic_gates
)
from api.services.efficacy_orchestrator.io_pathway_model import (
    compute_io_pathway_scores,
    logistic_regression_composite,
    IO_PATHWAYS,
    IO_LR_COEFFICIENTS,
    IO_LR_INTERCEPT
)


def test_compute_io_pathway_scores_basic():
    """Test basic pathway score computation with synthetic expression data."""
    # Create synthetic expression data with high EXHAUSTION and TIL_INFILTRATION
    # (these should predict high IO response)
    # DataFrame structure: genes as index, samples as columns
    gene_data = {
        # EXHAUSTION pathway genes (high expression)
        'PDCD1': [10.5],   # PD-1
        'CTLA4': [9.8],
        'LAG3': [8.2],
        'TIGIT': [7.5],
        'HAVCR2': [6.8],  # TIM-3
        'BTLA': [5.2],
        'CD96': [4.1],
        'VSIR': [3.5],    # VISTA
        
        # TIL_INFILTRATION pathway genes (high expression)
        'CD8A': [11.2],
        'CD8B': [10.8],
        'CD3D': [9.5],
        'CD3E': [9.1],
        'CD3G': [8.7],
        'CD4': [7.3],
        'CD2': [6.9],
        'GZMA': [8.5],
        'GZMB': [8.1],
        'PRF1': [7.7],
        'IFNG': [6.3],
        'TNF': [5.9],
        'IL2': [5.5],
        
        # Other pathway genes (moderate expression)
        'VEGFA': [4.0],
        'TGFB1': [3.0],
        'IL6': [2.0],
        'MKI67': [1.0],
        'PSMB8': [2.5],
        'CD274': [3.5],  # PD-L1
    }
    expression_data = pd.DataFrame(gene_data, index=['sample']).T
    
    pathway_scores = compute_io_pathway_scores(expression_data)
    
    # Verify all pathways computed
    assert 'EXHAUSTION' in pathway_scores
    assert 'TIL_INFILTRATION' in pathway_scores
    assert 'ANGIOGENESIS' in pathway_scores
    assert 'TGFB_RESISTANCE' in pathway_scores
    assert 'MYELOID_INFLAMMATION' in pathway_scores
    assert 'PROLIFERATION' in pathway_scores
    assert 'IMMUNOPROTEASOME' in pathway_scores
    assert 'T_EFFECTOR' in pathway_scores
    
    # Verify scores are numeric (not NaN)
    assert not np.isnan(pathway_scores['EXHAUSTION'])
    assert not np.isnan(pathway_scores['TIL_INFILTRATION'])
    
    # Verify EXHAUSTION and TIL_INFILTRATION have high scores (high expression)
    # Note: log2(TPM+1) transformation means scores are typically 2-5 range
    assert pathway_scores['EXHAUSTION'] > 2.0, f"EXHAUSTION score should be high, got {pathway_scores['EXHAUSTION']}"
    assert pathway_scores['TIL_INFILTRATION'] > 3.0, f"TIL_INFILTRATION score should be high, got {pathway_scores['TIL_INFILTRATION']}"
    
    print(f"✅ Pathway scores computed: EXHAUSTION={pathway_scores['EXHAUSTION']:.2f}, "
          f"TIL_INFILTRATION={pathway_scores['TIL_INFILTRATION']:.2f}")


def test_logistic_regression_composite_high_response():
    """Test logistic regression composite with high pathway scores (should predict high IO response)."""
    # High EXHAUSTION and TIL_INFILTRATION (strongest positive predictors)
    pathway_scores = {
        'EXHAUSTION': 8.0,           # High (coefficient +0.814)
        'TIL_INFILTRATION': 7.5,     # High (coefficient +0.740)
        'ANGIOGENESIS': 4.0,          # Moderate (coefficient +0.229)
        'MYELOID_INFLAMMATION': 3.0,  # Moderate (coefficient +0.117)
        'TGFB_RESISTANCE': 2.0,       # Low (coefficient -0.189)
        'T_EFFECTOR': 3.5,            # Moderate (coefficient -0.205)
        'PROLIFERATION': 1.5,         # Low (coefficient -0.368)
        'IMMUNOPROTEASOME': 2.5,      # Low (coefficient -0.944)
    }
    
    composite = logistic_regression_composite(pathway_scores)
    
    # High pathway scores should predict high IO response (composite > 0.5)
    assert composite > 0.5, f"High pathway scores should predict high IO response, got {composite:.3f}"
    assert composite <= 1.0, f"Composite should be ≤1.0, got {composite:.3f}"
    
    print(f"✅ High pathway composite: {composite:.3f} (should be >0.5)")


def test_logistic_regression_composite_low_response():
    """Test logistic regression composite with low pathway scores (should predict low IO response)."""
    # Low EXHAUSTION and TIL_INFILTRATION, high IMMUNOPROTEASOME (negative predictor)
    pathway_scores = {
        'EXHAUSTION': 2.0,            # Low (coefficient +0.814)
        'TIL_INFILTRATION': 1.5,      # Low (coefficient +0.740)
        'ANGIOGENESIS': 1.0,          # Low (coefficient +0.229)
        'MYELOID_INFLAMMATION': 0.5,  # Low (coefficient +0.117)
        'TGFB_RESISTANCE': 5.0,       # High (coefficient -0.189)
        'T_EFFECTOR': 4.0,            # High (coefficient -0.205)
        'PROLIFERATION': 6.0,         # High (coefficient -0.368)
        'IMMUNOPROTEASOME': 8.0,      # High (coefficient -0.944, strongest negative)
    }
    
    composite = logistic_regression_composite(pathway_scores)
    
    # Low pathway scores should predict low IO response (composite < 0.5)
    assert composite < 0.5, f"Low pathway scores should predict low IO response, got {composite:.3f}"
    assert composite >= 0.0, f"Composite should be ≥0.0, got {composite:.3f}"
    
    print(f"✅ Low pathway composite: {composite:.3f} (should be <0.5)")


def test_apply_io_boost_pathway_high():
    """Test apply_io_boost() with high pathway composite (should boost 1.40x)."""
    # Create expression data with high EXHAUSTION + TIL_INFILTRATION
    # Include enough genes to pass quality checks (≥1000 genes minimum)
    gene_data = {
        'PDCD1': [10.5], 'CTLA4': [9.8], 'LAG3': [8.2], 'TIGIT': [7.5], 'HAVCR2': [6.8],  # EXHAUSTION
        'CD8A': [11.2], 'CD8B': [10.8], 'CD3D': [9.5], 'CD3E': [9.2], 'CD3G': [8.8],  # TIL_INFILTRATION
        'GZMA': [10.0], 'GZMB': [9.5], 'PRF1': [8.5], 'IFNG': [9.0], 'TNF': [8.0], 'IL2': [7.5],
        'VEGFA': [4.0], 'VEGFB': [3.5], 'KDR': [4.2], 'FLT1': [3.8],  # ANGIOGENESIS
        'TGFB1': [3.0], 'TGFB2': [2.5], 'SMAD2': [2.8], 'SMAD3': [2.6],  # TGFB_RESISTANCE
        'IL6': [2.0], 'IL1B': [1.8], 'CXCL8': [2.2], 'CCL2': [1.9],  # MYELOID_INFLAMMATION
        'MKI67': [1.0], 'PCNA': [1.2], 'TOP2A': [1.1],  # PROLIFERATION
        'PSMB8': [2.5], 'PSMB9': [2.3], 'PSMB10': [2.1], 'TAP1': [2.4], 'TAP2': [2.2],  # IMMUNOPROTEASOME
        'CD274': [3.5], 'PDCD1LG2': [3.2], 'STAT1': [4.5], 'IRF1': [4.2],  # T_EFFECTOR
    }
    
    # Add dummy genes to meet minimum gene count (1000 genes)
    for i in range(1000 - len(gene_data)):
        gene_data[f'DUMMY_GENE_{i}'] = [1.0]
    
    expression_data = pd.DataFrame(gene_data, index=['sample']).T
    
    tumor_context = {"tmb": None, "msi_status": None}  # No TMB/MSI
    
    boost, rationale = apply_io_boost(
        tumor_context=tumor_context,
        expression_data=expression_data,
        cancer_type="melanoma"  # Validated cancer type (passes safety checks)
    )
    
    # High pathway composite should boost 1.40x (≥0.7 threshold)
    # Note: May be lower if confidence-adjusted, but should still boost
    assert boost >= 1.15, f"High pathway composite should boost, got {boost:.2f}x"
    assert rationale["gate"] == "IO_PATHWAY_BOOST", f"Should use pathway boost, got {rationale['gate']}"
    assert "pathway_composite_raw" in rationale or "pathway_composite" in rationale, "Should include pathway composite in rationale"
    
    print(f"✅ Pathway boost applied: {boost:.2f}x, "
          f"raw_composite={rationale.get('pathway_composite_raw', rationale.get('pathway_composite', 'N/A'))}, "
          f"adjusted={rationale.get('pathway_composite_adjusted', 'N/A')}")


def test_apply_io_boost_pathway_vs_tmb():
    """Test apply_io_boost() priority: pathway prediction > TMB (pathway takes precedence)."""
    # Create expression data with high pathway scores
    # Include enough genes to pass quality checks
    gene_data = {
        'PDCD1': [10.5], 'CTLA4': [9.8], 'LAG3': [8.2], 'TIGIT': [7.5],  # EXHAUSTION
        'CD8A': [11.2], 'CD8B': [10.8], 'CD3D': [9.5], 'CD3E': [9.2],  # TIL_INFILTRATION
        'GZMA': [10.0], 'GZMB': [9.5], 'PRF1': [8.5], 'IFNG': [9.0],
        'VEGFA': [4.0], 'VEGFB': [3.5], 'KDR': [4.2],  # ANGIOGENESIS
        'TGFB1': [3.0], 'TGFB2': [2.5], 'SMAD2': [2.8],  # TGFB_RESISTANCE
        'IL6': [2.0], 'IL1B': [1.8], 'CXCL8': [2.2],  # MYELOID_INFLAMMATION
        'MKI67': [1.0], 'PCNA': [1.2], 'TOP2A': [1.1],  # PROLIFERATION
        'PSMB8': [2.5], 'PSMB9': [2.3], 'PSMB10': [2.1], 'TAP1': [2.4],  # IMMUNOPROTEASOME
        'CD274': [3.5], 'PDCD1LG2': [3.2], 'STAT1': [4.5], 'IRF1': [4.2],  # T_EFFECTOR
    }
    
    # Add dummy genes to meet minimum gene count
    for i in range(1000 - len(gene_data)):
        gene_data[f'DUMMY_GENE_{i}'] = [1.0]
    
    expression_data = pd.DataFrame(gene_data, index=['sample']).T
    
    tumor_context = {"tmb": 25.0, "msi_status": None}  # TMB ≥20 (would normally boost 1.35x)
    
    boost, rationale = apply_io_boost(
        tumor_context=tumor_context,
        expression_data=expression_data,
        cancer_type="melanoma"  # Validated cancer type
    )
    
    # Pathway prediction should take precedence over TMB
    assert rationale["gate"] == "IO_PATHWAY_BOOST", f"Pathway should take precedence, got {rationale['gate']}"
    assert boost >= 1.15, f"Pathway boost should apply, got {boost:.2f}x"
    
    print(f"✅ Pathway priority test: {boost:.2f}x (pathway > TMB)")


def test_apply_io_boost_fallback_to_tmb():
    """Test apply_io_boost() fallback: no expression data → use TMB."""
    tumor_context = {"tmb": 25.0, "msi_status": None}  # TMB ≥20
    
    boost, rationale = apply_io_boost(
        tumor_context=tumor_context,
        expression_data=None  # No expression data
    )
    
    # Should fall back to TMB boost
    assert boost == 1.35, f"Should use TMB boost 1.35x, got {boost:.2f}x"
    assert rationale["gate"] == "IO_TMB_BOOST", f"Should use TMB boost, got {rationale['gate']}"
    
    print(f"✅ TMB fallback test: {boost:.2f}x (TMB ≥20)")


def test_apply_io_boost_fallback_to_msi():
    """Test apply_io_boost() fallback: no expression/TMB → use MSI."""
    tumor_context = {"tmb": 5.0, "msi_status": "MSI-High"}  # MSI-High, low TMB
    
    boost, rationale = apply_io_boost(
        tumor_context=tumor_context,
        expression_data=None  # No expression data
    )
    
    # Should fall back to MSI boost
    assert boost == 1.30, f"Should use MSI boost 1.30x, got {boost:.2f}x"
    assert rationale["gate"] == "IO_MSI_BOOST", f"Should use MSI boost, got {rationale['gate']}"
    
    print(f"✅ MSI fallback test: {boost:.2f}x (MSI-High)")


def test_apply_sporadic_gates_with_pathway():
    """Test apply_sporadic_gates() integration with pathway-based IO prediction."""
    # Create expression data with enough genes to pass quality checks
    gene_data = {
        'PDCD1': [10.5], 'CTLA4': [9.8], 'LAG3': [8.2], 'TIGIT': [7.5], 'HAVCR2': [6.8],  # EXHAUSTION
        'CD8A': [11.2], 'CD8B': [10.8], 'CD3D': [9.5], 'CD3E': [9.2], 'CD3G': [8.8],  # TIL_INFILTRATION
        'GZMA': [10.0], 'GZMB': [9.5], 'PRF1': [8.5], 'IFNG': [9.0], 'TNF': [8.0], 'IL2': [7.5],
        'VEGFA': [4.0], 'VEGFB': [3.5], 'KDR': [4.2], 'FLT1': [3.8],  # ANGIOGENESIS
        'TGFB1': [3.0], 'TGFB2': [2.5], 'SMAD2': [2.8], 'SMAD3': [2.6],  # TGFB_RESISTANCE
        'IL6': [2.0], 'IL1B': [1.8], 'CXCL8': [2.2], 'CCL2': [1.9],  # MYELOID_INFLAMMATION
        'MKI67': [1.0], 'PCNA': [1.2], 'TOP2A': [1.1],  # PROLIFERATION
        'PSMB8': [2.5], 'PSMB9': [2.3], 'PSMB10': [2.1], 'TAP1': [2.4], 'TAP2': [2.2],  # IMMUNOPROTEASOME
        'CD274': [3.5], 'PDCD1LG2': [3.2], 'STAT1': [4.5], 'IRF1': [4.2],  # T_EFFECTOR
    }
    
    # Add dummy genes to meet minimum gene count
    for i in range(1000 - len(gene_data)):
        gene_data[f'DUMMY_GENE_{i}'] = [1.0]
    
    expression_data = pd.DataFrame(gene_data, index=['sample']).T
    
    tumor_context = {
        "expression": expression_data,
        "tmb": None,
        "msi_status": None,
        "completeness_score": 0.9  # Level 2
    }
    
    efficacy_score, confidence, rationale = apply_sporadic_gates(
        drug_name="Pembrolizumab",
        drug_class="checkpoint_inhibitor",
        moa="PD-1 inhibition",
        efficacy_score=0.60,
        confidence=0.70,
        germline_status="negative",
        tumor_context=tumor_context,
        cancer_type="melanoma"  # Validated cancer type
    )
    
    # Should apply pathway-based boost (1.40x for high composite)
    assert efficacy_score > 0.60, f"Should boost efficacy, got {efficacy_score:.3f}"
    assert any("IO_PATHWAY_BOOST" in r.get("gate", "") for r in rationale), "Should have pathway boost in rationale"
    
    print(f"✅ Sporadic gates integration: efficacy={efficacy_score:.3f} (boosted from 0.60)")


def test_apply_io_boost_hypermutator_flag():
    """Test apply_io_boost() hypermutator flag when TMB unknown and no other signals."""
    tumor_context = {
        "tmb": None,
        "msi_status": None,
        "mutations": [{"gene": "POLE"}]
    }
    
    germline_mutations = None
    
    boost, rationale = apply_io_boost(
        tumor_context=tumor_context,
        expression_data=None,
        germline_mutations=germline_mutations
    )
    
    # Should flag hypermutator but not boost
    assert boost == 1.0, f"Should not boost (just flag), got {boost:.2f}x"
    assert rationale["gate"] == "IO_HYPERMUTATOR_FLAG", f"Should flag hypermutator, got {rationale['gate']}"
    assert "POLE" in str(rationale.get("hypermutator_genes", [])), "Should mention POLE"
    
    print(f"✅ Hypermutator flag test: {rationale['gate']} (no boost, just flag)")


def test_pathway_scores_missing_genes():
    """Test compute_io_pathway_scores() handles missing genes gracefully."""
    # Expression data with only some pathway genes
    gene_data = {
        'PDCD1': [10.5],  # EXHAUSTION
        'CD8A': [11.2],   # TIL_INFILTRATION
        # Missing most other genes
    }
    expression_data = pd.DataFrame(gene_data, index=['sample']).T
    
    pathway_scores = compute_io_pathway_scores(expression_data)
    
    # Should compute scores for pathways with available genes
    assert 'EXHAUSTION' in pathway_scores
    assert 'TIL_INFILTRATION' in pathway_scores
    
    # Pathways with no genes should be NaN
    # (This is expected behavior - missing genes → NaN score)
    
    print(f"✅ Missing genes handled: EXHAUSTION={pathway_scores.get('EXHAUSTION', 'NaN')}, "
          f"TIL_INFILTRATION={pathway_scores.get('TIL_INFILTRATION', 'NaN')}")


def test_gse91061_real_data_validation():
    """
    CRITICAL: Validate coefficients against real GSE91061 data.
    
    This test ensures the unstandardized coefficients and intercept are correct
    by comparing against the actual GSE91061 analysis results.
    """
    # Path to GSE91061 analysis results (relative to project root)
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
    gse91061_path = os.path.join(
        project_root,
        "scripts/data_acquisition/IO/gse91061_analysis_with_composites.csv"
    )
    
    if not os.path.exists(gse91061_path):
        pytest.skip(f"GSE91061 data not found at {gse91061_path}")
    
    # Load real GSE91061 pathway scores and composite predictions
    df = pd.read_csv(gse91061_path)
    
    # Extract pathway scores (first 8 columns)
    pathway_cols = ['TIL_INFILTRATION', 'T_EFFECTOR', 'ANGIOGENESIS', 'TGFB_RESISTANCE',
                    'MYELOID_INFLAMMATION', 'PROLIFERATION', 'IMMUNOPROTEASOME', 'EXHAUSTION']
    
    # Test first 5 samples
    for idx in range(min(5, len(df))):
        sample_pathway_scores = {
            col: df.iloc[idx][col] for col in pathway_cols
        }
        
        # Compute composite using our function
        computed_composite = logistic_regression_composite(
            sample_pathway_scores,
            coefficients=IO_LR_COEFFICIENTS,
            intercept=IO_LR_INTERCEPT
        )
        
        # Get actual composite from file
        actual_composite = df.iloc[idx]['composite_lr']
        
        # Verify match (within 0.001 tolerance for floating point)
        assert abs(computed_composite - actual_composite) < 0.001, (
            f"Sample {idx}: Computed composite {computed_composite:.6f} != "
            f"Actual composite {actual_composite:.6f}"
        )
    
    print("✅ GSE91061 real data validation: All 5 samples match within 0.001")


def test_coefficients_are_unstandardized():
    """
    CRITICAL: Verify coefficients are unstandardized (not standardized).
    
    Standardized coefficients would be ~0.7-0.9 for EXHAUSTION/TIL_INFILTRATION.
    Unstandardized coefficients should be ~0.5-0.75 (smaller magnitude).
    """
    # EXHAUSTION: Should be ~0.75 (unstandardized), not ~0.81 (standardized)
    assert abs(IO_LR_COEFFICIENTS['EXHAUSTION'] - 0.747468) < 0.001, (
        f"EXHAUSTION coefficient should be 0.747468 (unstandardized), "
        f"got {IO_LR_COEFFICIENTS['EXHAUSTION']}"
    )
    
    # TIL_INFILTRATION: Should be ~0.51 (unstandardized), not ~0.74 (standardized)
    assert abs(IO_LR_COEFFICIENTS['TIL_INFILTRATION'] - 0.513477) < 0.001, (
        f"TIL_INFILTRATION coefficient should be 0.513477 (unstandardized), "
        f"got {IO_LR_COEFFICIENTS['TIL_INFILTRATION']}"
    )
    
    # Intercept: Should be ~4.04 (unstandardized), not ~-1.5 (standardized)
    assert abs(IO_LR_INTERCEPT - 4.038603) < 0.001, (
        f"Intercept should be 4.038603 (unstandardized), got {IO_LR_INTERCEPT}"
    )
    
    print("✅ Coefficients verified as unstandardized (correct for raw pathway scores)")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
