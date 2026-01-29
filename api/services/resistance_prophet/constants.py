"""
Resistance Prophet Constants
Static dictionaries, thresholds, and configuration.
Externalized Intelligence for the Resistance Prophet.
"""

from enum import Enum
from api.services.resistance_prophet.schemas import ResistanceRiskLevel


class EvidenceLevel(str, Enum):
    """
    Evidence strength bucket for playbook recommendations.

    NOTE: This is used by `resistance_playbook_service.py` and intentionally lives
    in constants to avoid pulling full service code into schemas.
    """
    VALIDATED = "VALIDATED"                 # validated on cohort data (receipts)
    STANDARD_OF_CARE = "STANDARD_OF_CARE"   # guideline / on-label standard
    CLINICAL_TRIAL = "CLINICAL_TRIAL"       # trial-supported recommendation
    LITERATURE_BASED = "LITERATURE_BASED"   # mechanistically plausible from literature
    EXPERT_OPINION = "EXPERT_OPINION"       # heuristic / low confidence

# ============================================================================
# THRESHOLDS & CONFIG
# ============================================================================
DNA_REPAIR_THRESHOLD = 0.15      # Restoration detected if capacity increases >15%
PATHWAY_ESCAPE_THRESHOLD = 0.15  # Escape detected if target burden drops >15%

HIGH_RISK_PROBABILITY = 0.70
MEDIUM_RISK_PROBABILITY = 0.50
MIN_SIGNALS_FOR_HIGH = 2

# Reliability Weights (Missing Data Policy)
WEIGHT_PATIENT_BASELINE = 1.0
WEIGHT_POPULATION_BASELINE = 0.2

# Pathway Contribution Weights (Formula C1)
PATHWAY_CONTRIBUTIONS = {
    "ddr": 0.60,
    "hrr": 0.20,
    "exon": 0.20
}

PATHWAY_NAMES = ["DDR", "MAPK", "PI3K", "VEGF", "HER2", "IO", "Efflux"]

# ============================================================================
# KNOWLEDGE BASE: DRUG TARGETS
# ============================================================================
DRUG_PATHWAY_TARGETS = {
    "parp_inhibitor": ["DDR"],
    "parp": ["DDR"],
    "atr_inhibitor": ["DDR"],
    "atm_inhibitor": ["DDR"],
    "checkpoint_inhibitor": ["IO"],
    "pd1_inhibitor": ["IO"],
    "pdl1_inhibitor": ["IO"],
    "vegf_inhibitor": ["VEGF"],
    "bevacizumab": ["VEGF"],
    "her2_inhibitor": ["HER2"],
    "trastuzumab": ["HER2"],
    "mek_inhibitor": ["MAPK"],
    "pi3k_inhibitor": ["PI3K"],
    "platinum": ["DDR"],
    # MM Classes
    "proteasome_inhibitor": ["PROTEASOME"],
    "pi": ["PROTEASOME"],
    "bortezomib": ["PROTEASOME"],
    "carfilzomib": ["PROTEASOME"],
    "ixazomib": ["PROTEASOME"],
    "imid": ["CEREBLON"],
    "lenalidomide": ["CEREBLON"],
    "pomalidomide": ["CEREBLON"],
    "thalidomide": ["CEREBLON"],
    "anti_cd38": ["CD38"],
    "daratumumab": ["CD38"],
    "isatuximab": ["CD38"],
}

