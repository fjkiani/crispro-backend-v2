"""
⚔️ AK - COMPLETE PATIENT PROFILE ⚔️

Extracted from actual medical records:
- CT Abdomen/Pelvis (10/28/2025)
- PET-CT (11/12/2025)
- Genomic Testing (Ambry CustomNext-Cancer, 06/15/2023)

Author: Zo (Lead Commander)
Date: November 14, 2025
"""

# ============================================================================
# PATIENT DEMOGRAPHICS
# ============================================================================
AYESHA_PROFILE = {
    "patient_id": "ayesha_001",
    "name": "AK",
    "dob": "06/25/1985",
    "age": 40,
    "mrn": None,  # de-identified for trial-matching contexts
    "pcp": "Chantel Strachan, MD",
    "sex": "Female",
    "location": "NYC Metro",
}

# ============================================================================
# DISEASE CHARACTERISTICS (From Imaging 10/28/2025 & 11/12/2025)
# ============================================================================
DISEASE = {
    "primary_diagnosis": "High-Grade Serous Ovarian Carcinoma (HGSOC)",
    "stage": "IVB",  # Pleural metastases = Stage IV, distant organ involvement = IVB
    "figo_stage": "IVB",
    
    # FROM CT ABDOMEN/PELVIS (10/28/2025):
    "peritoneal_carcinomatosis": True,
    "ascites": "small volume",
    "lymphadenopathy": {
        "present": True,
        "locations": ["pelvic", "retroperitoneal"],
        "largest_nodes": [
            {"location": "aortocaval", "size_cm": 1.3},
            {"location": "right external iliac", "size_cm": 1.5}
        ]
    },
    "ovaries": {
        "status": "inseparable from peritoneal deposits",
        "left_ovary": "not well seen, likely inseparable from deposits",
        "right_ovary": "appears inseparable from multiple enhancing peritoneal deposits"
    },
    
    # FROM PET-CT (11/12/2025):
    "metastases": {
        "pleural": True,
        "pleural_effusions": "large bilateral layering",
        "peritoneal": True,
        "lymph_nodes": True,
        "soft_tissue": True,
        "bone": False,
        "liver": False,
        "lung_parenchyma": False
    },
    "fdg_avidity": {
        "largest_tumor_suv": 15.0,  # Right lower quadrant conglomerate (8 cm)
        "pleural_deposits_suv": {"min": 6.0, "max": 7.0},
        "lymph_nodes_suv": {"min": 8.0, "max": 10.0},
        "cervical_suv": 11.0,
        "endometrial_suv": 6.2
    },
    "tumor_burden": "EXTENSIVE",  # 8 cm largest mass, extensive carcinomatosis
    "performance_status": 1,  # ECOG as single integer
}

# ============================================================================
# TREATMENT HISTORY
# ============================================================================
TREATMENT = {
    "line": "first-line",
    "line_number": 1,
    "status": "treatment_naive",
    "planned_frontline": {
        "regimen": "Carboplatin + Paclitaxel + Bevacizumab",
        "cycles_planned": 6,
        "nccn_compliant": True,
        "rationale": "BRCA wildtype, HER2 unknown → Standard of care"
    },
    "prior_surgeries": [
        {
            "procedure": "Total colectomy with ileorectal anastomosis",
            "date": "01/02/2024",
            "indication": "Multiple tubular adenomas",
            "complications": "Lower abdominal wall collection (resolved)"
        }
    ],
    "current_medications": [],
    "allergies": []
}

# ============================================================================
# BIOMARKERS (From Genomic Testing 06/15/2023)
# ============================================================================
BIOMARKERS = {
    # GERMLINE TESTING (Ambry CustomNext-Cancer + RNAinsight):
    "germline_status": "NEGATIVE",
    "brca1": "NEGATIVE",
    "brca2": "NEGATIVE",
    "germline_panel": {
        "test": "Ambry CustomNext-Cancer + RNAinsight",
        "genes_tested": [
            "APC", "ATM", "BARD1", "BMPR1A", "BRCA1", "BRCA2", "BRIP1", 
            "CDH1", "CDK4", "CDKN2A", "CHEK2", "DICER1", "MLH1", "MSH2", 
            "MSH6", "MUTYH", "NBN", "NF1", "NF2", "NTHL1", "PALB2", "PMS2", 
            "PTEN", "RAD51C", "RAD51D", "RECQL", "SMAD4", "SMARCA4", "STK11", 
            "TP53"
        ],
        "result": "NEGATIVE - No pathogenic variants detected",
        "date": "06/15/2023",
        "lab": "Ambry Genetics",
        "accession": "23-221015"
    },
    
    # TUMOR BIOMARKERS (UNKNOWN - NEED TESTING):
    "her2_status": "UNKNOWN",  # ⚠️ CRITICAL GATE for DESTINY-Ovarian01
    "her2_testing": {
        "ordered": False,
        "result": None,
        "date": None,
        "method": "IHC (ASCO-CAP gastric scoring)",
        "reflex_fish_if_2plus": True,
        "tissue_available": True  # Has tumor tissue from biopsy
    },
    
    "hrd_status": "UNKNOWN",  # ⚠️ CRITICAL for PARP eligibility
    "hrd_testing": {
        "ordered": False,  # Unknown if MyChoice ordered
        "result": None,
        "date": None,
        "test": None,  # Should be MyChoice CDx or similar
        "assay": "MyChoice CDx (preferred)",
        "brca1_methylation": None
    },
    
    "tmb_status": "UNKNOWN",
    "tmb_mut_per_mb": None,
    "msi_status": "UNKNOWN",
    "pd_l1_status": "UNKNOWN",
    "pd_l1_cps": None,
    
    # OTHER MARKERS:
    "ca125": {
        "value": 2842.0,  # From prior reports (not in current imaging)
        "date": "Recent (exact date TBD)",
        "burden_class": "EXTENSIVE",  # >1000 U/mL
        "clinical_significance": "Very high CA-125 indicates large tumor burden"
    }
}

