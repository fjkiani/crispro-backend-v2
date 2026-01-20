"""Canonical resistance contract.

Goal: one stable response shape that can be emitted by:
- /api/resistance/predict
- /api/care/* resistance endpoints
- /api/complete_care/v2 (when include_resistance*)

This is intentionally conservative and does not make clinical claims. It standardizes:
- what we detected (mechanisms)
- what we recommend (actions)
- why we believe it (evidence tier + receipts)
- provenance (run metadata)
"""

from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional


class Receipt(BaseModel):
    name: str
    path: Optional[str] = None
    note: Optional[str] = None


class MechanismCard(BaseModel):
    mechanism: str = Field(..., description="Mechanism name (e.g., NF1_loss_MAPK)")
    detected: bool = True
    rationale: str

    # Evidence
    evidence_level: Optional[str] = None  # legacy (service-specific)
    evidence_tier: Optional[str] = None   # manager-facing Tier 1–5

    # Optional metadata
    biomarkers: Optional[List[str]] = None
    source: Optional[str] = None


class ActionCard(BaseModel):
    action_type: str = Field(..., description="treatment|monitoring|testing|handoff")
    title: str
    rationale: str

    evidence_level: Optional[str] = None
    evidence_tier: Optional[str] = None

    payload: Dict[str, Any] = Field(default_factory=dict)


class ResistanceContract(BaseModel):
    endpoint: str

    # risk can be absent for pure playbooks
    risk_level: Optional[str] = None
    probability: Optional[float] = None
    confidence: Optional[float] = None

    mechanisms: List[MechanismCard] = Field(default_factory=list)
    actions: List[ActionCard] = Field(default_factory=list)

    receipts: List[Receipt] = Field(default_factory=list)
    provenance: Dict[str, Any] = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)
