"""
IO Selection Router (RUO)
-------------------------
Exposes safest IO regimen selection as an API endpoint.

Notes:
- This endpoint is safety-focused: selects the safest IO option among candidates.
- Eligibility signals (MSI/TMB/PD-L1/hypermutator) are surfaced with a quality label
  (measured vs inferred) to avoid over-claiming.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from api.services.io_safest_selection_service import recommend_io_regimens


router = APIRouter(prefix="/api/io", tags=["io"])


class IOSelectRequest(BaseModel):
    patient_context: Optional[Dict[str, Any]] = Field(default=None)
    tumor_context: Optional[Dict[str, Any]] = Field(default=None)
    germline_mutations: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    eligible_drugs_override: Optional[List[str]] = Field(default=None)


@router.post("/select")
async def select_io(req: IOSelectRequest) -> Dict[str, Any]:
    return recommend_io_regimens(
        patient_context=req.patient_context,
        tumor_context=req.tumor_context,
        germline_mutations=req.germline_mutations or [],
        eligible_drugs_override=req.eligible_drugs_override,
    )
