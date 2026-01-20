"""
Resistance Playbook Service - Disease-Agnostic "What's Next" Logic

Maps detected resistance mechanisms → actionable clinical recommendations.

Supports:
- Multiple Myeloma (MM): DIS3, TP53, cytogenetics, treatment line
- Ovarian Cancer (OV): MAPK, PI3K, DDR/HRD, ABCB1

Architecture: DRY design - shared service with disease-specific mappings.

Created: January 28, 2025
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class EvidenceLevel(str, Enum):
    """Evidence level for recommendations"""
    VALIDATED = "VALIDATED"              # Validated in our cohort (p<0.05)
    TREND = "TREND"                      # Trend in our cohort (p<0.15)
    CLINICAL_TRIAL = "CLINICAL_TRIAL"    # From clinical trials
    STANDARD_OF_CARE = "STANDARD_OF_CARE"  # NCCN/guidelines
    LITERATURE_BASED = "LITERATURE_BASED"  # Published literature
    PRECLINICAL = "PRECLINICAL"          # Cell line/animal data
    PENDING_REVALIDATION = "PENDING_REVALIDATION"  # Was hard-coded, awaiting revalidation
    LOW_EVIDENCE = "LOW_EVIDENCE"        # Low power (n<5)
    EXPERT_OPINION = "EXPERT_OPINION"    # Mechanism-based reasoning


class Disease(str, Enum):
    """Supported diseases"""
    MYELOMA = "myeloma"
    OVARIAN = "ovarian"


@dataclass
class DrugAlternative:
    """A recommended alternative drug"""
    drug: str
    drug_class: str
    rationale: str
    evidence_level: EvidenceLevel
    priority: int  # Lower = higher priority
    source_gene: str  # Which resistance gene this bypasses
    requires: Optional[List[str]] = None  # Prerequisites (e.g., t_11_14)
    pubmed_ref: Optional[str] = None


@dataclass
class RegimenChange:
    """A recommended regimen change"""
    from_regimen: str
    to_regimen: str
    rationale: str
    evidence_level: EvidenceLevel


@dataclass
class MonitoringChange:
    """Updated monitoring recommendations"""
    mrd_frequency: Optional[str] = None
    ctdna_targets: Optional[List[str]] = None
    imaging_frequency: Optional[str] = None
    biomarker_frequency: Optional[str] = None
    bone_marrow_frequency: Optional[str] = None


@dataclass
class DownstreamHandoff:
    """Structured handoff to downstream agent"""
    agent: str  # "drug_efficacy", "care_plan", "monitoring"
    action: str
    payload: Dict[str, Any]
    patient_id: Optional[str] = None


@dataclass
class PlaybookResult:
    """Complete playbook result"""
    alternatives: List[DrugAlternative]
    regimen_changes: List[RegimenChange]
    monitoring_changes: MonitoringChange
    escalation_triggers: List[str]
    downstream_handoffs: Dict[str, DownstreamHandoff]
    provenance: Dict[str, Any]


# ============================================================================
# MULTIPLE MYELOMA PLAYBOOK
# ============================================================================

MM_RESISTANCE_PLAYBOOK = {
    "DIS3": {
        "relative_risk": 2.08,
        "p_value": 0.0145,
        "evidence_level": EvidenceLevel.VALIDATED,
        "validation_source": "MMRF_CoMMpass_GDC",
        "n_mutated": 38,
        "resistance_to": ["proteasome_inhibitor"],
        "mechanism": "RNA surveillance deficiency → reduced ER stress response",
        "alternatives": [
            {
                "drug": "carfilzomib",
                "drug_class": "proteasome_inhibitor_2nd_gen",
                "rationale": "2nd gen PI with irreversible binding may bypass DIS3 resistance",
                "evidence_level": EvidenceLevel.EXPERT_OPINION,
                "priority": 1
            },
            {
                "drug": "daratumumab",
                "drug_class": "anti_cd38",
                "rationale": "Different MoA - anti-CD38 ADCC/CDC not affected by DIS3",
                "evidence_level": EvidenceLevel.CLINICAL_TRIAL,
                "priority": 1
            },
            {
                "drug": "lenalidomide",
                "drug_class": "imid",
                "rationale": "IMiD class targets CRBN pathway, independent of DIS3",
                "evidence_level": EvidenceLevel.STANDARD_OF_CARE,
                "priority": 2
            },
            {
                "drug": "venetoclax",
                "drug_class": "bcl2_inhibitor",
                "rationale": "BCL2 inhibition for t(11;14) patients",
                "evidence_level": EvidenceLevel.CLINICAL_TRIAL,
                "priority": 3,
                "requires": ["t_11_14"]
            }
        ],
        "regimen_changes": [
            {
                "from": "VRd",
                "to": "D-VRd",
                "rationale": "Add daratumumab to triplet for DIS3+ patients"
            },
            {
                "from": "VRd",
                "to": "KRd",
                "rationale": "Switch bortezomib to carfilzomib"
            }
        ],
        "monitoring_changes": {
            "mrd_frequency": "every 3 months (was 6 months)",
            "ctdna_targets": ["DIS3", "TP53", "KRAS"],
            "bone_marrow_frequency": "every 6 months (was yearly)",
            "imaging_frequency": "as clinically indicated"
        },
        "escalation_triggers": [
            "MRD persistence after 4 cycles",
            "New clonal evolution (KRAS/NRAS acquisition)",
            "Rising M-protein despite therapy"
        ]
    },
    
    "TP53": {
        "relative_risk": 1.90,
        "p_value": 0.11,
        "evidence_level": EvidenceLevel.TREND,
        "validation_source": "MMRF_CoMMpass_GDC",
        "n_mutated": 16,
        "resistance_to": ["proteasome_inhibitor", "imid", "alkylator"],
        "mechanism": "Genomic instability, apoptosis resistance, multi-drug resistance",
        "alternatives": [
            {
                "drug": "venetoclax",
                "drug_class": "bcl2_inhibitor",
                "rationale": "BCL2 inhibition may overcome TP53-mediated apoptosis resistance",
                "evidence_level": EvidenceLevel.CLINICAL_TRIAL,
                "priority": 1
            },
            {
                "drug": "teclistamab",
                "drug_class": "bispecific",
                "rationale": "T-cell redirection bypasses TP53 pathway",
                "evidence_level": EvidenceLevel.CLINICAL_TRIAL,
                "priority": 1
            },
            {
                "drug": "elranatamab",
                "drug_class": "bispecific",
                "rationale": "BCMA-targeting bispecific for relapsed/refractory",
                "evidence_level": EvidenceLevel.CLINICAL_TRIAL,
                "priority": 2
            },
            {
                "drug": "ide-cel",
                "drug_class": "car_t",
                "rationale": "CAR-T may overcome TP53 resistance",
                "evidence_level": EvidenceLevel.CLINICAL_TRIAL,
                "priority": 2
            }
        ],
        "regimen_changes": [
            {
                "from": "VRd",
                "to": "VRd + venetoclax",
                "rationale": "Add BCL2 inhibitor for del(17p)/TP53 mutant"
            }
        ],
        "monitoring_changes": {
            "mrd_frequency": "every 2 months",
            "ctdna_targets": ["TP53", "subclonal_evolution"],
            "bone_marrow_frequency": "every 4 months",
            "imaging_frequency": "PET-CT every 6 months"
        },
        "escalation_triggers": [
            "Any MRD positivity",
            "M-protein rise >25%",
            "New extramedullary disease"
        ]
    },
    
    "CRBN": {
        "relative_risk": None,  # Low power, n=3
        "p_value": None,
        "evidence_level": EvidenceLevel.LOW_EVIDENCE,
        "validation_source": "MMRF_CoMMpass_GDC",
        "n_mutated": 3,
        "resistance_to": ["imid"],
        "mechanism": "Cereblon loss → IMiD cannot degrade IKZF1/3",
        "alternatives": [
            {
                "drug": "bortezomib",
                "drug_class": "proteasome_inhibitor",
                "rationale": "Switch to PI class - independent of CRBN",
                "evidence_level": EvidenceLevel.STANDARD_OF_CARE,
                "priority": 1
            },
            {
                "drug": "daratumumab",
                "drug_class": "anti_cd38",
                "rationale": "Anti-CD38 independent of CRBN",
                "evidence_level": EvidenceLevel.STANDARD_OF_CARE,
                "priority": 1
            }
        ],
        "regimen_changes": [
            {
                "from": "Rd",
                "to": "VCd",
                "rationale": "Switch from lenalidomide-based to bortezomib-based"
            }
        ],
        "monitoring_changes": {
            "mrd_frequency": "every 3 months",
            "ctdna_targets": ["CRBN", "IKZF1", "IKZF3"]
        },
        "escalation_triggers": [
            "Progression on IMiD-free regimen"
        ]
    },
    
    "PSMB5": {
        "relative_risk": None,  # Low power, n=2
        "p_value": None,
        "evidence_level": EvidenceLevel.LOW_EVIDENCE,
        "validation_source": "MMRF_CoMMpass_GDC",
        "n_mutated": 2,
        "resistance_to": ["proteasome_inhibitor"],
        "mechanism": "Proteasome subunit mutation → reduced PI binding",
        "alternatives": [
            {
                "drug": "carfilzomib",
                "drug_class": "proteasome_inhibitor_2nd_gen",
                "rationale": "Irreversible binding may overcome PSMB5 mutations",
                "evidence_level": EvidenceLevel.PRECLINICAL,
                "priority": 1
            },
            {
                "drug": "lenalidomide",
                "drug_class": "imid",
                "rationale": "Switch class to IMiD",
                "evidence_level": EvidenceLevel.STANDARD_OF_CARE,
                "priority": 1
            }
        ],
        "regimen_changes": [
            {
                "from": "VRd",
                "to": "KRd",
                "rationale": "Switch to carfilzomib"
            }
        ],
        "monitoring_changes": {
            "mrd_frequency": "every 3 months"
        },
        "escalation_triggers": [
            "Progression on 2nd gen PI"
        ]
    },
    
    # UPR/Antioxidant pathway genes (Literature-based)
    "NFE2L2": {
        "relative_risk": None,
        "p_value": None,
        "evidence_level": EvidenceLevel.LITERATURE_BASED,
        "validation_source": "PMC4636955",
        "n_mutated": None,
        "resistance_to": ["proteasome_inhibitor"],
        "mechanism": "NRF2 activation → antioxidant response → PI resistance",
        "alternatives": [
            {
                "drug": "lenalidomide",
                "drug_class": "imid",
                "rationale": "IMiD class may bypass NRF2-mediated PI resistance",
                "evidence_level": EvidenceLevel.LITERATURE_BASED,
                "priority": 1
            }
        ],
        "regimen_changes": [],
        "monitoring_changes": {
            "mrd_frequency": "every 3 months"
        },
        "escalation_triggers": [
            "Poor initial response to PI"
        ]
    },
    
    "XBP1": {
        "relative_risk": None,
        "p_value": None,
        "evidence_level": EvidenceLevel.LITERATURE_BASED,
        "validation_source": "Literature",
        "n_mutated": None,
        "resistance_to": ["proteasome_inhibitor"],
        "mechanism": "XBP1 is critical for UPR - alterations may affect PI response",
        "alternatives": [
            {
                "drug": "daratumumab",
                "drug_class": "anti_cd38",
                "rationale": "Anti-CD38 independent of UPR pathway",
                "evidence_level": EvidenceLevel.STANDARD_OF_CARE,
                "priority": 1
            }
        ],
        "regimen_changes": [],
        "monitoring_changes": {},
        "escalation_triggers": []
    },
    
    "IRE1": {
        "relative_risk": None,
        "p_value": None,
        "evidence_level": EvidenceLevel.LITERATURE_BASED,
        "validation_source": "Literature",
        "n_mutated": None,
        "resistance_to": ["proteasome_inhibitor"],
        "mechanism": "IRE1/XBP1 pathway alterations affect UPR",
        "aliases": ["ERN1"],
        "alternatives": [
            {
                "drug": "daratumumab",
                "drug_class": "anti_cd38",
                "rationale": "Anti-CD38 independent of UPR pathway",
                "evidence_level": EvidenceLevel.STANDARD_OF_CARE,
                "priority": 1
            }
        ],
        "regimen_changes": [],
        "monitoring_changes": {},
        "escalation_triggers": []
    }
}

# MM High-risk cytogenetics (Literature-based - no MMRF validation available)
MM_CYTOGENETICS = {
    "del_17p": {
        "genes": ["TP53"],
        "hazard_ratio": 2.5,  # Literature value
        "evidence_level": EvidenceLevel.LITERATURE_BASED,
        "validation_source": "IMWG_consensus",
        "mechanism": "TP53 loss → genomic instability, multi-drug resistance",
        "drug_classes_affected": ["all"],
        "interpretation": "ULTRA_HIGH_RISK",
        "alternatives": ["venetoclax", "bispecific", "car_t"],
        "monitoring": "aggressive_mrd_tracking"
    },
    "t_4_14": {
        "genes": ["FGFR3", "MMSET"],
        "hazard_ratio": 1.8,
        "evidence_level": EvidenceLevel.LITERATURE_BASED,
        "validation_source": "IMWG_consensus",
        "mechanism": "FGFR3 activation → aggressive biology",
        "drug_classes_affected": ["alkylator"],
        "interpretation": "HIGH_RISK",
        "alternatives": ["bortezomib_based"],  # PI may be more effective
        "monitoring": "standard_mrd_tracking"
    },
    "1q_gain": {
        "genes": ["CKS1B", "MCL1"],
        "hazard_ratio": 1.5,
        "evidence_level": EvidenceLevel.LITERATURE_BASED,
        "validation_source": "IMWG_consensus",
        "mechanism": "MCL1 amplification → anti-apoptotic",
        "drug_classes_affected": ["all"],
        "interpretation": "HIGH_RISK",
        "alternatives": ["mcl1_inhibitor_trial"],
        "monitoring": "standard_mrd_tracking"
    },
    "t_11_14": {
        "genes": ["CCND1"],
        "hazard_ratio": 0.8,  # Actually favorable for venetoclax
        "evidence_level": EvidenceLevel.LITERATURE_BASED,
        "validation_source": "IMWG_consensus",
        "mechanism": "Cyclin D1 overexpression → BCL2 dependent",
        "drug_classes_affected": [],
        "interpretation": "STANDARD_RISK_VENETOCLAX_SENSITIVE",
        "alternatives": ["venetoclax"],
        "monitoring": "standard"
    }
}


# ============================================================================
# OVARIAN CANCER PLAYBOOK
# ============================================================================

OV_RESISTANCE_PLAYBOOK = {
    "NF1": {
        "relative_risk": 2.10,
        "p_value": 0.05,
        "evidence_level": EvidenceLevel.VALIDATED,
        "validation_source": "TCGA_OV_469",
        "n_mutated": 26,
        "resistance_to": ["platinum"],
        "mechanism": "MAPK pathway activation → bypass signaling",
        "pathway": "MAPK",
        "alternatives": [
            {
                "drug": "olaparib",
                "drug_class": "parp_inhibitor",
                "rationale": "PARP maintenance may overcome MAPK-mediated resistance",
                "evidence_level": EvidenceLevel.CLINICAL_TRIAL,
                "priority": 1
            },
            {
                "drug": "trametinib",
                "drug_class": "mek_inhibitor",
                "rationale": "Direct MAPK pathway inhibition for NF1 loss",
                "evidence_level": EvidenceLevel.CLINICAL_TRIAL,
                "priority": 2
            },
            {
                "drug": "bevacizumab",
                "drug_class": "vegf_inhibitor",
                "rationale": "Add anti-VEGF to platinum backbone",
                "evidence_level": EvidenceLevel.STANDARD_OF_CARE,
                "priority": 2
            }
        ],
        "regimen_changes": [
            {
                "from": "carboplatin/paclitaxel",
                "to": "carboplatin/paclitaxel + bevacizumab",
                "rationale": "Add bevacizumab for high-risk disease"
            }
        ],
        "monitoring_changes": {
            "biomarker_frequency": "CA-125 every 2 weeks",
            "imaging_frequency": "CT every 2-3 months"
        },
        "escalation_triggers": [
            "CA-125 rise >50% from nadir",
            "New lesions on imaging"
        ]
    },
    
    "KRAS": {
        "relative_risk": None,  # PENDING REVALIDATION - was hard-coded RR=1.97
        "p_value": None,  # PENDING REVALIDATION - requires actual computation
        "evidence_level": EvidenceLevel.PENDING_REVALIDATION,
        "validation_source": "PENDING_REVALIDATION_MAPK_OV",
        "resistance_to": ["platinum"],
        "mechanism": "MAPK pathway activation → survival signaling",
        "pathway": "MAPK",
        "alternatives": [
            {
                "drug": "olaparib",
                "drug_class": "parp_inhibitor",
                "rationale": "PARP maintenance may overcome MAPK-mediated resistance",
                "evidence_level": EvidenceLevel.CLINICAL_TRIAL,
                "priority": 1
            },
            {
                "drug": "sotorasib",
                "drug_class": "kras_g12c_inhibitor",
                "rationale": "KRAS G12C inhibitor if applicable mutation",
                "evidence_level": EvidenceLevel.CLINICAL_TRIAL,
                "priority": 2,
                "requires": ["KRAS_G12C"]
            }
        ],
        "regimen_changes": [],
        "monitoring_changes": {
            "biomarker_frequency": "CA-125 every 2 weeks"
        },
        "escalation_triggers": [
            "CA-125 rise >50% from nadir"
        ]
    },
    
    "PIK3CA": {
        "relative_risk": 1.57,
        "p_value": 0.08,
        "evidence_level": EvidenceLevel.TREND,
        "validation_source": "TCGA_OV_469",
        "resistance_to": ["platinum"],
        "mechanism": "PI3K pathway activation → survival signaling",
        "pathway": "PI3K",
        "alternatives": [
            {
                "drug": "alpelisib",
                "drug_class": "pi3k_inhibitor",
                "rationale": "PI3K inhibitor for PIK3CA-mutant tumors",
                "evidence_level": EvidenceLevel.CLINICAL_TRIAL,
                "priority": 1
            },
            {
                "drug": "olaparib",
                "drug_class": "parp_inhibitor",
                "rationale": "PARP maintenance",
                "evidence_level": EvidenceLevel.STANDARD_OF_CARE,
                "priority": 2
            }
        ],
        "regimen_changes": [],
        "monitoring_changes": {
            "biomarker_frequency": "CA-125 every 2 weeks"
        },
        "escalation_triggers": [
            "CA-125 doubling"
        ]
    },
    
    "PTEN": {
        "relative_risk": 1.57,
        "p_value": 0.08,
        "evidence_level": EvidenceLevel.TREND,
        "validation_source": "TCGA_OV_469",
        "resistance_to": ["platinum"],
        "mechanism": "PI3K pathway activation via PTEN loss",
        "pathway": "PI3K",
        "alternatives": [
            {
                "drug": "alpelisib",
                "drug_class": "pi3k_inhibitor",
                "rationale": "PI3K inhibitor for PTEN-loss tumors",
                "evidence_level": EvidenceLevel.CLINICAL_TRIAL,
                "priority": 1
            }
        ],
        "regimen_changes": [],
        "monitoring_changes": {},
        "escalation_triggers": []
    },
    
    # DDR/HRD - Literature-based (validation blocked by data)
    "BRCA1": {
        "relative_risk": None,
        "p_value": None,
        "evidence_level": EvidenceLevel.STANDARD_OF_CARE,
        "validation_source": "NCCN_Guidelines",
        "resistance_to": [],  # BRCA1 = PARP sensitive, not resistant
        "mechanism": "HRD → PARP sensitivity",
        "pathway": "DDR",
        "alternatives": [
            {
                "drug": "olaparib",
                "drug_class": "parp_inhibitor",
                "rationale": "BRCA1/2 mutant tumors are PARP-sensitive",
                "evidence_level": EvidenceLevel.STANDARD_OF_CARE,
                "priority": 1
            },
            {
                "drug": "rucaparib",
                "drug_class": "parp_inhibitor",
                "rationale": "Alternative PARP inhibitor",
                "evidence_level": EvidenceLevel.STANDARD_OF_CARE,
                "priority": 2
            }
        ],
        "regimen_changes": [
            {
                "from": "carboplatin/paclitaxel",
                "to": "carboplatin/paclitaxel → olaparib maintenance",
                "rationale": "PARP maintenance for BRCA+ HGSOC"
            }
        ],
        "monitoring_changes": {
            "imaging_frequency": "CT every 3 months during maintenance"
        },
        "escalation_triggers": []
    },
    
    "BRCA2": {
        "relative_risk": None,
        "p_value": None,
        "evidence_level": EvidenceLevel.STANDARD_OF_CARE,
        "validation_source": "NCCN_Guidelines",
        "resistance_to": [],
        "mechanism": "HRD → PARP sensitivity",
        "pathway": "DDR",
        "alternatives": [
            {
                "drug": "olaparib",
                "drug_class": "parp_inhibitor",
                "rationale": "BRCA1/2 mutant tumors are PARP-sensitive",
                "evidence_level": EvidenceLevel.STANDARD_OF_CARE,
                "priority": 1
            }
        ],
        "regimen_changes": [
            {
                "from": "carboplatin/paclitaxel",
                "to": "carboplatin/paclitaxel → olaparib maintenance",
                "rationale": "PARP maintenance for BRCA+ HGSOC"
            }
        ],
        "monitoring_changes": {},
        "escalation_triggers": []
    }
}


# ============================================================================
# TREATMENT LINE ADJUSTMENTS (Expert Opinion)
# ============================================================================

TREATMENT_LINE_MULTIPLIERS = {
    1: 1.0,   # 1st line: use base RR
    2: 1.2,   # 2nd line: 20% increase (clone evolution)
    3: 1.4,   # 3rd+ line: 40% increase (heavily pre-treated)
}

CROSS_RESISTANCE_MULTIPLIER = 1.3  # Same-class prior exposure


# ============================================================================
# RESISTANCE PLAYBOOK SERVICE
# ============================================================================

class ResistancePlaybookService:
    """
    Disease-Agnostic Resistance Playbook Service
    
    Maps detected resistance mechanisms → actionable next steps:
    - Alternative drugs (ranked by priority)
    - Regimen changes
    - Monitoring updates
    - Escalation triggers
    - Downstream agent handoffs (Drug Efficacy, Care Plan, Monitoring)
    
    Supports: Multiple Myeloma (MM), Ovarian Cancer (OV)
    """
    
    def __init__(self):
        logger.info("ResistancePlaybookService initialized (DRY - OV+MM)")
    
    async def get_next_line_options(
        self,
        disease: str,
        detected_resistance: List[str],  # ["DIS3", "TP53"] or ["NF1", "PIK3CA"]
        current_regimen: Optional[str] = None,
        current_drug_class: Optional[str] = None,
        treatment_line: int = 1,
        prior_therapies: Optional[List[str]] = None,
        cytogenetics: Optional[Dict[str, bool]] = None,  # {"del_17p": True, "t_4_14": False}
        patient_id: Optional[str] = None
    ) -> PlaybookResult:
        """
        Get next-line treatment options based on detected resistance.
        
        Args:
            disease: "myeloma" or "ovarian"
            detected_resistance: List of detected resistance genes
            current_regimen: Current treatment regimen (e.g., "VRd")
            current_drug_class: Current drug class (e.g., "proteasome_inhibitor")
            treatment_line: Treatment line (1, 2, 3+)
            prior_therapies: List of prior drug classes
            cytogenetics: Dict of cytogenetic abnormalities (MM only)
            patient_id: Optional patient ID for handoffs
            
        Returns:
            PlaybookResult with alternatives, regimen changes, monitoring, handoffs
        """
        logger.info(f"ResistancePlaybook: disease={disease}, genes={detected_resistance}, line={treatment_line}")
        
        # Select playbook based on disease
        disease_lower = disease.lower()
        if disease_lower in ["myeloma", "mm", "multiple_myeloma"]:
            playbook = MM_RESISTANCE_PLAYBOOK
            cytogenetics_map = MM_CYTOGENETICS
        elif disease_lower in ["ovarian", "ov", "ovarian_cancer"]:
            playbook = OV_RESISTANCE_PLAYBOOK
            cytogenetics_map = {}  # OV doesn't use cytogenetics
        else:
            logger.warning(f"Unknown disease: {disease}, defaulting to empty playbook")
            return self._empty_result(disease, detected_resistance)
        
        # Collect alternatives from all detected genes
        all_alternatives: List[DrugAlternative] = []
        all_regimen_changes: List[RegimenChange] = []
        all_escalation_triggers: List[str] = []
        combined_monitoring = MonitoringChange()
        
        # Process gene-level resistance
        for gene in detected_resistance:
            gene_upper = gene.upper()
            if gene_upper in playbook:
                gene_info = playbook[gene_upper]
                
                # Get RR adjustment for treatment line
                line_multiplier = TREATMENT_LINE_MULTIPLIERS.get(
                    min(treatment_line, 3), 
                    TREATMENT_LINE_MULTIPLIERS[3]
                )
                
                # Cross-resistance adjustment
                cross_resistance = False
                if prior_therapies and current_drug_class:
                    if current_drug_class.lower() in [p.lower() for p in prior_therapies]:
                        line_multiplier *= CROSS_RESISTANCE_MULTIPLIER
                        cross_resistance = True
                
                # Get base relative risk
                base_rr = gene_info.get("relative_risk", 1.0)
                adjusted_rr = base_rr * line_multiplier if base_rr else None
                
                # Add alternatives
                for alt in gene_info.get("alternatives", []):
                    all_alternatives.append(DrugAlternative(
                        drug=alt["drug"],
                        drug_class=alt["drug_class"],
                        rationale=alt["rationale"],
                        evidence_level=EvidenceLevel(alt.get("evidence_level", EvidenceLevel.EXPERT_OPINION)),
                        priority=alt.get("priority", 5),
                        source_gene=gene_upper,
                        requires=alt.get("requires"),
                        pubmed_ref=alt.get("pubmed_ref")
                    ))
                
                # Add regimen changes
                for change in gene_info.get("regimen_changes", []):
                    if current_regimen and change.get("from", "").lower() == current_regimen.lower():
                        all_regimen_changes.append(RegimenChange(
                            from_regimen=change["from"],
                            to_regimen=change["to"],
                            rationale=change["rationale"],
                            evidence_level=gene_info.get("evidence_level", EvidenceLevel.EXPERT_OPINION)
                        ))
                    elif not current_regimen:
                        # Include if no current regimen specified
                        all_regimen_changes.append(RegimenChange(
                            from_regimen=change["from"],
                            to_regimen=change["to"],
                            rationale=change["rationale"],
                            evidence_level=gene_info.get("evidence_level", EvidenceLevel.EXPERT_OPINION)
                        ))
                
                # Merge monitoring changes
                mon = gene_info.get("monitoring_changes", {})
                if mon.get("mrd_frequency"):
                    combined_monitoring.mrd_frequency = mon["mrd_frequency"]
                if mon.get("ctdna_targets"):
                    if combined_monitoring.ctdna_targets is None:
                        combined_monitoring.ctdna_targets = []
                    combined_monitoring.ctdna_targets.extend(mon["ctdna_targets"])
                if mon.get("imaging_frequency"):
                    combined_monitoring.imaging_frequency = mon["imaging_frequency"]
                if mon.get("biomarker_frequency"):
                    combined_monitoring.biomarker_frequency = mon["biomarker_frequency"]
                if mon.get("bone_marrow_frequency"):
                    combined_monitoring.bone_marrow_frequency = mon["bone_marrow_frequency"]
                
                # Add escalation triggers
                all_escalation_triggers.extend(gene_info.get("escalation_triggers", []))
        
        # Process cytogenetics (MM only)
        if cytogenetics and cytogenetics_map:
            for cyto, present in cytogenetics.items():
                if present and cyto in cytogenetics_map:
                    cyto_info = cytogenetics_map[cyto]
                    
                    # Add cytogenetics-specific alternatives
                    for alt_drug in cyto_info.get("alternatives", []):
                        # Check if already present
                        if not any(a.drug == alt_drug for a in all_alternatives):
                            all_alternatives.append(DrugAlternative(
                                drug=alt_drug,
                                drug_class=f"cytogenetics_{cyto}",
                                rationale=f"Recommended for {cyto}: {cyto_info['mechanism']}",
                                evidence_level=EvidenceLevel(cyto_info.get("evidence_level", EvidenceLevel.LITERATURE_BASED)),
                                priority=1,  # Cytogenetics get high priority
                                source_gene=cyto
                            ))
                    
                    # Intensify monitoring for high-risk cytogenetics
                    if cyto_info.get("interpretation") in ["ULTRA_HIGH_RISK", "HIGH_RISK"]:
                        if not combined_monitoring.mrd_frequency:
                            combined_monitoring.mrd_frequency = "every 2 months"
        
        # Deduplicate and sort alternatives by priority, then by source gene RR
        unique_alternatives = self._deduplicate_alternatives(all_alternatives, playbook)
        
        # Deduplicate other lists
        unique_regimen_changes = list({(r.from_regimen, r.to_regimen): r for r in all_regimen_changes}.values())
        unique_triggers = list(set(all_escalation_triggers))
        
        # Deduplicate ctDNA targets
        if combined_monitoring.ctdna_targets:
            combined_monitoring.ctdna_targets = list(set(combined_monitoring.ctdna_targets))
        
        # Build downstream handoffs
        handoffs = self._build_handoffs(
            disease=disease,
            detected_resistance=detected_resistance,
            alternatives=unique_alternatives,
            regimen_changes=unique_regimen_changes,
            monitoring=combined_monitoring,
            escalation_triggers=unique_triggers,
            current_regimen=current_regimen,
            current_drug_class=current_drug_class,
            patient_id=patient_id
        )
        
        # Build provenance
        provenance = {
            "service_version": "resistance_playbook_v1.0_dry",
            "disease": disease,
            "detected_resistance": detected_resistance,
            "cytogenetics": cytogenetics,
            "treatment_line": treatment_line,
            "prior_therapies": prior_therapies,
            "line_multiplier_applied": TREATMENT_LINE_MULTIPLIERS.get(min(treatment_line, 3), 1.0),
            "cross_resistance_detected": prior_therapies and current_drug_class and 
                                          current_drug_class.lower() in [p.lower() for p in (prior_therapies or [])],
            "playbook_source": "MM_RESISTANCE_PLAYBOOK" if "myeloma" in disease_lower else "OV_RESISTANCE_PLAYBOOK",
            "alternatives_count": len(unique_alternatives),
            "regimen_changes_count": len(unique_regimen_changes)
        }
        
        logger.info(f"ResistancePlaybook: returning {len(unique_alternatives)} alternatives, {len(unique_regimen_changes)} regimen changes")
        
        return PlaybookResult(
            alternatives=unique_alternatives,
            regimen_changes=unique_regimen_changes,
            monitoring_changes=combined_monitoring,
            escalation_triggers=unique_triggers,
            downstream_handoffs=handoffs,
            provenance=provenance
        )
    
    def _deduplicate_alternatives(
        self, 
        alternatives: List[DrugAlternative],
        playbook: Dict
    ) -> List[DrugAlternative]:
        """Deduplicate alternatives, keeping highest priority for each drug"""
        seen = {}
        for alt in alternatives:
            key = alt.drug.lower()
            if key not in seen or alt.priority < seen[key].priority:
                seen[key] = alt
        
        # Sort by priority, then by source gene RR
        result = list(seen.values())
        result.sort(key=lambda a: (
            a.priority,
            -(playbook.get(a.source_gene, {}).get("relative_risk", 0) or 0)
        ))
        
        return result
    
    def _build_handoffs(
        self,
        disease: str,
        detected_resistance: List[str],
        alternatives: List[DrugAlternative],
        regimen_changes: List[RegimenChange],
        monitoring: MonitoringChange,
        escalation_triggers: List[str],
        current_regimen: Optional[str],
        current_drug_class: Optional[str],
        patient_id: Optional[str]
    ) -> Dict[str, DownstreamHandoff]:
        """Build structured handoffs for downstream agents"""
        
        # Get resistance_to classes from alternatives
        resistance_to = list(set(
            alt.drug_class for alt in alternatives 
            if "inhibitor" in alt.drug_class or alt.drug_class in ["imid", "proteasome_inhibitor", "anti_cd38"]
        ))
        
        # Drug Efficacy Agent handoff (Agent 04)
        drug_efficacy_handoff = DownstreamHandoff(
            agent="drug_efficacy",
            action="rerank_drugs",
            payload={
                "avoid_classes": [current_drug_class] if current_drug_class else [],
                "prefer_alternatives": [{"drug": a.drug, "class": a.drug_class, "priority": a.priority} 
                                        for a in alternatives[:5]],
                "resistance_context": {
                    "detected_genes": detected_resistance,
                    "disease": disease
                }
            },
            patient_id=patient_id
        )
        
        # Care Plan Agent handoff (Agent 07)
        care_plan_handoff = DownstreamHandoff(
            agent="care_plan",
            action="update_regimen",
            payload={
                "current_regimen": current_regimen,
                "recommended_regimens": [
                    {"from": r.from_regimen, "to": r.to_regimen, "rationale": r.rationale}
                    for r in regimen_changes
                ],
                "resistance_rationale": f"Resistance detected: {', '.join(detected_resistance)}"
            },
            patient_id=patient_id
        )
        
        # Monitoring Agent handoff (Agent 08)
        monitoring_handoff = DownstreamHandoff(
            agent="monitoring",
            action="intensify_monitoring",
            payload={
                "mrd_frequency": monitoring.mrd_frequency,
                "ctdna_targets": monitoring.ctdna_targets,
                "imaging_frequency": monitoring.imaging_frequency,
                "biomarker_frequency": monitoring.biomarker_frequency,
                "bone_marrow_frequency": monitoring.bone_marrow_frequency,
                "escalation_triggers": escalation_triggers
            },
            patient_id=patient_id
        )
        
        return {
            "drug_efficacy": drug_efficacy_handoff,
            "care_plan": care_plan_handoff,
            "monitoring": monitoring_handoff
        }
    
    def _empty_result(self, disease: str, detected_resistance: List[str]) -> PlaybookResult:
        """Return empty result for unknown disease"""
        return PlaybookResult(
            alternatives=[],
            regimen_changes=[],
            monitoring_changes=MonitoringChange(),
            escalation_triggers=[],
            downstream_handoffs={},
            provenance={
                "service_version": "resistance_playbook_v1.0_dry",
                "disease": disease,
                "detected_resistance": detected_resistance,
                "status": "unknown_disease"
            }
        )


# Singleton instance
_playbook_service: Optional[ResistancePlaybookService] = None


def get_resistance_playbook_service() -> ResistancePlaybookService:
    """Get or create singleton ResistancePlaybookService instance"""
    global _playbook_service
    if _playbook_service is None:
        _playbook_service = ResistancePlaybookService()
    return _playbook_service

