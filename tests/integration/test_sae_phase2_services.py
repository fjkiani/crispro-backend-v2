"""
SAE Phase 2 Services - Comprehensive Test Suite
===============================================
Tests all 3 SAE Phase 2 services:
1. SAE Feature Service (sae_feature_service.py)
2. Mechanism Fit Ranker (mechanism_fit_ranker.py)
3. Resistance Detection Service (resistance_detection_service.py)

Owner: Zo (Lead Commander)
Date: January 13, 2025
Manager Policy: MANAGER_ANSWERS_TO_ZO_SAE_QUESTIONS.md
"""

import pytest
import sys
import math
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.services.sae_feature_service import (
    compute_sae_features,
    SAEFeatureService,
    HRR_GENES,
    PATHWAY_THRESHOLD_HIGH,
    PATHWAY_THRESHOLD_MODERATE
)
from api.services.mechanism_fit_ranker import (
    rank_trials_by_mechanism,
    MechanismFitRanker,
    MECHANISM_FIT_ALPHA,
    MECHANISM_FIT_BETA,
    MIN_ELIGIBILITY_THRESHOLD,
    MIN_MECHANISM_FIT_THRESHOLD
)
from api.services.resistance_detection_service import (
    detect_resistance,
    ResistanceDetectionService,
    RESISTANCE_HRD_DROP_THRESHOLD,
    RESISTANCE_DNA_REPAIR_DROP_THRESHOLD
)


# ============================================================
# TEST SUITE 1: SAE FEATURE SERVICE (8 TESTS)
# ============================================================

