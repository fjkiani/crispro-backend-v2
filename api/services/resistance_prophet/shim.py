"""
Legacy Serialization Shim
Adapts V2 Internal Schema (snake_case) to Legacy Public Schema (Concatenated).
Used by ResistanceProphetService to maintain backward compatibility.
"""

from typing import Dict, Any, List
from enum import Enum
from dataclasses import asdict

from api.services.resistance_prophet.schemas import (
    ResistancePrediction, ResistanceSignalData, ResistanceSignal,
    ResistanceRiskLevel, UrgencyLevel
)

def _map_risk_level(level: ResistanceRiskLevel) -> str:
    """Pass-through usually, but ensures string value"""
    return level.value

def _map_signal_enum(sig_type: ResistanceSignal) -> str:
    """Map internal Enums to Legacy concatenated strings."""
    mapping = {
        ResistanceSignal.DNA_REPAIR_RESTORATION: "DNAREPAIRRESTORATION",
        ResistanceSignal.PATHWAY_ESCAPE: "PATHWAYESCAPE",
        ResistanceSignal.CA125_KINETICS: "CA125KINETICS",
        ResistanceSignal.CYTOGENETIC_ABNORMALITY: "MMCYTOGENETICS",
        ResistanceSignal.DRUG_CLASS_RESISTANCE: "MMDRUGCLASSRESISTANCE",
        # GENE_LEVEL_RESISTANCE -> EXCLUDED (Found in MM logic as MMHIGHRISKGENE?)
        # Legacy MM had MMHIGHRISKGENE. Our V2 uses GENE_LEVEL_RESISTANCE.
        # We map it to MMHIGHRISKGENE if present, assuming consumers handle it.
        # But instructions said "Exclude Gene Signal... or safe place".
        # We will try mapping to MMHIGHRISKGENE for MM context if possible?
        # Re-reading instructions: "Keep GENE_LEVEL_RESISTANCE excluded...".
        # Okay, we will exclude it from the main `signalsdetected` list if it's Gene Level.
        # UNLESS it's MM? Legacy had `MMHIGHRISKGENE`.
        # V2 uses generic `GENE_LEVEL_RESISTANCE`.
        # If we exclude it, we lose the signal.
        # Strict adherence to Gate Doc: "GENE_LEVEL_RESISTANCE | EXCLUDED".
        ResistanceSignal.GENE_LEVEL_RESISTANCE: None 
    }
    return mapping.get(sig_type, None)

def _map_provenance(internal_prov: Dict, sig_type: ResistanceSignal) -> Dict:
    """Map provenance keys to legacy keys."""
    legacy_prov = internal_prov.copy()
    
    if sig_type == ResistanceSignal.PATHWAY_ESCAPE:
        # Legacy expects: targetedpathways, escapedpathways...
        # Internal has: escaped_targets (list), max_drop, threshold
        # We need to construct legacy structure from internal one.
        # Note: 'targetedpathways' usually came from helper.
        # Here we just map what we have.
        if "escaped_targets" in internal_prov:
             # Legacy likely expects list of strings
             legacy_prov["targetedpathways"] = internal_prov.get("escaped_targets", []) 
        if "threshold" in internal_prov:
             legacy_prov["threshold"] = internal_prov["threshold"]
             
        # Remove internal keys
        legacy_prov.pop("escaped_targets", None)
        legacy_prov.pop("max_drop", None)
        
    return legacy_prov

def serialize_to_legacy(prediction: ResistancePrediction) -> Dict[str, Any]:
    """
    Convert V2 Prediction object to Legacy Dict format.
    """
    legacy_signals = []
    
    for sig in prediction.signals_detected:
        legacy_enum = _map_signal_enum(sig.signal_type)
        if not legacy_enum:
            # Skip signals that act as "New Features" breaking legacy enum contract
            continue
            
        # Flattened signal object
        sig_dict = {
            "signaltype": legacy_enum,
            "detected": sig.detected,
            "probability": sig.probability,
            "confidence": sig.confidence,
            "rationale": sig.rationale,
            "provenance": _map_provenance(sig.provenance, sig.signal_type)
        }
        
        # Optional fields flattened
        if sig.mechanism_breakdown:
            sig_dict["mechanismbreakdown"] = asdict(sig.mechanism_breakdown)
        if sig.escaped_pathways:
            sig_dict["escapedpathways"] = sig.escaped_pathways
        if sig.mechanism_alignment:
            sig_dict["mechanismalignment"] = sig.mechanism_alignment
            
        legacy_signals.append(sig_dict)

    # Top Level Mapping
    return {
        "risklevel": prediction.risk_level.value,
        "probability": prediction.probability,
        "confidence": prediction.confidence,
        "signalsdetected": legacy_signals,
        "signalcount": len(legacy_signals), # Recalculate based on filtered list
        "urgency": prediction.urgency.value,
        "recommendedactions": prediction.recommended_actions, # List[Dict] (assume dicts are safe)
        "nextlineoptions": prediction.next_line_options,
        "rationale": prediction.rationale,
        "provenance": prediction.provenance,
        "warnings": prediction.warnings,
        "baselinesource": prediction.baseline_source,
        "baselinepenaltyapplied": prediction.baseline_penalty_applied,
        "confidencecap": prediction.confidence_cap,
        "driveralerts": [asdict(a) for a in prediction.driver_alerts],
        "genomicalertcontext": prediction.genomic_alert_context
    }
