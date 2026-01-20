from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class InputCompleteness:
    """
    Lightweight L0/L1/L2 completeness classification for resistance.

    This is intentionally conservative and deterministic:
    - L0: pre-NGS / minimal context (no mutation list AND no serial biomarkers AND no partial markers)
    - L1: "mutations-only MVP" OR partial markers OR serial biomarkers (but not both mutations + markers)
    - L2: mutations + (serial biomarkers OR partial markers)
    """

    level: str  # "L0" | "L1" | "L2"
    confidence_cap: float
    warnings: List[str]


def compute_input_completeness(
    *,
    tumor_context: Optional[Dict[str, Any]] = None,
    ca125_history: Optional[List[Dict[str, Any]]] = None,
) -> InputCompleteness:
    tumor_context = tumor_context or {}
    somatic = tumor_context.get("somatic_mutations") or []

    has_mutations = bool(somatic)
    has_partial_markers = any(
        tumor_context.get(k) not in (None, "", [])
        for k in ("hrd_score", "tmb_score", "tmb", "msi_status", "msi")
    )
    has_ca125_series = bool(ca125_history) and len(ca125_history) >= 2

    warnings: List[str] = []
    if not has_mutations:
        warnings.append("MISSING_TUMOR_MUTATIONS")
    if not has_ca125_series:
        warnings.append("MISSING_CA125_HISTORY")

    # Conservative caps (mirrors the philosophy of progressive enhancement)
    # - L0: do not be confident
    # - L1: mutations-only MVP or markers-only => moderate only
    # - L2: mutations + markers => allow higher confidence (still conservative until Ring-2 outcomes validation)
    if has_mutations and (has_partial_markers or has_ca125_series):
        return InputCompleteness(level="L2", confidence_cap=0.8, warnings=warnings + ["INPUT_LEVEL_L2"])

    if has_mutations or has_partial_markers or has_ca125_series:
        return InputCompleteness(level="L1", confidence_cap=0.6, warnings=warnings + ["INPUT_LEVEL_L1"])

    return InputCompleteness(level="L0", confidence_cap=0.4, warnings=warnings + ["INPUT_LEVEL_L0"])


