"""
Unit Tests for Timing & Chemosensitivity Engine.

Tests cover PFI, PTPI, TFI, PFS, OS computation across disease sites and edge cases.
"""

import unittest
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from .timing_chemo_features import (
    build_timing_chemo_features,
)
from ...config.timing_config import get_timing_config


class TestTimingChemoFeatures(unittest.TestCase):
    """Test cases for timing and chemosensitivity engine."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Sample dates for testing
        self.base_date = datetime(2020, 1, 1)
    
    def test_tfi_first_regimen(self):
        """Test 1: First Regimen (No Prior Regimen)"""
        regimens = [
            {
                "patient_id": "TEST001",
                "regimen_id": "R1",
                "regimen_start_date": self.base_date,
                "regimen_end_date": self.base_date + timedelta(days=180),
                "regimen_type": "platinum",
                "line_of_therapy": 1,
                "setting": "frontline",
            }
        ]
        survival = [{
            "patient_id": "TEST001",
            "vital_status": "Alive",
            "last_followup_date": self.base_date + timedelta(days=365),
        }]
        clinical = [{
            "patient_id": "TEST001",
            "disease_site": "ovary",
        }]
        
        results = build_timing_chemo_features(
            regimen_table=regimens,
            survival_table=survival,
            clinical_table=clinical,
            ca125_features_table=None,
            config=None
        )
        
        self.assertEqual(len(results), 1)
        result = results[0]
        self.assertIsNone(result["TFI_days"], "First regimen should have TFI_days = None")
    
    def test_tfi_multiple_regimens(self):
        """Test 2: Multiple Regimens (TFI Computation)"""
        regimens = [
            {
                "patient_id": "TEST002",
                "regimen_id": "R1",
                "regimen_start_date": self.base_date,
                "regimen_end_date": self.base_date + timedelta(days=180),
                "regimen_type": "platinum",
                "line_of_therapy": 1,
                "setting": "frontline",
            },
            {
                "patient_id": "TEST002",
                "regimen_id": "R2",
                "regimen_start_date": self.base_date + timedelta(days=240),
                "regimen_end_date": self.base_date + timedelta(days=300),
                "regimen_type": "non_platinum_chemo",
                "line_of_therapy": 2,
                "setting": "first_recurrence",
            }
        ]
        survival = [{
            "patient_id": "TEST002",
            "vital_status": "Alive",
            "last_followup_date": self.base_date + timedelta(days=365),
        }]
        clinical = [{
            "patient_id": "TEST002",
            "disease_site": "ovary",
        }]
        
        results = build_timing_chemo_features(
            regimen_table=regimens,
            survival_table=survival,
            clinical_table=clinical,
            ca125_features_table=None,
            config=None
        )
        
        self.assertEqual(len(results), 2)
        r2 = results[1]
        expected_tfi = 60  # (240 - 180) = 60 days
        self.assertEqual(r2["TFI_days"], expected_tfi, f"TFI should be {expected_tfi} days")
    
    def test_pfi_platinum_regimen(self):
        """Test 3: PFI Computation for Platinum Regimen"""
        regimens = [
            {
                "patient_id": "TEST003",
                "regimen_id": "R1",
                "regimen_start_date": self.base_date,
                "regimen_end_date": self.base_date + timedelta(days=180),
                "regimen_type": "platinum",
                "line_of_therapy": 1,
                "setting": "frontline",
                "last_platinum_dose_date": self.base_date + timedelta(days=165),
                "progression_date": self.base_date + timedelta(days=365),  # 200 days later
            }
        ]
        survival = [{
            "patient_id": "TEST003",
            "vital_status": "Alive",
            "last_followup_date": self.base_date + timedelta(days=400),
        }]
        clinical = [{
            "patient_id": "TEST003",
            "disease_site": "ovary",
        }]
        
        results = build_timing_chemo_features(
            regimen_table=regimens,
            survival_table=survival,
            clinical_table=clinical,
            ca125_features_table=None,
            config=None
        )
        
        self.assertEqual(len(results), 1)
        result = results[0]
        # PFI from last platinum dose (day 165) to progression (day 365) = 200 days
        expected_pfi = 200
        self.assertEqual(result["PFI_days"], expected_pfi, f"PFI should be {expected_pfi} days")
        self.assertEqual(result["PFI_category"], "6-12m", "PFI category should be 6-12m")
    
    def test_pfi_multiple_platinum_lines(self):
        """Test 4: PFI for Second-Line Platinum (Multiple Platinum Lines)"""
        regimens = [
            {
                "patient_id": "TEST004",
                "regimen_id": "R1",
                "regimen_start_date": self.base_date,
                "regimen_end_date": self.base_date + timedelta(days=180),
                "regimen_type": "platinum",
                "line_of_therapy": 1,
                "setting": "frontline",
                "last_platinum_dose_date": self.base_date + timedelta(days=165),
            },
            {
                "patient_id": "TEST004",
                "regimen_id": "R2",
                "regimen_start_date": self.base_date + timedelta(days=240),
                "regimen_end_date": self.base_date + timedelta(days=300),
                "regimen_type": "non_platinum_chemo",
                "line_of_therapy": 2,
                "setting": "first_recurrence",
            },
            {
                "patient_id": "TEST004",
                "regimen_id": "R3",
                "regimen_start_date": self.base_date + timedelta(days=420),
                "regimen_end_date": self.base_date + timedelta(days=480),
                "regimen_type": "platinum",
                "line_of_therapy": 3,
                "setting": "later_recurrence",
                "last_platinum_dose_date": self.base_date + timedelta(days=465),
            }
        ]
        survival = [{
            "patient_id": "TEST004",
            "vital_status": "Alive",
            "last_followup_date": self.base_date + timedelta(days=500),
        }]
        clinical = [{
            "patient_id": "TEST004",
            "disease_site": "ovary",
        }]
        
        results = build_timing_chemo_features(
            regimen_table=regimens,
            survival_table=survival,
            clinical_table=clinical,
            ca125_features_table=None,
            config=None
        )
        
        self.assertEqual(len(results), 3)
        r3 = results[2]
        # PFI from R1 last platinum dose (day 165) to R3 start (day 420) = 255 days
        expected_pfi = 255
        self.assertEqual(r3["PFI_days"], expected_pfi, f"PFI should be {expected_pfi} days")
        self.assertEqual(r3["PFI_category"], "6-12m", "PFI category should be 6-12m")
    
    def test_ptpi_parpi_after_platinum(self):
        """Test 5: PTPI for PARPi After Platinum"""
        regimens = [
            {
                "patient_id": "TEST005",
                "regimen_id": "R1",
                "regimen_start_date": self.base_date,
                "regimen_end_date": self.base_date + timedelta(days=180),
                "regimen_type": "platinum",
                "line_of_therapy": 1,
                "setting": "frontline",
                "last_platinum_dose_date": self.base_date + timedelta(days=165),
            },
            {
                "patient_id": "TEST005",
                "regimen_id": "R2",
                "regimen_start_date": self.base_date + timedelta(days=240),
                "regimen_end_date": self.base_date + timedelta(days=360),
                "regimen_type": "PARPi",
                "line_of_therapy": 2,
                "setting": "first_recurrence",
            }
        ]
        survival = [{
            "patient_id": "TEST005",
            "vital_status": "Alive",
            "last_followup_date": self.base_date + timedelta(days=400),
        }]
        clinical = [{
            "patient_id": "TEST005",
            "disease_site": "ovary",
        }]
        
        results = build_timing_chemo_features(
            regimen_table=regimens,
            survival_table=survival,
            clinical_table=clinical,
            ca125_features_table=None,
            config=None
        )
        
        self.assertEqual(len(results), 2)
        r2 = results[1]
        # PTPI from R1 last platinum dose (day 165) to R2 start (day 240) = 75 days
        expected_ptpi = 75
        self.assertEqual(r2["PTPI_days"], expected_ptpi, f"PTPI should be {expected_ptpi} days")
    
    def test_ptpi_parpi_no_prior_platinum(self):
        """Test 6: PTPI for PARPi Without Prior Platinum"""
        regimens = [
            {
                "patient_id": "TEST006",
                "regimen_id": "R1",
                "regimen_start_date": self.base_date,
                "regimen_end_date": self.base_date + timedelta(days=180),
                "regimen_type": "PARPi",
                "line_of_therapy": 1,
                "setting": "frontline",
            }
        ]
        survival = [{
            "patient_id": "TEST006",
            "vital_status": "Alive",
            "last_followup_date": self.base_date + timedelta(days=365),
        }]
        clinical = [{
            "patient_id": "TEST006",
            "disease_site": "ovary",
        }]
        
        results = build_timing_chemo_features(
            regimen_table=regimens,
            survival_table=survival,
            clinical_table=clinical,
            ca125_features_table=None,
            config=None
        )
        
        self.assertEqual(len(results), 1)
        result = results[0]
        self.assertIsNone(result["PTPI_days"], "PARPi without prior platinum should have PTPI_days = None")
    
    def test_pfs_censored(self):
        """Test 7: PFS Censored (No Progression)"""
        regimens = [
            {
                "patient_id": "TEST007",
                "regimen_id": "R1",
                "regimen_start_date": self.base_date,
                "regimen_end_date": self.base_date + timedelta(days=180),
                "regimen_type": "platinum",
                "line_of_therapy": 1,
                "setting": "frontline",
                "progression_date": None,  # No progression
            }
        ]
        survival = [{
            "patient_id": "TEST007",
            "vital_status": "Alive",
            "last_followup_date": self.base_date + timedelta(days=365),
        }]
        clinical = [{
            "patient_id": "TEST007",
            "disease_site": "ovary",
        }]
        
        results = build_timing_chemo_features(
            regimen_table=regimens,
            survival_table=survival,
            clinical_table=clinical,
            ca125_features_table=None,
            config=None
        )
        
        self.assertEqual(len(results), 1)
        result = results[0]
        # PFS from start (day 0) to follow-up (day 365) = 365 days
        expected_pfs = 365
        self.assertEqual(result["PFS_from_regimen_days"], expected_pfs, f"PFS should be {expected_pfs} days")
        self.assertEqual(result["PFS_event"], 0, "PFS should be censored (no progression)")
    
    def test_os_death(self):
        """Test 8: OS with Death Event"""
        regimens = [
            {
                "patient_id": "TEST008",
                "regimen_id": "R1",
                "regimen_start_date": self.base_date,
                "regimen_end_date": self.base_date + timedelta(days=180),
                "regimen_type": "platinum",
                "line_of_therapy": 1,
                "setting": "frontline",
            }
        ]
        survival = [{
            "patient_id": "TEST008",
            "vital_status": "Dead",
            "death_date": self.base_date + timedelta(days=400),
            "last_followup_date": self.base_date + timedelta(days=400),
        }]
        clinical = [{
            "patient_id": "TEST008",
            "disease_site": "ovary",
        }]
        
        results = build_timing_chemo_features(
            regimen_table=regimens,
            survival_table=survival,
            clinical_table=clinical,
            ca125_features_table=None,
            config=None
        )
        
        self.assertEqual(len(results), 1)
        result = results[0]
        # OS from start (day 0) to death (day 400) = 400 days
        expected_os = 400
        self.assertEqual(result["OS_from_regimen_days"], expected_os, f"OS should be {expected_os} days")
        self.assertEqual(result["OS_event"], 1, "OS should have event (death)")
    
    def test_ca125_integration_ovary(self):
        """Test 9: CA-125 Integration (Ovary)"""
        regimens = [
            {
                "patient_id": "TEST009",
                "regimen_id": "R1",
                "regimen_start_date": self.base_date,
                "regimen_end_date": self.base_date + timedelta(days=180),
                "regimen_type": "platinum",
                "line_of_therapy": 1,
                "setting": "frontline",
            }
        ]
        survival = [{
            "patient_id": "TEST009",
            "vital_status": "Alive",
            "last_followup_date": self.base_date + timedelta(days=365),
        }]
        clinical = [{
            "patient_id": "TEST009",
            "disease_site": "ovary",
        }]
        ca125_features = [
            {
                "patient_id": "TEST009",
                "regimen_id": "R1",
                "kelim_k_value": 1.2,
                "kelim_category": "favorable",
                "ca125_percent_change_day21": -45.0,
                "ca125_percent_change_day42": -65.0,
            }
        ]
        
        results = build_timing_chemo_features(
            regimen_table=regimens,
            survival_table=survival,
            clinical_table=clinical,
            ca125_features_table=ca125_features,
            config=None
        )
        
        self.assertEqual(len(results), 1)
        result = results[0]
        self.assertEqual(result["kelim_k_value"], 1.2, "KELIM k-value should be 1.2")
        self.assertEqual(result["kelim_category"], "favorable", "KELIM category should be favorable")
        self.assertTrue(result["has_ca125_data"], "Should have CA-125 data")
    
    def test_ca125_not_used_breast(self):
        """Test 10: CA-125 Not Used (Breast)"""
        regimens = [
            {
                "patient_id": "TEST010",
                "regimen_id": "R1",
                "regimen_start_date": self.base_date,
                "regimen_end_date": self.base_date + timedelta(days=180),
                "regimen_type": "platinum",
                "line_of_therapy": 1,
                "setting": "frontline",
            }
        ]
        survival = [{
            "patient_id": "TEST010",
            "vital_status": "Alive",
            "last_followup_date": self.base_date + timedelta(days=365),
        }]
        clinical = [{
            "patient_id": "TEST010",
            "disease_site": "breast",
        }]
        ca125_features = [
            {
                "patient_id": "TEST010",
                "regimen_id": "R1",
                "kelim_k_value": 1.2,
                "kelim_category": "favorable",
            }
        ]
        
        results = build_timing_chemo_features(
            regimen_table=regimens,
            survival_table=survival,
            clinical_table=clinical,
            ca125_features_table=ca125_features,
            config=None
        )
        
        self.assertEqual(len(results), 1)
        result = results[0]
        # Breast doesn't use CA-125, so features should not be added
        self.assertIsNone(result.get("kelim_k_value"), "Breast should not have KELIM features")
        self.assertFalse(result["has_ca125_data"], "Should not have CA-125 data for breast")
    
    def test_different_disease_sites(self):
        """Test 11: Different Disease Sites (PFI Cutpoints)"""
        test_cases = [
            ("ovary", [180, 365]),
            ("breast", [180, 365]),
            ("endometrium", [180, 365]),
        ]
        
        for disease_site, expected_cutpoints in test_cases:
            config = get_timing_config(disease_site)
            actual_cutpoints = config.get("pfi_cutpoints_days")
            self.assertEqual(
                actual_cutpoints,
                expected_cutpoints,
                f"{disease_site} should have cutpoints {expected_cutpoints}"
            )
    
    def test_missing_data_handling(self):
        """Test 12: Missing Data Handling"""
        regimens = [
            {
                "patient_id": "TEST012",
                "regimen_id": "R1",
                "regimen_start_date": self.base_date,
                "regimen_end_date": None,  # Missing end date
                "regimen_type": "platinum",
                "line_of_therapy": 1,
                "setting": "frontline",
                "progression_date": None,  # Missing progression
            }
        ]
        survival = [{
            "patient_id": "TEST012",
            "vital_status": "Alive",
            "death_date": None,  # Missing death date
            "last_followup_date": self.base_date + timedelta(days=365),
        }]
        clinical = [{
            "patient_id": "TEST012",
            "disease_site": "ovary",
        }]
        
        results = build_timing_chemo_features(
            regimen_table=regimens,
            survival_table=survival,
            clinical_table=clinical,
            ca125_features_table=None,
            config=None
        )
        
        self.assertEqual(len(results), 1)
        result = results[0]
        # Should handle missing data gracefully
        self.assertIsNone(result.get("PFI_days"), "PFI should be None when progression date missing")
        self.assertEqual(result["PFS_event"], 0, "PFS should be censored when no progression")
        self.assertEqual(result["OS_event"], 0, "OS should be censored when alive")


if __name__ == "__main__":
    unittest.main()
