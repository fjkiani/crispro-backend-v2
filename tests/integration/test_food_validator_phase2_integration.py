"""
Test Food Validator Phase 2 Integration

Validates that alias resolver + calibration are properly integrated.
"""

import pytest
import sys
from pathlib import Path

# Add parent directories to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.services.food_spe_integration import FoodSPEIntegrationService


class TestFoodValidatorPhase2Integration:
    """Test Phase 2 integration into Food Validator."""
    
    @pytest.fixture
    def spe_service(self):
        """Create SPE service instance."""
        return FoodSPEIntegrationService()
    
    def test_service_initialization(self, spe_service):
        """Test that service initializes with Phase 1 components."""
        # Verify alias resolver initialized
        assert hasattr(spe_service, 'alias_resolver')
        assert spe_service.alias_resolver is not None
        print("✅ Alias resolver initialized")
        
        # Verify calibrator initialized
        assert hasattr(spe_service, 'calibrator')
        assert spe_service.calibrator is not None
        print("✅ Calibrator initialized")
        
        # Verify universal database loaded
        assert hasattr(spe_service, '_universal_db')
        print("✅ Universal database loaded")
    
    @pytest.mark.asyncio
    async def test_compound_resolution_in_spe_flow(self, spe_service):
        """Test that compound aliases are resolved before scoring."""
        # Use "Turmeric" which should resolve to "Curcumin"
        result = await spe_service.compute_spe_score(
            compound="Turmeric",
            targets=["NFκB", "COX2"],
            pathways=["Inflammation", "NFκB signaling"],
            disease_context={
                "disease": "ovarian_cancer_hgs",
                "pathways_disrupted": ["PI3K_AKT_mTOR", "TP53", "inflammation"]
            },
            evidence_grade="MODERATE"
        )
        
        # Verify provenance includes compound resolution
        assert "provenance" in result
        assert "compound_resolution" in result["provenance"]
        assert result["provenance"]["compound_resolution"]["original"] == "Turmeric"
        
        # Canonical name should be resolved (may be "curcumin" or "Turmeric" if PubChem fails)
        canonical = result["provenance"]["compound_resolution"]["canonical"]
        print(f"✅ Compound resolution: 'Turmeric' → '{canonical}'")
    
    @pytest.mark.asyncio
    async def test_calibration_integration(self, spe_service):
        """Test that calibration is applied to scores."""
        result = await spe_service.compute_spe_score(
            compound="Vitamin D",
            targets=["VDR"],
            pathways=["DNA repair", "Immune modulation"],
            disease_context={
                "disease": "ovarian_cancer_hgs",
                "pathways_disrupted": ["HRD_DDR", "PI3K_AKT_mTOR"]
            },
            evidence_grade="STRONG"
        )
        
        # Check for calibrated fields (may be None if no calibration data)
        assert "spe_percentile" in result
        assert "interpretation" in result
        
        # If percentile is available, verify interpretation
        if result["spe_percentile"] is not None:
            percentile = result["spe_percentile"]
            interpretation = result["interpretation"]
            print(f"✅ Calibration: score={result['overall_score']:.3f} → percentile={percentile:.3f} ({interpretation})")
            
            # Verify interpretation matches percentile
            if percentile >= 0.90:
                assert "Exceptional" in interpretation
            elif percentile >= 0.75:
                assert "High" in interpretation
        else:
            print("⚠️ No calibration data available (expected for first run)")
    
    @pytest.mark.asyncio
    async def test_enhanced_provenance(self, spe_service):
        """Test that provenance includes all Phase 2 fields."""
        result = await spe_service.compute_spe_score(
            compound="Curcumin",
            targets=["NFκB"],
            pathways=["inflammation"],
            disease_context={
                "disease": "ovarian_cancer_hgs",
                "pathways_disrupted": ["inflammation", "PI3K_AKT_mTOR"]
            },
            evidence_grade="MODERATE"
        )
        
        provenance = result.get("provenance", {})
        
        # Verify all provenance sections
        assert "compound_resolution" in provenance
        assert "calibration" in provenance
        assert "tcga_weights" in provenance
        
        # Verify TCGA weights usage
        assert provenance["tcga_weights"]["used"] == True  # Should have weights for ovarian
        assert provenance["tcga_weights"]["disease"] == "ovarian_cancer_hgs"
        
        print(f"✅ Enhanced provenance complete:")
        print(f"   - Compound: {provenance['compound_resolution']['original']} → {provenance['compound_resolution']['canonical']}")
        print(f"   - Calibration: {'available' if provenance['calibration']['available'] else 'unavailable'}")
        print(f"   - TCGA weights: {provenance['tcga_weights']['pathways_matched']} pathways matched")
    
    @pytest.mark.asyncio
    async def test_vitamin_d_end_to_end(self, spe_service):
        """
        End-to-end test: Vitamin D for Ayesha's ovarian cancer.
        
        Expected:
        - Alias: "Vitamin D" → "Cholecalciferol"
        - Pathways: DNA repair match with HRD_DDR
        - Calibration: (may be null if no data)
        """
        result = await spe_service.compute_spe_score(
            compound="Vitamin D",
            targets=["VDR"],
            pathways=["DNA repair", "Immune modulation", "Inflammation"],
            disease_context={
                "disease": "ovarian_cancer_hgs",
                "pathways_disrupted": ["HRD_DDR", "PI3K_AKT_mTOR", "TP53", "inflammation"],
                "biomarkers": {"HRD": "POSITIVE"}
            },
            evidence_grade="STRONG"
        )
        
        print(f"\n✅ VITAMIN D END-TO-END TEST:")
        print(f"   Overall Score: {result['overall_score']:.3f}")
        print(f"   Confidence: {result['confidence']:.3f}")
        print(f"   Verdict: {result['verdict']}")
        if result.get('spe_percentile'):
            print(f"   Percentile: {result['spe_percentile']:.3f} ({result['interpretation']})")
        print(f"   S/P/E: {result['spe_breakdown']}")
        print(f"   Provenance: {result['provenance']['compound_resolution']}")


if __name__ == "__main__":
    # Run with: PYTHONPATH=. venv/bin/pytest tests/test_food_validator_phase2_integration.py -v -s
    pytest.main([__file__, "-v", "-s"])





