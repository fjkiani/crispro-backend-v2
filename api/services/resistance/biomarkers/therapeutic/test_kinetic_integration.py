"""
Integration tests for Kinetic Biomarker Framework with Timing Engine.

Tests on-the-fly KELIM computation from raw CA-125 measurements in timing engine.
"""

import unittest
from datetime import datetime, timedelta
from typing import List, Dict, Any

from .timing_chemo_features import build_timing_chemo_features
from .ca125_kelim_ovarian import CA125KELIMOvarian


class TestKineticBiomarkerIntegration(unittest.TestCase):
    """Integration tests for kinetic biomarker framework."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.base_date = datetime(2020, 1, 1)
    
    def test_timing_engine_with_raw_ca125_measurements(self):
        """Test timing engine computes KELIM on-the-fly from raw CA-125 measurements."""
        # Setup regimen data
        regimen_table = [
            {
                "patient_id": "P001",
                "regimen_id": "R1",
                "regimen_start_date": self.base_date,
                "regimen_end_date": self.base_date + timedelta(days=180),
                "regimen_type": "platinum",
                "line_of_therapy": 1,
                "setting": "frontline",
                "last_platinum_dose_date": self.base_date + timedelta(days=150),
            }
        ]
        
        survival_table = [
            {
                "patient_id": "P001",
                "vital_status": "Alive",
                "last_followup_date": self.base_date + timedelta(days=365)
            }
        ]
        
        clinical_table = [
            {
                "patient_id": "P001",
                "disease_site": "ovary",
                "tumor_subtype": "HGSOC"
            }
        ]
        
        # Raw CA-125 measurements (generate with known K = 1.2)
        baseline_ca125 = 500.0
        k_ground_truth = 1.2
        ca125_measurements_table = []
        for days in [0, 21, 42, 63, 90]:
            ca125_value = baseline_ca125 * pow(2.71828, -k_ground_truth * (days / 30.0))
            ca125_measurements_table.append({
                "patient_id": "P001",
                "regimen_id": "R1",
                "date": self.base_date + timedelta(days=days),
                "value": ca125_value
            })
        
        # Run timing engine with raw measurements
        results = build_timing_chemo_features(
            regimen_table=regimen_table,
            survival_table=survival_table,
            clinical_table=clinical_table,
            ca125_features_table=None,  # No pre-computed features
            ca125_measurements_table=ca125_measurements_table,  # Raw measurements
            config=None
        )
        
        # Verify results
        self.assertEqual(len(results), 1)
        result = results[0]
        
        # Verify timing features are present
        self.assertIn("patient_id", result)
        self.assertIn("regimen_id", result)
        self.assertEqual(result["patient_id"], "P001")
        self.assertEqual(result["regimen_id"], "R1")
        
        # Verify KELIM was computed on-the-fly
        self.assertTrue(result.get("has_ca125_data", False))
        self.assertIsNotNone(result.get("kelim_k_value"))
        self.assertIsNotNone(result.get("kelim_category"))
        self.assertEqual(result["kelim_category"], "favorable")  # K = 1.2 is favorable
    
    def test_timing_engine_prefers_precomputed_features(self):
        """Test timing engine prefers pre-computed features over raw measurements."""
        regimen_table = [
            {
                "patient_id": "P001",
                "regimen_id": "R1",
                "regimen_start_date": self.base_date,
                "regimen_end_date": self.base_date + timedelta(days=180),
                "regimen_type": "platinum",
                "line_of_therapy": 1,
                "setting": "frontline",
            }
        ]
        
        survival_table = [
            {
                "patient_id": "P001",
                "vital_status": "Alive",
                "last_followup_date": self.base_date + timedelta(days=365)
            }
        ]
        
        clinical_table = [
            {
                "patient_id": "P001",
                "disease_site": "ovary",
            }
        ]
        
        # Pre-computed features (should be used)
        ca125_features_table = [
            {
                "patient_id": "P001",
                "regimen_id": "R1",
                "kelim_k_value": 0.8,  # Pre-computed value
                "kelim_category": "intermediate"
            }
        ]
        
        # Raw measurements (should be ignored if pre-computed features exist)
        ca125_measurements_table = [
            {
                "patient_id": "P001",
                "regimen_id": "R1",
                "date": self.base_date,
                "value": 500.0
            }
        ]
        
        # Run timing engine with both pre-computed and raw measurements
        results = build_timing_chemo_features(
            regimen_table=regimen_table,
            survival_table=survival_table,
            clinical_table=clinical_table,
            ca125_features_table=ca125_features_table,
            ca125_measurements_table=ca125_measurements_table,
            config=None
        )
        
        # Verify pre-computed features are used
        result = results[0]
        self.assertEqual(result.get("kelim_k_value"), 0.8)
        self.assertEqual(result.get("kelim_category"), "intermediate")
    
    def test_timing_engine_no_ca125_for_non_ovarian(self):
        """Test timing engine doesn't compute CA-125 KELIM for non-ovarian diseases."""
        regimen_table = [
            {
                "patient_id": "P001",
                "regimen_id": "R1",
                "regimen_start_date": self.base_date,
                "regimen_end_date": self.base_date + timedelta(days=180),
                "regimen_type": "platinum",
                "line_of_therapy": 1,
                "setting": "frontline",
            }
        ]
        
        survival_table = [
            {
                "patient_id": "P001",
                "vital_status": "Alive",
                "last_followup_date": self.base_date + timedelta(days=365)
            }
        ]
        
        clinical_table = [
            {
                "patient_id": "P001",
                "disease_site": "breast",  # Breast doesn't use CA-125
            }
        ]
        
        # Raw CA-125 measurements (should be ignored for breast)
        ca125_measurements_table = [
            {
                "patient_id": "P001",
                "regimen_id": "R1",
                "date": self.base_date,
                "value": 500.0
            }
        ]
        
        # Run timing engine
        results = build_timing_chemo_features(
            regimen_table=regimen_table,
            survival_table=survival_table,
            clinical_table=clinical_table,
            ca125_features_table=None,
            ca125_measurements_table=ca125_measurements_table,
            config=None
        )
        
        # Verify CA-125 features are not included
        result = results[0]
        self.assertFalse(result.get("has_ca125_data", False))
        self.assertIsNone(result.get("kelim_k_value"))
        self.assertIsNone(result.get("kelim_category"))
    
    def test_timing_engine_handles_insufficient_measurements(self):
        """Test timing engine handles insufficient CA-125 measurements gracefully."""
        regimen_table = [
            {
                "patient_id": "P001",
                "regimen_id": "R1",
                "regimen_start_date": self.base_date,
                "regimen_end_date": self.base_date + timedelta(days=180),
                "regimen_type": "platinum",
                "line_of_therapy": 1,
                "setting": "frontline",
            }
        ]
        
        survival_table = [
            {
                "patient_id": "P001",
                "vital_status": "Alive",
                "last_followup_date": self.base_date + timedelta(days=365)
            }
        ]
        
        clinical_table = [
            {
                "patient_id": "P001",
                "disease_site": "ovary",
            }
        ]
        
        # Insufficient measurements (only 2, need at least 3)
        ca125_measurements_table = [
            {
                "patient_id": "P001",
                "regimen_id": "R1",
                "date": self.base_date,
                "value": 500.0
            },
            {
                "patient_id": "P001",
                "regimen_id": "R1",
                "date": self.base_date + timedelta(days=21),
                "value": 400.0
            }
        ]
        
        # Run timing engine
        results = build_timing_chemo_features(
            regimen_table=regimen_table,
            survival_table=survival_table,
            clinical_table=clinical_table,
            ca125_features_table=None,
            ca125_measurements_table=ca125_measurements_table,
            config=None
        )
        
        # Verify CA-125 features are not included (insufficient data)
        result = results[0]
        self.assertFalse(result.get("has_ca125_data", False))
        self.assertIsNone(result.get("kelim_k_value"))
    
    def test_timing_engine_multiple_regimens_with_ca125(self):
        """Test timing engine handles multiple regimens with CA-125 measurements."""
        regimen_table = [
            {
                "patient_id": "P001",
                "regimen_id": "R1",
                "regimen_start_date": self.base_date,
                "regimen_end_date": self.base_date + timedelta(days=180),
                "regimen_type": "platinum",
                "line_of_therapy": 1,
                "setting": "frontline",
            },
            {
                "patient_id": "P001",
                "regimen_id": "R2",
                "regimen_start_date": self.base_date + timedelta(days=200),
                "regimen_end_date": self.base_date + timedelta(days=380),
                "regimen_type": "platinum",
                "line_of_therapy": 2,
                "setting": "first_recurrence",
            }
        ]
        
        survival_table = [
            {
                "patient_id": "P001",
                "vital_status": "Alive",
                "last_followup_date": self.base_date + timedelta(days=500)
            }
        ]
        
        clinical_table = [
            {
                "patient_id": "P001",
                "disease_site": "ovary",
            }
        ]
        
        # CA-125 measurements for both regimens
        baseline_ca125_r1 = 500.0
        baseline_ca125_r2 = 400.0
        k_r1 = 1.2  # Favorable
        k_r2 = 0.6  # Intermediate
        
        ca125_measurements_table = []
        
        # R1 measurements
        for days in [0, 21, 42, 63, 90]:
            ca125_value = baseline_ca125_r1 * pow(2.71828, -k_r1 * (days / 30.0))
            ca125_measurements_table.append({
                "patient_id": "P001",
                "regimen_id": "R1",
                "date": self.base_date + timedelta(days=days),
                "value": ca125_value
            })
        
        # R2 measurements
        r2_start = self.base_date + timedelta(days=200)
        for days in [0, 21, 42, 63]:
            ca125_value = baseline_ca125_r2 * pow(2.71828, -k_r2 * (days / 30.0))
            ca125_measurements_table.append({
                "patient_id": "P001",
                "regimen_id": "R2",
                "date": r2_start + timedelta(days=days),
                "value": ca125_value
            })
        
        # Run timing engine
        results = build_timing_chemo_features(
            regimen_table=regimen_table,
            survival_table=survival_table,
            clinical_table=clinical_table,
            ca125_features_table=None,
            ca125_measurements_table=ca125_measurements_table,
            config=None
        )
        
        # Verify both regimens have KELIM computed
        self.assertEqual(len(results), 2)
        
        r1_result = next(r for r in results if r["regimen_id"] == "R1")
        r2_result = next(r for r in results if r["regimen_id"] == "R2")
        
        # Verify R1 KELIM
        self.assertTrue(r1_result.get("has_ca125_data", False))
        self.assertIsNotNone(r1_result.get("kelim_k_value"))
        self.assertEqual(r1_result.get("kelim_category"), "favorable")
        
        # Verify R2 KELIM
        self.assertTrue(r2_result.get("has_ca125_data", False))
        self.assertIsNotNone(r2_result.get("kelim_k_value"))
        self.assertEqual(r2_result.get("kelim_category"), "intermediate")


if __name__ == "__main__":
    unittest.main()
