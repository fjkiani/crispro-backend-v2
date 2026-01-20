"""
Dossiers Router - API endpoints for JR2's dossier generation pipeline.

Endpoints:
- POST /api/dossiers/generate - Generate dossier
- GET /api/dossiers/{dossier_id} - Get dossier
- POST /api/dossiers/{dossier_id}/approve - Zo review/approve
- POST /api/trials/filter-batch - Batch filter trials
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging
from pathlib import Path

from api.services.client_dossier.dossier_generator import generate_dossier
from api.services.client_dossier.dossier_renderer import render_dossier_markdown
from api.services.client_dossier.trial_filter import filter_50_candidates
from api.services.client_dossier.trial_querier import get_trials_from_sqlite

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/dossiers", tags=["dossiers"])

# Dossier storage directory
DOSSIER_DIR = Path(__file__).parent.parent.parent / ".cursor" / "ayesha" / "dossiers"
DOSSIER_DIR.mkdir(parents=True, exist_ok=True)

class PatientProfile(BaseModel):
    """Patient profile for dossier generation."""
    patient_id: str
    disease: str
    treatment_line: str = "first-line"
    location: str = "NYC"
    biomarkers: Dict[str, Any] = {}

class DossierGenerateRequest(BaseModel):
    """Request to generate a dossier."""
    nct_id: str
    patient_profile: PatientProfile

class BatchFilterRequest(BaseModel):
    """Request to batch filter trials."""
    patient_profile: PatientProfile
    limit: int = 50

@router.post("/generate")
async def generate_dossier_endpoint(request: DossierGenerateRequest):
    """
    Generate a complete dossier for a trial.
    
    Returns:
        {
            'dossier_id': str,
            'nct_id': str,
            'markdown': str,
            'json': dict,
            'status': 'generated'
        }
    """
    try:
        # Generate dossier
        dossier = await generate_dossier(
            request.nct_id,
            request.patient_profile.dict()
        )
        
        # Render markdown
        markdown = render_dossier_markdown(dossier)
        
        # Save to file
        timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
        dossier_id = f"{request.nct_id}_{request.patient_profile.patient_id}_{timestamp}"
        
        nct_dir = DOSSIER_DIR / request.nct_id
        nct_dir.mkdir(parents=True, exist_ok=True)
        
        # Save markdown
        md_file = nct_dir / f"dossier_{dossier_id}.md"
        md_file.write_text(markdown)
        
        # Save JSON
        json_file = nct_dir / f"dossier_{dossier_id}.json"
        import json as json_lib
        json_file.write_text(json_lib.dumps(dossier, indent=2))
        
        logger.info(f"✅ Dossier generated: {dossier_id}")
        
        return {
            'dossier_id': dossier_id,
            'nct_id': request.nct_id,
            'markdown': markdown,
            'json': dossier,
            'status': 'generated',
            'file_path': str(md_file)
        }
        
    except Exception as e:
        logger.error(f"❌ Dossier generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{dossier_id}")
async def get_dossier_endpoint(dossier_id: str):
    """
    Get a generated dossier by ID.
    
    Returns:
        Complete dossier (markdown + JSON)
    """
    # Find dossier file
    for nct_dir in DOSSIER_DIR.iterdir():
        if nct_dir.is_dir():
            md_file = nct_dir / f"dossier_{dossier_id}.md"
            json_file = nct_dir / f"dossier_{dossier_id}.json"
            
            if md_file.exists() and json_file.exists():
                import json as json_lib
                return {
                    'dossier_id': dossier_id,
                    'markdown': md_file.read_text(),
                    'json': json_lib.loads(json_file.read_text()),
                    'status': 'found'
                }
    
    raise HTTPException(status_code=404, detail=f"Dossier {dossier_id} not found")

@router.post("/{dossier_id}/approve")
async def approve_dossier_endpoint(dossier_id: str, approved: bool = True):
    """
    Zo review/approve a dossier.
    
    Moves dossier to approved/ or rejected/ folder.
    """
    # Find dossier
    for nct_dir in DOSSIER_DIR.iterdir():
        if nct_dir.is_dir():
            md_file = nct_dir / f"dossier_{dossier_id}.md"
            json_file = nct_dir / f"dossier_{dossier_id}.json"
            
            if md_file.exists():
                # Move to approved/rejected
                target_dir = nct_dir / ("approved" if approved else "rejected")
                target_dir.mkdir(parents=True, exist_ok=True)
                
                md_file.rename(target_dir / md_file.name)
                if json_file.exists():
                    json_file.rename(target_dir / json_file.name)
                
                logger.info(f"✅ Dossier {dossier_id} {'approved' if approved else 'rejected'}")
                return {
                    'dossier_id': dossier_id,
                    'status': 'approved' if approved else 'rejected',
                    'moved_to': str(target_dir)
                }
    
    raise HTTPException(status_code=404, detail=f"Dossier {dossier_id} not found")

@router.post("/trials/filter-batch")
async def filter_batch_endpoint(request: BatchFilterRequest):
    """
    Batch filter trials using multi-tier logic.
    
    Returns:
        {
            'top_tier': List[Dict],
            'good_tier': List[Dict],
            'ok_tier': List[Dict],
            'total_filtered': int
        }
    """
    try:
        # Get trials
        trials = get_trials_from_sqlite(limit=request.limit if request.limit > 0 else 0)
        
        # Filter
        filtered = filter_50_candidates(trials, request.patient_profile.dict())
        
        return {
            'top_tier': filtered['top_tier'],
            'good_tier': filtered['good_tier'],
            'ok_tier': filtered['ok_tier'],
            'total_filtered': len(trials),
            'top_tier_count': len(filtered['top_tier']),
            'good_tier_count': len(filtered['good_tier']),
            'ok_tier_count': len(filtered['ok_tier'])
        }
        
    except Exception as e:
        logger.error(f"❌ Batch filtering failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

