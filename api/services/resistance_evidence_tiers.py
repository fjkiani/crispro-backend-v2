"""Resistance evidence tier mapping.

This maps internal evidence vocabularies (playbook/prophet) into the manager-facing
Tier 1–5 doctrine used for resistance outputs.

Important: this is **not** the same as drug-efficacy evidence banding
(`supported/consider/insufficient`).
"""

from __future__ import annotations

from enum import Enum
from typing import Optional


class ManagerEvidenceTier(str, Enum):
    TIER_1 = "TIER_1"  # FDA/guideline on-label
    TIER_2 = "TIER_2"  # RCT-validated
    TIER_3 = "TIER_3"  # Cohort-validated (p<0.05) with pinned receipt
    TIER_4 = "TIER_4"  # Literature-supported / trend / association
    TIER_5 = "TIER_5"  # Mechanistic inference / preclinical / low evidence


def map_resistance_evidence_to_manager_tier(evidence: Optional[object]) -> ManagerEvidenceTier:
    """Map various evidence representations to ManagerEvidenceTier."""
    if evidence is None:
        return ManagerEvidenceTier.TIER_5

    # Enum types (e.g., EvidenceLevel)
    if hasattr(evidence, "value"):
        evidence = getattr(evidence, "value")

    key = str(evidence).strip().upper()

    # Normalize a few legacy spellings
    if key in {"LITERATURE_ONLY", "LITERATURE_BASED"}:
        return ManagerEvidenceTier.TIER_4

    mapping = {
        "STANDARD_OF_CARE": ManagerEvidenceTier.TIER_1,
        "FDA": ManagerEvidenceTier.TIER_1,
        "GUIDELINE": ManagerEvidenceTier.TIER_1,

        "CLINICAL_TRIAL": ManagerEvidenceTier.TIER_2,
        "RCT": ManagerEvidenceTier.TIER_2,

        "VALIDATED": ManagerEvidenceTier.TIER_3,

        # Default policy: TREND is not validated
        "TREND": ManagerEvidenceTier.TIER_4,

        "PRECLINICAL": ManagerEvidenceTier.TIER_5,
        "LOW_EVIDENCE": ManagerEvidenceTier.TIER_5,
        "EXPERT_OPINION": ManagerEvidenceTier.TIER_5,
    }

    return mapping.get(key, ManagerEvidenceTier.TIER_5)
