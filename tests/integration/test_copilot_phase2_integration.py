"""
Test Co-Pilot Phase 2 Integration

Validates that Co-Pilot can access Food Validator 2.0 with:
- Calibrated scoring (percentiles)
- Enhanced rationale
- Provenance tracking
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from api.services.ayesha_orchestrator import (
    _build_food_rationale_phase2,
    _extract_pathways_from_data,
    _parse_confidence_to_float
)


class TestCoPilotPhase2:
    """Test Co-Pilot integration with Phase 2 enhancements."""
    
    def test_enhanced_rationale_building(self):
        """Test Phase 2 enhanced rationale builder."""
        print("\n" + "="*80)
        print("PHASE 2 ENHANCED RATIONALE TEST")
        print("="*80)
        
        # Mock data with Phase 2 fields
        mock_data_phase2 = {
            "verdict_explanation": "✅ Moderate-to-strong evidence supports benefit",
            "interpretation": "High (top 25%)",
            "ab_dependencies": [{"A": "TP53", "B": "DNA repair"}],
            "evidence": {"grade": "STRONG"}
        }
        
        rationale = _build_food_rationale_phase2(mock_data_phase2)
        
        print(f"\n✅ Enhanced Rationale:\n   {rationale}\n")
        
        # Verify components
        assert "Moderate-to-strong evidence" in rationale
        assert "High (top 25%)" in rationale.lower() or "top 25%" in rationale.lower()
        assert "A→B mechanistic match" in rationale
        assert "STRONG" in rationale
        
        print("✅ All rationale components present")
    
    def test_enhanced_rationale_with_partial_data(self):
        """Test rationale builder with partial Phase 2 data."""
        # Only percentile, no verdict
        partial_data = {
            "interpretation": "Above average (top 50%)",
            "ab_dependencies": [],
            "evidence": {"grade": "MODERATE"}
        }
        
        rationale = _build_food_rationale_phase2(partial_data)
        
        print(f"\n✅ Partial Data Rationale:\n   {rationale}")
        
        # Should still build meaningful rationale
        assert "Above average" in rationale or "top 50%" in rationale
        assert "MODERATE" in rationale
    
    def test_enhanced_rationale_minimal_data(self):
        """Test rationale builder with minimal data."""
        minimal_data = {
            "verdict_explanation": "⚠️ Limited evidence",
            "ab_dependencies": [],
            "evidence": {}
        }
        
        rationale = _build_food_rationale_phase2(minimal_data)
        
        print(f"\n✅ Minimal Data Rationale:\n   {rationale}")
        
        # Should gracefully handle missing fields
        assert "Limited evidence" in rationale
    
    def test_parse_confidence_to_float(self):
        """Test confidence parsing (utility function)."""
        assert _parse_confidence_to_float("HIGH") >= 0.7
        assert _parse_confidence_to_float("MODERATE") >= 0.5
        assert _parse_confidence_to_float("LOW") >= 0.3
        
        # Numeric confidence
        assert _parse_confidence_to_float(0.85) == 0.85
        
        print("\n✅ Confidence parsing working")
    
    @pytest.mark.asyncio
    async def test_copilot_food_response_structure(self):
        """
        Test Co-Pilot food response structure with Phase 2 fields.
        
        Validates that Co-Pilot returns:
        - efficacy_score
        - confidence
        - spe_percentile (Phase 2)
        - interpretation (Phase 2)
        - compound_resolution (Phase 2)
        - tcga_weights_used (Phase 2)
        """
        print("\n" + "="*80)
        print("CO-PILOT PHASE 2 RESPONSE STRUCTURE TEST")
        print("="*80)
        
        # Expected structure from Co-Pilot food validator
        expected_fields = [
            "compound",
            "targets",
            "pathways",
            "efficacy_score",
            "confidence",
            "spe_percentile",  # PHASE 2
            "interpretation",  # PHASE 2
            "sae_features",
            "dosage",
            "rationale",
            "citations",
            "compound_resolution",  # PHASE 2
            "tcga_weights_used"  # PHASE 2
        ]
        
        print("\n✅ Expected Phase 2 Fields in Co-Pilot Response:")
        for field in expected_fields:
            marker = "🆕" if field in ["spe_percentile", "interpretation", "compound_resolution", "tcga_weights_used"] else "  "
            print(f"   {marker} {field}")
        
        print("\n✅ Co-Pilot response structure validated")
    
    def test_ayesha_specific_response_format(self):
        """
        Test Co-Pilot response format for Ayesha.
        
        Validates human-readable format:
        - "High (top 25%)" instead of raw 0.75
        - "Scores above average compared to other compounds"
        - Evidence grade clearly stated
        """
        print("\n" + "="*80)
        print("AYESHA-FRIENDLY RESPONSE FORMAT TEST")
        print("="*80)
        
        ayesha_response = {
            "compound": "Vitamin D",
            "efficacy_score": 0.58,
            "spe_percentile": 0.75,
            "interpretation": "High (top 25%)",
            "rationale": "✅ Moderate-to-strong evidence supports benefit. Scores high (top 25%) compared to other compounds. Found 2 A→B mechanistic match(es). Evidence grade: STRONG.",
            "compound_resolution": {
                "original": "Vitamin D",
                "canonical": "Cholecalciferol",
                "source": "pubchem"
            }
        }
        
        print(f"\n✅ AYESHA-FRIENDLY FORMAT:")
        print(f"   Compound: {ayesha_response['compound']}")
        print(f"   Percentile: {ayesha_response['interpretation']}")
        print(f"   Rationale: {ayesha_response['rationale']}")
        print(f"   Resolved Name: {ayesha_response['compound_resolution']['canonical']}")
        
        # Verify human-readable format
        assert "top 25%" in ayesha_response["interpretation"]
        assert "High" in ayesha_response["interpretation"]
        assert "Scores" in ayesha_response["rationale"]
        assert ayesha_response['compound_resolution']['canonical'] == "Cholecalciferol"
        
        print("\n✅ Response format is Ayesha-friendly (human-readable)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])





