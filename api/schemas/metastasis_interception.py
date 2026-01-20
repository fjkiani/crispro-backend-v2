"""
Pydantic schemas for Metastasis Interception (RUO).

This keeps the API contract stable while allowing the implementation to evolve.
We intentionally keep several fields flexible (Dict[str, Any]) because downstream
provenance/rationale objects are additive over time.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class MetastasisInterceptRequest(BaseModel):
    mission_step: str = Field(..., description="One of the 8 metastatic cascade steps")
    mutations: List[Dict[str, Any]] = Field(default_factory=list, description="Variant list; include gene and ideally chrom/pos/ref/alt")
    patient_id: Optional[str] = None
    disease: Optional[str] = None
    options: Dict[str, Any] = Field(default_factory=dict)


class MetastasisCandidate(BaseModel):
    sequence: str
    pam: str = "NGG"
    gc: float = 0.0
    efficacy_proxy: float = 0.0
    safety_score: float = 0.0
    assassin_score: float = 0.0
    provenance: Dict[str, Any] = Field(default_factory=dict)


class MetastasisInterceptResponse(BaseModel):
    mission_step: str
    mission_objective: str
    validated_target: Dict[str, Any]
    considered_targets: List[Dict[str, Any]] = Field(default_factory=list)
    candidates: List[MetastasisCandidate] = Field(default_factory=list)
    rationale: List[str] = Field(default_factory=list)
    provenance: Dict[str, Any] = Field(default_factory=dict)
