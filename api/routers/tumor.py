"""
Tumor Context Router for Sporadic Cancer Strategy

Endpoints:
- POST /api/tumor/quick_intake: Level 0 intake (no NGS report)
- POST /api/tumor/ingest_ngs: Level 2 NGS report parsing (Foundation/Tempus)
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any
import hashlib
from datetime import datetime

from ..schemas.tumor_context import (
    QuickIntakeRequest,
    QuickIntakeResponse,
    IngestNGSRequest,
    IngestNGSResponse,
    TumorContext,
    SomaticMutation
)
from ..services.tumor_quick_intake import generate_level0_tumor_context
# from ..services.tumor_ngs_parser import parse_foundation_report, parse_tempus_report  # Day 3

router = APIRouter(prefix="/api/tumor", tags=["tumor"])


@router.post("/quick_intake", response_model=QuickIntakeResponse)
async def quick_intake(request: QuickIntakeRequest) -> QuickIntakeResponse:
    """
    Level 0/1 Quick Intake (no NGS report required).
    
    Uses disease priors + platinum response proxy to estimate tumor biomarkers
    for sporadic cancer patients without NGS reports.
    
    **Level 0:** Disease priors only (no manual inputs)
    **Level 1:** Partial manual inputs (TMB/MSI/HRD/mutations)
    
    Returns:
        QuickIntakeResponse with estimated TumorContext and confidence cap
    """
    try:
        # Generate tumor context using disease priors
        tumor_context, provenance, confidence_cap, recommendations = await generate_level0_tumor_context(
            cancer_type=request.cancer_type,
            stage=request.stage,
            line=request.line,
            platinum_response=request.platinum_response,
            manual_tmb=request.tmb,
            manual_msi=request.msi_status,
            manual_hrd=request.hrd_score,
            manual_mutations=request.somatic_mutations
        )
        
        return QuickIntakeResponse(
            tumor_context=tumor_context,
            provenance=provenance,
            confidence_cap=confidence_cap,
            recommendations=recommendations
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Quick intake failed: {str(e)}")


@router.post("/ingest_ngs", response_model=IngestNGSResponse)
async def ingest_ngs(request: IngestNGSRequest) -> IngestNGSResponse:
    """
    Level 2 NGS Report Ingestion (Foundation Medicine / Tempus).
    
    **Preferred:** Provide `report_json` (bypasses PDF parsing)
    **Fallback:** Provide `report_file` (base64 PDF, slower parsing)
    
    Returns:
        IngestNGSResponse with parsed TumorContext from NGS report
    """
    # TODO: Day 3 implementation
    raise HTTPException(
        status_code=501,
        detail="NGS report ingestion will be implemented on Day 3. Use quick_intake for now."
    )
    
    # # Day 3: Uncomment when parsers are ready
    # try:
    #     # Prefer JSON over PDF for speed
    #     if request.report_json:
    #         tumor_context = await parse_json_report(request.report_json, request.report_source)
    #         report_hash = hashlib.sha256(str(request.report_json).encode()).hexdigest()
    #     elif request.report_file:
    #         # Parse PDF (slower)
    #         if request.report_source == "Foundation":
    #             tumor_context = await parse_foundation_report(request.report_file)
    #         elif request.report_source == "Tempus":
    #             tumor_context = await parse_tempus_report(request.report_file)
    #         else:
    #             raise ValueError(f"Unsupported report source: {request.report_source}")
    #         
    #         report_hash = hashlib.sha256(request.report_file.encode()).hexdigest()
    #     else:
    #         raise ValueError("Must provide report_json or report_file")
    #     
    #     provenance = {
    #         "source": request.report_source,
    #         "report_hash": f"sha256:{report_hash}",
    #         "parsed_at": datetime.utcnow().isoformat(),
    #         "parser_version": "v1.0",
    #         "confidence_version": "v1.0"
    #     }
    #     
    #     return IngestNGSResponse(
    #         tumor_context=tumor_context,
    #         provenance=provenance
    #     )
    #     
    # except ValueError as e:
    #     raise HTTPException(status_code=400, detail=str(e))
    # except Exception as e:
    #     raise HTTPException(status_code=500, detail=f"NGS ingestion failed: {str(e)}")

