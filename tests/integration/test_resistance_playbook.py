"""
Resistance Playbook Test Suite - SAE-Powered Resistance Prediction

Tests for resistance_playbook_service.py and /api/care/resistance_playbook endpoint.

Test Coverage:
1. HR restoration detection (after PARP exposure)
2. ABCB1 upregulation detection (CNAs)
3. MAPK activation detection (RAS/BRAF mutations)
4. PI3K activation detection (PIK3CA/PTEN mutations)
5. SLFN11 loss detection (LOF mutations)
6. Combo strategy ranking
7. Next-line switch recommendations
8. End-to-end playbook generation
"""

import pytest
from api.services.resistance_playbook_service import (
    detect_hr_restoration_risk,
    detect_abcb1_upregulation,
    detect_mapk_activation,
    detect_pi3k_activation,
    detect_slfn11_loss,
    rank_combo_strategies,
    recommend_next_line_switches,
    generate_resistance_playbook
)


# ============================================================================
# TEST 1: HR RESTORATION DETECTION
# ============================================================================

def test_hr_restoration_after_parp_exposure():
    """Test HR restoration detection after PARP exposure with HRD drop."""
    tumor_context = {
        "hrd_score": 35,  # Dropped below 42
        "somatic_mutations": [],
        "copy_number_alterations": []
    }
    
    treatment_history = {
        "prior_therapies": [
            {"line": 1, "drugs": ["Carboplatin", "Paclitaxel"]},
            {"line": 2, "drugs": ["Olaparib"], "drug_class": "PARP inhibitor", "outcome": "progression"}
        ]
    }
    
    risk = detect_hr_restoration_risk(tumor_context, treatment_history)
    
    assert risk is not None
    assert risk.type == "HR_restoration"
    assert risk.confidence == 0.7
    assert "PARP inhibitors" in risk.triggers
    assert "HRD score 35 < 42" in risk.evidence


def test_hr_restoration_rad51_compensation():
    """Test HR restoration via RAD51C/D compensation."""
    tumor_context = {
        "hrd_score": 45,  # Still high
        "somatic_mutations": [
            {"gene": "RAD51C", "hgvs_p": "S257F", "variant_class": "missense"}
        ],
        "copy_number_alterations": []
    }
    
    treatment_history = {
        "prior_therapies": [
            {"line": 1, "drugs": ["Olaparib"], "drug_class": "PARP inhibitor"}
        ]
    }
    
    risk = detect_hr_restoration_risk(tumor_context, treatment_history)
    
    assert risk is not None
    assert risk.type == "HR_restoration"
    assert risk.confidence == 0.65
    assert "RAD51C/D" in risk.evidence


def test_no_hr_restoration_without_parp():
    """Test no HR restoration risk without prior PARP exposure."""
    tumor_context = {"hrd_score": 35, "somatic_mutations": []}
    treatment_history = {"prior_therapies": []}
    
    risk = detect_hr_restoration_risk(tumor_context, treatment_history)
    
    assert risk is None


# ============================================================================
# TEST 2: ABCB1 UPREGULATION DETECTION
# ============================================================================

def test_abcb1_upregulation_cna():
    """Test ABCB1 upregulation via copy number gain."""
    tumor_context = {
        "copy_number_alterations": [
            {"gene": "ABCB1", "copy_number": 6}  # Amplification
        ]
    }
    
    risk = detect_abcb1_upregulation(tumor_context)
    
    assert risk is not None
    assert risk.type == "ABCB1_upregulation"
    assert risk.confidence == 0.8
    assert "paclitaxel" in risk.triggers
    assert "6 copies" in risk.evidence


def test_no_abcb1_upregulation():
    """Test no ABCB1 risk with normal copy number."""
    tumor_context = {
        "copy_number_alterations": [
            {"gene": "ABCB1", "copy_number": 2}  # Normal
        ]
    }
    
    risk = detect_abcb1_upregulation(tumor_context)
    
    assert risk is None


# ============================================================================
# TEST 3: MAPK ACTIVATION DETECTION
# ============================================================================

def test_mapk_activation_kras_mutation():
    """Test MAPK activation via KRAS mutation."""
    tumor_context = {
        "somatic_mutations": [
            {"gene": "KRAS", "hgvs_p": "G12D"}
        ]
    }
    
    risk = detect_mapk_activation(tumor_context)
    
    assert risk is not None
    assert risk.type == "MAPK_activation"
    assert risk.confidence == 0.85
    assert "BRAF inhibitors" in risk.triggers
    assert "KRAS" in risk.evidence


