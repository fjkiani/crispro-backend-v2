"""
IO Safest Selection Service (RUO)
================================

Purpose:
Given a patient's IO eligibility signals (benefit-side) and patient risk factors
(harm-side), recommend a safest IO regimen among candidates.

This service intentionally separates:
- **Eligibility**: should we consider IO at all? (MSI/TMB/PD-L1/hypermutator inference)
- **Safety selection**: among eligible IO drugs, which is safest (irAE profile + patient factors)

RUO: Research Use Only. Not medical advice.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set

from api.services.toxicity_pathway_mappings import compare_io_drugs, select_safest_io


HYPERMUTATOR_GENES: Set[str] = {"POLE", "POLD1", "MBD4"}


def _safe_int(x: Any) -> Optional[int]:
    try:
        if x is None:
            return None
        return int(x)
    except Exception:
        return None


def _safe_float(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        return float(x)
    except Exception:
        return None


def _upper(x: Any) -> str:
    return str(x or "").strip().upper()


def _extract_gene_symbols(mutations: Any) -> List[str]:
    genes: List[str] = []
    if not isinstance(mutations, list):
        return genes
    for m in mutations:
        if isinstance(m, dict):
            g = m.get("gene") or m.get("geneSymbol") or m.get("gene_symbol")
            if g:
                genes.append(str(g).strip().upper())
    return genes


def _get_nested(d: Dict[str, Any], path: List[str]) -> Any:
    cur: Any = d
    for k in path:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(k)
    return cur


def _extract_pd_l1_cps(tumor_context: Dict[str, Any]) -> Optional[float]:
    # Support flat, nested, and biomarkers shapes
    return (
        _safe_float(tumor_context.get("pd_l1_cps"))
        or _safe_float(_get_nested(tumor_context, ["pd_l1", "cps"]))
        or _safe_float(_get_nested(tumor_context, ["biomarkers", "pd_l1_cps"]))
    )


def _extract_mmr_status(tumor_context: Dict[str, Any]) -> str:
    return _upper(tumor_context.get("mmr_status") or _get_nested(tumor_context, ["biomarkers", "mmr_status"]))


def _extract_msi_status(tumor_context: Dict[str, Any]) -> str:
    return _upper(
        tumor_context.get("msi_status")
        or tumor_context.get("msi")
        or _get_nested(tumor_context, ["biomarkers", "msi_status"])
    )


@dataclass
class IOEligibility:
    eligible: bool
    signals: List[str]
    evidence_gap: Optional[str] = None
    quality: str = "unknown"  # measured | inferred | insufficient
    needs_confirmatory_biomarkers: Optional[List[str]] = None


def assess_io_eligibility(
    tumor_context: Optional[Dict[str, Any]],
    *,
    germline_mutations: Optional[List[Dict[str, Any]]] = None,
) -> IOEligibility:
    tumor_context = tumor_context or {}

    signals: List[str] = []

    tmb = _safe_float(tumor_context.get("tmb"))
    msi_status = _extract_msi_status(tumor_context)
    mmr_status = _extract_mmr_status(tumor_context)
    pd_l1_cps = _extract_pd_l1_cps(tumor_context)

    somatic_mutations = tumor_context.get("somatic_mutations") or []
    genes = set(_extract_gene_symbols(somatic_mutations))

    if germline_mutations:
        genes |= set(_extract_gene_symbols(germline_mutations))

    # MSI/MMR signals
    if msi_status in {"MSI-H", "MSI-HIGH"}:
        signals.append("MSI_HIGH")
    if mmr_status in {"DEFICIENT", "DMMR", "LOSS"}:
        signals.append("DMMR")

    # TMB signals
    if tmb is not None and tmb >= 20:
        signals.append("TMB_HIGH_20")
    elif tmb is not None and tmb >= 10:
        signals.append("TMB_HIGH_10")

    # PD-L1 signal (indication dependent)
    if pd_l1_cps is not None and pd_l1_cps >= 1:
        signals.append("PDL1_POSITIVE_CPS")

    # Hypermutator inference (proxy when TMB missing)
    if genes & HYPERMUTATOR_GENES:
        signals.append(f"HYPERMUTATOR_INFERRED:{','.join(sorted(genes & HYPERMUTATOR_GENES))}")

    eligible = len(signals) > 0

    measured_signals = {"MSI_HIGH", "DMMR", "TMB_HIGH_10", "TMB_HIGH_20"}
    has_measured = any(s in measured_signals for s in signals)

    evidence_gap = None
    quality = "insufficient"
    needs_confirmatory: Optional[List[str]] = None

    if not eligible:
        evidence_gap = "No IO eligibility signals found (need MSI/TMB/PD-L1 or hypermutator evidence)."
        quality = "insufficient"
        needs_confirmatory = ["tmb", "msi_status", "mmr_status", "pd_l1_cps"]
    elif has_measured:
        quality = "measured"
    else:
        # Only supportive signals (PD-L1 and/or hypermutator)
        quality = "inferred"
        evidence_gap = (
            "Eligibility inferred from supportive signals (PD-L1 and/or hypermutator). "
            "Confirm with measured TMB/MSI/MMR when feasible."
        )
        needs_confirmatory = ["tmb", "msi_status", "mmr_status"]

    return IOEligibility(
        eligible=eligible,
        signals=signals,
        evidence_gap=evidence_gap,
        quality=quality,
        needs_confirmatory_biomarkers=needs_confirmatory,
    )


def recommend_io_regimens(
    *,
    patient_context: Optional[Dict[str, Any]] = None,
    tumor_context: Optional[Dict[str, Any]] = None,
    germline_mutations: Optional[List[Dict[str, Any]]] = None,
    eligible_drugs_override: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Recommend IO regimens emphasizing safest selection (RUO).

    patient_context supports:
      - age: int
      - autoimmune_history: list[str]
      - organ_risk_flags: list[str] (optional; e.g., ["prior_pneumonitis"])

    tumor_context supports:
      - tmb: float
      - msi_status / mmr_status
      - pd_l1_cps OR pd_l1.cps OR biomarkers.pd_l1_cps
      - somatic_mutations: list[dict]

    germline_mutations supports:
      - list[dict] with gene symbols (for hypermutator inference)
    """

    patient_context = patient_context or {}
    tumor_context = tumor_context or {}

    age = _safe_int(patient_context.get("age"))
    autoimmune_history = patient_context.get("autoimmune_history") or []
    if not isinstance(autoimmune_history, list):
        autoimmune_history = [str(autoimmune_history)]

    organ_risk_flags = patient_context.get("organ_risk_flags") or []
    if not isinstance(organ_risk_flags, list):
        organ_risk_flags = [str(organ_risk_flags)]

    eligibility = assess_io_eligibility(tumor_context, germline_mutations=germline_mutations)

    # Default candidate pool: conservative, mono-IO first.
    default_candidates = [
        "avelumab",
        "atezolizumab",
        "durvalumab",
        "nivolumab",
        "pembrolizumab",
        # high-risk options are present for "avoid" / transparency:
        "ipilimumab",
        "nivolumab+ipilimumab",
    ]
    eligible_drugs = eligible_drugs_override or default_candidates

    if not eligibility.eligible:
        return {
            "eligible": False,
            "eligibility_signals": eligibility.signals,
            "eligibility_quality": eligibility.quality,
            "needs_confirmatory_biomarkers": eligibility.needs_confirmatory_biomarkers,
            "evidence_gap": eligibility.evidence_gap,
            "selected_safest": None,
            "candidates": [],
            "ruo_disclaimer": "Research Use Only (RUO). This is decision support, not medical advice.",
            "provenance": {"service": "io_safest_selection_service", "version": "v1"},
        }

    safety = select_safest_io(
        eligible_drugs=eligible_drugs,
        patient_age=age,
        autoimmune_history=autoimmune_history if autoimmune_history else None,
        organ_risk_flags=organ_risk_flags if organ_risk_flags else None,
    )

    candidates = compare_io_drugs(eligible_drugs)

    return {
        "eligible": True,
        "eligibility_signals": eligibility.signals,
        "eligibility_quality": eligibility.quality,
        "needs_confirmatory_biomarkers": eligibility.needs_confirmatory_biomarkers,
        "evidence_gap": eligibility.evidence_gap,
        "selected_safest": safety,
        "candidates": candidates,
        "ruo_disclaimer": "Research Use Only (RUO). This is decision support, not medical advice.",
        "provenance": {"service": "io_safest_selection_service", "version": "v1"},
    }
