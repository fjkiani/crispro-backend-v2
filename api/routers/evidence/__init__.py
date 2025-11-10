"""
Evidence Package - Modular evidence analysis endpoints
"""
from fastapi import APIRouter
from . import clinvar, literature, rag, extraction, jobs

# Create main evidence router
router = APIRouter(prefix="/api/evidence", tags=["evidence"])

# Include all sub-routers
router.include_router(clinvar.router)
router.include_router(literature.router)
router.include_router(rag.router)
router.include_router(extraction.router)
router.include_router(jobs.router)

# Health check endpoint
@router.get("/health")
async def evidence_health():
    """Health check for evidence package"""
    return {
        "status": "healthy",
        "modules": ["clinvar", "literature", "rag", "extraction", "jobs"],
        "service": "evidence"
    }