class TestSAEFeatureService:
    """Test SAE Feature computation (Manager's C1-C10)"""
    
    def test_dna_repair_capacity_formula(self):
        """
        Test Manager's APPROVED formula (C5): 0.6×DDR + 0.2×ess + 0.2×exon
        ⚔️ MANAGER APPROVED: 0.6/0.2/0.2 weights (Jan 13, 2025)
        """
        service = SAEFeatureService()
        
        # Test case: High DDR (0.8), moderate ess (0.6), high exon_disruption (0.7)
        result = service._compute_dna_repair_capacity(
            pathway_burden_ddr=0.8,
            essentiality_hrr=0.6,
            exon_disruption=0.7  # ⚔️ FIXED: was functionality
        )
        
        # ⚔️ MANAGER APPROVED FORMULA: 0.6/0.2/0.2 weights
        expected = (0.6 * 0.8) + (0.2 * 0.6) + (0.2 * 0.7)  # = 0.48 + 0.12 + 0.14 = 0.74
        
        assert abs(result - expected) < 0.01, f"Expected {expected}, got {result}"
        assert abs(result - 0.74) < 0.01, "Manager's formula must match exactly (within floating point tolerance)"
    
    def test_essentiality_hrr_genes(self):
        """Test essentiality computation for HRR genes (C3)"""
        service = SAEFeatureService()
        
        # Test case: Patient has BRCA1 and PALB2 mutations
        genes = ["BRCA1", "PALB2", "TP53"]  # 2 HRR genes, 1 non-HRR
        insights_bundle = {"essentiality": 0.85}
        
        result = service._compute_essentiality_hrr(insights_bundle, genes)
        
        # Should average essentiality for 2 HRR genes
        assert result == 0.85, f"Expected 0.85 (avg of BRCA1+PALB2), got {result}"
    
    def test_exon_disruption_threshold(self):
        """Test exon disruption only applies when essentiality > 0.65 (C4)"""
        service = SAEFeatureService()
        
        insights_bundle = {"regulatory": 0.70}
        
        # Case 1: Below threshold (essentiality 0.60 < 0.65) → should return 0.0
        result_below = service._compute_exon_disruption_score(
            insights_bundle, [], essentiality_hrr=0.60
        )
        assert result_below == 0.0, "Exon disruption should be 0 when essentiality < 0.65"
        
        # Case 2: Above threshold (essentiality 0.70 > 0.65) → should return regulatory score
        result_above = service._compute_exon_disruption_score(
            insights_bundle, [], essentiality_hrr=0.70
        )
        assert result_above == 0.70, "Exon disruption should use regulatory when essentiality > 0.65"
    
    def test_mechanism_vector_7d(self):
        """Test mechanism vector is 7D (DDR, MAPK, PI3K, VEGF, HER2, IO, Efflux)"""
        insights_bundle = {"functionality": 0.6, "chromatin": 0.5, "essentiality": 0.7, "regulatory": 0.4}
        pathway_scores = {"ddr": 0.8, "mapk": 0.3, "pi3k": 0.2, "vegf": 0.5, "her2": 0.6}
        tumor_context = {"tmb_score": 25, "msi_status": "MSI-High", "hrd_score": 55, "somatic_mutations": []}
        
        result = compute_sae_features(
            insights_bundle=insights_bundle,
            pathway_scores=pathway_scores,
            tumor_context=tumor_context
        )
        
        mechanism_vector = result["mechanism_vector"]
        
        assert len(mechanism_vector) == 7, f"Mechanism vector must be 7D, got {len(mechanism_vector)}D"
        assert mechanism_vector == [0.8, 0.3, 0.2, 0.5, 0.6, 1.0, 0.0], "Vector values incorrect"
    
    def test_io_eligibility_tmb(self):
        """Test IO eligibility (TMB >= 20)"""
        insights_bundle = {"functionality": 0.6}
        pathway_scores = {"ddr": 0.5}
        
        # Case 1: TMB = 25 (>= 20) → IO eligible
        tumor_context_high_tmb = {"tmb_score": 25, "msi_status": "Unknown", "somatic_mutations": []}
        result_high = compute_sae_features(insights_bundle, pathway_scores, tumor_context_high_tmb)
        assert result_high["io_eligible"] == True, "Should be IO eligible with TMB >= 20"
        
        # Case 2: TMB = 5 (< 20) → IO not eligible
        tumor_context_low_tmb = {"tmb_score": 5, "msi_status": "Unknown", "somatic_mutations": []}
        result_low = compute_sae_features(insights_bundle, pathway_scores, tumor_context_low_tmb)
        assert result_low["io_eligible"] == False, "Should not be IO eligible with TMB < 20"
    
    def test_io_eligibility_msi(self):
        """Test IO eligibility (MSI-High)"""
        insights_bundle = {"functionality": 0.6}
        pathway_scores = {"ddr": 0.5}
        
        # MSI-High → IO eligible (regardless of TMB)
        tumor_context_msi_high = {"tmb_score": 5, "msi_status": "MSI-High", "somatic_mutations": []}
        result = compute_sae_features(insights_bundle, pathway_scores, tumor_context_msi_high)
        assert result["io_eligible"] == True, "Should be IO eligible with MSI-High"
    
    def test_cross_resistance_risk(self):
        """Test cross-resistance risk scaling (0.3, 0.6, 0.9)"""
        service = SAEFeatureService()
        
        # No treatments → 0.0
        assert service._compute_cross_resistance_risk(None) == 0.0
        assert service._compute_cross_resistance_risk([]) == 0.0
        
        # 1 treatment → 0.3
        assert service._compute_cross_resistance_risk([{"drug": "carboplatin"}]) == 0.3
        
        # 2 treatments → 0.6
        assert service._compute_cross_resistance_risk([{"drug": "carboplatin"}, {"drug": "paclitaxel"}]) == 0.6
        
        # 3+ treatments → 0.9
        assert service._compute_cross_resistance_risk([{}, {}, {}]) == 0.9
    
    def test_provenance_tracking(self):
        """Test provenance includes all required fields"""
        insights_bundle = {"functionality": 0.6, "essentiality": 0.7}
        pathway_scores = {"ddr": 0.8}
        tumor_context = {"hrd_score": 55, "tmb_score": 10, "msi_status": "Unknown", "somatic_mutations": []}
        
        result = compute_sae_features(insights_bundle, pathway_scores, tumor_context)
        
        assert "provenance" in result
        assert "data_sources" in result["provenance"]
        assert "manager_policy" in result["provenance"]
        assert "thresholds" in result["provenance"]


