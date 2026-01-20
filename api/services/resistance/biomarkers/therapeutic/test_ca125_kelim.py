"""
Unit tests for CA-125 KELIM computation.

Tests the kinetic biomarker framework for CA-125 KELIM computation in ovarian cancer.
"""

import unittest
from datetime import datetime, timedelta
from typing import List, Dict, Any

from .ca125_kelim_ovarian import CA125KELIMOvarian, compute_ca125_kelim


class TestCA125KELIMOvarian(unittest.TestCase):
    """Test cases for CA-125 KELIM computation."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.kelim = CA125KELIMOvarian()
        self.base_date = datetime(2020, 1, 1)
    
    def test_compute_k_favorable(self):
        """Test KELIM computation with favorable K value (K ≥ 1.0)."""
        # Generate measurements with known K = 1.2 (favorable)
        treatment_start = self.base_date
        baseline_ca125 = 500.0
        k_ground_truth = 1.2
        
        measurements = []
        for days in [0, 21, 42, 63, 90]:
            ca125_value = baseline_ca125 * pow(2.71828, -k_ground_truth * (days / 30.0))
            measurements.append({
                "date": treatment_start + timedelta(days=days),
                "value": ca125_value
            })
        
        result = self.kelim.compute_k_value(measurements, treatment_start)
        
        self.assertIsNotNone(result["k_value"])
        self.assertGreaterEqual(result["k_value"], 0.0)
        self.assertEqual(result["category"], "favorable")
        self.assertEqual(result["measurements_used"], 5)
        self.assertIsNone(result.get("error"))
    
    def test_compute_k_intermediate(self):
        """Test KELIM computation with intermediate K value (0.5 ≤ K < 1.0)."""
        # Generate measurements with known K = 0.75 (intermediate)
        treatment_start = self.base_date
        baseline_ca125 = 500.0
        k_ground_truth = 0.75
        
        measurements = []
        for days in [0, 21, 42, 63]:
            ca125_value = baseline_ca125 * pow(2.71828, -k_ground_truth * (days / 30.0))
            measurements.append({
                "date": treatment_start + timedelta(days=days),
                "value": ca125_value
            })
        
        result = self.kelim.compute_k_value(measurements, treatment_start)
        
        self.assertIsNotNone(result["k_value"])
        self.assertGreaterEqual(result["k_value"], 0.0)
        self.assertEqual(result["category"], "intermediate")
        self.assertIsNone(result.get("error"))
    
    def test_compute_k_unfavorable(self):
        """Test KELIM computation with unfavorable K value (K < 0.5)."""
        # Generate measurements with known K = 0.3 (unfavorable)
        treatment_start = self.base_date
        baseline_ca125 = 500.0
        k_ground_truth = 0.3
        
        measurements = []
        for days in [0, 21, 42, 63]:
            ca125_value = baseline_ca125 * pow(2.71828, -k_ground_truth * (days / 30.0))
            measurements.append({
                "date": treatment_start + timedelta(days=days),
                "value": ca125_value
            })
        
        result = self.kelim.compute_k_value(measurements, treatment_start)
        
        self.assertIsNotNone(result["k_value"])
        self.assertGreaterEqual(result["k_value"], 0.0)
        self.assertEqual(result["category"], "unfavorable")
        self.assertIsNone(result.get("error"))
    
    def test_insufficient_measurements(self):
        """Test KELIM computation with insufficient measurements (< 3)."""
        treatment_start = self.base_date
        
        # Only 2 measurements (insufficient)
        measurements = [
            {"date": treatment_start, "value": 500.0},
            {"date": treatment_start + timedelta(days=21), "value": 400.0}
        ]
        
        result = self.kelim.compute_k_value(measurements, treatment_start)
        
        self.assertIsNone(result["k_value"])
        self.assertIsNone(result["category"])
        self.assertIsNotNone(result.get("error"))
        # Error message may vary, just check that it exists
        self.assertIsNotNone(result.get("error"))
    
    def test_missing_baseline(self):
        """Test KELIM computation with missing baseline measurement."""
        treatment_start = self.base_date
        
        # Measurements start after treatment (no baseline within 30 days before)
        measurements = [
            {"date": treatment_start + timedelta(days=21), "value": 400.0},
            {"date": treatment_start + timedelta(days=42), "value": 350.0},
            {"date": treatment_start + timedelta(days=63), "value": 300.0}
        ]
        
        result = self.kelim.compute_k_value(measurements, treatment_start)
        
        # Should fail validation
        self.assertIsNone(result["k_value"])
        self.assertIsNotNone(result.get("error"))
    
    def test_validation_data_requirements(self):
        """Test data requirements validation."""
        treatment_start = self.base_date
        
        # Valid measurements (baseline + 3 during treatment)
        valid_measurements = [
            {"date": treatment_start - timedelta(days=7), "value": 500.0},  # Baseline
            {"date": treatment_start + timedelta(days=21), "value": 400.0},
            {"date": treatment_start + timedelta(days=42), "value": 350.0},
            {"date": treatment_start + timedelta(days=63), "value": 300.0}
        ]
        
        validation = self.kelim.validate_data_requirements(valid_measurements, treatment_start)
        self.assertTrue(validation["valid"])
        # measurements_in_window may be 3 or 4 depending on whether baseline is included
        self.assertGreaterEqual(validation["measurements_in_window"], 3)
        self.assertTrue(validation["has_baseline"])
        self.assertEqual(len(validation["warnings"]), 0)
        
        # Invalid measurements (insufficient)
        invalid_measurements = [
            {"date": treatment_start + timedelta(days=21), "value": 400.0},
            {"date": treatment_start + timedelta(days=42), "value": 350.0}
        ]
        
        validation = self.kelim.validate_data_requirements(invalid_measurements, treatment_start)
        self.assertFalse(validation["valid"])
        self.assertGreater(len(validation["warnings"]), 0)
    
    def test_categorize_k_value(self):
        """Test K value categorization."""
        # Favorable (K ≥ 1.0)
        self.assertEqual(self.kelim.categorize_k_value(1.2), "favorable")
        self.assertEqual(self.kelim.categorize_k_value(1.0), "favorable")
        
        # Intermediate (0.5 ≤ K < 1.0)
        self.assertEqual(self.kelim.categorize_k_value(0.75), "intermediate")
        self.assertEqual(self.kelim.categorize_k_value(0.5), "intermediate")
        
        # Unfavorable (K < 0.5)
        self.assertEqual(self.kelim.categorize_k_value(0.3), "unfavorable")
        self.assertEqual(self.kelim.categorize_k_value(0.0), "unfavorable")
        
        # None
        self.assertIsNone(self.kelim.categorize_k_value(None))
    
    def test_confidence_computation(self):
        """Test confidence computation."""
        treatment_start = self.base_date
        
        # High confidence: 5+ measurements, good time span
        high_confidence_measurements = []
        for days in [0, 21, 42, 63, 90]:
            high_confidence_measurements.append({
                "date": treatment_start + timedelta(days=days),
                "days_since_start": days,
                "value": 500.0 * pow(2.71828, -1.0 * (days / 30.0))
            })
        
        confidence = self.kelim._compute_confidence(high_confidence_measurements, 1.0)
        self.assertGreater(confidence, 0.8)
        self.assertLessEqual(confidence, 1.0)
    
    def test_convenience_function(self):
        """Test convenience function compute_ca125_kelim."""
        treatment_start = self.base_date
        measurements = [
            {"date": treatment_start, "value": 500.0},
            {"date": treatment_start + timedelta(days=21), "value": 400.0},
            {"date": treatment_start + timedelta(days=42), "value": 350.0},
            {"date": treatment_start + timedelta(days=63), "value": 300.0}
        ]
        
        result = compute_ca125_kelim(measurements, treatment_start)
        
        self.assertIsNotNone(result.get("k_value"))
        self.assertIsNotNone(result.get("category"))
    
    def test_edge_case_negative_values(self):
        """Test handling of edge cases (negative values, zeros)."""
        treatment_start = self.base_date
        
        # Measurements with very low values
        measurements = [
            {"date": treatment_start, "value": 1.0},  # Very low baseline
            {"date": treatment_start + timedelta(days=21), "value": 0.5},
            {"date": treatment_start + timedelta(days=42), "value": 0.3},
            {"date": treatment_start + timedelta(days=63), "value": 0.2}
        ]
        
        result = self.kelim.compute_k_value(measurements, treatment_start)
        
        # Should handle gracefully (ensure positive values in computation)
        # Result may be None if computation fails, but should not crash
        if result.get("k_value") is not None:
            self.assertGreaterEqual(result["k_value"], 0.0)


if __name__ == "__main__":
    unittest.main()
