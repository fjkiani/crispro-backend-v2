"""Builders that convert existing services into the canonical ResistanceContract."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from api.contracts.resistance_contract import ResistanceContract, MechanismCard, ActionCard, Receipt
from api.services.resistance_evidence_tiers import map_resistance_evidence_to_manager_tier
from api.services.resistance_evidence_tiers import ManagerEvidenceTier
from api.orchestrator_runtime import get_code_version, get_contract_version


def _inputs_snapshot_hash(payload: Dict[str, Any]) -> str:
    """Deterministically hash inputs for reproducibility receipts."""
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def _genes_from_tumor_context(tumor_context: Dict[str, Any]) -> List[str]:
    muts = tumor_context.get("somatic_mutations") or []
    genes = []
    for m in muts:
        g = (m.get("gene") or "").strip()
        if g:
            genes.append(g.upper())
    return sorted(set(genes))


def contract_from_playbook_result(
    *,
    endpoint: str,
    disease_canonical: str,
    tumor_context: Dict[str, Any],
    playbook_disease_key: str,
    playbook_result: Any,
    warnings: Optional[List[str]] = None,
    receipts: Optional[List[Receipt]] = None,
) -> ResistanceContract:
    warnings = warnings or []
    receipts = receipts or []

    detected_genes = _genes_from_tumor_context(tumor_context)

    mechanisms: List[MechanismCard] = []
    if detected_genes:
        mechanisms.append(
            MechanismCard(
                mechanism="mutation_panel",
                detected=True,
                biomarkers=detected_genes,
                rationale=f"Detected genes from tumor_context: {', '.join(detected_genes)}",
                evidence_tier="TIER_4",
                source="tumor_context.somatic_mutations",
            )
        )

    actions: List[ActionCard] = []

    # Alternatives
    for alt in getattr(playbook_result, "alternatives", []) or []:
        ev_level = alt.evidence_level
        actions.append(
            ActionCard(
                action_type="treatment",
                title=f"Consider alternative: {alt.drug}",
                rationale=alt.rationale,
                evidence_level=ev_level.value if hasattr(ev_level, "value") else str(ev_level),
                evidence_tier=map_resistance_evidence_to_manager_tier(ev_level).value,
                payload={
                    "drug": alt.drug,
                    "drug_class": alt.drug_class,
                    "priority": alt.priority,
                    "source_gene": alt.source_gene,
                    "requires": alt.requires,
                },
            )
        )

    # Regimen changes
    for rc in getattr(playbook_result, "regimen_changes", []) or []:
        ev_level = rc.evidence_level
        actions.append(
            ActionCard(
                action_type="treatment",
                title=f"Regimen change: {rc.from_regimen} → {rc.to_regimen}",
                rationale=rc.rationale,
                evidence_level=ev_level.value if hasattr(ev_level, "value") else str(ev_level),
                evidence_tier=map_resistance_evidence_to_manager_tier(ev_level).value,
                payload={
                    "from_regimen": rc.from_regimen,
                    "to_regimen": rc.to_regimen,
                },
            )
        )

    # Monitoring changes
    mon = getattr(playbook_result, "monitoring_changes", None)
    if mon:
        payload = {
            "mrd_frequency": getattr(mon, "mrd_frequency", None),
            "ctdna_targets": getattr(mon, "ctdna_targets", None),
            "imaging_frequency": getattr(mon, "imaging_frequency", None),
            "biomarker_frequency": getattr(mon, "biomarker_frequency", None),
            "bone_marrow_frequency": getattr(mon, "bone_marrow_frequency", None),
        }
        # only emit if something set
        if any(v is not None for v in payload.values()):
            actions.append(
                ActionCard(
                    action_type="monitoring",
                    title="Adjust monitoring",
                    rationale="Playbook monitoring adjustments",
                    payload=payload,
                )
            )

    # Downstream handoffs
    for name, handoff in (getattr(playbook_result, "downstream_handoffs", {}) or {}).items():
        actions.append(
            ActionCard(
                action_type="handoff",
                title=f"Downstream handoff: {name}",
                rationale=f"Handoff to {getattr(handoff, 'agent', name)}",
                payload={
                    "agent": getattr(handoff, "agent", name),
                    "action": getattr(handoff, "action", None),
                    "payload": getattr(handoff, "payload", {}) or {},
                },
            )
        )

    provenance = {
        # Canonical provenance fields (stable keys for UI + validators)
        "service_version": (getattr(playbook_result, "provenance", {}) or {}).get("service_version", "unknown")
        if isinstance(getattr(playbook_result, "provenance", None), dict)
        else "unknown",
        "run_id": hashlib.sha256(
            json.dumps(
                {
                    "endpoint": endpoint,
                    "disease": disease_canonical,
                    "playbook_disease": playbook_disease_key,
                    "detected_genes": detected_genes,
                },
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()[:16],
        "generated_at": datetime.utcnow().isoformat(),
        "disease_original": disease_canonical,
        "disease_normalized": disease_canonical,
        "code_version": get_code_version(),
        "contract_version": get_contract_version(),
        "inputs_snapshot_hash": _inputs_snapshot_hash(
            {
                "endpoint": endpoint,
                "disease": disease_canonical,
                "playbook_disease": playbook_disease_key,
                "tumor_context": tumor_context,
                "warnings": warnings,
            }
        ),
        "flags": warnings,
        # Context (still useful)
        "disease": disease_canonical,
        "playbook_disease": playbook_disease_key,
        "playbook_provenance": getattr(playbook_result, "provenance", {}) or {},
    }

    return ResistanceContract(
        endpoint=endpoint,
        mechanisms=mechanisms,
        actions=actions,
        receipts=receipts,
        provenance=provenance,
        warnings=warnings,
    )


def contract_for_missing_inputs(
    *,
    endpoint: str,
    disease_canonical: str,
    missing: List[str],
    warnings: Optional[List[str]] = None,
    receipts: Optional[List[Receipt]] = None,
) -> ResistanceContract:
    """
    Build a canonical ResistanceContract even when required inputs are missing (L0/L1).
    This prevents UI/schema drift and makes missing data explicit.
    """
    warnings = warnings or []
    receipts = receipts or []

    missing_flags = [f"MISSING:{m}" for m in missing]
    merged_warnings: List[str] = []
    for w in list(warnings) + missing_flags:
        if w and w not in merged_warnings:
            merged_warnings.append(w)

    provenance = {
        "service_version": "unknown",
        "run_id": hashlib.sha256(
            json.dumps({"endpoint": endpoint, "disease": disease_canonical, "missing": missing}, sort_keys=True).encode("utf-8")
        ).hexdigest()[:16],
        "generated_at": datetime.utcnow().isoformat(),
        "disease_original": disease_canonical,
        "disease_normalized": disease_canonical,
        "code_version": get_code_version(),
        "contract_version": get_contract_version(),
        "inputs_snapshot_hash": _inputs_snapshot_hash(
            {"endpoint": endpoint, "disease": disease_canonical, "missing": missing, "warnings": merged_warnings}
        ),
        "flags": merged_warnings,
        "disease": disease_canonical,
        "missing_inputs": missing,
    }

    return ResistanceContract(
        endpoint=endpoint,
        mechanisms=[],
        actions=[],
        receipts=receipts,
        provenance=provenance,
        warnings=merged_warnings,
    )


def _map_sl_evidence_tier_to_manager_tier(sl_evidence_tier: str | None) -> ManagerEvidenceTier:
    """
    Map Synthetic Lethality module evidence tiers to ManagerTier.

    Synthetic lethality currently emits coarse tiers like:
    - "I", "II", "III" or "Research"
    We map conservatively (research-mode safe defaults).
    """
    if not sl_evidence_tier:
        return ManagerEvidenceTier.TIER_5

    v = str(sl_evidence_tier).strip().lower()
    if v in ("i", "tier i", "tier 1", "fda", "guideline"):
        return ManagerEvidenceTier.TIER_1
    if v in ("ii", "tier ii", "tier 2", "rct", "clinical trial"):
        return ManagerEvidenceTier.TIER_2
    if v in ("iii", "tier iii", "tier 3", "cohort", "validated"):
        return ManagerEvidenceTier.TIER_3
    if v in ("literature", "trend"):
        return ManagerEvidenceTier.TIER_4
    return ManagerEvidenceTier.TIER_5


def action_cards_from_synthetic_lethality_result(*, sl_result: Any) -> List[ActionCard]:
    """
    Convert a Synthetic Lethality result into standardized ActionCards.

    This does NOT change any API responses yet; it is a contract-alignment helper
    to surface SL recommendations in the same UI surfaces as resistance actions.
    """
    recs = getattr(sl_result, "recommended_drugs", None) or []
    actions: List[ActionCard] = []

    for rec in recs:
        drug_name = getattr(rec, "drug_name", None) or getattr(rec, "drug", None) or "unknown"
        drug_class = getattr(rec, "drug_class", None) or "unknown"
        target_pathway = getattr(rec, "target_pathway", None) or "unknown"
        confidence = getattr(rec, "confidence", None)
        fda_approved = bool(getattr(rec, "fda_approved", False))
        mechanism = getattr(rec, "mechanism", None) or ""
        rationale_list = getattr(rec, "rationale", None) or []
        evidence_level = getattr(rec, "evidence_tier", None)  # legacy field name in SL module

        tier = _map_sl_evidence_tier_to_manager_tier(evidence_level)

        actions.append(
            ActionCard(
                action_type="treatment",
                title=f"Synthetic lethality candidate: {drug_name}",
                rationale=mechanism or ("; ".join([str(x) for x in rationale_list]) if rationale_list else "Synthetic lethality recommendation"),
                evidence_level=str(evidence_level) if evidence_level is not None else None,
                evidence_tier=tier.value,
                payload={
                    "drug": drug_name,
                    "drug_class": drug_class,
                    "target_pathway": target_pathway,
                    "confidence": float(confidence) if isinstance(confidence, (int, float)) else None,
                    "fda_approved": fda_approved,
                },
            )
        )

    return actions