# ============================================================================
# KNOWLEDGE BASE: MULTIPLE MYELOMA
# ============================================================================
MM_HIGH_RISK_GENES = {
    "DIS3": {
        "effect": "RESISTANCE",
        "relative_risk": 2.08,
        "p_value": 0.0145,
        "confidence": 0.95,
        "validation_source": "MMRF_CoMMpass_GDC",
        "n_mutated": 38,
        "mechanism": "RNA surveillance deficiency",
        "drug_classes_affected": ["proteasome_inhibitor", "imid"],
        "rationale": "DIS3 loss-of-function impairs RNA quality control, associated with 2x mortality risk"
    },
    "TP53": {
        "effect": "RESISTANCE",
        "relative_risk": 1.90,
        "p_value": 0.11,
        "confidence": 0.75,
        "validation_source": "MMRF_CoMMpass_GDC",
        "n_mutated": 16,
        "mechanism": "Genomic instability, therapy resistance",
        "drug_classes_affected": ["proteasome_inhibitor", "imid", "anti_cd38"],
        "rationale": "TP53 mutations confer genomic instability and multi-drug resistance"
    },
    "KRAS": {
        "effect": "RESISTANCE",
        "relative_risk": 0.93,
        "p_value": 0.87,
        "confidence": 0.0,
        "validation_source": "MMRF_CoMMpass_GDC",
        "mechanism": "MAPK pathway activation",
        "drug_classes_affected": [],
        "rationale": "KRAS mutations do not predict mortality in MM (no validated signal)"
    },
    "NRAS": {
        "effect": "RESISTANCE",
        "relative_risk": 0.93,
        "p_value": 0.87,
        "confidence": 0.0,
        "validation_source": "MMRF_CoMMpass_GDC",
        "mechanism": "MAPK pathway activation",
        "drug_classes_affected": [],
        "rationale": "NRAS mutations do not predict mortality in MM (no validated signal)"
    },
    "NFE2L2": {
        "effect": "RESISTANCE",
        "relative_risk": None,
        "confidence": 0.50,
        "validation_source": "PMC4636955",
        "mechanism": "NRF2 activation → antioxidant response → PI resistance",
        "drug_classes_affected": ["proteasome_inhibitor"],
        "rationale": "NFE2L2/NRF2 upregulates antioxidant genes, counteracting PI-induced oxidative stress"
    },
    "XBP1": {
        "effect": "RESISTANCE",
        "relative_risk": None,
        "confidence": 0.50,
        "validation_source": "Literature",
        "mechanism": "XBP1 is critical for UPR",
        "drug_classes_affected": ["proteasome_inhibitor"],
        "rationale": "XBP1 alterations affect unfolded protein response"
    },
    "IRE1": {
        "effect": "RESISTANCE",
        "relative_risk": None,
        "confidence": 0.50,
        "validation_source": "Literature",
        "mechanism": "IRE1/XBP1 pathway alterations affect UPR",
        "drug_classes_affected": ["proteasome_inhibitor"],
        "rationale": "IRE1 (ERN1) activates XBP1, critical for PI response"
    }
}

# ============================================================================
# KNOWLEDGE BASE: OVARIAN CANCER
# ============================================================================
OV_HIGH_RISK_GENES = {
    "MBD4": {
        "effect": "SENSITIVITY",
        "relative_risk": None,
        "confidence": 0.80,
        "validation_source": "Zeta_Protocol_Inference",
        "mechanism": "BER deficiency → PARP trapping",
        "drug_classes_affected": ["participates_in_synthetic_lethality"],
        "rationale": "MBD4 loss confers PARP sensitivity; Reversion confers resistance"
    },
    "BRCA1": {
        "effect": "SENSITIVITY",
        "relative_risk": None,
        "confidence": 0.95,
        "validation_source": "NCCN_Guidelines",
        "mechanism": "HRD → PARP sensitivity",
        "drug_classes_affected": ["parp_inhibitor", "platinum"],
        "rationale": "Classic HRD marker"
    },
    "BRCA2": {
        "effect": "SENSITIVITY",
        "relative_risk": None,
        "confidence": 0.95,
        "validation_source": "NCCN_Guidelines",
        "mechanism": "HRD → PARP sensitivity",
        "drug_classes_affected": ["parp_inhibitor", "platinum"],
        "rationale": "Classic HRD marker"
    },
    "NF1": {
        "effect": "RESISTANCE",
        "relative_risk": 2.10,
        "confidence": 0.90,
        "validation_source": "TCGA_OV_469",
        "mechanism": "MAPK pathway activation → platinum resistance",
        "drug_classes_affected": ["platinum"],
        "rationale": "NF1 loss activates MAPK, bypassing platinum-induced DDR"
    },
    "TP53BP1": {
        "effect": "RESISTANCE",
        "relative_risk": 2.50,
        "confidence": 0.85,
        "validation_source": "Lin_et_al_2019",
        "mechanism": "HR Restoration (NHEJ suppression loss)",
        "drug_classes_affected": ["parp_inhibitor"],
        "rationale": "53BP1 loss restores HR in BRCA-deficient cells, causing PARP resistance"
    },
    "CCNE1": {
        "effect": "RESISTANCE",
        "relative_risk": 2.20,
        "confidence": 0.90,
        "validation_source": "ARIEL3_Feedback",
        "mechanism": "Replication Stress / HR Proficient",
        "drug_classes_affected": ["parp_inhibitor", "platinum"],
        "rationale": "CCNE1 amplification drives replication stress and correlates with poor PARP response"
    },
    "RAD51C": {
         "effect": "SENSITIVITY",
         "relative_risk": None,
         "confidence": 0.95,
         "validation_source": "ARIEL3",
         "mechanism": "HRD",
         "drug_classes_affected": ["parp_inhibitor"],
         "rationale": "RAD51C mutations confer deep PARP sensitivity (ARIEL3)"
    },
    "RAD51D": {
         "effect": "SENSITIVITY",
         "relative_risk": None,
         "confidence": 0.95,
         "validation_source": "ARIEL3",
         "mechanism": "HRD",
         "drug_classes_affected": ["parp_inhibitor"],
         "rationale": "RAD51D mutations confer deep PARP sensitivity (ARIEL3)"
    }
}

