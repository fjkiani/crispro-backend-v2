"""
FDA/Guideline Mapping: disease→on-label drug classes.

Research-mode stub; replace with curated tables.
"""
from typing import Dict, Set


_MM_ON_LABEL: Set[str] = {"IMiD", "Proteasome inhibitor", "Anti-CD38"}


def is_on_label(disease: str, drug_class: str) -> bool:
    d = (disease or "").strip().lower()
    if d in {"multiple myeloma", "mm"}:
        return drug_class in _MM_ON_LABEL
    return False


