"""
Ovarian Signal Detectors
Encapsulates Ovarian-specific resistance logic:
1. DNA Repair Restoration (Positive Delta) - The "Reversion" Signal
2. Pathway Escape (Target Loss) - The "Downregulation" Signal

Refactored from monolithic ResistanceProphetService.
"""

from typing import Dict, List, Optional
import logging

from api.services.resistance_prophet.schemas import (
    ResistanceSignalData, ResistanceSignal, MechanismBreakdown
)
from api.services.resistance_prophet.constants import (
    DNA_REPAIR_THRESHOLD, PATHWAY_ESCAPE_THRESHOLD,
    WEIGHT_PATIENT_BASELINE, WEIGHT_POPULATION_BASELINE,
    PATHWAY_CONTRIBUTIONS, DRUG_PATHWAY_TARGETS,
    OV_HIGH_RISK_GENES, PATHWAY_NAMES
)


logger = logging.getLogger(__name__)

import math


async def detect_restoration(
    current_sae: Dict,
    baseline_sae: Dict
) -> ResistanceSignalData:
    """
    Detect DNA Repair Restoration (Signal 1 - Phenotypic).
    
    Logic:
    DNA Repair Capacity Score = Deficiency Score (High = High Deficiency/Sensitive).
    Restoration (Resistance) = Deficiency DROPS (Score goes High -> Low).
    
    restoration_delta = baseline_deficiency - current_deficiency
    Restoration Detected if delta > Threshold.
    
    Ref: MANAGER_ANSWERS_TO_ZO_SAE_QUESTIONS.md (C7, R2)
    """
    logger.info("Detecting DNA_REPAIR_RESTORATION (OV) - explicit deficiency logic...")
    
    # Explicit Naming: Score is Deficiency
    if not current_sae or not baseline_sae:
        return ResistanceSignalData(
            signal_type=ResistanceSignal.DNA_REPAIR_RESTORATION,
            detected=False,
            probability=0.0,
            confidence=0.0,
            rationale="SAE features unavailable for restoration analysis",
            provenance={"status": "missing_sae_features"},
            baseline_reliability=1.0
        )

    current_deficiency = current_sae.get("dna_repair_capacity", 0.5)
    baseline_deficiency = baseline_sae.get("dna_repair_capacity", 0.5)
    
    # Calculate Delta (Positive Drop = Restoration/Resistance)
    restoration_delta = baseline_deficiency - current_deficiency
    
    # Check reliability
    is_pop_baseline = baseline_sae.get("is_population_average", False)
    reliability = WEIGHT_POPULATION_BASELINE if is_pop_baseline else WEIGHT_PATIENT_BASELINE
    
    # Detection Threshold
    detected = restoration_delta > DNA_REPAIR_THRESHOLD
    
    # Probability (Sigmoid): Smooth transition around threshold
    # Matches legacy shape but with corrected sign (restoration_delta)
    # If delta == threshold, prob = 0.5
    # If delta >> threshold, prob -> 1.0
    try:
        probability = 1.0 / (1.0 + math.exp(-10 * (restoration_delta - DNA_REPAIR_THRESHOLD)))
    except OverflowError:
        probability = 0.0 if restoration_delta < DNA_REPAIR_THRESHOLD else 1.0
        
    probability = float(max(0.0, min(1.0, probability)))
    
    # Confidence (do not zero out - capture signal quality)
    base_confidence = 0.85  # Max confidence for this signal type
    confidence = float(base_confidence * reliability)
        
    # Build Rationale
    rationale = (
        f"DNA repair deficiency change: {restoration_delta:+.2f} "
        f"(baseline={baseline_deficiency:.2f} → current={current_deficiency:.2f}). "
        f"{'Restoration detected' if detected else 'No significant restoration'} "
        f"(threshold={DNA_REPAIR_THRESHOLD:+.2f}). "
        f"Baselined against {'Population (Penalty Applied)' if is_pop_baseline else 'Patient History'}."
    )
    
    # Mechanism Breakdown (components are typically current - baseline in legacy schemas)
    # We clarify directionality in the provenance
    breakdown = MechanismBreakdown(
        ddr_pathway_change=current_sae.get("pathway_burden_ddr", 0) - baseline_sae.get("pathway_burden_ddr", 0),
        hrr_essentiality_change=current_sae.get("essentiality_hrr", 0) - baseline_sae.get("essentiality_hrr", 0),
        exon_disruption_change=current_sae.get("exon_disruption_score", 0) - baseline_sae.get("exon_disruption_score", 0),
        pathway_contributions=PATHWAY_CONTRIBUTIONS
    )
    
    return ResistanceSignalData(
        signal_type=ResistanceSignal.DNA_REPAIR_RESTORATION,
        detected=detected,
        probability=probability,
        confidence=confidence,
        rationale=rationale,
        provenance={
            "restoration_delta": restoration_delta,
            "baseline_deficiency": baseline_deficiency,
            "current_deficiency": current_deficiency,
            "threshold": DNA_REPAIR_THRESHOLD,
            "baseline_source": "population" if is_pop_baseline else "patient",
            "note": "Positive delta = Deficiency Dropping = Restoration"
        },
        mechanism_breakdown=breakdown,
        baseline_reliability=reliability
    )