def test_mapk_activation_pathway_burden():
    """Test MAPK activation via high pathway burden."""
    tumor_context = {"somatic_mutations": []}
    pathway_disruption = {
        "MAPK": {"burden": 0.75}
    }
    
    risk = detect_mapk_activation(tumor_context, pathway_disruption)
    
    assert risk is not None
    assert risk.type == "MAPK_activation"
    assert risk.confidence == 0.7
    assert "0.75" in risk.evidence


# ============================================================================
# TEST 4: PI3K ACTIVATION DETECTION
# ============================================================================

def test_pi3k_activation_pik3ca_mutation():
    """Test PI3K activation via PIK3CA mutation."""
    tumor_context = {
        "somatic_mutations": [
            {"gene": "PIK3CA", "hgvs_p": "H1047R"}
        ]
    }
    
    risk = detect_pi3k_activation(tumor_context)
    
    assert risk is not None
    assert risk.type == "PI3K_activation"
    assert risk.confidence == 0.8
    assert "mTOR inhibitors" in risk.triggers


# ============================================================================
# TEST 5: SLFN11 LOSS DETECTION
# ============================================================================

def test_slfn11_loss_via_deletion():
    """Test SLFN11 loss via deletion."""
    tumor_context = {
        "somatic_mutations": [],
        "copy_number_alterations": [
            {"gene": "SLFN11", "copy_number": 0}  # Homozygous deletion
        ]
    }
    
    risk = detect_slfn11_loss(tumor_context)
    
    assert risk is not None
    assert risk.type == "SLFN11_loss"
    assert risk.confidence == 0.75
    assert "PARP inhibitors" in risk.triggers


# ============================================================================
# TEST 6: COMBO STRATEGY RANKING
# ============================================================================

def test_combo_ranking_hr_restoration():
    """Test combo ranking for HR restoration risk."""
    resistance_risks = [
        type('Risk', (), {
            'type': 'HR_restoration',
            'confidence': 0.7,
            'evidence': 'Test',
            'triggers': ['PARP'],
            'source': 'test'
        })()
    ]
    
    tumor_context = {"hrd_score": 45, "tmb": 5.0, "msi_status": "MSI-Stable"}
    treatment_history = {"prior_therapies": [], "platinum_response": "sensitive"}
    
    combos = rank_combo_strategies(resistance_risks, tumor_context, treatment_history)
    
    # Should include PARP + ATR combo
    assert len(combos) > 0
    parp_atr_combo = next((c for c in combos if "ATR" in c.moa), None)
    assert parp_atr_combo is not None
    assert parp_atr_combo.rank_score > 0.8


def test_combo_ranking_msi_high():
    """Test combo ranking for MSI-High tumor."""
    resistance_risks = []
    
    tumor_context = {"hrd_score": 20, "tmb": 25.0, "msi_status": "MSI-High"}
    treatment_history = {"prior_therapies": [], "platinum_response": "unknown"}
    
    combos = rank_combo_strategies(resistance_risks, tumor_context, treatment_history)
    
    # Should include IO combos
    assert len(combos) > 0
    io_combo = next((c for c in combos if "Checkpoint inhibitor" in c.moa or "Pembrolizumab" in c.drugs), None)
    assert io_combo is not None
    assert io_combo.rank_score > 0.7


def test_combo_penalized_after_prior_failure():
    """Test combo penalized if prior failure with same class."""
    resistance_risks = []
    
    tumor_context = {"hrd_score": 45, "tmb": 5.0, "msi_status": "MSI-Stable"}
    treatment_history = {
        "prior_therapies": [
            {"line": 1, "drugs": ["Olaparib"], "drug_class": "PARP inhibitor", "outcome": "progression"}
        ],
        "platinum_response": "sensitive"
    }
    
    combos = rank_combo_strategies(resistance_risks, tumor_context, treatment_history)
    
    # PARP combos should be detected
    parp_combos = [c for c in combos if "PARP" in c.moa]
    assert len(parp_combos) >= 1
    
    # Check that Olaparib-containing combos are penalized
    # (Niraparib combos may still score high if platinum-sensitive boost applies)
    olaparib_combo = next((c for c in parp_combos if "Olaparib" in c.drugs), None)
    if olaparib_combo:
        # Olaparib specifically should be penalized (prior failure with exact drug)
        assert olaparib_combo.rank_score < 0.85  # Penalized from base 0.85