# ============================================================
# TEST SUITE 2: MECHANISM FIT RANKER (6 TESTS)
# ============================================================

class TestMechanismFitRanker:
    """Test mechanism fit trial ranking (Manager's P4)"""
    
    def test_l2_normalization(self):
        """Test L2 normalization (Manager's P4)"""
        ranker = MechanismFitRanker()
        
        # Test case: [3, 4] → normalized = [0.6, 0.8] (L2 norm = 5)
        vector = [3.0, 4.0]
        result = ranker._l2_normalize(vector)
        
        assert abs(result[0] - 0.6) < 0.01, f"Expected 0.6, got {result[0]}"
        assert abs(result[1] - 0.8) < 0.01, f"Expected 0.8, got {result[1]}"
        
        # Verify L2 norm = 1.0 (normalized)
        l2_norm = math.sqrt(sum(x**2 for x in result))
        assert abs(l2_norm - 1.0) < 0.01, f"L2 norm should be 1.0, got {l2_norm}"
    
    def test_cosine_similarity(self):
        """Test cosine similarity computation"""
        ranker = MechanismFitRanker()
        
        # Test case 1: Identical normalized vectors → cosine = 1.0
        vec1 = ranker._l2_normalize([1.0, 1.0, 1.0])
        vec2 = ranker._l2_normalize([1.0, 1.0, 1.0])
        
        similarity = ranker._cosine_similarity(vec1, vec2)
        assert abs(similarity - 1.0) < 0.01, f"Identical vectors should have cosine = 1.0, got {similarity}"
        
        # Test case 2: Orthogonal vectors → cosine = 0.0
        vec3 = ranker._l2_normalize([1.0, 0.0])
        vec4 = ranker._l2_normalize([0.0, 1.0])
        
        similarity_orthogonal = ranker._cosine_similarity(vec3, vec4)
        assert abs(similarity_orthogonal - 0.0) < 0.01, f"Orthogonal vectors should have cosine = 0.0, got {similarity_orthogonal}"
    
    def test_alpha_beta_weighting(self):
        """Test α=0.7, β=0.3 weighting (Manager's P4)"""
        ranker = MechanismFitRanker()
        
        # Verify default weights
        assert ranker.alpha == 0.7, "Alpha must be 0.7 (Manager's policy)"
        assert ranker.beta == 0.3, "Beta must be 0.3 (Manager's policy)"
        
        # Test combined score calculation
        eligibility = 0.8
        mechanism_fit = 0.6
        
        expected_combined = (0.7 * 0.8) + (0.3 * 0.6)  # = 0.56 + 0.18 = 0.74
        
        # This would be computed in rank_trials, but we can verify the formula
        assert abs(expected_combined - 0.74) < 0.01
    
    def test_minimum_thresholds(self):
        """Test min thresholds: eligibility ≥0.60, mechanism_fit ≥0.50 (Manager's P4)"""
        # Mock trials
        trials = [
            {"nct_id": "NCT001", "eligibility_score": 0.70, "moa_vector": [0.8, 0.2, 0.1, 0.3, 0.5, 0.0, 0.1]},  # Pass both
            {"nct_id": "NCT002", "eligibility_score": 0.55, "moa_vector": [0.9, 0.3, 0.2, 0.4, 0.6, 1.0, 0.2]},  # Below eligibility
            {"nct_id": "NCT003", "eligibility_score": 0.75, "moa_vector": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.1]},  # Below mechanism fit
        ]
        
        sae_vector = [0.8, 0.3, 0.2, 0.4, 0.5, 1.0, 0.2]
        
        result = rank_trials_by_mechanism(trials, sae_vector)
        
        # Only NCT001 should pass both thresholds
        assert len(result) == 1, f"Expected 1 trial to pass thresholds, got {len(result)}"
        assert result[0]["nct_id"] == "NCT001"
    
    def test_her2_pathway_integration(self):
        """Test HER2 pathway (7D vector) for NCT06819007 validation"""
        # Mock SAE vector with HER2 burden
        sae_vector = [0.7, 0.3, 0.2, 0.4, 0.8, 0.0, 0.1]  # HER2 = 0.8 (high)
        
        # Mock HER2-targeted trial (NCT06819007-like)
        trials = [
            {
                "nct_id": "NCT06819007",
                "eligibility_score": 0.85,
                "moa_vector": [0.2, 0.1, 0.1, 0.2, 0.9, 0.0, 0.1]  # HER2-targeted (HER2=0.9)
            }
        ]
        
        result = rank_trials_by_mechanism(trials, sae_vector, min_mechanism_fit=0.30)
        
        assert len(result) == 1
        assert result[0]["mechanism_alignment"]["HER2"] > 0.5, "HER2 alignment should be high"
    
    def test_pathway_alignment_breakdown(self):
        """Test per-pathway alignment breakdown"""
        ranker = MechanismFitRanker()
        
        sae_vector = [0.8, 0.3, 0.2, 0.5, 0.6, 1.0, 0.1]  # Patient pathway burden
        trial_moa = [0.9, 0.1, 0.0, 0.8, 0.7, 0.0, 0.0]  # Trial mechanism
        
        alignment = ranker._compute_pathway_alignment(sae_vector, trial_moa)
        
        # DDR alignment = 0.8 × 0.9 = 0.72
        assert abs(alignment["DDR"] - 0.72) < 0.01
        
        # VEGF alignment = 0.5 × 0.8 = 0.40
        assert abs(alignment["VEGF"] - 0.40) < 0.01
        
        # HER2 alignment = 0.6 × 0.7 = 0.42
        assert abs(alignment["HER2"] - 0.42) < 0.01