async def detect_escape(
    current_sae: Dict,
    baseline_sae: Dict,
    drug_class: Optional[str]
) -> ResistanceSignalData:
    """
    Detect Pathway Escape / Target Loss (Signal 2 - Phenotypic).
    
    Logic:
    Escape = Target Pathway Burden DROPS significantly (tumor no longer relies on it).
    
    Example: 
    - Drug: Anti-VEGF
    - Baseline VEGF: 0.8
    - Current VEGF: 0.2
    - Result: TARGETLOST / ESCAPE
    """
    logger.info("Detecting PATHWAY_ESCAPE (OV)...")

    if not current_sae or not baseline_sae:
        return ResistanceSignalData(
            signal_type=ResistanceSignal.PATHWAY_ESCAPE,
            detected=False,
            probability=0.0,
            confidence=0.0,
            rationale="SAE features unavailable for escape analysis",
            provenance={"status": "missing_sae_features"},
            baseline_reliability=1.0
        )
    
    if not drug_class:
        return ResistanceSignalData(
            signal_type=ResistanceSignal.PATHWAY_ESCAPE,
            detected=False,
            probability=0.0,
            confidence=0.0,
            rationale="No drug class provided for pathway escape analysis",
            provenance={"status": "no_drug_class"},
            baseline_reliability=1.0
        )
        
    # Identify target pathways for this drug
    targets = []
    drug_key = drug_class.lower().replace(" ", "_").replace("-", "_")
    
    # Try direct match
    if drug_key in DRUG_PATHWAY_TARGETS:
        targets = DRUG_PATHWAY_TARGETS[drug_key]
    else:
        # Try suffix match
        for key, vals in DRUG_PATHWAY_TARGETS.items():
            if key in drug_key or drug_key in key:
                targets = vals
                break
                
    if not targets:
        return ResistanceSignalData(
            signal_type=ResistanceSignal.PATHWAY_ESCAPE,
            detected=False,
            probability=0.0,
            confidence=0.0,
            rationale=f"No target pathways mapped for class: {drug_class}",
            provenance={"status": "unknown_targets"},
            baseline_reliability=1.0
        )

    # Check for Target Loss
    current_vec = current_sae.get("mechanism_vector", [])
    baseline_vec = baseline_sae.get("mechanism_vector", [])
    
    # Assuming vector is indexed corresponding to PATHWAY_NAMES order in constants
    # For now, simplistic generic check since we don't have the explicit map index available
    # in constants.py (only names). 
    # TODO: In integration, ensure we have the Index Map. 
    # For V2 Refactor, avoiding complex mapping logic drift, we assume logic provided
    # in SAE service handles the vector properly. Here we will use a simplified assumption
    # or just placeholder logic if the vector indices aren't guaranteed.
    
    # SAFEGUARD: If vectors are empty/mismatched, abort
    if not current_vec or not baseline_vec or len(current_vec) != len(baseline_vec):
         return ResistanceSignalData(
            signal_type=ResistanceSignal.PATHWAY_ESCAPE,
            detected=False,
            probability=0.0,
            confidence=0.0,
            rationale="Mechanism vectors unavailable or mismatched",
            provenance={"status": "vector_error"},
            baseline_reliability=1.0
        )
        
    # Check reliability
    is_pop_baseline = baseline_sae.get("is_population_average", False)
    reliability = WEIGHT_POPULATION_BASELINE if is_pop_baseline else WEIGHT_PATIENT_BASELINE

    escaped_targets = []
    max_drop = 0.0
    
    # Create Index Map from Canonical Constants
    PATHWAY_INDEX = {name.upper(): i for i, name in enumerate(PATHWAY_NAMES)}
    
    # Validation: Ensure vector length matches canonical definition
    if len(current_vec) != len(PATHWAY_NAMES):
        logger.error(f"Mechanism vector length mismatch. Expected {len(PATHWAY_NAMES)}, got {len(current_vec)}")
        return ResistanceSignalData(
            signal_type=ResistanceSignal.PATHWAY_ESCAPE,
            detected=False,
            probability=0.0,
            confidence=0.0,
            rationale=f"Vector length mismatch (Exp {len(PATHWAY_NAMES)} vs {len(current_vec)})",
            provenance={"status": "vector_mismatch_error"},
            baseline_reliability=1.0
        )
    
    for target in targets:
        target_key = target.upper()
        if target_key in PATHWAY_INDEX:
            idx = PATHWAY_INDEX[target_key]
            # Since we validated length, simplistic index access is safe
            drop = baseline_vec[idx] - current_vec[idx] # Positive value = Drop
            if drop > PATHWAY_ESCAPE_THRESHOLD:
                escaped_targets.append(target)
                max_drop = max(max_drop, drop)
    
    detected = len(escaped_targets) > 0
    
    if detected:
        probability = min(0.95, 0.5 + (max_drop * 2.0))
        confidence = 0.80
    else:
        probability = 0.0
        confidence = 0.0
        
    rationale = (
        f"Target pathway analysis: {len(escaped_targets)} escaped. "
        f"{'ESCAPE DETECTED' if detected else 'Targets engaged'}: {', '.join(escaped_targets) if escaped_targets else 'None'}. "
        f"Max drop: {max_drop:.2f}."
    )
    
    return ResistanceSignalData(
        signal_type=ResistanceSignal.PATHWAY_ESCAPE,
        detected=detected,
        probability=float(probability),
        confidence=float(confidence),
        rationale=rationale,
        provenance={
            "escaped_targets": escaped_targets,
            "max_drop": max_drop,
            "threshold": PATHWAY_ESCAPE_THRESHOLD
        },
        escaped_pathways=escaped_targets,
        baseline_reliability=reliability
    )

