"""
Resistance Prophet Service - Baseline Resistance Risk Stratification.

PRODUCTION STATUS: RUO (Research Use Only)
- Phase 1 AUROC: 0.464 (failed target ≥0.70)
- Mode: baseline_only until CA-125 kinetics validated
- Source of Truth: .cursor/MOAT/RESISTANCE_PROPHET_PRODUCTION_AUDIT.md

Enhanced with mechanism-based signals (Day 2 - Manager Agent, Jan 28 2025)

Based on Manager Approved Plan (Jan 14, 2025):
- Phase 1: Retrospective validation WITHOUT CA-125 (DNA repair + pathway escape only)
- Phase 1b: Prospective with CA-125 kinetics (Ayesha live)
- Phase 1c: Optional retrospective CA-125 if external source appears

Methodology:
- DNA repair restoration detection (signal 1) - WITH MECHANISM BREAKDOWN
- Pathway escape detection (signal 2) - WITH ESCAPED PATHWAYS
- CA-125 kinetics (signal 3 - Phase 1b/1c only)
- 2-of-3 signal detection for HIGH confidence

Enhancement (Jan 28, 2025):
- mechanism_breakdown: DDR/HRR/exon pathway contributions
- pathway_contributions: Formula weights (DDR=0.60, HRR=0.20, exon=0.20)
- escaped_pathways: List of bypassed pathways
- mechanism_alignment: Per-pathway change breakdown
- baseline_source: Documentation when using population average
- baseline_penalty_applied: Flag for confidence adjustment
- confidence_cap: Explicit cap tracking

Manager Decisions Applied:
Q3: Phase 1 = retrospective WITHOUT CA-125 (DNA repair + pathway escape only)
Q5: Detection logic in ResistanceProphetService; minimal getters in sae_feature_service
Q6: Resistance logic here; CA-125 computation stays in ca125_intelligence.py
Q7: Opt-in via include_resistance_prediction=true; default=off
Q9: Thresholds - HIGH: >=0.70 + >=2 signals; MEDIUM: 0.50-0.69 or 1 signal; LOW: <0.50
Q10: HIGH urgency actions defined
Q11: Consult ResistancePlaybookService for next-line; TreatmentLineService for appropriateness
Q15: When CA-125 missing, skip signal; cap confidence at MEDIUM unless >=2 non-CA-125 signals
Q16: If baseline SAE missing, use 0.50 with confidence penalty
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime
from enum import Enum
import logging
from dataclasses import dataclass, field
import math
from api.services.mm_pathway_service import get_mm_pathway_service

logger = logging.getLogger(__name__)


class ResistanceRiskLevel(str, Enum):
    """Resistance risk stratification levels (Manager Q9)"""
    HIGH = "HIGH"      # >=0.70 probability + >=2 signals
    MEDIUM = "MEDIUM"  # 0.50-0.69 or exactly 1 signal
    LOW = "LOW"        # <0.50 probability


class ResistanceSignal(str, Enum):
    """Individual resistance signals"""
    DNA_REPAIR_RESTORATION = "DNA_REPAIR_RESTORATION"  # Signal 1
    PATHWAY_ESCAPE = "PATHWAY_ESCAPE"                  # Signal 2
    CA125_KINETICS = "CA125_KINETICS"                  # Signal 3 (Phase 1b+)
    # MM-specific signals (Gene-level / Proxy SAE)
    MM_HIGH_RISK_GENE = "MM_HIGH_RISK_GENE"           # Signal 4: DIS3, TP53 mutations
    MM_CYTOGENETICS = "MM_CYTOGENETICS"               # Signal 5: del(17p), t(4;14), 1q gain
    MM_DRUG_CLASS_RESISTANCE = "MM_DRUG_CLASS_RESISTANCE"  # Signal 6: PSMB5/CRBN mutations (Work Item 2)


class UrgencyLevel(str, Enum):
    """Action urgency levels (Manager Q10)"""
    CRITICAL = "CRITICAL"  # HIGH risk - immediate escalation
    ELEVATED = "ELEVATED"  # MEDIUM risk - weekly monitoring
    ROUTINE = "ROUTINE"    # LOW risk - routine monitoring


# Pathway contribution weights for DNA repair capacity (Manager C1 formula)
PATHWAY_CONTRIBUTIONS = {
    "ddr": 0.60,  # DDR pathway (60% contribution to DNA repair capacity)
    "hrr": 0.20,  # HRR pathway (20% contribution)
    "exon": 0.20  # Exon disruption (20% contribution)
}

# 7D mechanism vector phway order
PATHWAY_NAMES = ["DDR", "MAPK", "PI3K", "VEGF", "HER2", "IO", "Efflux"]

# Production disclaimers (Phase 1 validation: AUROC 0.464)
RUO_DISCLAIMER = (
    "Research Use Only (RUO). Baseline resistance risk stratification based on genetics. "
    "Phase 1 validation AUROC: 0.464 (target was ≥0.70). "
    "Not validated for clinical decision-making without CA-125 kinetics. "
    "Validated markers: NF1 (OV, RR=2.10), DIS3 (MM, RR=2.08, p=0.0145). "
    "MAPK pathway markers pending revalidation."
)

# Baseline-only mode configuration
BASELINE_ONLY_CLAIMS_DISABLED = [
    "early_detection",
    "lead_time_analysis",
    "3_6_months_early"
]

# Drug class to targeted pathway mapping
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
    # MM-specific drug classes
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

# MM HIGH-RISK GENE MARKERS (Proxy SAE - Gene-Level Validated)
# Source: MMRF CoMMpass GDC data, N=219 patients with mutations
MM_HIGH_RISK_GENES = {
    "DIS3": {
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
        "relative_risk": 1.90,
        "p_value": 0.11,
        "confidence": 0.75,  # Trend, not significant
        "validation_source": "MMRF_CoMMpass_GDC",
        "n_mutated": 16,
        "mechanism": "Genomic instability, therapy resistance",
        "drug_classes_affected": ["proteasome_inhibitor", "imid", "anti_cd38"],
        "rationale": "TP53 mutations confer genomic instability and multi-drug resistance"
    },
    "KRAS": {
        "relative_risk": 0.93,
        "p_value": 0.87,
        "confidence": 0.0,  # No signal
        "validation_source": "MMRF_CoMMpass_GDC",
        "n_mutated": 73,
        "mechanism": "MAPK pathway activation",
        "drug_classes_affected": [],
        "rationale": "KRAS mutations do not predict mortality in MM (no validated signal)"
    },
    "NRAS": {
        "relative_risk": 0.93,
        "p_value": 0.87,
        "confidence": 0.0,  # No signal
        "validation_source": "MMRF_CoMMpass_GDC",
        "n_mutated": 52,
        "mechanism": "MAPK pathway activation",
        "drug_classes_affected": [],
        "rationale": "NRAS mutations do not predict mortality in MM (no validated signal)"
    },
    # UPR/Antioxidant pathway genes (Literature-based - Task 7)
    "NFE2L2": {
        "relative_risk": None,
        "p_value": None,
        "confidence": 0.50,  # Literature-based
        "validation_source": "PMC4636955",
        "n_mutated": None,
        "mechanism": "NRF2 activation → antioxidant response → PI resistance",
        "drug_classes_affected": ["proteasome_inhibitor"],
        "rationale": "NFE2L2/NRF2 upregulates antioxidant genes, counteracting PI-induced oxidative stress"
    },
    "XBP1": {
        "relative_risk": None,
        "p_value": None,
        "confidence": 0.50,
        "validation_source": "Literature",
        "n_mutated": None,
        "mechanism": "XBP1 is critical for UPR - alterations may affect PI response",
        "drug_classes_affected": ["proteasome_inhibitor"],
        "rationale": "XBP1 alterations affect unfolded protein response"
    },
    "IRE1": {
        "relative_risk": None,
        "p_value": None,
        "confidence": 0.50,
        "validation_source": "Literature",
        "n_mutated": None,
        "mechanism": "IRE1/XBP1 pathway alterations affect UPR",
        "drug_classes_affected": ["proteasome_inhibitor"],
        "rationale": "IRE1 (ERN1) activates XBP1, critical for PI response"
    },
}

# MM High-Risk Cytogenetics (Literature-based - MMRF has no cytogenetics data)
# Evidence: IMWG Consensus Guidelines
MM_CYTOGENETICS = {
    "del_17p": {
        "genes": ["TP53"],
        "hazard_ratio": 2.5,
        "p_value": None,
        "evidence_level": "LITERATURE_BASED",
        "validation_source": "IMWG_consensus",
        "mechanism": "TP53 loss → genomic instability, multi-drug resistance",
        "drug_classes_affected": ["all"],
        "interpretation": "ULTRA_HIGH_RISK",
        "rationale": "del(17p) is universally associated with poor prognosis in MM"
    },
    "t_4_14": {
        "genes": ["FGFR3", "MMSET"],
        "hazard_ratio": 1.8,
        "p_value": None,
        "evidence_level": "LITERATURE_BASED",
        "validation_source": "IMWG_consensus",
        "mechanism": "FGFR3 activation → aggressive biology",
        "drug_classes_affected": ["alkylator"],
        "interpretation": "HIGH_RISK",
        "rationale": "t(4;14) patients may benefit from bortezomib-based therapy"
    },
    "1q_gain": {
        "genes": ["CKS1B", "MCL1"],
        "hazard_ratio": 1.5,
        "p_value": None,
        "evidence_level": "LITERATURE_BASED",
        "validation_source": "IMWG_consensus",
        "mechanism": "MCL1 amplification → anti-apoptotic",
        "drug_classes_affected": ["all"],
        "interpretation": "HIGH_RISK",
        "rationale": "1q gain is associated with shorter PFS/OS"
    },
    "t_11_14": {
        "genes": ["CCND1"],
        "hazard_ratio": 0.8,  # Favorable for venetoclax
        "p_value": None,
        "evidence_level": "LITERATURE_BASED",
        "validation_source": "IMWG_consensus",
        "mechanism": "Cyclin D1 overexpression → BCL2 dependent",
        "drug_classes_affected": [],
        "interpretation": "STANDARD_RISK_VENETOCLAX_SENSITIVE",
        "rationale": "t(11;14) patients are venetoclax-sensitive"
    }
}

# MM Drug-Class Specific Resistance Mutations (Work Item 2)
# Source: Literature-based (PSMB5/CRBN mutations are rare, n=2-3)
# Validation: LITERATURE_ONLY (acceptable for rare mutations)
MM_RESISTANCE_MUTATIONS = {
    "proteasome_inhibitor": {
        "PSMB5": {
            "relative_risk": 5.0,  # High risk for specific drug
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

# Treatment line adjustment multipliers (Expert Opinion - Task 3)
TREATMENT_LINE_MULTIPLIERS = {
    1: 1.0,   # 1st line: use base RR
    2: 1.2,   # 2nd line: 20% increase (clone evolution)
    3: 1.4,   # 3rd+ line: 40% increase (heavily pre-treated)
}
CROSS_RESISTANCE_MULTIPLIER = 1.3  # Same-class prior exposure


@dataclass
class MechanismBreakdown:
    """Mechanism-level breakdown for DNA repair restoration signal"""
    ddr_pathway_change: float  # Change in DDR pathway burden
    hrr_essentiality_change: float  # Change in HRR essentiality
    exon_disruption_change: float  # Change in exon disruption score
    pathway_contributions: Dict[str, float] = field(default_factory=lambda: PATHWAY_CONTRIBUTIONS.copy())


@dataclass
class ResistanceSignalData:
    """Data for a single resistance signal - enhanced with mechanism breakdown"""
    signal_type: ResistanceSignal
    detected: bool
    probability: float  # 0.0-1.0
    confidence: float   # 0.0-1.0
    rationale: str
    provenance: Dict
    # NEW: Mechanism-based enhancements (Jan 28, 2025)
    mechanism_breakdown: Optional[MechanismBreakdown] = None  # For DNA_REPAIR_RESTORATION
    escaped_pathways: Optional[List[str]] = None  # For PATHWAY_ESCAPE
    mechanism_alignment: Optional[Dict[str, float]] = None  # Per-pathway changes


@dataclass
class ResistancePrediction:
    """Complete resistance prediction output"""
    risk_level: ResistanceRiskLevel
    probability: float  # Overall resistance probability (0.0-1.0)
    confidence: float   # Prediction confidence (0.0-1.0)
    signals_detected: List[ResistanceSignalData]
    signal_count: int
    urgency: UrgencyLevel
    recommended_actions: List[Dict]
    next_line_options: List[Dict]  # From ResistancePlaybookService
    rationale: List[str]
    provenance: Dict
    warnings: List[str]
    # NEW: Baseline handling documentation (Jan 28, 2025)
    baseline_source: str = "patient_baseline"  # "patient_baseline" or "population_average"
    baseline_penalty_applied: bool = False
    confidence_cap: Optional[str] = None  # "MEDIUM" if capped


class ResistanceProphetService:
    """
    Predicts treatment resistance before clinical progression.
    
    Enhanced with mechanism-based signals (Jan 28, 2025):
    - mechanism_breakdown: DDR/HRR/exon pathway contributions
    - escaped_pathways: Which pathways were bypassed
    - mechanism_alignment: Per-pathway change tracking
    
    Phase 1: DNA repair + pathway escape (NO CA-125)
    Phase 1b: Add CA-125 kinetics for prospective (Ayesha)
    Phase 1c: Optional retrospective CA-125 if external data available
    """
    
    # Manager Q9: Signal detection thresholds
    DNA_REPAIR_THRESHOLD = 0.15  # Restoration detected if capacity changes >15%
    PATHWAY_ESCAPE_THRESHOLD = 0.15  # Escape detected if targeted pathway drops >15%
    
    # Manager Q9: Risk stratification thresholds
    HIGH_RISK_PROBABILITY = 0.70
    MEDIUM_RISK_PROBABILITY = 0.50
    MIN_SIGNALS_FOR_HIGH = 2
    
    def __init__(self, 
                 sae_service=None,
                 ca125_service=None,
                 treatment_line_service=None,
                 resistance_playbook_service=None,
                 mm_pathway_service=None):
        """
        Initialize Resistance Prophet.
        """
        self.sae_service = sae_service
        self.ca125_service = ca125_service
        self.treatment_line_service = treatment_line_service
        self.resistance_playbook_service = resistance_playbook_service
        self.mm_pathway_service = mm_pathway_service or get_mm_pathway_service()
        
        logger.info("ResistanceProphetService initialized (Enhanced with mechanism breakdown)")
    
    
    async def predict_resistance(
        self,
        current_sae_features: Dict,
        baseline_sae_features: Optional[Dict] = None,
        ca125_history: Optional[List[Dict]] = None,
        treatment_history: Optional[List[Dict]] = None,
        current_drug_class: Optional[str] = None
    ) -> ResistancePrediction:
        """
        Predict treatment resistance risk with mechanism-based signals.
        
        Enhanced (Jan 28, 2025):
        - Returns mechanism_breakdown for DNA repair restoration
        - Returns escaped_pathways for pathway escape
        - Documents baseline_source and penalty
        
        Args:
            current_sae_features: Current SAE mechanism vector + DNA repair capacity
            baseline_sae_features: Baseline SAE features (pre-treatment if available)
            ca125_history: List of CA-125 measurements (Phase 1b+)
            treatment_history: Patient treatment history
            current_drug_class: Current drug being assessed
            
        Returns:
            ResistancePrediction with risk level, signals, mechanism breakdown
        """
        logger.info("=== RESISTANCE PROPHET: Starting prediction (enhanced) ===")
        
        signals_detected: List[ResistanceSignalData] = []
        warnings: List[str] = []
        
        # Track baseline handling
        baseline_source = "patient_baseline"
        baseline_penalty_applied = False
        
        # Manager Q16: Handle missing baseline
        if baseline_sae_features is None:
            logger.warning("Baseline SAE features missing - using population average (0.50)")
            warnings.append("INSUFFICIENT_BASELINE_DATA")
            baseline_sae_features = self._get_population_baseline()
            baseline_source = "population_average"
            baseline_penalty_applied = True
        
        # SIGNAL 1: DNA Repair Restoration (Phase 1) - WITH MECHANISM BREAKDOWN
        dna_repair_signal = await self._detect_dna_repair_restoration(
            current_sae=current_sae_features,
            baseline_sae=baseline_sae_features,
            baseline_source=baseline_source
        )
        signals_detected.append(dna_repair_signal)
        
        # SIGNAL 2: Pathway Escape (Phase 1) - WITH ESCAPED PATHWAYS
        pathway_escape_signal = await self._detect_pathway_escape(
            current_sae=current_sae_features,
            baseline_sae=baseline_sae_features,
            drug_class=current_drug_class
        )
        signals_detected.append(pathway_escape_signal)
        
        # SIGNAL 3: CA-125 Kinetics (Phase 1b/1c ONLY)
        ca125_signal = None
        if ca125_history and len(ca125_history) >= 2:
            logger.info("CA-125 history available - computing kinetics signal (Phase 1b+)")
            ca125_signal = await self._detect_ca125_kinetics(ca125_history)
            signals_detected.append(ca125_signal)
        else:
            logger.info("CA-125 history unavailable - skipping signal (Phase 1 mode)")
            warnings.append("INSUFFICIENT_CA125_DATA")
        
        
        # MM Signal 4: Pathway burden (mechanism-level prediction)
        if self.mm_pathway_service:
            try:
                pathway_burden = self.mm_pathway_service.compute_mm_pathway_burden(mutations)
                mechanism_vector = self.mm_pathway_service.compute_mm_mechanism_vector(pathway_burden)
                
                # Create pathway signal (if significant burden detected)
                max_burden = max([p.get("score", 0.0) for p in pathway_burden.values()])
                if max_burden > 0.3:  # Threshold for significant pathway burden
                    pathway_signal = ResistanceSignalData(
                        signal_type=ResistanceSignal.MM_DRUG_CLASS_RESISTANCE,  # Reuse signal type
                        detected=True,
                        probability=float(min(0.8, max_burden * 1.2)),  # Scale burden to probability
                        confidence=0.70,
                        rationale=f"Pathway burden detected: max={max_burden:.2f}. Mechanism vector: {[f'{v:.2f}' for v in mechanism_vector]}",
                        provenance={
                            "signal_type": "MM_PATHWAY_BURDEN",
                            "pathway_burden": {k: {"score": v["score"], "mutated_genes": v["mutated_genes"]} 
                                             for k, v in pathway_burden.items()},
                            "mechanism_vector": mechanism_vector
                        }
                    )
                    signals_detected.append(pathway_signal)
                    logger.info(f"Pathway burden signal: max={max_burden:.2f}, pathways={[k for k, v in pathway_burden.items() if v['score'] > 0.3]}")
            except Exception as e:
                logger.warning(f"Pathway burden computation failed: {e}")
                warnings.append("PATHWAY_SERVICE_ERROR")
        
# Count positive signals
        signal_count = sum(1 for sig in signals_detected if sig.detected)
        
        # Compute overall resistance probability
        probability = self._compute_resistance_probability(signals_detected)
        
        # Manager Q9: Stratify risk level
        risk_level = self._stratify_risk(
            probability, signal_count, 
            ca125_available=(ca125_signal is not None)
        )
        
        # Compute confidence with penalty tracking
        confidence, confidence_cap = self._compute_confidence(
            signals_detected=signals_detected,
            baseline_available=(baseline_source == "patient_baseline"),
            ca125_available=(ca125_signal is not None),
            signal_count=signal_count
        )
        
        # Manager Q10: Determine urgency and actions
        urgency, actions = self._determine_actions(risk_level, signal_count, signals_detected)
        
        # Manager Q11: Get next-line options from ResistancePlaybookService
        next_line_options = []
        if self.resistance_playbook_service and risk_level != ResistanceRiskLevel.LOW:
            try:
                playbook_result = await self.resistance_playbook_service.get_next_line_options(
                    current_drug_class=current_drug_class,
                    resistance_mechanisms=[sig.signal_type for sig in signals_detected if sig.detected],
                    sae_features=current_sae_features
                )
                next_line_options = playbook_result.get("options", [])
            except Exception as e:
                logger.error(f"Failed to fetch next-line options: {e}")
                warnings.append("PLAYBOOK_SERVICE_UNAVAILABLE")
        
        # Build rationale
        rationale = self._build_rationale(signals_detected, probability, risk_level)
        
        # Build provenance
        provenance = {
            "model_version": "resistance_prophet_v1.1_mechanism_enhanced",
            "phase": "phase1_retrospective_no_ca125",
            "timestamp": datetime.utcnow().isoformat(),
            "enhancement_date": "2025-01-28",
            "thresholds": {
                "dna_repair": self.DNA_REPAIR_THRESHOLD,
                "pathway_escape": self.PATHWAY_ESCAPE_THRESHOLD,
                "high_risk_probability": self.HIGH_RISK_PROBABILITY,
                "medium_risk_probability": self.MEDIUM_RISK_PROBABILITY,
                "min_signals_for_high": self.MIN_SIGNALS_FOR_HIGH
            },
            "pathway_contributions": PATHWAY_CONTRIBUTIONS,
            "signals_used": [sig.signal_type.value for sig in signals_detected],
            "ca125_available": ca125_signal is not None,
            "baseline_available": baseline_source == "patient_baseline",
            "baseline_source": baseline_source,
            "baseline_penalty_applied": baseline_penalty_applied
        }
        
        logger.info(f"=== RESISTANCE PROPHET: Prediction complete - Risk={risk_level}, Probability={probability:.2f}, Signals={signal_count} ===")
        
        return ResistancePrediction(
            risk_level=risk_level,
            probability=probability,
            confidence=confidence,
            signals_detected=signals_detected,
            signal_count=signal_count,
            urgency=urgency,
            recommended_actions=actions,
            next_line_options=next_line_options,
            rationale=rationale,
            provenance=provenance,
            warnings=warnings,
            baseline_source=baseline_source,
            baseline_penalty_applied=baseline_penalty_applied,
            confidence_cap=confidence_cap
        )
    
    
    async def _detect_dna_repair_restoration(
        self,
        current_sae: Dict,
        baseline_sae: Dict,
        baseline_source: str = "patient_baseline"
    ) -> ResistanceSignalData:
        """
        Detect DNA repair capacity restoration (Signal 1).
        
        Enhanced (Jan 28, 2025):
        - Returns mechanism_breakdown with DDR/HRR/exon changes
        - Returns pathway_contributions (DDR=0.60, HRR=0.20, exon=0.20)
        - Documents baseline_source
        
        Logic:
        - Compare current DNA repair capacity to baseline
        - Restoration detected if capacity drops (tumor restoring repair)
        - Indicates PARP resistance mechanism
        """
        logger.info("Detecting DNA repair restoration signal (enhanced)...")
        
        # Extract DNA repair capacity
        current_repair = current_sae.get("dna_repair_capacity", 0.0)
        baseline_repair = baseline_sae.get("dna_repair_capacity", 0.5)
        
        # Extract pathway-level features for mechanism breakdown
        current_ddr = current_sae.get("pathway_burden_ddr", current_sae.get("mechanism_vector", [0.5]*7)[0] if current_sae.get("mechanism_vector") else 0.5)
        baseline_ddr = baseline_sae.get("pathway_burden_ddr", baseline_sae.get("mechanism_vector", [0.5]*7)[0] if baseline_sae.get("mechanism_vector") else 0.5)
        
        current_hrr = current_sae.get("essentiality_hrr", 0.5)
        baseline_hrr = baseline_sae.get("essentiality_hrr", 0.5)
        
        current_exon = current_sae.get("exon_disruption_score", 0.5)
        baseline_exon = baseline_sae.get("exon_disruption_score", 0.5)
        
        # Compute mechanism breakdown (changes)
        ddr_change = current_ddr - baseline_ddr
        hrr_change = current_hrr - baseline_hrr
        exon_change = current_exon - baseline_exon
        
        mechanism_breakdown = MechanismBreakdown(
            ddr_pathway_change=float(ddr_change),
            hrr_essentiality_change=float(hrr_change),
            exon_disruption_change=float(exon_change)
        )
        
        # Compute DNA repair capacity change
        repair_change = current_repair - baseline_repair
        
        # Restoration = DNA repair capacity DROPPING (tumor repairing its repair deficiency)
        # A negative change means the patient's tumor is becoming MORE repair-proficient
        detected = repair_change < -self.DNA_REPAIR_THRESHOLD
        
        # Compute probability (sigmoid mapping)
        # More negative change = higher restoration probability
        probability = 1.0 / (1.0 + math.exp(10 * (repair_change + self.DNA_REPAIR_THRESHOLD)))
        probability = max(0.0, min(1.0, probability))
        
        # Confidence depends on baseline quality
        confidence = 0.90 if baseline_source == "patient_baseline" else 0.60
        
        rationale = (
            f"DNA repair capacity change: {repair_change:+.2f} "
            f"(baseline={baseline_repair:.2f} → current={current_repair:.2f}). "
            f"{'RESTORATION DETECTED' if detected else 'No restoration'} "
            f"(threshold={-self.DNA_REPAIR_THRESHOLD:+.2f}). "
            f"Mechanism breakdown: DDR={ddr_change:+.2f}, HRR={hrr_change:+.2f}, exon={exon_change:+.2f}."
        )
        
        provenance = {
            "signal_type": "DNA_REPAIR_RESTORATION",
            "baseline_capacity": float(baseline_repair),
            "current_capacity": float(current_repair),
            "absolute_change": float(repair_change),
            "threshold": float(self.DNA_REPAIR_THRESHOLD),
            "detection_method": "threshold_comparison",
            "baseline_source": baseline_source,
            "baseline_penalty_applied": baseline_source == "population_average",
            "mechanism_breakdown": {
                "ddr_pathway_change": float(ddr_change),
                "hrr_essentiality_change": float(hrr_change),
                "exon_disruption_change": float(exon_change)
            },
            "pathway_contributions": PATHWAY_CONTRIBUTIONS
        }
        
        logger.info(f"DNA repair signal: detected={detected}, probability={probability:.2f}, confidence={confidence:.2f}")
        
        return ResistanceSignalData(
            signal_type=ResistanceSignal.DNA_REPAIR_RESTORATION,
            detected=detected,
            probability=float(probability),
            confidence=float(confidence),
            rationale=rationale,
            provenance=provenance,
            mechanism_breakdown=mechanism_breakdown
        )
    
    
    async def _detect_pathway_escape(
        self,
        current_sae: Dict,
        baseline_sae: Dict,
        drug_class: Optional[str]
    ) -> ResistanceSignalData:
        """
        Detect pathway escape mechanism (Signal 2).
        
        Enhanced (Jan 28, 2025):
        - Returns escaped_pathways list
        - Returns mechanism_alignment with per-pathway changes
        
        Logic:
        - Compare current mechanism vector to baseline
        - If drug targets a pathway and that pathway burden drops, it's escape
        - Indicates bypass resistance mechanism
        """
        logger.info("Detecting pathway escape signal (enhanced)...")
        
        # Extract mechanism vectors (7D: DDR, MAPK, PI3K, VEGF, HER2, IO, Efflux)
        current_vector = current_sae.get("mechanism_vector", [0.5] * 7)
        baseline_vector = baseline_sae.get("mechanism_vector", [0.5] * 7)
        
        # Ensure vectors are proper length
        if len(current_vector) != 7:
            current_vector = [0.5] * 7
        if len(baseline_vector) != 7:
            baseline_vector = [0.5] * 7
        
        # Compute per-pathway changes
        mechanism_alignment = {}
        for i, pathway in enumerate(PATHWAY_NAMES):
            change = current_vector[i] - baseline_vector[i]
            mechanism_alignment[pathway] = float(change)
        
        # Identify targeted pathways for current drug
        targeted_pathways = []
        if drug_class:
            drug_class_lower = drug_class.lower().replace(" ", "_").replace("-", "_")
            for drug_pattern, pathways in DRUG_PATHWAY_TARGETS.items():
                if drug_pattern in drug_class_lower or drug_class_lower in drug_pattern:
                    targeted_pathways.extend(pathways)
            targeted_pathways = list(set(targeted_pathways))
        
        # Detect escaped pathways
        # Escape = targeted pathway burden DROPPED (tumor escaping the drug's target)
        escaped_pathways = []
        for pathway in targeted_pathways:
            if pathway in mechanism_alignment:
                change = mechanism_alignment[pathway]
                if change < -self.PATHWAY_ESCAPE_THRESHOLD:
                    escaped_pathways.append(pathway)
                    logger.info(f"Pathway escape detected: {pathway} (change={change:.2f})")
        
        # Also detect any pathway with significant drop
        for pathway, change in mechanism_alignment.items():
            if change < -self.PATHWAY_ESCAPE_THRESHOLD and pathway not in escaped_pathways:
                # Check if this is a bypass (alternative pathway emerging)
                pass  # Track but don't add to escaped unless targeted
        
        detected = len(escaped_pathways) > 0
        
        # Compute probability based on magnitude of escape
        if escaped_pathways:
            max_escape = max(abs(mechanism_alignment[p]) for p in escaped_pathways)
            probability = 1.0 / (1.0 + math.exp(-10 * (max_escape - self.PATHWAY_ESCAPE_THRESHOLD)))
        else:
            # Check for general vector shift (bypass mechanism)
            total_shift = sum(abs(v) for v in mechanism_alignment.values())
            probability = min(0.4, total_shift / 3.0)  # Cap at 0.4 for non-targeted escape
        
        probability = max(0.0, min(1.0, probability))
        
        # Confidence depends on baseline quality and drug targeting info
        base_confidence = 0.85 if baseline_sae.get("mechanism_vector") is not None else 0.55
        if not drug_class:
            base_confidence *= 0.80  # Reduce confidence if drug class unknown
        confidence = base_confidence
        
        # Build shift summary
        top_shifts = sorted(mechanism_alignment.items(), key=lambda x: abs(x[1]), reverse=True)[:3]
        shift_summary = ", ".join([f"{name}:{delta:+.2f}" for name, delta in top_shifts])
        
        escaped_str = ", ".join(escaped_pathways) if escaped_pathways else "none"
        targeted_str = ", ".join(targeted_pathways) if targeted_pathways else "unknown"
        
        rationale = (
            f"Pathway escape analysis for drug class '{drug_class or 'unknown'}'. "
            f"Targeted pathways: [{targeted_str}]. "
            f"Escaped pathways: [{escaped_str}]. "
            f"{'ESCAPE DETECTED' if detected else 'No escape'}. "
            f"Top changes: {shift_summary}."
        )
        
        provenance = {
            "signal_type": "PATHWAY_ESCAPE",
            "baseline_vector": [float(v) for v in baseline_vector],
            "current_vector": [float(v) for v in current_vector],
            "mechanism_alignment": mechanism_alignment,
            "targeted_pathways": targeted_pathways,
            "escaped_pathways": escaped_pathways,
            "threshold": float(self.PATHWAY_ESCAPE_THRESHOLD),
            "drug_class": drug_class,
            "detection_method": "targeted_pathway_drop",
            "baseline_source": "baseline_sae_features" if baseline_sae.get("mechanism_vector") else "population_average"
        }
        
        logger.info(f"Pathway escape signal: detected={detected}, escaped={escaped_pathways}, probability={probability:.2f}")
        
        return ResistanceSignalData(
            signal_type=ResistanceSignal.PATHWAY_ESCAPE,
            detected=detected,
            probability=float(probability),
            confidence=float(confidence),
            rationale=rationale,
            provenance=provenance,
            escaped_pathways=escaped_pathways,
            mechanism_alignment=mechanism_alignment
        )
    
    
    async def _detect_ca125_kinetics(
        self,
        ca125_history: List[Dict]
    ) -> ResistanceSignalData:
        """
        Detect rising CA-125 trend (Signal 3).
        
        Phase 1b+: Add CA-125 kinetics analysis
        Phase 1: NOT USED (retrospective validation without CA-125)
        """
        logger.info("Detecting CA-125 kinetics signal (Phase 1b+)...")
        
        if not self.ca125_service:
            logger.warning("CA125Intelligence service not available")
            return ResistanceSignalData(
                signal_type=ResistanceSignal.CA125_KINETICS,
                detected=False,
                probability=0.0,
                confidence=0.0,
                rationale="CA-125 service unavailable",
                provenance={"signal_type": "CA125_KINETICS", "status": "service_unavailable"}
            )
        
        try:
            # Use existing CA125Intelligence service
            ca125_analysis = await self.ca125_service.analyze_kinetics(ca125_history)
            
            # Extract resistance signals
            resistance_flags = ca125_analysis.get("resistance_flags", [])
            detected = len(resistance_flags) > 0
            
            probability = ca125_analysis.get("resistance_probability", 0.0)
            confidence = ca125_analysis.get("confidence", 0.80)
            
            rationale = (
                f"CA-125 kinetics analysis: {len(resistance_flags)} resistance flag(s) detected. "
                f"{ca125_analysis.get('summary', 'See detailed analysis for context')}."
            )
            
            provenance = {
                "signal_type": "CA125_KINETICS",
                "measurements_count": len(ca125_history),
                "resistance_flags": resistance_flags,
                "analysis": ca125_analysis,
                "detection_method": "ca125_intelligence_service"
            }
            
            logger.info(f"CA-125 kinetics signal: detected={detected}, probability={probability:.2f}")
            
            return ResistanceSignalData(
                signal_type=ResistanceSignal.CA125_KINETICS,
                detected=detected,
                probability=float(probability),
                confidence=float(confidence),
                rationale=rationale,
                provenance=provenance
            )
            
        except Exception as e:
            logger.error(f"CA-125 kinetics detection failed: {e}")
            return ResistanceSignalData(
                signal_type=ResistanceSignal.CA125_KINETICS,
                detected=False,
                probability=0.0,
                confidence=0.0,
                rationale=f"CA-125 analysis failed: {str(e)}",
                provenance={"signal_type": "CA125_KINETICS", "error": str(e)}
            )
    
    
    async def _detect_mm_high_risk_genes(
        self,
        mutations: List[Dict],
        drug_class: Optional[str] = None
    ) -> ResistanceSignalData:
        """
        Detect MM high-risk gene mutations (Signal 4 - MM-specific).
        
        Validated markers (Proxy SAE - Gene-Level):
        - DIS3: RR=2.08, p=0.0145 (SIGNIFICANT) - RNA surveillance
        - TP53: RR=1.90, p=0.11 (TREND) - Genomic instability
        
        Args:
            mutations: List of patient mutations with 'gene' field
            drug_class: Current drug class (to assess relevance)
            
        Returns:
            ResistanceSignalData with detected high-risk genes
        """
        logger.info("Detecting MM high-risk gene mutations (Proxy SAE)...")
        
        if not mutations:
            return ResistanceSignalData(
                signal_type=ResistanceSignal.MM_HIGH_RISK_GENE,
                detected=False,
                probability=0.0,
                confidence=0.0,
                rationale="No mutations provided for MM high-risk gene analysis",
                provenance={"signal_type": "MM_HIGH_RISK_GENE", "status": "no_mutations"}
            )
        
        # Extract gene names from mutations
        patient_genes = {m.get("gene", "").upper() for m in mutations}
        
        # Check for high-risk gene mutations
        detected_high_risk = []
        total_relative_risk = 0.0
        max_relative_risk = 0.0
        weighted_confidence = 0.0
        
        for gene, info in MM_HIGH_RISK_GENES.items():
            if gene in patient_genes and info["confidence"] > 0:
                detected_high_risk.append({
                    "gene": gene,
                    "relative_risk": info["relative_risk"],
                    "p_value": info["p_value"],
                    "mechanism": info["mechanism"],
                    "rationale": info["rationale"],
                    "drug_classes_affected": info["drug_classes_affected"]
                })
                total_relative_risk += info["relative_risk"]
                max_relative_risk = max(max_relative_risk, info["relative_risk"])
                weighted_confidence += info["confidence"]
        
        detected = len(detected_high_risk) > 0
        
        # Compute probability from relative risk
        # RR=2.0 → ~0.67 probability, RR=1.0 → 0.50, RR=3.0 → 0.75
        if detected:
            # Use max RR for probability (not additive)
            probability = max_relative_risk / (max_relative_risk + 1.0)
            confidence = min(1.0, weighted_confidence / len(detected_high_risk))
        else:
            probability = 0.0
            confidence = 0.0
        
        # Check drug class relevance
        drug_relevant = False
        if drug_class and detected:
            drug_class_lower = drug_class.lower().replace(" ", "_").replace("-", "_")
            for gene_info in detected_high_risk:
                for affected_class in gene_info["drug_classes_affected"]:
                    if affected_class in drug_class_lower or drug_class_lower in affected_class:
                        drug_relevant = True
                        break
        
        # Boost confidence if drug-relevant
        if drug_relevant:
            confidence = min(1.0, confidence * 1.1)
        
        gene_names = [g["gene"] for g in detected_high_risk]
        rationale = (
            f"MM high-risk gene analysis: {len(detected_high_risk)} gene(s) detected. "
            f"{'DETECTED' if detected else 'Not detected'}: {', '.join(gene_names) if gene_names else 'none'}. "
            f"Max RR: {max_relative_risk:.2f}. "
            f"Drug relevance: {'YES' if drug_relevant else 'NO'}."
        )
        
        provenance = {
            "signal_type": "MM_HIGH_RISK_GENE",
            "detected_genes": detected_high_risk,
            "patient_genes_checked": list(patient_genes & set(MM_HIGH_RISK_GENES.keys())),
            "max_relative_risk": max_relative_risk,
            "drug_class": drug_class,
            "drug_relevant": drug_relevant,
            "validation_source": "MMRF_CoMMpass_GDC",
            "method": "proxy_sae_gene_level"
        }
        
        logger.info(f"MM high-risk gene signal: detected={detected}, genes={gene_names}, probability={probability:.2f}")
        
        return ResistanceSignalData(
            signal_type=ResistanceSignal.MM_HIGH_RISK_GENE,
            detected=detected,
            probability=float(probability),
            confidence=float(confidence),
            rationale=rationale,
            provenance=provenance
        )
    
    
    async def _detect_mm_cytogenetics(
        self,
        cytogenetics: Dict[str, bool],
        drug_class: Optional[str] = None
    ) -> ResistanceSignalData:
        """
        Detect MM high-risk cytogenetics (Signal 5 - MM-specific).
        
        Literature-based markers (MMRF has no cytogenetics data):
        - del(17p): HR=2.5 (ULTRA_HIGH_RISK)
        - t(4;14): HR=1.8 (HIGH_RISK)
        - 1q gain: HR=1.5 (HIGH_RISK)
        - t(11;14): HR=0.8 (VENETOCLAX_SENSITIVE - favorable)
        
        Args:
            cytogenetics: Dict like {"del_17p": True, "t_4_14": False}
            drug_class: Current drug class
            
        Returns:
            ResistanceSignalData with cytogenetic risk assessment
        """
        logger.info("Detecting MM cytogenetic abnormalities...")
        
        if not cytogenetics:
            return ResistanceSignalData(
                signal_type=ResistanceSignal.MM_CYTOGENETICS,
                detected=False,
                probability=0.0,
                confidence=0.0,
                rationale="No cytogenetics data provided (requires external data)",
                provenance={"signal_type": "MM_CYTOGENETICS", "status": "no_data"}
            )
        
        detected_abnormalities = []
        max_hazard_ratio = 1.0
        interpretations = []
        
        for cyto, present in cytogenetics.items():
            if present and cyto in MM_CYTOGENETICS:
                cyto_info = MM_CYTOGENETICS[cyto]
                detected_abnormalities.append({
                    "abnormality": cyto,
                    "hazard_ratio": cyto_info["hazard_ratio"],
                    "genes": cyto_info["genes"],
                    "interpretation": cyto_info["interpretation"],
                    "mechanism": cyto_info["mechanism"],
                    "rationale": cyto_info["rationale"]
                })
                max_hazard_ratio = max(max_hazard_ratio, cyto_info["hazard_ratio"])
                interpretations.append(cyto_info["interpretation"])
        
        detected = len(detected_abnormalities) > 0
        
        # Probability from hazard ratio
        if detected:
            probability = max_hazard_ratio / (max_hazard_ratio + 1.0)
            confidence = 0.70  # Literature-based, not validated
        else:
            probability = 0.0
            confidence = 0.0
        
        # Determine overall risk interpretation
        if "ULTRA_HIGH_RISK" in interpretations:
            risk_interpretation = "ULTRA_HIGH_RISK"
        elif "HIGH_RISK" in interpretations:
            risk_interpretation = "HIGH_RISK"
        else:
            risk_interpretation = "STANDARD_RISK"
        
        cyto_names = [c["abnormality"] for c in detected_abnormalities]
        rationale = (
            f"MM cytogenetics analysis: {len(detected_abnormalities)} abnormality(ies) detected. "
            f"{'DETECTED' if detected else 'Not detected'}: {', '.join(cyto_names) if cyto_names else 'none'}. "
            f"Max HR: {max_hazard_ratio:.2f}. "
            f"Risk interpretation: {risk_interpretation}."
        )
        
        provenance = {
            "signal_type": "MM_CYTOGENETICS",
            "detected_abnormalities": detected_abnormalities,
            "max_hazard_ratio": max_hazard_ratio,
            "risk_interpretation": risk_interpretation,
            "evidence_level": "LITERATURE_BASED",
            "validation_source": "IMWG_consensus",
            "note": "MMRF CoMMpass has no cytogenetics data - using literature values"
        }
        
        logger.info(f"MM cytogenetics signal: detected={detected}, abnormalities={cyto_names}, HR={max_hazard_ratio:.2f}")
        
        return ResistanceSignalData(
            signal_type=ResistanceSignal.MM_CYTOGENETICS,
            detected=detected,
            probability=float(probability),
            confidence=float(confidence),
            rationale=rationale,
            provenance=provenance
        )
    
    


    def _check_drug_class_resistance(
        self,
        mutations: List[Dict],
        drug_class: Optional[str]
    ) -> Dict:
        """
        Check for drug-class specific resistance mutations (Work Item 2).
        
        Detects PSMB5 mutations → PI resistance
        Detects CRBN mutations → IMiD resistance
        Detects CD38 loss → anti-CD38 resistance
        
        Args:
            mutations: List of patient mutations with 'gene' and optional 'protein_change' fields
            drug_class: Current drug class (e.g., "proteasome_inhibitor", "imid", "anti_cd38")
            
        Returns:
            Dict with:
                - detected: bool
                - mutations: List of detected resistance mutations
                - max_relative_risk: float (highest RR among detected mutations)
                - drug_class: str
        """
        if not drug_class or drug_class not in MM_RESISTANCE_MUTATIONS:
            return {
                "detected": False,
                "mutations": [],
                "max_relative_risk": 1.0,
                "drug_class": drug_class
            }
        
        class_mutations = MM_RESISTANCE_MUTATIONS[drug_class]
        detected_mutations = []
        
        for mutation in mutations:
            gene = mutation.get("gene", "").upper()
            if gene in class_mutations:
                gene_info = class_mutations[gene]
                
                # Check if mutation matches expected mutation types
                protein_change = mutation.get("protein_change", "").strip()
                mutation_type = mutation.get("mutation_type", "").lower()
                variant_class = mutation.get("variant_class", "").lower()
                
                expected_mutations = gene_info.get("mutations", [])
                matches = False
                
                if protein_change:
                    for expected in expected_mutations:
                        if expected.lower() in protein_change.lower() or protein_change.lower() in expected.lower():
                            matches = True
                            break
                
                if not matches and (mutation_type or variant_class):
                    for expected in expected_mutations:
                        if expected.lower() in mutation_type or expected.lower() in variant_class:
                            matches = True
                            break
                
                if not matches and gene in class_mutations:
                    matches = True  # Gene-level match
                
                if matches:
                    detected_mutations.append({
                        "gene": gene,
                        "mutation": mutation,
                        "mechanism": gene_info["mechanism"],
                        "relative_risk": gene_info["relative_risk"],
                        "confidence": gene_info["confidence"],
                        "validation_source": gene_info["validation_source"],
                        "rationale": gene_info["rationale"]
                    })
        
        max_relative_risk = max([m["relative_risk"] for m in detected_mutations]) if detected_mutations else 1.0
        
        return {
            "detected": len(detected_mutations) > 0,
            "mutations": detected_mutations,
            "max_relative_risk": max_relative_risk,
            "drug_class": drug_class
        }
    
    def _adjust_risk_for_treatment_line(
        self,
        base_probability: float,
        treatment_line: int,
        prior_therapies: Optional[List[str]],
        current_drug_class: Optional[str]
    ) -> Tuple[float, Dict]:
        """
        Adjust resistance probability based on treatment line context.
        
        Expert Opinion - Task 3:
        - 1st line: base probability
        - 2nd line: probability × 1.2 (clone evolution)
        - 3rd+ line: probability × 1.4 (heavily pre-treated)
        - Same-class prior: probability × 1.3 (cross-resistance)
        
        Returns:
            (adjusted_probability, adjustment_details)
        """
        line_multiplier = TREATMENT_LINE_MULTIPLIERS.get(
            min(treatment_line, 3),
            TREATMENT_LINE_MULTIPLIERS[3]
        )
        
        cross_resistance_applied = False
        if prior_therapies and current_drug_class:
            prior_classes = [p.lower().replace(" ", "_").replace("-", "_") for p in prior_therapies]
            current_class = current_drug_class.lower().replace(" ", "_").replace("-", "_")
            if current_class in prior_classes:
                line_multiplier *= CROSS_RESISTANCE_MULTIPLIER
                cross_resistance_applied = True
        
        # Apply multiplier but cap at 0.95
        adjusted_probability = min(0.95, base_probability * line_multiplier)
        
        adjustment_details = {
            "treatment_line": treatment_line,
            "line_multiplier": TREATMENT_LINE_MULTIPLIERS.get(min(treatment_line, 3), 1.0),
            "cross_resistance_applied": cross_resistance_applied,
            "cross_resistance_multiplier": CROSS_RESISTANCE_MULTIPLIER if cross_resistance_applied else 1.0,
            "final_multiplier": line_multiplier,
            "evidence_level": "EXPERT_OPINION",
            "prior_therapies": prior_therapies,
            "current_drug_class": current_drug_class
        }
        
        return adjusted_probability, adjustment_details
    
    
    async def predict_mm_resistance(
        self,
        mutations: List[Dict],
        drug_class: Optional[str] = None,
        treatment_history: Optional[List[Dict]] = None,
        treatment_line: int = 1,
        prior_therapies: Optional[List[str]] = None,
        cytogenetics: Optional[Dict[str, bool]] = None
    ) -> ResistancePrediction:
        """
        Predict MM-specific treatment resistance risk.
        
        Enhanced interface for MM using:
        - Validated gene-level markers (Proxy SAE): DIS3, TP53
        - Literature-based cytogenetics: del(17p), t(4;14), 1q gain
        - Treatment line context: adjusts risk for 2nd/3rd+ line
        - Cross-resistance: same-class prior therapy
        
        Args:
            mutations: List of patient mutations
            drug_class: Current drug class (PI, IMiD, anti-CD38)
            treatment_history: Optional treatment history
            treatment_line: Treatment line (1, 2, 3+)
            prior_therapies: List of prior drug classes
            cytogenetics: Dict of cytogenetic abnormalities (optional)
            
        Returns:
            ResistancePrediction with MM-specific risk assessment
        """
        logger.info(f"=== RESISTANCE PROPHET (MM): Starting prediction (line={treatment_line}) ===")
        
        signals_detected: List[ResistanceSignalData] = []
        warnings: List[str] = []
        
        # MM Signal 1: High-risk gene mutations
        mm_gene_signal = await self._detect_mm_high_risk_genes(
            mutations=mutations,
            drug_class=drug_class
        )
        signals_detected.append(mm_gene_signal)
        
        # MM Signal 2: Cytogenetics (if provided)
        if cytogenetics:
            mm_cyto_signal = await self._detect_mm_cytogenetics(
                cytogenetics=cytogenetics,
                drug_class=drug_class
            )
            signals_detected.append(mm_cyto_signal)
        else:
            warnings.append("CYTOGENETICS_NOT_PROVIDED")
        

        # MM Signal 3: Drug-class specific resistance mutations (Work Item 2)
        drug_class_resistance = self._check_drug_class_resistance(
            mutations=mutations,
            drug_class=drug_class
        )
        if drug_class_resistance["detected"]:
            # Create signal data for drug-class resistance
            detected_muts = drug_class_resistance["mutations"]
            max_rr = drug_class_resistance["max_relative_risk"]
            # Probability from relative risk (RR=5.0 → ~0.83, RR=3.5 → ~0.78, RR=2.0 → ~0.67)
            probability = max_rr / (max_rr + 1.0)
            # Confidence is average of mutation confidences
            avg_confidence = sum(m["confidence"] for m in detected_muts) / len(detected_muts) if detected_muts else 0.75
            
            gene_names = [m["gene"] for m in detected_muts]
            rationale = (
                f"Drug-class specific resistance mutations detected for {drug_class}: "
                f"{', '.join(gene_names)}. "
                f"Max relative risk: {max_rr:.2f}. "
                f"Mechanisms: {', '.join(set(m['mechanism'] for m in detected_muts))}."
            )
            
            provenance = {
                "signal_type": "MM_DRUG_CLASS_RESISTANCE",
                "detected_mutations": detected_muts,
                "max_relative_risk": max_rr,
                "drug_class": drug_class,
                "validation_source": detected_muts[0]["validation_source"] if detected_muts else "LITERATURE_ONLY"
            }
            
            mm_drug_class_signal = ResistanceSignalData(
                signal_type=ResistanceSignal.MM_DRUG_CLASS_RESISTANCE,
                detected=True,
                probability=float(probability),
                confidence=float(avg_confidence),
                rationale=rationale,
                provenance=provenance
            )
            signals_detected.append(mm_drug_class_signal)
            logger.info(f"Drug-class resistance signal: {gene_names} → {drug_class} (RR={max_rr:.2f})")
        else:
            # Still add signal but mark as not detected
            mm_drug_class_signal = ResistanceSignalData(
                signal_type=ResistanceSignal.MM_DRUG_CLASS_RESISTANCE,
                detected=False,
                probability=0.0,
                confidence=0.0,
                rationale=f"No drug-class specific resistance mutations detected for {drug_class or 'unknown'}",
                provenance={"signal_type": "MM_DRUG_CLASS_RESISTANCE", "drug_class": drug_class}
            )
            signals_detected.append(mm_drug_class_signal)
        
        
        # MM Signal 4: Pathway burden (mechanism-level prediction)
        if self.mm_pathway_service:
            try:
                pathway_burden = self.mm_pathway_service.compute_mm_pathway_burden(mutations)
                mechanism_vector = self.mm_pathway_service.compute_mm_mechanism_vector(pathway_burden)
                
                # Create pathway signal (if significant burden detected)
                max_burden = max([p.get("score", 0.0) for p in pathway_burden.values()])
                if max_burden > 0.3:  # Threshold for significant pathway burden
                    pathway_signal = ResistanceSignalData(
                        signal_type=ResistanceSignal.MM_DRUG_CLASS_RESISTANCE,  # Reuse signal type
                        detected=True,
                        probability=float(min(0.8, max_burden * 1.2)),  # Scale burden to probability
                        confidence=0.70,
                        rationale=f"Pathway burden detected: max={max_burden:.2f}. Mechanism vector: {[f'{v:.2f}' for v in mechanism_vector]}",
                        provenance={
                            "signal_type": "MM_PATHWAY_BURDEN",
                            "pathway_burden": {k: {"score": v["score"], "mutated_genes": v["mutated_genes"]} 
                                             for k, v in pathway_burden.items()},
                            "mechanism_vector": mechanism_vector
                        }
                    )
                    signals_detected.append(pathway_signal)
                    logger.info(f"Pathway burden signal: max={max_burden:.2f}, pathways={[k for k, v in pathway_burden.items() if v['score'] > 0.3]}")
            except Exception as e:
                logger.warning(f"Pathway burden computation failed: {e}")
                warnings.append("PATHWAY_SERVICE_ERROR")
        
# Count positive signals
        signal_count = sum(1 for sig in signals_detected if sig.detected)
        
        # Compute base probability
        base_probability = self._compute_resistance_probability(signals_detected)
        
        # Apply treatment line adjustment (Task 3)
        probability, line_adjustment_details = self._adjust_risk_for_treatment_line(
            base_probability=base_probability,
            treatment_line=treatment_line,
            prior_therapies=prior_therapies,
            current_drug_class=drug_class
        )
        
        # Stratify risk (MM uses same thresholds)
        risk_level = self._stratify_risk(probability, signal_count, ca125_available=False)
        
        # Confidence
        confidence, confidence_cap = self._compute_confidence(
            signals_detected=signals_detected,
            baseline_available=True,  # Gene-level doesn't need baseline
            ca125_available=False,
            signal_count=signal_count
        )
        
        # Urgency and actions
        urgency, actions = self._determine_mm_actions(risk_level, signal_count, signals_detected)
        
        # Get next-line options from ResistancePlaybookService (Task 1)
        next_line_options = []
        downstream_handoffs = {}
        detected_genes = []
        for sig in signals_detected:
            if sig.provenance.get("detected_genes"):
                detected_genes.extend([g["gene"] for g in sig.provenance["detected_genes"]])
            if sig.provenance.get("detected_abnormalities"):
                detected_genes.extend([a["abnormality"] for a in sig.provenance["detected_abnormalities"]])
        
        if self.resistance_playbook_service and risk_level != ResistanceRiskLevel.LOW:
            try:
                playbook_result = await self.resistance_playbook_service.get_next_line_options(
                    disease="myeloma",
                    detected_resistance=detected_genes,
                    current_regimen=None,  # Can be passed if available
                    current_drug_class=drug_class,
                    treatment_line=treatment_line,
                    prior_therapies=prior_therapies,
                    cytogenetics=cytogenetics
                )
                # Convert alternatives to dict format
                next_line_options = [
                    {
                        "drug": alt.drug,
                        "drug_class": alt.drug_class,
                        "rationale": alt.rationale,
                        "evidence_level": alt.evidence_level.value if hasattr(alt.evidence_level, 'value') else str(alt.evidence_level),
                        "priority": alt.priority,
                        "source_gene": alt.source_gene
                    }
                    for alt in playbook_result.alternatives
                ]
                # Capture downstream handoffs
                downstream_handoffs = {
                    agent: {
                        "agent": handoff.agent,
                        "action": handoff.action,
                        "payload": handoff.payload
                    }
                    for agent, handoff in playbook_result.downstream_handoffs.items()
                }
            except Exception as e:
                logger.error(f"Failed to fetch next-line options: {e}")
                warnings.append("PLAYBOOK_SERVICE_UNAVAILABLE")
        
        # Build rationale
        rationale = self._build_mm_rationale(signals_detected, probability, risk_level)
        
        # Add treatment line info to rationale
        if treatment_line > 1:
            rationale.append(f"Treatment line adjustment: {treatment_line}L (×{line_adjustment_details['final_multiplier']:.2f})")
        if line_adjustment_details.get("cross_resistance_applied"):
            rationale.append(f"Cross-resistance detected: prior {drug_class} exposure")
        
        # Provenance
        provenance = {
            "model_version": "resistance_prophet_mm_v2.0",
            "phase": "mm_gene_level_validated_with_playbook",
            "timestamp": datetime.utcnow().isoformat(),
            "method": "proxy_sae_gene_level",
            "validation_source": "MMRF_CoMMpass_GDC",
            "signals_used": [sig.signal_type.value for sig in signals_detected],
            "drug_class": drug_class,
            "treatment_line": treatment_line,
            "prior_therapies": prior_therapies,
            "cytogenetics_provided": cytogenetics is not None,
            "line_adjustment": line_adjustment_details,
            "playbook_version": "resistance_playbook_v1.0_dry"
        }
        
        logger.info(f"=== RESISTANCE PROPHET (MM): Risk={risk_level}, Probability={probability:.2f}, Signals={signal_count}, Line={treatment_line} ===")
        
        return ResistancePrediction(
            risk_level=risk_level,
            probability=probability,
            confidence=confidence,
            signals_detected=signals_detected,
            signal_count=signal_count,
            urgency=urgency,
            recommended_actions=actions,
            next_line_options=next_line_options,
            rationale=rationale,
            provenance=provenance,
            warnings=warnings,
            baseline_source="gene_level",
            baseline_penalty_applied=False,
            confidence_cap=confidence_cap
        )
    
    
    def _determine_mm_actions(
        self,
        risk_level: ResistanceRiskLevel,
        signal_count: int,
        signals_detected: List[ResistanceSignalData]
    ) -> Tuple[UrgencyLevel, List[Dict]]:
        """Determine MM-specific actions"""
        if risk_level == ResistanceRiskLevel.HIGH:
            urgency = UrgencyLevel.CRITICAL
            
            # Extract detected genes
            detected_genes = []
            for sig in signals_detected:
                if sig.provenance.get("detected_genes"):
                    detected_genes.extend([g["gene"] for g in sig.provenance["detected_genes"]])
            
            actions = [
                {
                    "action": "CONSIDER_INTENSIFICATION",
                    "timeframe": "at next treatment decision",
                    "rationale": f"High-risk gene(s) detected: {', '.join(detected_genes)}. Consider intensified therapy.",
                    "priority": 1
                },
                {
                    "action": "EVALUATE_TRIPLET_REGIMEN",
                    "timeframe": "within 2 weeks",
                    "rationale": "High-risk MM may benefit from triplet or quadruplet regimens.",
                    "priority": 2
                },
                {
                    "action": "CONSIDER_TRANSPLANT_ELIGIBILITY",
                    "timeframe": "if applicable",
                    "rationale": "Assess for autologous stem cell transplant in eligible patients.",
                    "priority": 3
                }
            ]
        elif risk_level == ResistanceRiskLevel.MEDIUM:
            urgency = UrgencyLevel.ELEVATED
            actions = [
                {
                    "action": "MONITOR_MRD",
                    "timeframe": "per protocol",
                    "rationale": "Monitor minimal residual disease status.",
                    "priority": 1
                },
                {
                    "action": "CONSIDER_MAINTENANCE_MODIFICATION",
                    "timeframe": "at maintenance phase",
                    "rationale": "Consider modified maintenance strategy.",
                    "priority": 2
                }
            ]
        else:
            urgency = UrgencyLevel.ROUTINE
            actions = [
                {
                    "action": "STANDARD_MONITORING",
                    "timeframe": "per standard of care",
                    "rationale": "Continue standard MM monitoring protocols.",
                    "priority": 1
                }
            ]
        
        return urgency, actions
    
    
    def _build_mm_rationale(
        self,
        signals_detected: List[ResistanceSignalData],
        probability: float,
        risk_level: ResistanceRiskLevel
    ) -> List[str]:
        """Build MM-specific rationale"""
        rationale = []
        
        rationale.append(
            f"MM resistance probability: {probability:.1%} ({risk_level.value} risk)"
        )
        
        for sig in signals_detected:
            status = "✓ DETECTED" if sig.detected else "✗ Not detected"
            rationale.append(f"{sig.signal_type.value}: {status}")
            
            if sig.provenance.get("detected_genes"):
                for gene_info in sig.provenance["detected_genes"]:
                    rationale.append(
                        f"  → {gene_info['gene']}: RR={gene_info['relative_risk']:.2f}, "
                        f"p={gene_info['p_value']:.4f} ({gene_info['mechanism']})"
                    )
        
        rationale.append("")
        rationale.append("Method: Proxy SAE (Gene-Level) - Validated on MMRF CoMMpass (N=219)")
        
        return rationale
    
    
    def _compute_resistance_probability(
        self,
        signals_detected: List[ResistanceSignalData]
    ) -> float:
        """
        Compute overall resistance probability from individual signals.
        """
        if not signals_detected:
            return 0.0
        
        # Filter to signals that were computed
        active_signals = [sig for sig in signals_detected if sig.confidence > 0.0]
        
        if not active_signals:
            return 0.0
        
        # Weighted average by confidence
        total_probability = sum(sig.probability * sig.confidence for sig in active_signals)
        total_weight = sum(sig.confidence for sig in active_signals)
        
        overall_probability = total_probability / total_weight if total_weight > 0 else 0.0
        
        return min(overall_probability, 1.0)
    
    
    def _stratify_risk(
        self,
        probability: float,
        signal_count: int,
        ca125_available: bool
    ) -> ResistanceRiskLevel:
        """
        Stratify resistance risk level.
        
        Manager Q9: HIGH if probability >=0.70 AND >=2 signals
                    MEDIUM if 0.50-0.69 OR exactly 1 signal
                    LOW if <0.50
        """
        # Manager Q15: If no CA-125 and <2 signals, cap at MEDIUM
        if not ca125_available and signal_count < 2 and probability >= self.HIGH_RISK_PROBABILITY:
            logger.info("Capping risk at MEDIUM due to insufficient CA-125 data and <2 signals")
            return ResistanceRiskLevel.MEDIUM
        
        # Manager Q9: Risk stratification
        if probability >= self.HIGH_RISK_PROBABILITY and signal_count >= self.MIN_SIGNALS_FOR_HIGH:
            return ResistanceRiskLevel.HIGH
        elif probability >= self.MEDIUM_RISK_PROBABILITY or signal_count == 1:
            return ResistanceRiskLevel.MEDIUM
        else:
            return ResistanceRiskLevel.LOW
    
    
    def _compute_confidence(
        self,
        signals_detected: List[ResistanceSignalData],
        baseline_available: bool,
        ca125_available: bool,
        signal_count: int
    ) -> Tuple[float, Optional[str]]:
        """
        Compute prediction confidence.
        
        Returns (confidence, confidence_cap) where confidence_cap is "MEDIUM" if capped.
        """
        confidence_cap = None
        
        # Start with average signal confidence
        active_signals = [sig for sig in signals_detected if sig.confidence > 0.0]
        if not active_signals:
            return 0.0, None
        
        avg_confidence = sum(sig.confidence for sig in active_signals) / len(active_signals)
        
        # Manager Q16: Penalty if baseline missing
        if not baseline_available:
            avg_confidence *= 0.80
            logger.info("Confidence penalty applied: baseline SAE missing")
        
        # Manager Q15: Cap at 0.60 if no CA-125 unless >=2 non-CA-125 signals
        if not ca125_available and signal_count < 2:
            if avg_confidence > 0.60:
                avg_confidence = 0.60
                confidence_cap = "MEDIUM"
                logger.info("Confidence capped at 0.60 (MEDIUM): insufficient CA-125 data")
        
        return min(avg_confidence, 1.0), confidence_cap
    
    
    def _determine_actions(
        self,
        risk_level: ResistanceRiskLevel,
        signal_count: int,
        signals_detected: List[ResistanceSignalData]
    ) -> Tuple[UrgencyLevel, List[Dict]]:
        """
        Determine urgency and recommended actions.
        """
        if risk_level == ResistanceRiskLevel.HIGH:
            urgency = UrgencyLevel.CRITICAL
            
            # Build mechanism-specific actions based on detected signals
            escaped_pathways = []
            for sig in signals_detected:
                if sig.escaped_pathways:
                    escaped_pathways.extend(sig.escaped_pathways)
            
            actions = [
                {
                    "action": "ESCALATE_IMAGING",
                    "timeframe": "within 1 week",
                    "rationale": f"HIGH resistance risk ({signal_count} signals). Early imaging may reveal subclinical progression.",
                    "priority": 1
                },
                {
                    "action": "CONSIDER_SWITCH",
                    "timeframe": "within 2 weeks",
                    "rationale": f"Mechanism-based resistance predicted. Review next-line options.",
                    "priority": 2,
                    "escaped_pathways": escaped_pathways if escaped_pathways else None
                },
                {
                    "action": "REVIEW_RESISTANCE_PLAYBOOK",
                    "timeframe": "within 1 week",
                    "rationale": f"Consult Resistance Playbook for mechanism-specific strategies.",
                    "priority": 3
                }
            ]
        elif risk_level == ResistanceRiskLevel.MEDIUM:
            urgency = UrgencyLevel.ELEVATED
            actions = [
                {
                    "action": "MONITOR_WEEKLY",
                    "timeframe": "4 weeks",
                    "rationale": f"MEDIUM resistance risk. Weekly monitoring recommended.",
                    "priority": 1
                },
                {
                    "action": "REASSESS",
                    "timeframe": "after 4 weeks",
                    "rationale": "Re-run Resistance Prophet to assess trend.",
                    "priority": 2
                }
            ]
        else:
            urgency = UrgencyLevel.ROUTINE
            actions = [
                {
                    "action": "ROUTINE_MONITORING",
                    "timeframe": "per standard of care",
                    "rationale": "LOW resistance risk. Continue routine monitoring.",
                    "priority": 1
                }
            ]
        
        return urgency, actions
    
    
    def _build_rationale(
        self,
        signals_detected: List[ResistanceSignalData],
        probability: float,
        risk_level: ResistanceRiskLevel
    ) -> List[str]:
        """Build human-readable rationale for prediction"""
        rationale = []
        
        # Overall assessment
        rationale.append(
            f"Overall resistance probability: {probability:.1%} ({risk_level.value} risk)"
        )
        
        # Signal-by-signal rationale
        for sig in signals_detected:
            status = "✓ DETECTED" if sig.detected else "✗ Not detected"
            rationale.append(f"{sig.signal_type.value}: {status}")
            
            # Add mechanism breakdown for DNA repair
            if sig.mechanism_breakdown:
                mb = sig.mechanism_breakdown
                rationale.append(
                    f"  → Mechanism breakdown: DDR={mb.ddr_pathway_change:+.2f}, "
                    f"HRR={mb.hrr_essentiality_change:+.2f}, exon={mb.exon_disruption_change:+.2f}"
                )
            
            # Add escaped pathways
            if sig.escaped_pathways:
                rationale.append(f"  → Escaped pathways: {', '.join(sig.escaped_pathways)}")
        
        return rationale
    
    
    def _get_population_baseline(self) -> Dict:
        """
        Return population average baseline SAE features.
        """
        return {
            "dna_repair_capacity": 0.50,
            "mechanism_vector": [0.50] * 7,
            "pathway_burden_ddr": 0.50,
            "essentiality_hrr": 0.50,
            "exon_disruption_score": 0.50,
            "source": "population_average",
            "is_population_average": True
        }


# Singleton instance
_resistance_prophet_service = None

def get_resistance_prophet_service(
    sae_service=None,
    ca125_service=None,
    treatment_line_service=None,
    resistance_playbook_service=None
) -> ResistanceProphetService:
    """Get or create singleton ResistanceProphetService instance"""
    global _resistance_prophet_service
    if _resistance_prophet_service is None:
        _resistance_prophet_service = ResistanceProphetService(
            sae_service=sae_service,
            ca125_service=ca125_service,
            treatment_line_service=treatment_line_service,
            resistance_playbook_service=resistance_playbook_service
        )
    return _resistance_prophet_service