MM_CYTOGENETICS = {
    "del_17p": {
        "genes": ["TP53"],
        "hazard_ratio": 2.5,
        "interpretation": "ULTRA_HIGH_RISK",
        "mechanism": "TP53 loss → genomic instability",
        "rationale": "del(17p) is universally associated with poor prognosis in MM"
    },
    "t_4_14": {
        "genes": ["FGFR3", "MMSET"],
        "hazard_ratio": 1.8,
        "interpretation": "HIGH_RISK",
        "mechanism": "FGFR3 activation → aggressive biology",
        "rationale": "t(4;14) patients may benefit from bortezomib-based therapy"
    },
    "1q_gain": {
        "genes": ["CKS1B", "MCL1"],
        "hazard_ratio": 1.5,
        "interpretation": "HIGH_RISK",
        "mechanism": "MCL1 amplification → anti-apoptotic",
        "rationale": "1q gain is associated with shorter PFS/OS"
    },
    "t_11_14": {
        "genes": ["CCND1"],
        "hazard_ratio": 0.8,
        "interpretation": "STANDARD_RISK_VENETOCLAX_SENSITIVE",
        "mechanism": "Cyclin D1 overexpression → BCL2 dependent",
        "rationale": "t(11;14) patients are venetoclax-sensitive"
    }
}

MM_RESISTANCE_MUTATIONS = {
    "proteasome_inhibitor": {
        "PSMB5": {
            "relative_risk": 5.0,
            "mutations": ["G322", "M45", "C52", "A49", "A108", "T31"],
            "mechanism": "Mutations in PI binding pocket",
            "evidence_level": "LITERATURE_ONLY"
        }
    },
    "imid": {
        "CRBN": {
            "relative_risk": 4.0,
            "mutations": ["Y384", "C391", "W386", "H378"],
            "mechanism": "IMiD binding pocket mutations",
            "evidence_level": "LITERATURE_ONLY"
        },
        "IRF4": {
            "relative_risk": 3.0,
            "mutations": ["deletion", "low_expression"],
            "mechanism": "Loss of essential IMiD transcription factor",
            "evidence_level": "LITERATURE_ONLY"
        }
    },
    "anti_cd38": {
        "CD38": {
            "relative_risk": 3.5,
            "mutations": ["deletion", "low_expression"],
            "mechanism": "Target loss",
            "evidence_level": "LITERATURE_ONLY"
        }
    }
}

TREATMENT_LINE_MULTIPLIERS = {
    1: 1.0,
    2: 1.2,
    3: 1.4,
}
CROSS_RESISTANCE_MULTIPLIER = 1.3