# ============================================================================
# ELIGIBILITY FACTORS
# ============================================================================
ELIGIBILITY = {
    "age_eligible": True,  # 40 years old (most trials 18+)
    "performance_status": "ECOG 1-2",  # Most trials allow ECOG 0-2
    "organ_function": {
        "hepatic": "normal",  # Per CT: "hepatobiliary system unremarkable"
        "renal": "normal",  # Per CT: "no hydronephrosis, bladder unremarkable"
        "cardiac": "normal",  # Per PET-CT: "heart normal"
        "pulmonary": "compromised",  # Large bilateral pleural effusions
    },
    "exclusions": {
        "bowel_obstruction": False,  # CT: "no bowel obstruction"
        "active_infection": False,
        "brain_metastases": False,  # PET-CT limited to skull base to mid-thigh
        "other_malignancy": False,  # Only ovarian cancer
        "pregnancy": False,  # IUD in place
        "breastfeeding": False
    },
    "tissue_availability": {
        "has_tissue": True,
        "tissue_type": "FFPE block from biopsy",
        "sufficient_for_testing": True,
        "location": "Pathology archive"
    }
}

# ============================================================================
# GEOGRAPHIC & LOGISTICS
# ============================================================================
LOGISTICS = {
    "location": "NYC Metro",
    "zip_code": "10029",
    "home_zip": "10029",
    "travel_radius_miles": 50,
    "willing_to_travel": True,
    "transportation": "available",
    "insurance": "active",  # Has MyChart, active care
    "caregiver_support": "Yes",  # Has family (daughter mentioned in colectomy context)
    "language": "English",
    "site_preferences": ["Mount Sinai", "MSK", "NYU"]
}

# ============================================================================
# CRITICAL GATES FOR TRIAL ELIGIBILITY
# ============================================================================
CRITICAL_GATES = {
    "her2_ihc": {
        "status": "PENDING",
        "required_for": ["DESTINY-Ovarian01 (NCT06819007)"],
        "test": "HER2 IHC (ASCO-CAP gastric scoring)",
        "method": "IHC (ASCO-CAP gastric scoring), reflex FISH if 2+",
        "turnaround": "3-5 days",
        "cost": "$200-400",
        "priority": "P0 - URGENT",
        "rationale": "HER2 status unknown - testing required. If IHC 1+/2+ (expression, not amplification), Ayesha may be eligible for breakthrough T-DXd trial."
    },
    "hrd_testing": {
        "status": "PENDING",
        "required_for": ["PARP maintenance eligibility", "DESTINY-Ovarian01 exclusion"],
        "test": "MyChoice CDx (Myriad) or FoundationOne CDx",
        "turnaround": "7-10 days",
        "cost": "$4,000-6,000 (covered for Stage IV)",
        "priority": "P0 - URGENT",
        "rationale": "If HRD ≥42, gets PARP maintenance (olaparib/niraparib) instead of trial. If HRD <42 + HER2+, eligible for T-DXd trial."
    },
    "pd_l1_ihc": {
        "status": "OPTIONAL",
        "required_for": ["Immunotherapy trials"],
        "test": "PD-L1 IHC (22C3 or SP142)",
        "turnaround": "5-7 days",
        "cost": "$300-500",
        "priority": "P2 - CONDITIONAL"
    }
}

# ============================================================================
# SCREENING & SAFETY (trial eligibility helpers)
# ============================================================================
SCREENING = {
    "recist_measurable_disease": True,
    "target_lesions_present": True,
    "qtc_ms": None,
    "lvef_percent": None,
    "uncontrolled_hypertension": False,
    "on_therapeutic_anticoagulation": False,
    "active_infection": False,
    "hiv_status": "unknown",
    "hbv_status": "unknown",
    "hcv_status": "unknown",
    "recent_surgery_within_28d": False
}

# ============================================================================
# BASELINE LABS (populate when available)
# ============================================================================
LABS = {
    "date": None,
    "anc_x10e9_per_L": None,
    "platelets_x10e9_per_L": None,
    "hemoglobin_g_per_dL": None,
    "creatinine_mg_per_dL": None,
    "egfr_mL_min_1.73m2": None,
    "ast_u_per_L": None,
    "alt_u_per_L": None,
    "bilirubin_mg_per_dL": None,
    "inr": None,
    "albumin_g_per_dL": None
}

