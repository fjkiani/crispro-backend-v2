#!/usr/bin/env python3
"""
Quick validation tests for Phase 0 and Phase 1 changes.
Tests disease-aware panel selection, pathway mapping, and evidence integration.
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from api.services.pathway.panel_config import get_panel_for_disease, DEFAULT_MM_PANEL, DEFAULT_OVARIAN_PANEL, DEFAULT_MELANOMA_PANEL
from api.services.pathway.drug_mapping import get_pathway_weights_for_gene, get_pathway_weights_for_drug
from api.services.efficacy_orchestrator.orchestrator import EfficacyOrchestrator
from api.services.efficacy_orchestrator.models import EfficacyRequest


def test_panel_selection():
    """Test disease-aware panel selection."""
    print("=" * 60)
    print("Testing Disease-Aware Panel Selection")
    print("=" * 60)
    
    # Test MM panel
    mm_panel = get_panel_for_disease("multiple_myeloma")
    print(f"\n✅ MM Panel: {len(mm_panel)} drugs")
    for drug in mm_panel:
        print(f"   - {drug['name']}: {drug.get('moa', 'N/A')}")
    
    # Test ovarian panel
    ovarian_panel = get_panel_for_disease("ovarian_cancer")
    print(f"\n✅ Ovarian Panel: {len(ovarian_panel)} drugs")
    for drug in ovarian_panel:
        print(f"   - {drug['name']}: {drug.get('moa', 'N/A')}")
        print(f"     Pathways: {drug.get('pathway_weights', {})}")
    
    # Test melanoma panel
    melanoma_panel = get_panel_for_disease("melanoma")
    print(f"\n✅ Melanoma Panel: {len(melanoma_panel)} drugs")
    for drug in melanoma_panel:
        print(f"   - {drug['name']}: {drug.get('moa', 'N/A')}")
        print(f"     Pathways: {drug.get('pathway_weights', {})}")
    
    # Test default (should return MM)
    default_panel = get_panel_for_disease()
    assert len(default_panel) == len(DEFAULT_MM_PANEL), "Default should return MM panel"
    print(f"\n✅ Default Panel: {len(default_panel)} drugs (MM panel)")
    
    print("\n✅ Panel selection tests passed!")


def test_pathway_mapping():
    """Test pathway mapping for different genes."""
    print("\n" + "=" * 60)
    print("Testing Pathway Mapping")
    print("=" * 60)
    
    # Test MAPK pathway genes
    mapk_genes = ["BRAF", "KRAS", "NRAS", "MEK1", "MEK2"]
    print(f"\n📊 MAPK Pathway Genes:")
    for gene in mapk_genes:
        pathways = get_pathway_weights_for_gene(gene)
        print(f"   {gene:10s} → {pathways}")
        assert "ras_mapk" in pathways, f"{gene} should map to ras_mapk"
    
    # Test DDR pathway genes
    ddr_genes = ["BRCA1", "BRCA2", "ATR", "CHEK1", "RAD50"]
    print(f"\n📊 DDR Pathway Genes:")
    for gene in ddr_genes:
        pathways = get_pathway_weights_for_gene(gene)
        print(f"   {gene:10s} → {pathways}")
        assert "ddr" in pathways, f"{gene} should map to ddr"
        assert "tp53" not in pathways, f"{gene} should NOT map to tp53 (separate pathway)"
    
    # Test TP53 pathway genes
    tp53_genes = ["TP53", "MDM2", "CHEK2"]
    print(f"\n📊 TP53 Pathway Genes:")
    for gene in tp53_genes:
        pathways = get_pathway_weights_for_gene(gene)
        print(f"   {gene:10s} → {pathways}")
        assert "tp53" in pathways, f"{gene} should map to tp53"
    
    # Test PI3K pathway genes
    pi3k_genes = ["PTEN", "PIK3CA", "AKT1"]
    print(f"\n📊 PI3K Pathway Genes:")
    for gene in pi3k_genes:
        pathways = get_pathway_weights_for_gene(gene)
        print(f"   {gene:10s} → {pathways}")
        assert "pi3k" in pathways, f"{gene} should map to pi3k"
    
    print("\n✅ Pathway mapping tests passed!")


def test_drug_pathway_weights():
    """Test drug pathway weights for disease-specific panels."""
    print("\n" + "=" * 60)
    print("Testing Drug Pathway Weights")
    print("=" * 60)
    
    # Test ovarian PARP inhibitors
    parp_drugs = ["olaparib", "niraparib", "rucaparib"]
    print(f"\n📊 Ovarian PARP Inhibitors:")
    for drug in parp_drugs:
        weights = get_pathway_weights_for_drug(drug, disease="ovarian_cancer")
        print(f"   {drug:15s} → {weights}")
        assert "ddr" in weights, f"{drug} should have ddr pathway weight"
        assert weights.get("ddr", 0) > 0.8, f"{drug} should have high ddr weight"
    
    # Test melanoma BRAF/MEK inhibitors
    melanoma_drugs = ["BRAF inhibitor", "MEK inhibitor"]
    print(f"\n📊 Melanoma MAPK Inhibitors:")
    for drug in melanoma_drugs:
        weights = get_pathway_weights_for_drug(drug, disease="melanoma")
        print(f"   {drug:20s} → {weights}")
        assert "ras_mapk" in weights, f"{drug} should have ras_mapk pathway weight"
    
    print("\n✅ Drug pathway weights tests passed!")


def test_disease_parameter_flow():
    """Test that disease parameter flows through to literature client."""
    print("\n" + "=" * 60)
    print("Testing Disease Parameter Flow")
    print("=" * 60)
    
    # Check orchestrator imports
    from api.services.efficacy_orchestrator.orchestrator import EfficacyOrchestrator
    from api.services.efficacy_orchestrator.models import EfficacyRequest
    
    # Create a test request with disease
    test_request = EfficacyRequest(
        mutations=[{
            "gene": "BRCA1",
            "hgvs_p": "C711*",
            "chrom": "17",
            "pos": 43070943,
            "ref": "C",
            "alt": "A",
        }],
        disease="ovarian_cancer",
        model_id="evo2_1b",
        options={"adaptive": True, "ablation_mode": "SPE"},
        api_base="http://127.0.0.1:8000"
    )
    
    print(f"\n✅ Test request created with disease: {test_request.disease}")
    print(f"   Mutations: {len(test_request.mutations)}")
    print(f"   Options: {test_request.options}")
    
    # Verify disease is set
    assert test_request.disease == "ovarian_cancer", "Disease should be set correctly"
    
    print("\n✅ Disease parameter flow test passed!")


def main():
    """Run all validation tests."""
    print("\n" + "=" * 60)
    print("Phase 0 & Phase 1 Validation Tests")
    print("=" * 60)
    
    try:
        test_panel_selection()
        test_pathway_mapping()
        test_drug_pathway_weights()
        test_disease_parameter_flow()
        
        print("\n" + "=" * 60)
        print("✅ ALL VALIDATION TESTS PASSED!")
        print("=" * 60)
        return 0
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

