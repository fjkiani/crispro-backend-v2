"""
Unit Tests for DDR_bin Scoring Engine.

Tests cover all disease sites, edge cases, and priority-ordered rules.
"""

import unittest
from typing import List, Dict, Any, Optional

from .ddr_bin_scoring import (
    assign_ddr_status,
    get_ddr_status_for_patient,
)
from ...config.ddr_config import get_ddr_config


class TestDDRBinScoring(unittest.TestCase):
    """Test cases for DDR_bin scoring engine."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Sample clinical records for different disease sites
        self.ovary_clinical = {
            "patient_id": "TEST_OV",
            "disease_site": "ovary",
            "tumor_subtype": "HGSOC"
        }
        self.breast_clinical = {
            "patient_id": "TEST_BR",
            "disease_site": "breast",
            "tumor_subtype": "TNBC"
        }
        self.pancreas_clinical = {
            "patient_id": "TEST_PA",
            "disease_site": "pancreas",
            "tumor_subtype": "PDAC"
        }
        self.prostate_clinical = {
            "patient_id": "TEST_PR",
            "disease_site": "prostate",
            "tumor_subtype": None
        }
        self.default_clinical = {
            "patient_id": "TEST_DEF",
            "disease_site": "other",
            "tumor_subtype": None
        }
    
    def test_brca_pathogenic_all_sites(self):
        """Test 1: BRCA Pathogenic (All Sites)"""
        for disease_site in ["ovary", "breast", "pancreas", "prostate", "default"]:
            clinical = {
                "patient_id": f"TEST_{disease_site.upper()}",
                "disease_site": disease_site,
            }
            mutations = [
                {
                    "patient_id": clinical["patient_id"],
                    "gene_symbol": "BRCA1",
                    "variant_classification": "pathogenic",
                    "variant_type": "SNV"
                }
            ]
            clinical_table = [clinical]
            
            results = assign_ddr_status(
                mutations_table=mutations,
                clinical_table=clinical_table,
                cna_table=None,
                hrd_assay_table=None,
                config=None
            )
            
            self.assertEqual(len(results), 1, f"Should return 1 result for {disease_site}")
            result = results[0]
            self.assertEqual(result["DDR_bin_status"], "DDR_defective", f"DDR_bin_status should be DDR_defective for {disease_site}")
            self.assertTrue(result["BRCA_pathogenic"], f"BRCA_pathogenic should be True for {disease_site}")
            self.assertEqual(result["DDR_score"], 3.0, f"DDR_score should be 3.0 for {disease_site} (BRCA weight)")
            self.assertIn("BRCA_pathogenic", result["DDR_features_used"], f"DDR_features_used should include BRCA_pathogenic for {disease_site}")
    
    def test_hrd_positive_by_score_ovary(self):
        """Test 2: HRD Positive by Score (Ovary)"""
        mutations = []
        clinical = self.ovary_clinical.copy()
        hrd_assay = [
            {
                "patient_id": clinical["patient_id"],
                "hrd_score": 45,  # Above cutoff of 42
                "hrd_status": None,
                "assay_name": "Myriad"
            }
        ]
        clinical_table = [clinical]
        
        results = assign_ddr_status(
            mutations_table=mutations,
            clinical_table=clinical_table,
            cna_table=None,
            hrd_assay_table=hrd_assay,
            config=None
        )
        
        self.assertEqual(len(results), 1)
        result = results[0]
        self.assertEqual(result["DDR_bin_status"], "DDR_defective")
        self.assertEqual(result["HRD_status_inferred"], "HRD_positive")
        self.assertEqual(result["HRD_score_raw"], 45.0)
        self.assertIn("HRD_score_high", result["DDR_features_used"])
    
    def test_hrd_positive_by_status_breast(self):
        """Test 3: HRD Positive by Status (Breast)"""
        mutations = []
        clinical = self.breast_clinical.copy()
        hrd_assay = [
            {
                "patient_id": clinical["patient_id"],
                "hrd_score": None,
                "hrd_status": "HRD_positive",
                "assay_name": "Leuven"
            }
        ]
        clinical_table = [clinical]
        
        results = assign_ddr_status(
            mutations_table=mutations,
            clinical_table=clinical_table,
            cna_table=None,
            hrd_assay_table=hrd_assay,
            config=None
        )
        
        self.assertEqual(len(results), 1)
        result = results[0]
        self.assertEqual(result["DDR_bin_status"], "DDR_defective")
        self.assertEqual(result["HRD_status_inferred"], "HRD_positive")
        self.assertIn("HRD_status_positive", result["DDR_features_used"])
    
    def test_core_hrr_pathogenic_all_sites(self):
        """Test 4: Core HRR Pathogenic (All Sites)"""
        # Use disease-specific genes: PALB2 for ovary/breast/pancreas/default, BRCA1 for prostate
        test_cases = {
            "ovary": "PALB2",
            "breast": "PALB2",
            "pancreas": "PALB2",
            "prostate": "BRCA1",  # Prostate core HRR includes BRCA1
            "default": "PALB2",
        }
        
        for disease_site, test_gene in test_cases.items():
            clinical = {
                "patient_id": f"TEST_{disease_site.upper()}_HRR",
                "disease_site": disease_site,
            }
            mutations = [
                {
                    "patient_id": clinical["patient_id"],
                    "gene_symbol": test_gene,
                    "variant_classification": "pathogenic",
                    "variant_type": "SNV"
                }
            ]
            clinical_table = [clinical]
            
            results = assign_ddr_status(
                mutations_table=mutations,
                clinical_table=clinical_table,
                cna_table=None,
                hrd_assay_table=None,
                config=None
            )
            
            self.assertEqual(len(results), 1, f"Should return 1 result for {disease_site}")
            result = results[0]
            # Should be DDR_defective (no BRCA, no HRD, but core HRR)
            # For prostate with BRCA1, it will be classified as BRCA_pathogenic (higher priority)
            # For other sites with PALB2, it should be core_HRR_pathogenic
            if disease_site == "prostate" and test_gene == "BRCA1":
                # BRCA1 will be caught as BRCA_pathogenic (higher priority)
                self.assertEqual(result["DDR_bin_status"], "DDR_defective", f"DDR_bin_status should be DDR_defective for {disease_site}")
                self.assertTrue(result["BRCA_pathogenic"], f"BRCA_pathogenic should be True for {disease_site} (BRCA1)")
                self.assertIn("BRCA_pathogenic", result["DDR_features_used"], f"DDR_features_used should include BRCA_pathogenic for {disease_site}")
            else:
                self.assertEqual(result["DDR_bin_status"], "DDR_defective", f"DDR_bin_status should be DDR_defective for {disease_site}")
                self.assertTrue(result["core_HRR_pathogenic"], f"core_HRR_pathogenic should be True for {disease_site}")
                self.assertFalse(result["BRCA_pathogenic"], f"BRCA_pathogenic should be False for {disease_site}")
                self.assertIn("core_hrr_pathogenic", result["DDR_features_used"], f"DDR_features_used should include core_hrr_pathogenic for {disease_site}")
    
    def test_extended_ddr_pathogenic_all_sites(self):
        """Test 5: Extended DDR Pathogenic (All Sites)"""
        # Use disease-specific genes: ATM for ovary/breast/pancreas/default, CHEK2 for prostate
        test_cases = {
            "ovary": "ATM",
            "breast": "ATM",
            "pancreas": "ATM",
            "prostate": "CHEK2",  # Prostate extended DDR includes CHEK2 (not ATM in core HRR)
            "default": "ATM",
        }
        
        for disease_site, test_gene in test_cases.items():
            clinical = {
                "patient_id": f"TEST_{disease_site.upper()}_DDR",
                "disease_site": disease_site,
            }
            mutations = [
                {
                    "patient_id": clinical["patient_id"],
                    "gene_symbol": test_gene,
                    "variant_classification": "pathogenic",
                    "variant_type": "SNV"
                }
            ]
            clinical_table = [clinical]
            
            results = assign_ddr_status(
                mutations_table=mutations,
                clinical_table=clinical_table,
                cna_table=None,
                hrd_assay_table=None,
                config=None
            )
            
            self.assertEqual(len(results), 1, f"Should return 1 result for {disease_site}")
            result = results[0]
            # Should be DDR_defective (no BRCA, no HRD, no core HRR, but extended DDR)
            self.assertEqual(result["DDR_bin_status"], "DDR_defective", f"DDR_bin_status should be DDR_defective for {disease_site}")
            self.assertTrue(result["extended_DDR_pathogenic"], f"extended_DDR_pathogenic should be True for {disease_site} (gene: {test_gene})")
            self.assertFalse(result["BRCA_pathogenic"], f"BRCA_pathogenic should be False for {disease_site}")
            # For prostate, ATM might be in core HRR, so check appropriately
            if disease_site == "prostate":
                # CHEK2 should be in extended DDR, not core HRR for prostate
                self.assertFalse(result["core_HRR_pathogenic"], f"core_HRR_pathogenic should be False for {disease_site} (CHEK2 is extended)")
            else:
                self.assertFalse(result["core_HRR_pathogenic"], f"core_HRR_pathogenic should be False for {disease_site}")
            self.assertIn("extended_ddr_pathogenic", result["DDR_features_used"], f"DDR_features_used should include extended_ddr_pathogenic for {disease_site}")
    
    def test_no_ddr_info_all_sites(self):
        """Test 6: No DDR Info (All Sites)"""
        for disease_site in ["ovary", "breast", "pancreas", "prostate", "default"]:
            clinical = {
                "patient_id": f"TEST_{disease_site.upper()}_NO_DDR",
                "disease_site": disease_site,
            }
            mutations = []
            clinical_table = [clinical]
            
            results = assign_ddr_status(
                mutations_table=mutations,
                clinical_table=clinical_table,
                cna_table=None,
                hrd_assay_table=None,
                config=None
            )
            
            self.assertEqual(len(results), 1, f"Should return 1 result for {disease_site}")
            result = results[0]
            self.assertEqual(result["DDR_bin_status"], "unknown", f"DDR_bin_status should be unknown for {disease_site} (no DDR data)")
            self.assertFalse(result["BRCA_pathogenic"], f"BRCA_pathogenic should be False for {disease_site}")
            self.assertFalse(result["core_HRR_pathogenic"], f"core_HRR_pathogenic should be False for {disease_site}")
            self.assertFalse(result["extended_DDR_pathogenic"], f"extended_DDR_pathogenic should be False for {disease_site}")
    
    def test_ddr_proficient_all_sites(self):
        """Test 7: DDR Proficient (All Sites) - VUS only, HRD negative"""
        for disease_site in ["ovary", "breast", "pancreas", "prostate", "default"]:
            clinical = {
                "patient_id": f"TEST_{disease_site.upper()}_PROF",
                "disease_site": disease_site,
            }
            # VUS (not pathogenic)
            mutations = [
                {
                    "patient_id": clinical["patient_id"],
                    "gene_symbol": "BRCA1",
                    "variant_classification": "VUS",
                    "variant_type": "SNV"
                }
            ]
            hrd_assay = [
                {
                    "patient_id": clinical["patient_id"],
                    "hrd_score": 20,  # Below cutoff
                    "hrd_status": "HRD_negative",
                    "assay_name": "Myriad"
                }
            ]
            clinical_table = [clinical]
            
            results = assign_ddr_status(
                mutations_table=mutations,
                clinical_table=clinical_table,
                cna_table=None,
                hrd_assay_table=hrd_assay,
                config=None
            )
            
            self.assertEqual(len(results), 1, f"Should return 1 result for {disease_site}")
            result = results[0]
            self.assertEqual(result["DDR_bin_status"], "DDR_proficient", f"DDR_bin_status should be DDR_proficient for {disease_site}")
            self.assertEqual(result["HRD_status_inferred"], "HRD_negative", f"HRD_status_inferred should be HRD_negative for {disease_site}")
            self.assertFalse(result["BRCA_pathogenic"], f"BRCA_pathogenic should be False for {disease_site} (VUS not pathogenic)")
    
    def test_priority_ordering_brca_over_hrd(self):
        """Test 8: Priority Ordering - BRCA over HRD"""
        clinical = self.ovary_clinical.copy()
        mutations = [
            {
                "patient_id": clinical["patient_id"],
                "gene_symbol": "BRCA1",
                "variant_classification": "pathogenic",
                "variant_type": "SNV"
            }
        ]
        hrd_assay = [
            {
                "patient_id": clinical["patient_id"],
                "hrd_score": 50,  # Also HRD positive
                "hrd_status": None,
            }
        ]
        clinical_table = [clinical]
        
        results = assign_ddr_status(
            mutations_table=mutations,
            clinical_table=clinical_table,
            cna_table=None,
            hrd_assay_table=hrd_assay,
            config=None
        )
        
        self.assertEqual(len(results), 1)
        result = results[0]
        self.assertEqual(result["DDR_bin_status"], "DDR_defective")
        # Should use BRCA_pathogenic (higher priority), not HRD
        self.assertIn("BRCA_pathogenic", result["DDR_features_used"])
        self.assertTrue(result["BRCA_pathogenic"])
    
    def test_different_cutoffs_site_specific(self):
        """Test 9: Different Cutoffs (Site-Specific)"""
        # Test with HRD score = 41 (below default cutoff of 42)
        clinical_ovary = self.ovary_clinical.copy()
        clinical_ovary["patient_id"] = "TEST_OV_41"
        hrd_assay_ovary = [
            {
                "patient_id": clinical_ovary["patient_id"],
                "hrd_score": 41,  # Below cutoff of 42
                "hrd_status": None,
            }
        ]
        
        results_ovary = assign_ddr_status(
            mutations_table=[],
            clinical_table=[clinical_ovary],
            cna_table=None,
            hrd_assay_table=hrd_assay_ovary,
            config=None
        )
        
        self.assertEqual(len(results_ovary), 1)
        result_ovary = results_ovary[0]
        # Should be HRD_negative (below cutoff)
        self.assertEqual(result_ovary["HRD_status_inferred"], "HRD_negative")
        self.assertEqual(result_ovary["DDR_bin_status"], "DDR_proficient")
    
    def test_biallelic_brca_ovary(self):
        """Test 10: Biallelic BRCA (Ovary - require_biallelic_if_cn_available=True)"""
        clinical = self.ovary_clinical.copy()
        mutations = [
            {
                "patient_id": clinical["patient_id"],
                "gene_symbol": "BRCA1",
                "variant_classification": "pathogenic",
                "variant_type": "SNV"
            }
        ]
        cna = [
            {
                "patient_id": clinical["patient_id"],
                "gene_symbol": "BRCA1",
                "copy_number_state": "deletion",
                "copy_number": 0.5
            }
        ]
        clinical_table = [clinical]
        
        results = assign_ddr_status(
            mutations_table=mutations,
            clinical_table=clinical_table,
            cna_table=cna,
            hrd_assay_table=None,
            config=None
        )
        
        self.assertEqual(len(results), 1)
        result = results[0]
        # Should still be DDR_defective (biallelic confirmed)
        self.assertEqual(result["DDR_bin_status"], "DDR_defective")
        self.assertTrue(result["BRCA_pathogenic"])
    
    def test_non_biallelic_brca_pancreas(self):
        """Test 11: Non-Biallelic BRCA (Pancreas - require_biallelic_if_cn_available=False)"""
        clinical = self.pancreas_clinical.copy()
        mutations = [
            {
                "patient_id": clinical["patient_id"],
                "gene_symbol": "BRCA1",
                "variant_classification": "pathogenic",
                "variant_type": "SNV"
            }
        ]
        # No CNA deletion (not biallelic)
        clinical_table = [clinical]
        
        results = assign_ddr_status(
            mutations_table=mutations,
            clinical_table=clinical_table,
            cna_table=None,
            hrd_assay_table=None,
            config=None
        )
        
        self.assertEqual(len(results), 1)
        result = results[0]
        # Should still be DDR_defective (pancreas doesn't require biallelic)
        self.assertEqual(result["DDR_bin_status"], "DDR_defective")
        self.assertTrue(result["BRCA_pathogenic"])
    
    def test_get_ddr_status_for_patient_convenience(self):
        """Test 12: Convenience Function (get_ddr_status_for_patient)"""
        mutations = [
            {
                "gene_symbol": "BRCA2",
                "variant_classification": "pathogenic",
                "variant_type": "SNV"
            }
        ]
        clinical = {
            "disease_site": "ovary",
            "tumor_subtype": "HGSOC"
        }
        
        result = get_ddr_status_for_patient(
            patient_id="TEST_CONVENIENCE",
            mutations=mutations,
            clinical=clinical,
            cna=None,
            hrd_assay=None,
            config=None
        )
        
        self.assertEqual(result["patient_id"], "TEST_CONVENIENCE")
        self.assertEqual(result["DDR_bin_status"], "DDR_defective")
        self.assertTrue(result["BRCA_pathogenic"])


if __name__ == "__main__":
    unittest.main()
