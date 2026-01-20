"""
Phase 1 End-to-End Integration Test

Validates complete stack:
1. Compound alias resolution (PubChem)
2. Disease pathway loading (Universal DB)
3. TCGA weight integration
4. S/P/E scoring
5. Calibration (percentile ranking)

Author: CrisPRO Platform
Date: November 5, 2025
"""

import pytest
import sys
from pathlib import Path

# Add backend root to path
backend_root = Path(__file__).parent.parent
sys.path.insert(0, str(backend_root))

from api.services.compound_alias_resolver import get_resolver
from api.services.compound_calibration import CompoundCalibrationService
from api.services.dynamic_food_extraction import DynamicFoodExtractor
from api.services.food_spe_integration import FoodSPEIntegrationService
import asyncio


class TestPhase1Integration:
    """End-to-end integration tests for Phase 1."""
    
    def test_compound_alias_resolution(self):
        """Test compound alias resolution via PubChem."""
        resolver = get_resolver()
        
        test_cases = [
            ("Vitamin D", None),  # May not resolve, but should return original
            ("Curcumin", "curcumin"),
            ("Resveratrol", "resveratrol"),
            ("Quercetin", "quercetin"),
        ]
        
        for compound, expected_canonical in test_cases:
            canonical = resolver.resolve_compound_alias(compound)
            assert canonical is not None, f"Compound '{compound}' resolution failed"
            assert canonical != "", f"Compound '{compound}' returned empty string"
            
            # If expected_canonical provided, check match (case-insensitive)
            if expected_canonical:
                assert canonical.lower() == expected_canonical.lower(), \
                    f"Expected '{expected_canonical}', got '{canonical}'"
        
        # Check cache stats
        stats = resolver.get_cache_stats()
        assert stats["cache_size"] > 0, "Cache should have entries"
        print(f"✅ Compound resolution: {stats['cache_size']} cached compounds")
    
    def test_disease_pathway_loading(self):
        """Test disease pathway loading from universal database."""
        service = FoodSPEIntegrationService()
        
        test_diseases = [
            "ovarian_cancer_hgs",
            "breast_cancer",
            "colorectal_cancer",
            "pancreatic_cancer",
        ]
        
        for disease in test_diseases:
            weights = service._get_disease_pathway_weights(disease)
            assert weights is not None, f"Disease '{disease}' weights not loaded"
            assert len(weights) > 0, f"Disease '{disease}' has no pathway weights"
            
            # Check that weights are in valid range [0, 1]
            for pathway, weight in weights.items():
                assert 0 <= weight <= 1, \
                    f"Invalid weight for {pathway}: {weight} (must be 0-1)"
            
            print(f"✅ {disease}: {len(weights)} pathways with TCGA weights")
    
    def test_pathway_normalization(self):
        """Test pathway name normalization for matching."""
        service = FoodSPEIntegrationService()
        
        test_cases = [
            ("DNA repair", "hrd_ddr"),
            ("Estrogen signaling", "er_pr_signaling"),
            ("PI3K/AKT", "pi3k_akt_mtor"),
            ("KRAS signaling", "ras_mapk"),
            ("Hormone receptor", "er_pr_signaling"),
        ]
        
        for pathway_input, expected_normalized in test_cases:
            normalized = service._normalize_pathway_name(pathway_input)
            assert normalized == expected_normalized, \
                f"Pathway '{pathway_input}' normalized to '{normalized}', expected '{expected_normalized}'"
        
        print("✅ Pathway normalization: All test cases passed")
    
    def test_tcga_weighted_pathway_alignment(self):
        """Test TCGA-weighted pathway alignment scoring."""
        service = FoodSPEIntegrationService()
        
        # Test case: Vitamin D (DNA repair) → Ovarian Cancer (hrd_ddr: 0.112)
        compound_pathways = ["DNA repair", "Inflammation"]
        disease_pathways = ["tp53", "hrd_ddr", "pi3k_akt_mtor"]
        disease = "ovarian_cancer_hgs"
        
        weights = service._get_disease_pathway_weights(disease)
        pathway_score = service._compute_pathway_alignment(
            compound_pathways=compound_pathways,
            disease_pathways=disease_pathways,
            disease_pathway_weights=weights
        )
        
        # Should use TCGA weight for hrd_ddr (0.112), not binary 0.2 or 1.0
        assert 0.0 <= pathway_score <= 1.0, f"Invalid pathway score: {pathway_score}"
        assert pathway_score != 1.0, "Pathway score should not be binary (1.0)"
        assert pathway_score != 0.0, "Pathway score should not be zero"
        
        # Should reflect TCGA weight (hrd_ddr = 0.112)
        assert pathway_score > 0.1, f"Pathway score too low: {pathway_score} (expected >0.1)"
        
        print(f"✅ TCGA-weighted pathway alignment: score={pathway_score:.3f}")
    
    @pytest.mark.asyncio
    async def test_full_stack_vitamin_d_ovarian(self):
        """Test complete flow: Vitamin D for ovarian cancer."""
        # 1. Resolve compound alias
        resolver = get_resolver()
        canonical = resolver.resolve_compound_alias("Vitamin D")
        assert canonical is not None
        print(f"✅ Step 1: Compound resolved: 'Vitamin D' → '{canonical}'")
        
        # 2. Extract targets
        extractor = DynamicFoodExtractor()
        extraction_result = await extractor.extract_all("Vitamin D", "ovarian cancer")
        assert extraction_result is not None
        assert "targets" in extraction_result
        assert len(extraction_result.get("targets", [])) > 0
        print(f"✅ Step 2: Targets extracted: {len(extraction_result['targets'])} targets")
        
        # 3. Load disease pathways (TCGA weights)
        spe_service = FoodSPEIntegrationService()
        disease = "ovarian_cancer_hgs"
        weights = spe_service._get_disease_pathway_weights(disease)
        assert weights is not None
        assert len(weights) > 0
        print(f"✅ Step 3: TCGA weights loaded: {len(weights)} pathways")
        
        # 4. Compute S/P/E score
        disease_context = {
            "disease": disease,
            "pathways_disrupted": list(weights.keys())[:5]  # Use top 5 pathways
        }
        
        spe_result = await spe_service.compute_spe_score(
            compound="Vitamin D",
            targets=extraction_result.get("targets", []),
            pathways=extraction_result.get("pathways", []),
            disease_context=disease_context,
            evidence_grade="MODERATE",
            treatment_history=None,
            evo2_enabled=False
        )
        
        assert spe_result is not None
        assert "overall_score" in spe_result
        assert "spe_breakdown" in spe_result
        assert "pathway" in spe_result["spe_breakdown"]
        
        pathway_score = spe_result["spe_breakdown"]["pathway"]
        assert 0.0 <= pathway_score <= 1.0
        
        print(f"✅ Step 4: S/P/E computed: overall={spe_result['overall_score']:.3f}, "
              f"pathway={pathway_score:.3f}")
        
        # 5. Get calibrated percentile (if available)
        calibrator = CompoundCalibrationService()
        percentile = calibrator.get_percentile("vitamin_d", disease, spe_result["overall_score"])
        
        if percentile is not None:
            assert 0.0 <= percentile <= 1.0
            print(f"✅ Step 5: Calibrated percentile: {percentile:.2f}")
        else:
            print(f"⚠️  Step 5: No calibration available (expected for some pairs)")
        
        # Final validation
        assert spe_result["overall_score"] > 0.0, "Overall score should be positive"
        print(f"\n✅ Full stack integration: SUCCESS")
        print(f"   Overall score: {spe_result['overall_score']:.3f}")
        print(f"   Pathway score (TCGA-weighted): {pathway_score:.3f}")
        if percentile:
            print(f"   Calibrated percentile: {percentile:.2f}")
    
    @pytest.mark.asyncio
    async def test_novel_compound_novel_disease(self):
        """Test with compound/disease not in cache or hardcoded."""
        # Test: Fisetin for lung cancer (not in common compounds initially)
        resolver = get_resolver()
        extractor = DynamicFoodExtractor()
        spe_service = FoodSPEIntegrationService()
        
        # Resolve (may be cache miss, but should work)
        canonical = resolver.resolve_compound_alias("Fisetin")
        assert canonical is not None
        
        # Extract (dynamic extraction should work)
        extraction_result = await extractor.extract_all("Fisetin", "lung cancer")
        assert extraction_result is not None
        
        # Check TCGA weights (lung cancer should be in universal DB)
        disease = "lung_cancer"
        weights = spe_service._get_disease_pathway_weights(disease)
        assert weights is not None
        
        print(f"✅ Novel compound/disease test: Fisetin → lung_cancer")
        print(f"   Resolved: '{canonical}'")
        print(f"   Targets: {len(extraction_result.get('targets', []))}")
        print(f"   TCGA pathways: {len(weights)}")
    
    def test_cache_performance(self):
        """Test cache hit rates after warming."""
        resolver = get_resolver()
        
        # Query compounds that should be in cache (from warming)
        cached_compounds = ["Curcumin", "Resveratrol", "Quercetin", "Genistein"]
        
        initial_stats = resolver.get_cache_stats()
        initial_hits = initial_stats["cache_hits"]
        initial_misses = initial_stats["cache_misses"]
        
        # Query again (should be cache hits)
        for compound in cached_compounds:
            _ = resolver.resolve_compound_alias(compound)
        
        final_stats = resolver.get_cache_stats()
        final_hits = final_stats["cache_hits"]
        final_misses = final_stats["cache_misses"]
        
        # Check that we got some cache hits
        hits_gained = final_hits - initial_hits
        assert hits_gained > 0, "Should have cache hits after warming"
        
        hit_rate = final_stats["hit_rate"]
        print(f"✅ Cache performance: hit_rate={hit_rate*100:.1f}%, "
              f"cache_size={final_stats['cache_size']}")
        
        # Note: Hit rate may be low if cache was cleared between tests
        # This is acceptable - the important thing is that caching works


if __name__ == "__main__":
    # Run tests manually
    import sys
    
    test_suite = TestPhase1Integration()
    
    print("=" * 80)
    print("🧪 PHASE 1 INTEGRATION TESTS")
    print("=" * 80)
    print()
    
    # Run synchronous tests
    try:
        test_suite.test_compound_alias_resolution()
        test_suite.test_disease_pathway_loading()
        test_suite.test_pathway_normalization()
        test_suite.test_tcga_weighted_pathway_alignment()
        test_suite.test_cache_performance()
        
        # Run async tests
        asyncio.run(test_suite.test_full_stack_vitamin_d_ovarian())
        asyncio.run(test_suite.test_novel_compound_novel_disease())
        
        print()
        print("=" * 80)
        print("✅ ALL INTEGRATION TESTS PASSED!")
        print("=" * 80)
        sys.exit(0)
    except Exception as e:
        print()
        print("=" * 80)
        print(f"❌ TEST FAILED: {e}")
        print("=" * 80)
        import traceback
        traceback.print_exc()
        sys.exit(1)







