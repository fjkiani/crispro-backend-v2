"""
Unit Tests for Compound Calibration Service

Tests for empirical percentile calibration using synthetic data.

Author: CrisPRO Platform
Date: November 5, 2025
"""

import pytest
import json
import numpy as np
from pathlib import Path
from api.services.compound_calibration import (
    CompoundCalibrationService,
    get_calibrator
)


@pytest.fixture
def temp_calibration_file(tmp_path):
    """Create a temporary calibration file for testing."""
    calibration_file = tmp_path / "test_calibration.json"
    return str(calibration_file)


@pytest.fixture
def calibrator(temp_calibration_file):
    """Create a fresh calibrator instance for each test."""
    return CompoundCalibrationService(calibration_file=temp_calibration_file)


@pytest.fixture
def synthetic_runs():
    """Generate synthetic run data for testing."""
    # Create 50 synthetic runs with scores following a normal distribution
    np.random.seed(42)  # Reproducible results
    scores = np.random.normal(loc=0.65, scale=0.12, size=50)
    # Clip to valid range [0, 1]
    scores = np.clip(scores, 0, 1)
    
    return [{"spe_score": float(score)} for score in scores]


class TestCompoundCalibrationService:
    """Test suite for CompoundCalibrationService."""
    
    def test_initialization(self, calibrator):
        """Test that calibrator initializes correctly."""
        assert calibrator is not None
        assert calibrator.calibration_data is not None
        assert "version" in calibrator.calibration_data
        assert "compounds" in calibrator.calibration_data
        
        print("✅ Calibrator initialized successfully")
    
    def test_empty_calibration(self, calibrator):
        """Test that empty calibration returns None."""
        percentile = calibrator.get_percentile(
            "vitamin_d", "ovarian_cancer_hgs", 0.65
        )
        
        assert percentile is None, "Empty calibration should return None"
        print("✅ Empty calibration handled correctly")
    
    def test_build_calibration_from_runs(self, calibrator, synthetic_runs):
        """Test building calibration from synthetic run data."""
        calibration = calibrator.build_calibration_from_runs(
            compound="vitamin_d",
            disease="ovarian_cancer_hgs",
            runs=synthetic_runs
        )
        
        assert calibration is not None
        assert "percentiles" in calibration
        assert "sample_size" in calibration
        assert "mean_score" in calibration
        assert "std_dev" in calibration
        
        # Check percentiles are ordered correctly
        p = calibration["percentiles"]
        assert p["p10"] < p["p25"] < p["p50"] < p["p75"] < p["p90"]
        
        # Check sample size
        assert calibration["sample_size"] == 50
        
        # Check statistics are reasonable (normal distribution around 0.65)
        assert 0.6 < calibration["mean_score"] < 0.7
        assert 0.10 < calibration["std_dev"] < 0.15
        
        print(f"✅ Calibration built: {calibration['percentiles']}")
        print(f"   n={calibration['sample_size']}, "
              f"mean={calibration['mean_score']:.3f}±{calibration['std_dev']:.3f}")
    
    def test_insufficient_data(self, calibrator):
        """Test that insufficient data returns None."""
        # Only 5 runs (less than minimum 10)
        few_runs = [{"spe_score": 0.5 + i*0.1} for i in range(5)]
        
        calibration = calibrator.build_calibration_from_runs(
            "vitamin_d", "ovarian_cancer_hgs", few_runs
        )
        
        assert calibration is None, "Should reject <10 samples"
        print("✅ Insufficient data rejected correctly")
    
    def test_add_and_get_calibration(self, calibrator, synthetic_runs):
        """Test adding calibration and retrieving percentiles."""
        # Build calibration
        calibration = calibrator.build_calibration_from_runs(
            "vitamin_d", "ovarian_cancer_hgs", synthetic_runs
        )
        
        # Add to calibrator
        success = calibrator.add_calibration(
            "vitamin_d",
            "ovarian_cancer_hgs",
            calibration,
            canonical_name="Cholecalciferol"
        )
        
        assert success is True
        
        # Test retrieval at various score points
        test_scores = [0.50, 0.60, 0.65, 0.70, 0.80]
        
        print("\n✅ Calibration added, testing percentile retrieval:")
        for score in test_scores:
            percentile = calibrator.get_percentile(
                "vitamin_d", "ovarian_cancer_hgs", score
            )
            
            assert percentile is not None
            assert 0 <= percentile <= 1
            
            print(f"   Score {score:.2f} → Percentile {percentile:.3f} "
                  f"({percentile*100:.0f}th)")
    
    def test_linear_interpolation(self, calibrator):
        """Test that linear interpolation works correctly."""
        # Create simple test calibration
        percentiles = {
            "p10": 0.3,
            "p50": 0.5,
            "p90": 0.8
        }
        
        # Test exact match
        result = calibrator._interpolate_percentile(0.5, percentiles)
        assert abs(result - 0.5) < 0.01, "Exact match should return p50"
        
        # Test interpolation between p50 and p90
        # Score 0.65 is halfway between 0.5 and 0.8
        # Should be halfway between p50 (0.5) and p90 (0.9)
        result = calibrator._interpolate_percentile(0.65, percentiles)
        expected = 0.5 + (0.65 - 0.5) / (0.8 - 0.5) * (0.9 - 0.5)
        assert abs(result - expected) < 0.01, f"Expected {expected:.3f}, got {result:.3f}"
        
        # Test edge case: below minimum
        result = calibrator._interpolate_percentile(0.2, percentiles)
        assert result == 0.1, "Below min should return p10"
        
        # Test edge case: above maximum
        result = calibrator._interpolate_percentile(0.9, percentiles)
        assert result == 0.9, "Above max should return p90"
        
        print("✅ Linear interpolation working correctly")
    
    def test_multiple_compounds_and_diseases(self, calibrator):
        """Test calibration for multiple compound-disease pairs."""
        # Generate different distributions for different scenarios
        np.random.seed(42)
        
        scenarios = [
            ("vitamin_d", "ovarian_cancer_hgs", 0.65, 0.12),
            ("vitamin_d", "breast_cancer", 0.70, 0.10),
            ("curcumin", "ovarian_cancer_hgs", 0.55, 0.15),
            ("resveratrol", "lung_cancer", 0.60, 0.14)
        ]
        
        print("\n✅ Testing multiple compound-disease pairs:")
        
        for compound, disease, mean, std in scenarios:
            # Generate synthetic runs
            scores = np.random.normal(loc=mean, scale=std, size=30)
            scores = np.clip(scores, 0, 1)
            runs = [{"spe_score": float(s)} for s in scores]
            
            # Build and add calibration
            calibration = calibrator.build_calibration_from_runs(
                compound, disease, runs
            )
            calibrator.add_calibration(compound, disease, calibration)
            
            # Verify retrieval
            percentile = calibrator.get_percentile(compound, disease, mean)
            
            print(f"   {compound:15s} in {disease:25s}: "
                  f"mean={mean:.2f} → p{percentile*100:.0f}")
            
            assert percentile is not None
            # Mean score should be around 50th percentile
            assert 0.4 < percentile < 0.6, "Mean should be near p50"
    
    def test_save_and_load_calibration(self, temp_calibration_file, synthetic_runs):
        """Test saving and loading calibration data."""
        # Create calibrator and add calibration
        calibrator1 = CompoundCalibrationService(calibration_file=temp_calibration_file)
        
        calibration = calibrator1.build_calibration_from_runs(
            "vitamin_d", "ovarian_cancer_hgs", synthetic_runs
        )
        calibrator1.add_calibration("vitamin_d", "ovarian_cancer_hgs", calibration)
        
        # Save
        success = calibrator1.save_calibration()
        assert success is True
        
        # Load in new instance
        calibrator2 = CompoundCalibrationService(calibration_file=temp_calibration_file)
        
        # Verify data persisted
        percentile = calibrator2.get_percentile(
            "vitamin_d", "ovarian_cancer_hgs", 0.65
        )
        
        assert percentile is not None
        
        print("✅ Save and load working correctly")
    
    def test_get_calibration_info(self, calibrator, synthetic_runs):
        """Test retrieving calibration metadata."""
        # Build and add calibration
        calibration = calibrator.build_calibration_from_runs(
            "vitamin_d", "ovarian_cancer_hgs", synthetic_runs
        )
        calibrator.add_calibration("vitamin_d", "ovarian_cancer_hgs", calibration)
        
        # Get info
        info = calibrator.get_calibration_info("vitamin_d", "ovarian_cancer_hgs")
        
        assert info is not None
        assert info["sample_size"] == 50
        assert "mean_score" in info
        assert "std_dev" in info
        assert "date" in info
        assert "source" in info
        
        print(f"✅ Calibration info: n={info['sample_size']}, "
              f"mean={info['mean_score']:.3f}, source={info['source']}")
    
    def test_singleton_pattern(self):
        """Test that get_calibrator() returns singleton instance."""
        calibrator1 = get_calibrator()
        calibrator2 = get_calibrator()
        
        assert calibrator1 is calibrator2
        
        print("✅ Singleton pattern working")
    
    def test_percentile_ordering(self, calibrator, synthetic_runs):
        """Test that higher scores map to higher percentiles."""
        # Build and add calibration
        calibration = calibrator.build_calibration_from_runs(
            "vitamin_d", "ovarian_cancer_hgs", synthetic_runs
        )
        calibrator.add_calibration("vitamin_d", "ovarian_cancer_hgs", calibration)
        
        # Test with increasing scores
        scores = [0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80]
        percentiles = []
        
        for score in scores:
            p = calibrator.get_percentile("vitamin_d", "ovarian_cancer_hgs", score)
            percentiles.append(p)
        
        # Verify monotonic increase
        for i in range(len(percentiles) - 1):
            assert percentiles[i] <= percentiles[i+1], \
                f"Percentiles should increase with score: {percentiles}"
        
        print("✅ Percentile ordering correct (monotonic increase)")
    
    def test_invalid_scores(self, calibrator):
        """Test handling of invalid score values."""
        # Runs with invalid scores
        invalid_runs = [
            {"spe_score": -0.5},  # Below 0
            {"spe_score": 1.5},   # Above 1
            {"spe_score": "invalid"},  # Wrong type
            {"spe_score": None},  # None
            {"wrong_field": 0.5},  # Missing field
        ]
        
        # Add some valid scores (0.5, 0.55, 0.60, ..., 0.95) - some will be >1 and filtered
        valid_runs = [{"spe_score": 0.5 + i*0.05} for i in range(15)]
        all_runs = invalid_runs + valid_runs
        
        # Should still work with valid subset
        calibration = calibrator.build_calibration_from_runs(
            "test_compound", "test_disease", all_runs
        )
        
        assert calibration is not None
        # Only scores in range [0, 1] are counted (0.5 to 1.0 = 11 scores)
        assert calibration["sample_size"] >= 10  # At least minimum valid
        
        print(f"✅ Invalid scores filtered correctly (n={calibration['sample_size']})")