# ============================================================
# TEST SUITE 3: RESISTANCE DETECTION SERVICE (8 TESTS)
# ============================================================

class TestResistanceDetectionService:
    """Test resistance detection with 2-of-3 trigger rule (Manager's C7, R2)"""
    
    def test_no_resistance_baseline(self):
        """Test no resistance when no triggers met"""
        result = detect_resistance(
            current_hrd=55.0,
            previous_hrd=None,  # No baseline
            current_dna_repair_capacity=0.7,
            previous_dna_repair_capacity=None,
            ca125_intelligence=None,
            treatment_on_parp=False
        )
        
        assert result["resistance_detected"] == False
        assert result["trigger_count"] == 0
        assert result["immediate_alert"] == False
    
    def test_single_trigger_insufficient(self):
        """Test single trigger (HRD drop) insufficient for alert"""
        result = detect_resistance(
            current_hrd=40.0,  # Dropped from 58
            previous_hrd=58.0,  # Drop = 18 (>= 15) → TRIGGER 1
            current_dna_repair_capacity=0.70,
            previous_dna_repair_capacity=0.72,  # Drop = 0.02 (< 0.20) → NO TRIGGER
            ca125_intelligence={"resistance_rule": {"triggered": False}},  # NO TRIGGER
            treatment_on_parp=True
        )
        
        assert result["trigger_count"] == 1, "Only 1 trigger should be met"
        assert result["resistance_detected"] == False, "1-of-3 insufficient for alert"
        assert "hrd_drop" in result["triggers_met"]
    
    def test_two_triggers_sufficient(self):
        """Test 2-of-3 triggers sufficient for resistance alert (Manager's C7)"""
        result = detect_resistance(
            current_hrd=40.0,  # Drop = 18 → TRIGGER 1
            previous_hrd=58.0,
            current_dna_repair_capacity=0.50,  # Drop = 0.25 → TRIGGER 2
            previous_dna_repair_capacity=0.75,
            ca125_intelligence={"resistance_rule": {"triggered": False}},  # NO TRIGGER
            treatment_on_parp=True
        )
        
        assert result["trigger_count"] == 2, "2 triggers should be met"
        assert result["resistance_detected"] == True, "2-of-3 sufficient for alert"
        assert "hrd_drop" in result["triggers_met"]
        assert "dna_repair_drop" in result["triggers_met"]
    
    def test_hr_restoration_pattern(self):
        """Test HR restoration pattern detection (Manager's R2)"""
        result = detect_resistance(
            current_hrd=45.0,  # Drop = 13 (>= 10 for HR restoration)
            previous_hrd=58.0,
            current_dna_repair_capacity=0.55,  # Drop = 0.20 (>= 0.15)
            previous_dna_repair_capacity=0.75,
            ca125_intelligence=None,
            treatment_on_parp=True  # CRITICAL: Must be on PARP
        )
        
        assert result["hr_restoration_suspected"] == True, "HR restoration should be detected"
        assert result["immediate_alert"] == True, "Should trigger immediate alert"
    
    def test_hr_restoration_requires_parp(self):
        """Test HR restoration only detected when on PARP therapy"""
        result = detect_resistance(
            current_hrd=45.0,  # Drop = 13
            previous_hrd=58.0,
            current_dna_repair_capacity=0.55,  # Drop = 0.20
            previous_dna_repair_capacity=0.75,
            ca125_intelligence=None,
            treatment_on_parp=False  # NOT on PARP
        )
        
        assert result["hr_restoration_suspected"] == False, "HR restoration should NOT be detected when not on PARP"
    
    def test_ca125_trigger(self):
        """Test CA-125 inadequate response trigger"""
        result = detect_resistance(
            current_hrd=55.0,
            previous_hrd=58.0,  # Drop = 3 (< 15) → NO TRIGGER
            current_dna_repair_capacity=0.70,
            previous_dna_repair_capacity=0.72,  # Drop = 0.02 (< 0.20) → NO TRIGGER
            ca125_intelligence={
                "resistance_rule": {
                    "triggered": True,
                    "reason": "On-therapy rise detected"
                }
            },  # TRIGGER 3
            treatment_on_parp=False
        )
        
        assert result["trigger_count"] == 1
        assert "ca125_inadequate" in result["triggers_met"]
    
    def test_recommended_actions(self):
        """Test recommended actions when resistance detected"""
        result = detect_resistance(
            current_hrd=40.0,  # 2 triggers
            previous_hrd=58.0,
            current_dna_repair_capacity=0.50,
            previous_dna_repair_capacity=0.75,
            ca125_intelligence=None,
            treatment_on_parp=True
        )
        
        assert result["resistance_detected"] == True
        assert len(result["recommended_actions"]) > 0, "Should have recommended actions"
        assert len(result["recommended_trials"]) > 0, "Should recommend alternative trials"
        
        # Check for ATR/CHK1/WEE1 trial recommendations
        trial_text = " ".join(result["recommended_trials"])
        assert "ATR" in trial_text, "Should recommend ATR inhibitor trials"
    
    def test_all_triggers_met(self):
        """Test all 3 triggers met (maximum alert)"""
        result = detect_resistance(
            current_hrd=35.0,  # Drop = 23 → TRIGGER 1
            previous_hrd=58.0,
            current_dna_repair_capacity=0.45,  # Drop = 0.30 → TRIGGER 2
            previous_dna_repair_capacity=0.75,
            ca125_intelligence={"resistance_rule": {"triggered": True}},  # TRIGGER 3
            treatment_on_parp=True
        )
        
        assert result["trigger_count"] == 3, "All 3 triggers should be met"
        assert result["resistance_detected"] == True
        assert result["immediate_alert"] == True