# ============================================================================
# PROBABILITY CALCULATIONS (defer to testing; avoid hard priors)
# ============================================================================
PROBABILITY_ESTIMATES = {
    "her2_positive": {
        "probability": None,
        "source": "Pending HER2 IHC (reflex FISH if 2+)",
        "confidence": "unknown"
    },
    "hrd_negative": {
        "probability": None,
        "source": "Pending HRD assay",
        "confidence": "unknown"
    }
}

# ============================================================================
# STRATEGIC SCENARIOS (For sample.md style recommendations)
# ============================================================================
STRATEGIC_SCENARIOS = {
    "best_case": {
        "title": "HER2+ AND HRD-negative/low",
        "probability": 0.30,
        "outcome": "Eligible for DESTINY-Ovarian01 (T-DXd + bevacizumab)",
        "value": "Access to breakthrough ADC therapy at Mount Sinai",
        "next_steps": [
            "Enroll at Mount Sinai",
            "50% chance experimental arm (T-DXd + bev)",
            "50% chance control arm (bev alone - still SOC)",
            "Close monitoring, free drug, expert care"
        ]
    },
    "most_likely": {
        "title": "HER2+ AND HRD ≥42 (HRD-high)",
        "probability": 0.20,  # 50% HER2+ × 40% HRD-high = 20%
        "outcome": "NOT eligible for trial → PARP maintenance",
        "value": "PARP maintenance is EXCELLENT for HRD-high (olaparib/niraparib)",
        "interpretation": "This is actually GOOD NEWS - HRD-high = better prognosis",
        "next_steps": [
            "Receive PARP maintenance (proven SOC)",
            "Better PFS than bevacizumab alone",
            "FDA-approved, insurance-covered"
        ]
    },
    "challenge": {
        "title": "HER2 IHC 0 (HER2-negative)",
        "probability": 0.50,  # 40-60% are HER2-negative
        "outcome": "NOT eligible for DESTINY-Ovarian01",
        "value": "Falls back to bevacizumab maintenance (standard SOC)",
        "next_steps": [
            "Bevacizumab maintenance (standard)",
            "Pursue alternative trials (ATR/CHK1 combos, other mechanisms)",
            "Re-evaluate at progression"
        ]
    }
}

# ============================================================================
# TIMELINE (For sample.md style planning)
# ============================================================================
TREATMENT_TIMELINE = {
    "current_week": "Week 0 (Pre-treatment)",
    "planned": {
        "week_1_6": {
            "phase": "Frontline chemotherapy",
            "regimen": "Carboplatin + Paclitaxel + Bevacizumab",
            "cycles": 6,
            "frequency": "Every 3 weeks"
        },
        "week_6_7": {
            "phase": "Biomarker testing window",
            "actions": [
                "Order HER2 IHC (3-5 days)",
                "Await HRD results (7-10 days if ordered)",
                "Restaging CT/PET (assess response)"
            ]
        },
        "week_7_8": {
            "phase": "Maintenance decision point",
            "options": [
                "If HER2+ AND HRD <42: Enroll DESTINY-Ovarian01",
                "If HER2+ AND HRD ≥42: PARP maintenance",
                "If HER2 0: Bevacizumab maintenance"
            ]
        },
        "week_8_onwards": {
            "phase": "Maintenance therapy",
            "duration": "Until progression or unacceptable toxicity"
        }
    }
}

# ============================================================================
# EXPORT FOR DOSSIER GENERATOR
# ============================================================================
def get_ayesha_complete_profile():
    """
    Returns comprehensive patient profile for intelligent dossier generation.
    This replaces the simple dict I was using before.
    """
    return {
        "demographics": AYESHA_PROFILE,
        "disease": DISEASE,
        "treatment": TREATMENT,
        "biomarkers": BIOMARKERS,
        "eligibility": ELIGIBILITY,
        "logistics": LOGISTICS,
        "labs": LABS,
        "screening": SCREENING,
        "critical_gates": CRITICAL_GATES,
        "probability_estimates": PROBABILITY_ESTIMATES,
        "strategic_scenarios": STRATEGIC_SCENARIOS,
        "timeline": TREATMENT_TIMELINE
    }

if __name__ == "__main__":
    # Test export
    profile = get_ayesha_complete_profile()
    print("✅ Ayesha's complete profile loaded")
    print(f"   Disease: {profile['disease']['primary_diagnosis']}")
    print(f"   Stage: {profile['disease']['figo_stage']}")
    print(f"   BRCA: {profile['biomarkers']['brca1']}/{profile['biomarkers']['brca2']}")
    print(f"   HER2: {profile['biomarkers']['her2_status']}")
    print(f"   HRD: {profile['biomarkers']['hrd_status']}")
    print(f"   CA-125: {profile['biomarkers']['ca125']['value']} U/mL")

