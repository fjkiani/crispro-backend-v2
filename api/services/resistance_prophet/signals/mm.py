"""
Myeloma Signal Detectors
Encapsulates MM-specific resistance logic:
1. High-Risk Genes (e.g., DIS3, TP53)
2. Cytogenetics (e.g., del(17p))
3. Drug-Class Specific Mutations (e.g., PSMB5)

Refactored from monolithic ResistanceProphetService.
"""

from typing import List, Dict, Optional, Tuple
import logging

from api.services.resistance_prophet.schemas import (
    ResistanceSignalData, ResistanceSignal
)
from api.services.resistance_prophet.constants import (
    MM_HIGH_RISK_GENES, MM_CYTOGENETICS, MM_RESISTANCE_MUTATIONS
)

logger = logging.getLogger(__name__)

async def detect_mm_high_risk_genes(
    mutations: List[Dict],
    drug_class: Optional[str] = None
) -> ResistanceSignalData:
    """
    Detect MM high-risk gene mutations (Signal 4 - Gene Level).
    Uses MM_HIGH_RISK_GENES knowledge base.
    """
    logger.info("Detecting GENE_LEVEL_RESISTANCE (MM)...")
    
    if not mutations:
        return ResistanceSignalData(
            signal_type=ResistanceSignal.GENE_LEVEL_RESISTANCE,
            detected=False,
            probability=0.0,
            confidence=0.0,
            rationale="No mutations provided for gene analysis",
            provenance={"signal_type": "GENE_LEVEL_RESISTANCE", "status": "no_mutations"}
        )
    
    # Extract gene names from mutations
    patient_genes = {m.get("gene", "").upper() for m in mutations}
    
    # Check for high-risk gene mutations
    detected_high_risk = []
    total_relative_risk = 0.0
    max_relative_risk = 0.0
    weighted_confidence = 0.0
    
    for gene, info in MM_HIGH_RISK_GENES.items():
        if gene in patient_genes and info.get("confidence", 0) > 0:
            detected_high_risk.append({
                "gene": gene,
                "relative_risk": info.get("relative_risk"),
                "p_value": info.get("p_value"),
                "mechanism": info.get("mechanism"),
                "rationale": info.get("rationale"),
                "drug_classes_affected": info.get("drug_classes_affected", [])
            })
            rr = info.get("relative_risk") or 1.0
            max_relative_risk = max(max_relative_risk, rr)
            weighted_confidence += info.get("confidence", 0.5)
    
    detected = len(detected_high_risk) > 0
    
    # Compute probability from relative risk
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
        f"Gene-level analysis: {len(detected_high_risk)} gene(s) detected. "
        f"{'DETECTED' if detected else 'Not detected'}: {', '.join(gene_names) if gene_names else 'none'}. "
        f"Max RR: {max_relative_risk:.2f}. "
        f"Drug relevance: {'YES' if drug_relevant else 'NO'}."
    )
    
    provenance = {
        "signal_type": "GENE_LEVEL_RESISTANCE",
        "detected_genes": detected_high_risk,
        "patient_genes_checked": list(patient_genes & set(MM_HIGH_RISK_GENES.keys())),
        "max_relative_risk": max_relative_risk,
        "drug_class": drug_class,
        "drug_relevant": drug_relevant,
        "validation_source": "MMRF_CoMMpass_GDC",
        "method": "gene_list_lookup"
    }
    
    return ResistanceSignalData(
        signal_type=ResistanceSignal.GENE_LEVEL_RESISTANCE,
        detected=detected,
        probability=float(probability),
        confidence=float(confidence),
        rationale=rationale,
        provenance=provenance
    )


async def detect_mm_cytogenetics(
    cytogenetics: Dict[str, bool],
    drug_class: Optional[str] = None
) -> ResistanceSignalData:
    """
    Detect MM high-risk cytogenetics (Signal 5).
    Uses MM_CYTOGENETICS knowledge base.
    """
    logger.info("Detecting CYTOGENETIC_ABNORMALITY (MM)...")
    
    if not cytogenetics:
        return ResistanceSignalData(
            signal_type=ResistanceSignal.CYTOGENETIC_ABNORMALITY,
            detected=False,
            probability=0.0,
            confidence=0.0,
            rationale="No cytogenetics data provided",
            provenance={"signal_type": "CYTOGENETIC_ABNORMALITY", "status": "no_data"}
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
        confidence = 0.70  # Literature-based
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
        f"Cytogenetics analysis: {len(detected_abnormalities)} abnormality(ies). "
        f"{'DETECTED' if detected else 'Not detected'}: {', '.join(cyto_names) if cyto_names else 'none'}. "
        f"Risk: {risk_interpretation}."
    )
    
    provenance = {
        "signal_type": "CYTOGENETIC_ABNORMALITY",
        "detected_abnormalities": detected_abnormalities,
        "max_hazard_ratio": max_hazard_ratio,
        "risk_interpretation": risk_interpretation,
        "evidence_level": "LITERATURE_BASED"
    }
    
    return ResistanceSignalData(
        signal_type=ResistanceSignal.CYTOGENETIC_ABNORMALITY,
        detected=detected,
        probability=float(probability),
        confidence=float(confidence),
        rationale=rationale,
        provenance=provenance
    )