async def detect_genomic_resistance(
    mutations: List[Dict],
    drug_class: Optional[str] = None
) -> ResistanceSignalData:
    """
    Detect Ovarian high-risk gene resistance (Signal 4).
    Uses OV_HIGH_RISK_GENES.
    
    CRITICAL LOGIC:
    - Filters by 'effect': "RESISTANCE" vs "SENSITIVITY".
    - "SENSITIVITY" genes (e.g. MBD4) do NOT contribute to Risk Probability.
    """
    logger.info("Detecting GENE_LEVEL_RESISTANCE (OV)...")
    
    if not mutations:
        return ResistanceSignalData(
            signal_type=ResistanceSignal.GENE_LEVEL_RESISTANCE,
            detected=False,
            probability=0.0,
            confidence=0.0,
            rationale="No mutations provided",
            provenance={"status": "no_mutations"}
        )
        
    patient_genes = {m.get("gene", "").upper() for m in mutations}
    
    detected_resistance_genes = []
    detected_sensitivity_genes = []
    
    max_risk_prob = 0.0
    
    for gene, info in OV_HIGH_RISK_GENES.items():
        if gene in patient_genes:
            effect = info.get("effect", "RESISTANCE")
            
            entry = {
                "gene": gene,
                "effect": effect,
                "mechanism": info.get("mechanism"),
                "rationale": info.get("rationale")
            }
            
            if effect == "RESISTANCE":
                detected_resistance_genes.append(entry)
                # Naive probability mapping for V2
                rr = info.get("relative_risk") or 1.5
                prob = rr / (rr + 1.0)
                max_risk_prob = max(max_risk_prob, prob)
            else:
                detected_sensitivity_genes.append(entry)
                
    # Determination:
    # Detected if we found RESISTANCE genes.
    # We report Sensitivity genes in provenance/rationale but they don't drive "Resistance Detected" flag directly
    # unless we want "Mixed Signal". For Prophet "Resistance", we flag bad news only.
    
    detected = len(detected_resistance_genes) > 0
    
    rationale_parts = []
    if detected:
        genes = ", ".join([g["gene"] for g in detected_resistance_genes])
        rationale_parts.append(f"Resistance driver(s) detected: {genes}.")
    
    if detected_sensitivity_genes:
        genes = ", ".join([g["gene"] for g in detected_sensitivity_genes])
        rationale_parts.append(f"Sensitivity marker(s) detected: {genes} (Positive Prognosis).")
        
    if not rationale_parts:
        rationale_parts.append("No genomic resistance drivers detected.")
        
    provenance = {
        "resistance_genes": detected_resistance_genes,
        "sensitivity_genes": detected_sensitivity_genes,
        "validation_source": "OV_Knowledge_Base"
    }
    
    return ResistanceSignalData(
        signal_type=ResistanceSignal.GENE_LEVEL_RESISTANCE,
        detected=detected,
        probability=float(max_risk_prob),
        confidence=0.90 if detected else 0.0,
        rationale=" ".join(rationale_parts),
        provenance=provenance,
        baseline_reliability=1.0 # Genomic data is reliable (not dependent on baseline)
    )