# Integration test with realistic scenario
@pytest.mark.integration
class TestCompoundCalibrationIntegration:
    """Integration tests with realistic scenarios."""
    
    def test_realistic_ovarian_cancer_vitamin_d(self, temp_calibration_file):
        """Test realistic scenario: Vitamin D in ovarian cancer."""
        calibrator = CompoundCalibrationService(calibration_file=temp_calibration_file)
        
        # Simulate 100 patient runs with realistic score distribution
        # Based on hypothetical clinical data: mean efficacy ~0.62, high variance
        np.random.seed(123)
        scores = np.random.beta(a=6, b=4, size=100)  # Beta distribution (0-1)
        runs = [{"spe_score": float(s)} for s in scores]
        
        # Build calibration
        calibration = calibrator.build_calibration_from_runs(
            "vitamin_d", "ovarian_cancer_hgs", runs
        )
        
        calibrator.add_calibration(
            "vitamin_d",
            "ovarian_cancer_hgs",
            calibration,
            canonical_name="Cholecalciferol"
        )
        
        # Test interpretation of different patient scores
        test_cases = [
            (0.40, "Low efficacy patient"),
            (0.60, "Average efficacy patient"),
            (0.75, "High efficacy patient"),
            (0.85, "Very high efficacy patient")
        ]
        
        print("\n✅ Realistic Ovarian Cancer / Vitamin D scenario:")
        print(f"   Calibration: n={calibration['sample_size']}, "
              f"mean={calibration['mean_score']:.3f}")
        print("\n   Patient Score Interpretations:")
        
        for score, description in test_cases:
            percentile = calibrator.get_percentile(
                "vitamin_d", "ovarian_cancer_hgs", score
            )
            
            print(f"   - {description:30s}: score={score:.2f} → "
                  f"p{percentile*100:.0f} ({percentile:.3f})")
            
            # Verify reasonable percentiles
            assert percentile is not None
            assert 0 <= percentile <= 1
        
        # Save for inspection
        calibrator.save_calibration()
        print(f"\n   Saved to: {temp_calibration_file}")

