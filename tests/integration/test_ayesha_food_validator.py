"""
Ayesha-Specific Food Validator Tests (Task 2.3)

Tests 5 key food/supplement compounds for Ayesha's ovarian cancer.
Validates: compound resolution, S/P/E scoring, calibration, evidence, provenance.
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from api.services.food_spe_integration import FoodSPEIntegrationService


class TestAyeshaFoodValidator:
    """Test Food Validator for Ayesha's use-cases (Ovarian Cancer HGS)."""
    
    @pytest.fixture
    def spe_service(self):
        """Create SPE service instance."""
        return FoodSPEIntegrationService()
    
    @pytest.fixture
    def ayesha_disease_context(self):
        """Ayesha's disease context."""
        return {
            "disease": "ovarian_cancer_hgs",
            "pathways_disrupted": [
                "HRD_DDR",  # DNA repair deficiency
                "PI3K_AKT_mTOR",  # PI3K/AKT pathway
                "TP53",  # TP53 mutation
                "inflammation",  # Inflammatory response
                "angiogenesis"  # Blood vessel formation
            ],
            "biomarkers": {
                "HRD": "POSITIVE",
                "TMB": 8,
                "MSI": "STABLE"
            }
        }
    
    @pytest.mark.asyncio
    async def test_1_vitamin_d_for_ayesha(self, spe_service, ayesha_disease_context):
        """Test 1: Vitamin D for Ayesha's ovarian cancer."""
        print("\n" + "="*80)
        print("TEST 1: VITAMIN D FOR OVARIAN CANCER (AYESHA)")
        print("="*80)
        
        result = await spe_service.compute_spe_score(
            compound="Vitamin D",
            targets=["VDR"],  # Vitamin D Receptor
            pathways=["DNA repair", "Immune modulation", "Inflammation"],
            disease_context=ayesha_disease_context,
            evidence_grade="STRONG"  # Well-studied compound
        )
        
        # Assertions
        assert result["overall_score"] > 0
        assert result["confidence"] > 0
        assert result["verdict"] in ["SUPPORTED", "WEAK_SUPPORT", "NOT_SUPPORTED"]
        
        # Phase 2: Check calibrated fields
        assert "spe_percentile" in result
        assert "interpretation" in result
        assert "provenance" in result
        
        # Verify compound resolution
        assert result["provenance"]["compound_resolution"]["original"] == "Vitamin D"
        
        # Verify TCGA weights used
        assert result["provenance"]["tcga_weights"]["used"] == True
        assert result["provenance"]["tcga_weights"]["disease"] == "ovarian_cancer_hgs"
        
        # Report results
        print(f"\n✅ VITAMIN D RESULTS:")
        print(f"   Resolved: {result['provenance']['compound_resolution']['original']} → {result['provenance']['compound_resolution']['canonical']}")
        print(f"   Overall Score: {result['overall_score']:.3f}")
        print(f"   Confidence: {result['confidence']:.3f}")
        print(f"   Verdict: {result['verdict']}")
        if result.get('spe_percentile'):
            print(f"   Percentile: {result['spe_percentile']:.3f} ({result['interpretation']})")
        print(f"   S/P/E: {result['spe_breakdown']}")
        print(f"   TCGA Pathways Matched: {result['provenance']['tcga_weights']['pathways_matched']}")
    
    @pytest.mark.asyncio
    async def test_2_curcumin_for_ayesha(self, spe_service, ayesha_disease_context):
        """Test 2: Curcumin for Ayesha's ovarian cancer."""
        print("\n" + "="*80)
        print("TEST 2: CURCUMIN FOR OVARIAN CANCER (AYESHA)")
        print("="*80)
        
        result = await spe_service.compute_spe_score(
            compound="Curcumin",
            targets=["NFκB", "COX2", "STAT3"],
            pathways=["Inflammation", "NFκB signaling", "JAK-STAT"],
            disease_context=ayesha_disease_context,
            evidence_grade="STRONG"  # Well-studied for anti-cancer
        )
        
        # Assertions
        assert result["overall_score"] > 0
        assert result["verdict"] in ["SUPPORTED", "WEAK_SUPPORT", "NOT_SUPPORTED"]
        
        # Report
        print(f"\n✅ CURCUMIN RESULTS:")
        print(f"   Overall Score: {result['overall_score']:.3f}")
        print(f"   Verdict: {result['verdict']}")
        if result.get('spe_percentile'):
            print(f"   Percentile: {result['spe_percentile']:.3f} ({result['interpretation']})")
    
    @pytest.mark.asyncio
    async def test_3_omega3_for_ayesha(self, spe_service, ayesha_disease_context):
        """Test 3: Omega-3 for Ayesha's ovarian cancer."""
        print("\n" + "="*80)
        print("TEST 3: OMEGA-3 FOR OVARIAN CANCER (AYESHA)")
        print("="*80)
        
        result = await spe_service.compute_spe_score(
            compound="Omega-3 fatty acids",
            targets=["COX2", "PPAR"],
            pathways=["Inflammation", "Lipid metabolism"],
            disease_context=ayesha_disease_context,
            evidence_grade="MODERATE"
        )
        
        print(f"\n✅ OMEGA-3 RESULTS:")
        print(f"   Overall Score: {result['overall_score']:.3f}")
        print(f"   Verdict: {result['verdict']}")
        if result.get('spe_percentile'):
            print(f"   Percentile: {result['spe_percentile']:.3f} ({result['interpretation']})")
    
    @pytest.mark.asyncio
    async def test_4_green_tea_for_ayesha(self, spe_service, ayesha_disease_context):
        """Test 4: Green Tea Extract for Ayesha's ovarian cancer."""
        print("\n" + "="*80)
        print("TEST 4: GREEN TEA EXTRACT FOR OVARIAN CANCER (AYESHA)")
        print("="*80)
        
        result = await spe_service.compute_spe_score(
            compound="Green Tea Extract",
            targets=["EGFR", "VEGF", "Bcl-2"],
            pathways=["Angiogenesis", "Apoptosis", "Cell cycle"],
            disease_context=ayesha_disease_context,
            evidence_grade="MODERATE"
        )
        
        print(f"\n✅ GREEN TEA RESULTS:")
        print(f"   Overall Score: {result['overall_score']:.3f}")
        print(f"   Verdict: {result['verdict']}")
        if result.get('spe_percentile'):
            print(f"   Percentile: {result['spe_percentile']:.3f} ({result['interpretation']})")
    
    @pytest.mark.asyncio
    async def test_5_resveratrol_for_ayesha(self, spe_service, ayesha_disease_context):
        """Test 5: Resveratrol for Ayesha's ovarian cancer."""
        print("\n" + "="*80)
        print("TEST 5: RESVERATROL FOR OVARIAN CANCER (AYESHA)")
        print("="*80)
        
        result = await spe_service.compute_spe_score(
            compound="Resveratrol",
            targets=["SIRT1", "NF-κB", "COX2"],
            pathways=["Inflammation", "Autophagy", "Apoptosis"],
            disease_context=ayesha_disease_context,
            evidence_grade="MODERATE"
        )
        
        print(f"\n✅ RESVERATROL RESULTS:")
        print(f"   Overall Score: {result['overall_score']:.3f}")
        print(f"   Verdict: {result['verdict']}")
        if result.get('spe_percentile'):
            print(f"   Percentile: {result['spe_percentile']:.3f} ({result['interpretation']})")
    
    @pytest.mark.asyncio
    async def test_all_compounds_summary(self, spe_service, ayesha_disease_context):
        """
        Summary test: Compare all 5 compounds for Ayesha.
        
        Expected ranking (based on ovarian cancer biology):
        1. Vitamin D (DNA repair support, immune modulation)
        2. Curcumin (broad anti-inflammatory, anti-proliferative)
        3. Omega-3 (inflammation, lipid metabolism)
        4. Green Tea (EGFR inhibition, antioxidant)
        5. Resveratrol (autophagy, SIRT1 activation)
        """
        print("\n" + "="*80)
        print("COMPARATIVE ANALYSIS: ALL 5 COMPOUNDS FOR AYESHA")
        print("="*80)
        
        compounds = [
            ("Vitamin D", ["VDR"], ["DNA repair", "Immune modulation"], "STRONG"),
            ("Curcumin", ["NFκB", "COX2"], ["Inflammation", "NFκB signaling"], "STRONG"),
            ("Omega-3 fatty acids", ["COX2", "PPAR"], ["Inflammation"], "MODERATE"),
            ("Green Tea Extract", ["EGFR", "VEGF"], ["Angiogenesis"], "MODERATE"),
            ("Resveratrol", ["SIRT1", "NF-κB"], ["Inflammation", "Autophagy"], "MODERATE")
        ]
        
        results = []
        for compound, targets, pathways, evidence_grade in compounds:
            result = await spe_service.compute_spe_score(
                compound=compound,
                targets=targets,
                pathways=pathways,
                disease_context=ayesha_disease_context,
                evidence_grade=evidence_grade
            )
            results.append((compound, result))
        
        # Sort by overall score (descending)
        results.sort(key=lambda x: x[1]['overall_score'], reverse=True)
        
        print(f"\n🏆 RANKING FOR AYESHA (Ovarian Cancer HGS):\n")
        print(f"{'Rank':<5} {'Compound':<22} {'Score':<7} {'Verdict':<15} {'Percentile':<12} {'Interpretation'}")
        print("-" * 100)
        
        for i, (compound, result) in enumerate(results, 1):
            score = result['overall_score']
            verdict = result['verdict']
            percentile = result.get('spe_percentile')
            interpretation = result.get('interpretation', 'N/A')
            
            percentile_str = f"{percentile:.3f}" if percentile else "N/A"
            
            print(f"{i:<5} {compound:<22} {score:<7.3f} {verdict:<15} {percentile_str:<12} {interpretation}")
        
        print("\n✅ All 5 Ayesha-specific test cases completed successfully!")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])





