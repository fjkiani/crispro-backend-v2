"""
Universal Dossier Intelligence API Router

Provides universal access to the trial intelligence pipeline for any patient.
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from pathlib import Path
import json
from datetime import datetime
import logging

from api.services.trial_intelligence_universal.pipeline import TrialIntelligencePipeline
from api.services.trial_intelligence_universal.profile_adapter import adapt_simple_to_full_profile, is_simple_profile
from api.services.trial_intelligence_universal.config import FilterConfig, create_config_from_patient_profile
from api.services.trial_intelligence_universal.stage6_dossier.assembler import assemble
from api.services.clinical_trial_search_service import ClinicalTrialSearchService
from api.services.comprehensive_analysis.moat_analysis_generator import get_moat_analysis_generator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/dossiers/intelligence", tags=["Dossier Intelligence"])

# Storage directory
DOSSIER_STORAGE_ROOT = Path(__file__).resolve().parent.parent.parent / ".cursor" / "patients"
DOSSIER_STORAGE_ROOT.mkdir(parents=True, exist_ok=True)

# Singleton search service
_search_service = None

def get_search_service() -> ClinicalTrialSearchService:
    """Get singleton search service instance."""
    global _search_service
    if _search_service is None:
        _search_service = ClinicalTrialSearchService()
    return _search_service

class SimplePatientProfile(BaseModel):
    """Simple patient profile (for easy adoption)."""
    patient_id: str
    disease: str
    treatment_line: str = "first-line"
    location: str = "Unknown"
    biomarkers: Dict[str, Any] = {}
    zip_code: Optional[str] = None
    age: Optional[int] = None
    sex: Optional[str] = None
    stage: Optional[str] = None
    name: Optional[str] = None

class FilterRequest(BaseModel):
    """Request to filter trials."""
    patient_profile: Dict[str, Any]  # Accepts both simple and full
    candidates: List[Dict[str, Any]]  # Trial candidates to filter
    use_llm: bool = True
    config_override: Optional[Dict[str, Any]] = None  # Override config values

class GenerateDossierRequest(BaseModel):
    """Request to generate dossier."""
    patient_profile: Dict[str, Any]
    nct_id: str
    use_llm: bool = True

class BatchGenerateRequest(BaseModel):
    """Request to batch generate dossiers."""
    patient_profile: Dict[str, Any]
    nct_ids: List[str]
    use_llm: bool = True

class ComprehensiveAnalysisRequest(BaseModel):
    """Request to generate comprehensive MOAT analysis."""
    patient_profile: Dict[str, Any]
    treatment_context: Dict[str, Any]
    use_llm: bool = True
    include_sections: Optional[List[str]] = None

@router.post("/filter")
async def filter_trials(request: FilterRequest):
    """
    Filter trials using universal pipeline.
    
    Accepts both simple and full patient profiles.
    """
    try:
        # Adapt profile if needed
        if is_simple_profile(request.patient_profile):
            patient_profile = adapt_simple_to_full_profile(request.patient_profile)
        else:
            patient_profile = request.patient_profile
        
        # Create config (with override if provided)
        if request.config_override:
            config = create_config_from_patient_profile(patient_profile)
            # Apply overrides
            for key, value in request.config_override.items():
                setattr(config, key, value)
        else:
            config = create_config_from_patient_profile(patient_profile)
        
        # Run pipeline
        pipeline = TrialIntelligencePipeline(
            patient_profile=patient_profile,
            config=config,
            use_llm=request.use_llm,
            verbose=False
        )
        
        results = await pipeline.execute(request.candidates)
        
        return {
            'top_tier': results['top_tier'],
            'good_tier': results['good_tier'],
            'rejected': results['rejected'],
            'statistics': results['statistics']
        }
    
    except Exception as e:
        logger.error(f"❌ Filter failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/generate")
async def generate_dossier(request: GenerateDossierRequest):
    """
    Generate dossier for a single trial.
    
    Accepts both simple and full patient profiles.
    """
    try:
        # Adapt profile if needed
        if is_simple_profile(request.patient_profile):
            patient_profile = adapt_simple_to_full_profile(request.patient_profile)
        else:
            patient_profile = request.patient_profile
        
        # Get trial from database
        search_service = get_search_service()
        trial = await search_service.get_trial_details(request.nct_id)
        
        if not trial:
            raise HTTPException(status_code=404, detail=f"Trial {request.nct_id} not found")
        
        # Run pipeline on single trial
        config = create_config_from_patient_profile(patient_profile)
        pipeline = TrialIntelligencePipeline(
            patient_profile=patient_profile,
            config=config,
            use_llm=request.use_llm,
            verbose=False
        )
        
        # Run through pipeline
        results = await pipeline.execute([trial])
        
        # Get the processed trial (should be in top_tier or good_tier)
        processed_trial = None
        if results['top_tier']:
            processed_trial = results['top_tier'][0]
        elif results['good_tier']:
            processed_trial = results['good_tier'][0]
        else:
            # Even if rejected, we can still generate a dossier
            if results['rejected']:
                processed_trial = results['rejected'][0]
            else:
                processed_trial = trial
        
        # Generate dossier
        markdown = assemble(processed_trial, patient_profile)
        
        # Save to file system
        patient_id = patient_profile['demographics']['patient_id']
        dossier_dir = DOSSIER_STORAGE_ROOT / patient_id / "dossiers"
        dossier_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
        dossier_file = dossier_dir / f"{request.nct_id}_{timestamp}.md"
        dossier_file.write_text(markdown)
        
        # Also save JSON metadata
        metadata = {
            'dossier_id': f"{patient_id}_{request.nct_id}_{timestamp}",
            'nct_id': request.nct_id,
            'patient_id': patient_id,
            'tier': 'TOP_TIER' if processed_trial.get('_composite_score', 0) >= 0.8 else 'GOOD_TIER' if processed_trial.get('_composite_score', 0) >= 0.6 else 'OK_TIER',
            'match_score': processed_trial.get('_composite_score', 0),
            'file_path': str(dossier_file),
            'created_at': datetime.now().isoformat(),
        }
        
        metadata_file = dossier_dir / f"{request.nct_id}_{timestamp}.json"
        metadata_file.write_text(json.dumps(metadata, indent=2))
        
        return {
            'dossier_id': metadata['dossier_id'],
            'nct_id': request.nct_id,
            'patient_id': patient_id,
            'markdown': markdown,
            'metadata': metadata,
            'file_path': str(dossier_file)
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Dossier generation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/batch-generate")
async def batch_generate_dossiers(request: BatchGenerateRequest):
    """
    Batch generate dossiers for multiple trials.
    
    Returns list of generated dossier IDs.
    """
    try:
        # Adapt profile if needed
        if is_simple_profile(request.patient_profile):
            patient_profile = adapt_simple_to_full_profile(request.patient_profile)
        else:
            patient_profile = request.patient_profile
        
        # Get all trials
        search_service = get_search_service()
        trials = []
        for nct_id in request.nct_ids:
            trial = await search_service.get_trial_details(nct_id)
            if trial:
                trials.append(trial)
        
        if not trials:
            raise HTTPException(status_code=404, detail="No trials found")
        
        # Run pipeline
        config = create_config_from_patient_profile(patient_profile)
        pipeline = TrialIntelligencePipeline(
            patient_profile=patient_profile,
            config=config,
            use_llm=request.use_llm,
            verbose=False
        )
        
        results = await pipeline.execute(trials)
        
        # Generate dossiers for all survivors
        all_survivors = results['top_tier'] + results['good_tier']
        generated_dossiers = []
        
        patient_id = patient_profile['demographics']['patient_id']
        dossier_dir = DOSSIER_STORAGE_ROOT / patient_id / "dossiers"
        dossier_dir.mkdir(parents=True, exist_ok=True)
        
        for trial in all_survivors:
            try:
                markdown = assemble(trial, patient_profile)
                
                nct_id = trial.get('nct_id', 'UNKNOWN')
                timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
                
                dossier_file = dossier_dir / f"{nct_id}_{timestamp}.md"
                dossier_file.write_text(markdown)
                
                metadata = {
                    'dossier_id': f"{patient_id}_{nct_id}_{timestamp}",
                    'nct_id': nct_id,
                    'patient_id': patient_id,
                    'tier': 'TOP_TIER' if trial.get('_composite_score', 0) >= 0.8 else 'GOOD_TIER',
                    'match_score': trial.get('_composite_score', 0),
                    'file_path': str(dossier_file),
                    'created_at': datetime.now().isoformat(),
                }
                
                metadata_file = dossier_dir / f"{nct_id}_{timestamp}.json"
                metadata_file.write_text(json.dumps(metadata, indent=2))
                
                generated_dossiers.append(metadata)
            except Exception as e:
                logger.error(f"❌ Failed to generate dossier for {trial.get('nct_id')}: {e}")
                continue
        
        return {
            'generated_count': len(generated_dossiers),
            'total_trials': len(request.nct_ids),
            'dossiers': generated_dossiers
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Batch generation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/list/{patient_id}")
async def list_dossiers(
    patient_id: str,
    tier: Optional[str] = Query(None, description="Filter by tier: TOP_TIER, GOOD_TIER, OK_TIER"),
    limit: int = Query(50, ge=1, le=200)
):
    """List all dossiers for a patient."""
    try:
        dossier_dir = DOSSIER_STORAGE_ROOT / patient_id / "dossiers"
        
        if not dossier_dir.exists():
            return {
                'patient_id': patient_id,
                'dossiers': [],
                'total': 0
            }
        
        dossiers = []
        for json_file in dossier_dir.glob("*.json"):
            try:
                metadata = json.loads(json_file.read_text())
                if tier and metadata.get('tier') != tier:
                    continue
                dossiers.append(metadata)
            except Exception as e:
                logger.warning(f"Failed to parse {json_file}: {e}")
                continue
        
        # Sort by match_score descending
        dossiers.sort(key=lambda x: x.get('match_score', 0), reverse=True)
        
        # Apply limit
        if limit:
            dossiers = dossiers[:limit]
        
        return {
            'patient_id': patient_id,
            'dossiers': dossiers,
            'total': len(dossiers)
        }
    
    except Exception as e:
        logger.error(f"❌ List dossiers failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{patient_id}/{nct_id}")
async def get_dossier(patient_id: str, nct_id: str):
    """Get a specific dossier by patient_id and nct_id."""
    try:
        dossier_dir = DOSSIER_STORAGE_ROOT / patient_id / "dossiers"
        
        if not dossier_dir.exists():
            raise HTTPException(status_code=404, detail=f"Dossier directory not found for patient {patient_id}")
        
        # Find most recent dossier for this NCT ID
        matching_files = list(dossier_dir.glob(f"{nct_id}_*.md"))
        if not matching_files:
            raise HTTPException(status_code=404, detail=f"Dossier for {nct_id} not found")
        
        # Get most recent
        latest_file = max(matching_files, key=lambda f: f.stat().st_mtime)
        
        markdown = latest_file.read_text()
        
        # Try to get metadata
        metadata_file = latest_file.with_suffix('.json')
        metadata = {}
        if metadata_file.exists():
            try:
                metadata = json.loads(metadata_file.read_text())
            except:
                pass
        
        return {
            'patient_id': patient_id,
            'nct_id': nct_id,
            'markdown': markdown,
            'metadata': metadata
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Get dossier failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/comprehensive-analysis")
async def generate_comprehensive_analysis(request: ComprehensiveAnalysisRequest):
    """
    Generate comprehensive MOAT analysis document.
    
    Creates a detailed, personalized analysis connecting genomics → drugs → toxicity → nutrition,
    similar to AK_CYCLE_2_MOAT_ANALYSIS.md.
    
    Request:
        {
            "patient_profile": Dict[str, Any],  # Full patient profile
            "treatment_context": {
                "current_drugs": List[str],
                "treatment_line": str,
                "cycle_number": int,
                "treatment_goal": str,  # e.g., "pre-cycle-2"
                "status": str
            },
            "use_llm": bool = True,
            "include_sections": List[str] = None  # Optional: filter sections
        }
    
    Response:
        {
            "analysis_id": str,
            "markdown": str,  # Full markdown document
            "sections": Dict[str, Any],  # Structured data
            "metadata": Dict[str, Any]
        }
    """
    try:
        # Adapt profile if needed
        if is_simple_profile(request.patient_profile):
            patient_profile = adapt_simple_to_full_profile(request.patient_profile)
        else:
            patient_profile = request.patient_profile
        
        # Generate comprehensive analysis
        generator = get_moat_analysis_generator()
        result = await generator.generate_comprehensive_analysis(
            patient_profile=patient_profile,
            treatment_context=request.treatment_context,
            use_llm=request.use_llm
        )
        
        # Save to file system
        patient_id = patient_profile.get("demographics", {}).get("patient_id", "unknown")
        analysis_dir = DOSSIER_STORAGE_ROOT / patient_id / "moat_analyses"
        analysis_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
        analysis_file = analysis_dir / f"moat_analysis_{timestamp}.md"
        analysis_file.write_text(result["markdown"])
        
        # Save metadata
        metadata_file = analysis_dir / f"moat_analysis_{timestamp}.json"
        metadata_file.write_text(json.dumps({
            **result["metadata"],
            "sections_summary": {k: "generated" for k in result["sections"].keys()}
        }, indent=2))
        
        logger.info(f"✅ Comprehensive analysis generated: {result['analysis_id']}")
        
        return {
            **result,
            "file_path": str(analysis_file)
        }
    
    except Exception as e:
        logger.error(f"❌ Comprehensive analysis generation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


