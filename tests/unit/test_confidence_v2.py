"""
Unit tests for CONFIDENCE_V2 feature flag implementation.
"""
import os
import pytest
from api.services.confidence.confidence_computation import (
    compute_confidence_v2, 
    clamp01,
    compute_confidence
)
from api.services.confidence.insights_lifts import (
    compute_insights_lifts_v2,
    compute_insights_lifts
)
from api.services.confidence.tier_computation import (
    compute_evidence_tier_v2,
    compute_evidence_tier
)
from api.services.confidence.models import ConfidenceConfig


class TestConfidenceV2:
    """Test suite for CONFIDENCE_V2 implementation."""
    
    def setup_method(self):
        """Set up test environment."""
        # Ensure CONFIDENCE_V2 is disabled for legacy tests
        os.environ["CONFIDENCE_V2"] = "0"
        self.config = ConfidenceConfig()
    
    def test_clamp01_function(self):
        """Test clamp01 utility function."""
        assert clamp01(0.5) == 0.5
        assert clamp01(-0.1) == 0.0
        assert clamp01(1.1) == 1.0
        assert clamp01(0.0) == 0.0
        assert clamp01(1.0) == 1.0
    
    def test_confidence_v2_formula(self):
        """Test exact confidence formula compliance."""
        # Test case: supported tier, high S/P, all insights qualifying
        insights = {
            "functionality": 0.7,  # ≥0.6 → +0.04
            "chromatin": 0.6,      # ≥0.5 → +0.02
            "essentiality": 0.8,   # ≥0.7 → +0.02
            "regulatory": 0.7      # ≥0.6 → +0.02
        }
        
        confidence = compute_confidence_v2(
            tier="supported",  # E = 0.05
            seq_pct=0.8,       # S = 0.8
            path_pct=0.6,      # P = 0.6
            insights=insights,
            config=self.config
        )
        
        # Expected: 0.5*0.8 + 0.2*0.6 + 0.3*0.05 + 0.08 = 0.4 + 0.12 + 0.015 + 0.08 = 0.615
        # Rounded to 2 decimals: 0.61 (actual implementation rounds 0.615 to 0.61)
        assert confidence == 0.61
    
    def test_confidence_v2_lifts_capping(self):
        """Test lifts capping at +0.08."""
        # Test case: all insights qualifying (total would be 0.10, capped to 0.08)
        insights = {
            "functionality": 0.7,  # +0.04
            "chromatin": 0.6,      # +0.02
            "essentiality": 0.8,   # +0.02
            "regulatory": 0.7      # +0.02
        }
        
        confidence = compute_confidence_v2(
            tier="supported",  # E = 0.05
            seq_pct=0.0,       # S = 0.0
            path_pct=0.0,      # P = 0.0
            insights=insights,
            config=self.config
        )
        
        # Expected: 0.5*0.0 + 0.2*0.0 + 0.3*0.05 + 0.08 = 0.0 + 0.0 + 0.015 + 0.08 = 0.095
        # Rounded to 2 decimals: 0.10
        assert confidence == 0.10
    
    def test_confidence_v2_tier_boosts(self):
        """Test tier-based evidence boosts."""
        insights = {"functionality": 0.0, "chromatin": 0.0, "essentiality": 0.0, "regulatory": 0.0}
        
        # Test supported tier
        confidence_supported = compute_confidence_v2(
            tier="supported", seq_pct=0.0, path_pct=0.0, insights=insights, config=self.config
        )
        assert confidence_supported == 0.01  # 0.3 * 0.05 = 0.015, rounded to 0.01
        
        # Test consider tier
        confidence_consider = compute_confidence_v2(
            tier="consider", seq_pct=0.0, path_pct=0.0, insights=insights, config=self.config
        )
        assert confidence_consider == 0.01  # 0.3 * 0.02 = 0.006, rounded to 0.01
        
        # Test insufficient tier
        confidence_insufficient = compute_confidence_v2(
            tier="insufficient", seq_pct=0.0, path_pct=0.0, insights=insights, config=self.config
        )
        assert confidence_insufficient == 0.00  # 0.3 * 0.00 = 0.0
    
    def test_insights_lifts_v2_exact_values(self):
        """Test exact insights lift values."""
        insights = {
            "functionality": 0.6,  # Should qualify
            "chromatin": 0.5,      # Should qualify
            "essentiality": 0.7,   # Should qualify
            "regulatory": 0.6     # Should qualify
        }
        
        lifts = compute_insights_lifts_v2(insights)
        
        assert lifts["functionality"] == 0.032  # Capped from 0.04
        assert lifts["chromatin"] == 0.016       # Capped from 0.02
        assert lifts["essentiality"] == 0.016   # Capped from 0.02
        assert lifts["regulatory"] == 0.016      # Capped from 0.02
        assert sum(lifts.values()) == 0.08  # Total capped at 0.08
    
    def test_insights_lifts_v2_capping(self):
        """Test lifts capping at +0.08."""
        insights = {
            "functionality": 0.7,  # +0.04
            "chromatin": 0.6,      # +0.02
            "essentiality": 0.8,   # +0.02
            "regulatory": 0.7      # +0.02
        }
        
        lifts = compute_insights_lifts_v2(insights)
        
        # Should be capped at 0.08 total
        assert sum(lifts.values()) == 0.08
        
        # Should maintain relative proportions
        assert lifts["functionality"] == 0.032  # 0.04 * 0.8
        assert lifts["chromatin"] == 0.016       # 0.02 * 0.8
        assert lifts["essentiality"] == 0.016   # 0.02 * 0.8
        assert lifts["regulatory"] == 0.016      # 0.02 * 0.8
    
    def test_tier_v2_classification(self):
        """Test exact tier classification criteria."""
        # Test Tier I (supported): FDA-OnLabel
        tier = compute_evidence_tier_v2(0.0, 0.0, 0.0, ["FDA-OnLabel"], self.config)
        assert tier == "supported"
        
        # Test Tier I (supported): RCT
        tier = compute_evidence_tier_v2(0.0, 0.0, 0.0, ["RCT"], self.config)
        assert tier == "supported"
        
        # Test Tier I (supported): ClinVar-Strong + pathway alignment
        tier = compute_evidence_tier_v2(0.0, 0.3, 0.0, ["ClinVar-Strong"], self.config)
        assert tier == "supported"
        
        # Test Tier II (consider): strong evidence
        tier = compute_evidence_tier_v2(0.0, 0.0, 0.7, [], self.config)
        assert tier == "consider"
        
        # Test Tier II (consider): moderate evidence + pathway alignment
        tier = compute_evidence_tier_v2(0.0, 0.3, 0.5, [], self.config)
        assert tier == "consider"
        
        # Test Tier III (insufficient): else
        tier = compute_evidence_tier_v2(0.0, 0.1, 0.3, [], self.config)
        assert tier == "insufficient"
    
    def test_feature_flag_gating(self):
        """Test feature flag gating preserves legacy behavior."""
        # With CONFIDENCE_V2=0, should use legacy implementation
        os.environ["CONFIDENCE_V2"] = "0"
        
        insights = {"functionality": 0.7, "chromatin": 0.6, "essentiality": 0.8, "regulatory": 0.7}
        
        # Should use legacy tier-based calculation
        confidence_legacy = compute_confidence("supported", 0.8, 0.6, insights, self.config)
        
        # Enable CONFIDENCE_V2
        os.environ["CONFIDENCE_V2"] = "1"
        
        # Should use new linear formula
        confidence_v2 = compute_confidence("supported", 0.8, 0.6, insights, self.config)
        
        # Results should be different (proving feature flag works)
        assert confidence_legacy != confidence_v2
    
    def test_boundary_cases(self):
        """Test boundary cases for lift thresholds."""
        # Test exact thresholds
        insights_exact = {
            "functionality": 0.6,  # Exactly at threshold
            "chromatin": 0.5,      # Exactly at threshold
            "essentiality": 0.7,   # Exactly at threshold
            "regulatory": 0.6     # Exactly at threshold
        }
        
        lifts = compute_insights_lifts_v2(insights_exact)
        assert len(lifts) == 4  # All should qualify
        
        # Test just below thresholds
        insights_below = {
            "functionality": 0.59,  # Just below threshold
            "chromatin": 0.49,      # Just below threshold
            "essentiality": 0.69,   # Just below threshold
            "regulatory": 0.59      # Just below threshold
        }
        
        lifts = compute_insights_lifts_v2(insights_below)
        assert len(lifts) == 0  # None should qualify
    
    def test_performance_targets(self):
        """Test performance targets are met."""
        import time
        
        insights = {"functionality": 0.7, "chromatin": 0.6, "essentiality": 0.8, "regulatory": 0.7}
        
        # Test confidence calculation performance
        start_time = time.time()
        for _ in range(1000):
            compute_confidence_v2("supported", 0.8, 0.6, insights, self.config)
        end_time = time.time()
        
        avg_time_ms = (end_time - start_time) * 1000 / 1000
        assert avg_time_ms < 1.0  # Should be much faster than 1ms per call


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
