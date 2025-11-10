"""
Health and basic status endpoints.
"""
from fastapi import APIRouter
from typing import Dict, Any
from ..config import MOCK_ORACLE_RESPONSE, MOCK_FORGE_RESPONSE, MOCK_GAUNTLET_RESPONSE, MOCK_DOSSIER_RESPONSE
from ..models.requests import VariantRequest, TherapeuticRequest, DossierRequest

router = APIRouter(prefix="", tags=["health"])

@router.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "CrisPRO Oncology Backend v2 - Live!",
        "status": "operational",
        "version": "2.0.0"
    }

@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "services": "operational"}

# Mock endpoints for YC demo
@router.post("/api/oracle/assess_variant_threat")
async def assess_variant_threat(request: VariantRequest):
    """Oracle: Assess variant pathogenicity and impact"""
    return MOCK_ORACLE_RESPONSE

@router.post("/api/forge/generate_therapeutics")
async def generate_therapeutics(request: TherapeuticRequest):
    """Forge: Generate CRISPR guides and small molecules"""
    return MOCK_FORGE_RESPONSE

@router.post("/api/gauntlet/run_trials")
async def run_trials(request: Dict[str, Any]):
    """Gauntlet: Run in silico clinical trials"""
    return MOCK_GAUNTLET_RESPONSE

@router.post("/api/dossier/generate")
async def generate_dossier(request: DossierRequest):
    """Generate complete IND-ready dossier"""
    return MOCK_DOSSIER_RESPONSE

@router.post("/api/workflow/run_seed_soil_analysis")
async def run_seed_soil_analysis(request: Dict[str, Any]):
    """Seed & Soil metastatic analysis"""
    return {
        "metastatic_potential": {
            "score": 0.73,
            "target_organs": ["liver", "lung", "bone"],
            "intervention_targets": ["VEGF", "PDGF"]
        }
    } 