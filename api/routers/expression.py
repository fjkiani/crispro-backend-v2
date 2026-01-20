"""
Expression ingestion (RUO).

Sprint 2 deliverable:
- Define schema + storage path so we can later enable OV expression features (e.g., MFAP4/EMT)
  without “flying blind”.

This is intentionally minimal:
- Stores small JSON payloads under `oncology-coPilot/oncology-backend-minimal/data/expression/`.
- No external calls, no DB.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/expression", tags=["expression"])


DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "expression"


class ExpressionIngestRequest(BaseModel):
    patient_id: str = Field(..., description="Patient ID (opaque; do not include PHI)")
    disease: Optional[str] = Field(None, description="Canonical disease key (optional)")
    assay: str = Field("rna_seq", description="Assay type, e.g., rna_seq, microarray")
    sample_id: Optional[str] = Field(None, description="Sample ID (optional)")
    expression: Dict[str, float] = Field(
        ...,
        description="Gene -> expression value (TPM/FPKM/log2/etc). Keep small (subset) for now.",
    )
    units: str = Field("TPM", description="Units for expression values")
    notes: Optional[str] = Field(None, description="RUO notes (free text)")


class ExpressionIngestResponse(BaseModel):
    status: str
    stored_path: str
    stored_at: str


@router.post("/ingest", response_model=ExpressionIngestResponse)
def ingest_expression(req: ExpressionIngestRequest) -> ExpressionIngestResponse:
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)

        safe_patient = "".join([c for c in req.patient_id if c.isalnum() or c in ("-", "_")])[:80]
        safe_sample = "".join([c for c in (req.sample_id or "sample") if c.isalnum() or c in ("-", "_")])[:80]
        ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")

        out_path = DATA_DIR / f"{safe_patient}__{safe_sample}__{ts}.json"

        payload: Dict[str, Any] = req.model_dump()
        payload["stored_at"] = datetime.utcnow().isoformat()
        out_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

        return ExpressionIngestResponse(status="ok", stored_path=str(out_path), stored_at=payload["stored_at"])
    except Exception as e:
        logger.error(f"Expression ingest failed: {e}")
        raise HTTPException(status_code=500, detail="Expression ingest failed")

