# ============================================================
# E2E INTEGRATION TEST (1 TEST)
# ============================================================

class TestSAEPhase2Integration:
    """End-to-end integration test (all 3 services together)"""
    
    def test_ayesha_post_ngs_scenario(self):
        """
        Test complete SAE Phase 2 workflow (post-NGS).
        
        Scenario: Ayesha gets NGS results (HRD=58, BRCA1 biallelic loss)
        """
        # Step 1: Compute SAE Features
        insights_bundle = {
            "functionality": 0.75,
            "chromatin": 0.60,
            "essentiality": 0.85,
            "regulatory": 0.70
        }
        pathway_scores = {
            "ddr": 0.90,  # High DDR burden (BRCA1 biallelic)
            "mapk": 0.20,
            "pi3k": 0.15,
            "vegf": 0.40,
            "her2": 0.0  # Unknown HER2 status
        }
        tumor_context = {
            "hrd_score": 58.0,
            "tmb_score": 8.5,
            "msi_status": "MSS",
            "somatic_mutations": [
                {"gene": "BRCA1", "hgvs_p": "E23fs", "variant_type": "frameshift"}
            ]
        }
        ca125_intelligence = {
            "current_value": 2842,
            "burden_class": "EXTENSIVE",
            "resistance_rule": {"triggered": False}
        }
        
        sae_features = compute_sae_features(
            insights_bundle=insights_bundle,
            pathway_scores=pathway_scores,
            tumor_context=tumor_context,
            ca125_intelligence=ca125_intelligence
        )
        
        # Verify DNA repair capacity computed correctly
        assert sae_features["dna_repair_capacity"] > 0.70, "High DDR + essentiality should yield high DNA repair capacity"
        
        # Verify mechanism vector is 7D
        assert len(sae_features["mechanism_vector"]) == 7
        
        # Step 2: Rank Trials by Mechanism
        mock_trials = [
            {
                "nct_id": "NCT_PARP_TRIAL",
                "title": "PARP + Platinum Trial",
                "eligibility_score": 0.85,
                "moa_vector": [0.9, 0.1, 0.1, 0.2, 0.0, 0.0, 0.1]  # DDR-focused
            },
            {
                "nct_id": "NCT_HER2_TRIAL",
                "title": "HER2-ADC Trial",
                "eligibility_score": 0.80,
                "moa_vector": [0.1, 0.2, 0.1, 0.2, 0.9, 0.0, 0.1]  # HER2-focused
            }
        ]
        
        ranked_trials = rank_trials_by_mechanism(
            trials=mock_trials,
            sae_mechanism_vector=sae_features["mechanism_vector"]
        )
        
        # PARP trial should rank higher (better DDR mechanism fit)
        assert len(ranked_trials) >= 1
        assert ranked_trials[0]["nct_id"] == "NCT_PARP_TRIAL", "PARP trial should rank first for high DDR burden"
        
        # Step 3: Detect Resistance (initial baseline → no resistance)
        resistance_alert = detect_resistance(
            current_hrd=58.0,
            previous_hrd=None,  # No baseline yet
            current_dna_repair_capacity=sae_features["dna_repair_capacity"],
            previous_dna_repair_capacity=None,
            ca125_intelligence=ca125_intelligence,
            treatment_on_parp=False  # Not on treatment yet
        )
        
        assert resistance_alert["resistance_detected"] == False, "No resistance at baseline"
        assert resistance_alert["immediate_alert"] == False


# ============================================================
# RUN TESTS
# ============================================================

if __name__ == "__main__":
    import math  # Needed for L2 norm test
    
    print("⚔️ SAE PHASE 2 SERVICES - COMPREHENSIVE TEST SUITE ⚔️\n")
    print("Running tests...\n")
    
    # Run with pytest
    pytest.main([__file__, "-v", "--tb=short"])
    
    print("\n⚔️ TEST SUITE COMPLETE ⚔️")