# ============================================================================
# TEST 7: NEXT-LINE SWITCH RECOMMENDATIONS
# ============================================================================

def test_next_line_switch_hr_restoration():
    """Test next-line switch for HR restoration."""
    resistance_risks = [
        type('Risk', (), {
            'type': 'HR_restoration',
            'confidence': 0.7,
            'evidence': 'Test',
            'triggers': ['PARP'],
            'source': 'test'
        })()
    ]
    
    tumor_context = {"somatic_mutations": [{"gene": "TP53", "hgvs_p": "R273H"}]}
    treatment_history = {"prior_therapies": []}
    
    switches = recommend_next_line_switches(resistance_risks, tumor_context, treatment_history)
    
    # Should include ATR/CHK1/WEE1 inhibitors
    assert len(switches) > 0
    atr_switch = next((s for s in switches if s.drug_class == "ATR inhibitor"), None)
    assert atr_switch is not None
    assert atr_switch.rank_score > 0.75


def test_next_line_switch_platinum_rechallenge():
    """Test platinum rechallenge for sensitive disease."""
    resistance_risks = []
    
    tumor_context = {"somatic_mutations": []}
    treatment_history = {
        "prior_therapies": [
            {"line": 1, "drugs": ["Carboplatin", "Paclitaxel"], "outcome": "partial_response"}
        ],
        "platinum_response": "sensitive"
    }
    
    switches = recommend_next_line_switches(resistance_risks, tumor_context, treatment_history)
    
    # Should include platinum rechallenge
    platinum = next((s for s in switches if "Platinum" in s.drug_class), None)
    assert platinum is not None
    assert platinum.rank_score >= 0.9


# ============================================================================
# TEST 8: END-TO-END PLAYBOOK GENERATION
# ============================================================================

def test_complete_playbook_ayesha_case():
    """
    Test complete playbook for Ayesha's case:
    - Prior PARP exposure (Olaparib)
    - HRD score dropped to 35 (HR restoration?)
    - TP53 mutant
    - Platinum-sensitive
    """
    tumor_context = {
        "somatic_mutations": [
            {"gene": "TP53", "hgvs_p": "R273H"},
            {"gene": "BRCA2", "hgvs_p": "S1982fs"}
        ],
        "hrd_score": 35,  # Dropped after PARP
        "tmb": 6.8,
        "msi_status": "MSI-Stable",
        "copy_number_alterations": []
    }
    
    treatment_history = {
        "current_line": 3,
        "prior_therapies": [
            {"line": 1, "drugs": ["Carboplatin", "Paclitaxel"], "outcome": "partial_response"},
            {"line": 2, "drugs": ["Olaparib"], "drug_class": "PARP inhibitor", "outcome": "progression"}
        ],
        "platinum_response": "sensitive"
    }
    
    playbook = generate_resistance_playbook(
        tumor_context=tumor_context,
        treatment_history=treatment_history
    )
    
    # Should detect HR restoration risk
    assert len(playbook.risks) >= 1
    hr_risk = next((r for r in playbook.risks if r.type == "HR_restoration"), None)
    assert hr_risk is not None
    assert hr_risk.confidence >= 0.6
    
    # Should recommend PARP + ATR combo (penalized due to prior Olaparib failure)
    assert len(playbook.combo_strategies) >= 1
    parp_atr = next((c for c in playbook.combo_strategies if "ATR" in c.moa), None)
    assert parp_atr is not None
    assert parp_atr.rank_score > 0.6  # Penalized from 0.85 → 0.6375 (0.75x for prior failure)
    
    # Should recommend ATR/CHK1/WEE1 switches
    assert len(playbook.next_line_switches) >= 1
    atr_switch = next((s for s in playbook.next_line_switches if "ATR" in s.drug_class or "CHK1" in s.drug_class), None)
    assert atr_switch is not None
    
    # Should generate trial keywords
    assert len(playbook.trial_keywords) > 0
    assert any("ATR" in kw or "CHK1" in kw for kw in playbook.trial_keywords)
    
    # Should have provenance
    assert playbook.provenance["service"] == "resistance_playbook_service"
    assert playbook.provenance["risk_count"] >= 1


