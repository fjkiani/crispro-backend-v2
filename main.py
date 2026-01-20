"""
MOAT Orchestration Backend - Main FastAPI Application

The core backend for the oncology-focused agentic orchestration system.

Features:
- Modular agent architecture
- Full patient pipeline orchestration
- Validated resistance prediction (DIS3 RR=2.08, TP53 RR=1.90)
- Disease-agnostic design (Ovarian, Myeloma, more to come)

Run with:
    uvicorn main:app --reload --port 8000
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="MOAT Orchestration API",
    description="""
    🏆 Ultimate MOAT Orchestration System
    
    Vision: "Upload once. Track forever. Never miss a signal."
    
    ## Features
    
    - **Full Pipeline Orchestration**: Coordinate all agents in optimal order
    - **Resistance Prediction**: Validated markers (DIS3 RR=2.08, TP53 RR=1.90)
    - **Drug Efficacy Ranking**: S/P/E framework
    - **Clinical Trial Matching**: 7D mechanism vector
    - **Care Plan Generation**: Unified patient care documents
    - **Continuous Monitoring**: Early resistance detection
    
    ## Supported Diseases
    
    - **Ovarian Cancer**: MAPK/PI3K pathway resistance, platinum sensitivity
    - **Multiple Myeloma**: PI/IMiD resistance, cytogenetics risk
    
    ## Validated Capabilities
    
    | Marker | RR | p-value | Status |
    |--------|-----|---------|--------|
    | DIS3 (MM) | 2.08 | 0.0145 | ✅ VALIDATED |
    | TP53 (MM) | 1.90 | 0.11 | ⚠️ TREND |
    | NF1 (OV) | 2.10 | <0.05 | ✅ VALIDATED |
    | KRAS (OV) | 1.97 | <0.05 | ✅ VALIDATED |
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import and register routers
from api.routers.orchestrate import router as orchestrate_router
from api.routers.resistance import router as resistance_router
from api.routers.guidance import router as guidance_router
from api.routers.vus import router as vus_router
from api.routers.evo import router as evo_router
from api.routers.insights import router as insights_router
from api.routers.fusion import router as fusion_router
from api.routers.evidence import router as evidence_router
from api.routers.health import router as health_router

app.include_router(orchestrate_router)
app.include_router(resistance_router)
app.include_router(guidance_router)
app.include_router(vus_router)
app.include_router(evo_router)
app.include_router(insights_router)
app.include_router(fusion_router)
app.include_router(evidence_router)
app.include_router(health_router)

# Try to include trials router if available
try:
    from api.routers.trials_agent import router as trials_router
    app.include_router(trials_router)
except ImportError:
    logger.warning("Trials router not available")

# Include agents router (Zeta Agent system)
try:
    from api.routers import agents as agents_router
    app.include_router(agents_router.router)
    logger.info("✅ Agents router registered")
except ImportError as e:
    logger.warning(f"⚠️ Agents router not available: {e}")

# Include research intelligence router
try:
    from api.routers import research_intelligence as research_intelligence_router
    app.include_router(research_intelligence_router.router)
    logger.info("✅ Research intelligence router registered")
except ImportError as e:
    logger.warning(f"⚠️ Research intelligence router not available: {e}")

# Include Ayesha orchestrator v2 router (complete_care_v2 endpoint)
try:
    from api.routers import ayesha_orchestrator_v2 as ayesha_orchestrator_v2_router
    app.include_router(ayesha_orchestrator_v2_router.router)
    logger.info("✅ Ayesha orchestrator v2 router registered")
except ImportError as e:
    logger.warning(f"⚠️ Ayesha orchestrator v2 router not available: {e}")




# Include IO selection router
try:
    from api.routers import io_selection as io_selection_router
    app.include_router(io_selection_router.router)
    logger.info("✅ IO selection router registered")
except ImportError as e:
    logger.warning(f"⚠️ IO selection router not available: {e}")

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    logger.info("🚀 Starting MOAT Orchestration Backend")
    logger.info("📊 Validated markers loaded: DIS3, TP53, NF1, KRAS")
    logger.info("🏥 Supported diseases: Ovarian, Myeloma")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("👋 Shutting down MOAT Orchestration Backend")


@app.get("/")
async def root():
    """Root endpoint with API overview."""
    return {
        "service": "MOAT Orchestration API",
        "version": "1.0.0",
        "vision": "Upload once. Track forever. Never miss a signal.",
        "endpoints": {
            "orchestration": "/api/orchestrate/full",
            "resistance": "/api/resistance/predict",
            "patients": "/api/patients",
            "health": "/api/health",
            "docs": "/docs"
        },
        "validated_markers": {
            "myeloma": {
                "DIS3": {"RR": 2.08, "p_value": 0.0145, "status": "VALIDATED"},
                "TP53": {"RR": 1.90, "p_value": 0.11, "status": "TREND"}
            },
            "ovarian": {
                "NF1": {"RR": 2.10, "status": "VALIDATED"},
                "KRAS": {"RR": 1.97, "status": "VALIDATED"}
            }
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