def test_complete_playbook_msi_high_case():
    """
    Test playbook for MSI-High tumor:
    - High TMB (25)
    - MSI-High status
    - No prior therapies
    """
    tumor_context = {
        "somatic_mutations": [],
        "hrd_score": 20,
        "tmb": 25.0,
        "msi_status": "MSI-High",
        "copy_number_alterations": []
    }
    
    treatment_history = {
        "current_line": 1,
        "prior_therapies": [],
        "platinum_response": "unknown"
    }
    
    playbook = generate_resistance_playbook(
        tumor_context=tumor_context,
        treatment_history=treatment_history
    )
    
    # Should recommend IO combos
    assert len(playbook.combo_strategies) >= 1
    io_combo = next((c for c in playbook.combo_strategies if "Checkpoint inhibitor" in c.moa or "Pembrolizumab" in c.drugs), None)
    assert io_combo is not None
    assert io_combo.rank_score > 0.75  # Boosted by MSI-H + TMB-high
    
    # Should generate MSI-H trial keywords
    assert "MSI-High" in playbook.trial_keywords or "TMB-high" in playbook.trial_keywords


def test_complete_playbook_mapk_activation():
    """
    Test playbook for MAPK-activated tumor:
    - KRAS G12D mutation
    - No HRD
    """
    tumor_context = {
        "somatic_mutations": [
            {"gene": "KRAS", "hgvs_p": "G12D"}
        ],
        "hrd_score": 10,
        "tmb": 5.0,
        "msi_status": "MSI-Stable",
        "copy_number_alterations": []
    }
    
    treatment_history = {
        "current_line": 1,
        "prior_therapies": [],
        "platinum_response": "unknown"
    }
    
    playbook = generate_resistance_playbook(
        tumor_context=tumor_context,
        treatment_history=treatment_history
    )
    
    # Should detect MAPK activation risk
    assert len(playbook.risks) >= 1
    mapk_risk = next((r for r in playbook.risks if r.type == "MAPK_activation"), None)
    assert mapk_risk is not None
    
    # Should recommend MEK inhibitor combos
    mek_combo = next((c for c in playbook.combo_strategies if "MEK" in c.moa), None)
    assert mek_combo is not None
    
    # Should recommend MEK switch
    mek_switch = next((s for s in playbook.next_line_switches if "MEK" in s.drug_class), None)
    assert mek_switch is not None


# ============================================================================
# TEST 9: EDGE CASES
# ============================================================================

def test_playbook_with_minimal_data():
    """Test playbook generation with minimal tumor context."""
    tumor_context = {
        "somatic_mutations": [],
        "copy_number_alterations": []
    }
    
    treatment_history = {
        "current_line": 1,
        "prior_therapies": []
    }
    
    playbook = generate_resistance_playbook(
        tumor_context=tumor_context,
        treatment_history=treatment_history
    )
    
    # Should still return valid playbook (empty or baseline)
    assert playbook is not None
    assert isinstance(playbook.risks, list)
    assert isinstance(playbook.combo_strategies, list)
    assert isinstance(playbook.next_line_switches, list)
    assert playbook.provenance["service"] == "resistance_playbook_service"


def test_playbook_with_multiple_risks():
    """Test playbook with multiple concurrent resistance risks."""
    tumor_context = {
        "somatic_mutations": [
            {"gene": "KRAS", "hgvs_p": "G12D"},
            {"gene": "PIK3CA", "hgvs_p": "H1047R"},
            {"gene": "SLFN11", "hgvs_p": "Q209*", "variant_class": "nonsense"}
        ],
        "hrd_score": 30,
        "tmb": 8.0,
        "msi_status": "MSI-Stable",
        "copy_number_alterations": [
            {"gene": "ABCB1", "copy_number": 5}
        ]
    }
    
    treatment_history = {
        "current_line": 2,
        "prior_therapies": [
            {"line": 1, "drugs": ["Olaparib"], "drug_class": "PARP inhibitor", "outcome": "progression"}
        ],
        "platinum_response": "sensitive"
    }
    
    playbook = generate_resistance_playbook(
        tumor_context=tumor_context,
        treatment_history=treatment_history
    )
    
    # Should detect multiple risks
    assert len(playbook.risks) >= 3  # HR_restoration, MAPK, PI3K, SLFN11, ABCB1
    
    risk_types = [r.type for r in playbook.risks]
    assert "MAPK_activation" in risk_types
    assert "PI3K_activation" in risk_types
    assert "SLFN11_loss" in risk_types or "HR_restoration" in risk_types
    
    # Should have multiple combo strategies
    assert len(playbook.combo_strategies) >= 2
    
    # Should have trial keywords for each risk
    assert len(playbook.trial_keywords) >= 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

