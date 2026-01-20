"""
Advanced Trial Query Router

REST endpoint for complex multi-criteria clinical trial queries.
Supports direct API queries, semantic search, mechanism fit ranking,
efficacy prediction integration, and sporadic cancer filtering.
"""
import logging
from typing import Dict, List, Any, Optional
from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel, Field
from datetime import datetime

from api.services.ctgov_query_builder import CTGovQueryBuilder, execute_query
from api.services.autonomous_trial_agent import AutonomousTrialAgent
from api.services.hybrid_trial_search import HybridTrialSearchService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/trials", tags=["advanced_trial_queries"])


class LocationInfo(BaseModel):
    """Trial location information"""
    facility: str
    city: str
    state: str
    country: str
    status: Optional[str] = None


class PIInfo(BaseModel):
    """Principal Investigator information"""
    name: str
    email: Optional[str] = None
    institution: Optional[str] = None
    phone: Optional[str] = None


class ContactInfo(BaseModel):
    """Site contact information"""
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None


class TrialDetail(BaseModel):
    """Detailed trial information"""
    nct_id: str
    title: str
    phase: str
    status: str
    therapy_types: List[str] = []
    locations: List[LocationInfo] = []
    enrollment_criteria: str = ""
    genetic_requirements: List[str] = []
    principal_investigator: Optional[PIInfo] = None
    site_contact: Optional[ContactInfo] = None
    source_url: str = ""
    mechanism_fit_score: Optional[float] = None
    combined_score: Optional[float] = None
    mechanism_alignment: Optional[Dict[str, float]] = None
    low_mechanism_fit_warning: Optional[bool] = None
    mechanism_boost_applied: Optional[bool] = None


class AdvancedTrialQueryRequest(BaseModel):
    """Request for advanced trial query"""
    conditions: List[str] = Field(..., description="Conditions (e.g., ['ovarian cancer', 'high-grade serous'])")
    mutations: List[str] = Field(default=[], description="Mutations (e.g., ['MBD4', 'TP53'])")
    interventions: List[str] = Field(default=[], description="Interventions (e.g., ['PARP inhibitor', 'checkpoint inhibitor'])")
    status: List[str] = Field(default=["RECRUITING", "NOT_YET_RECRUITING"], description="Status filters")
    phases: List[str] = Field(default=["PHASE1", "PHASE2", "PHASE3"], description="Phase filters")
    study_type: str = Field(default="INTERVENTIONAL", description="Study type")
    keywords: List[str] = Field(default=[], description="Keywords (e.g., ['basket trial', 'rare disease', 'DNA repair'])")
    geo: Optional[str] = Field(default="United States", description="Geographic filter")
    max_results: int = Field(default=100, description="Maximum number of results")
    use_semantic_search: bool = Field(default=True, description="Also use AstraDB semantic search")
    enable_mechanism_fit: bool = Field(default=True, description="Rank by mechanism alignment (pathway-based)")
    mechanism_vector: Optional[List[float]] = Field(
        default=None,
        description="6D or 7D pathway vector [DDR, MAPK, PI3K, VEGF, IO, Efflux] or [DDR, MAPK, PI3K, VEGF, HER2, IO, Efflux]"
    )
    efficacy_predictions: Optional[Dict[str, Any]] = Field(
        default=None,
        description="S/P/E framework output from /api/efficacy/predict"
    )
    pathway_scores: Optional[Dict[str, float]] = Field(
        default=None,
        description="Pathway disruption scores (e.g., {'ddr': 0.85, 'ras_mapk': 0.20})"
    )
    germline_status: Optional[str] = Field(
        default=None,
        description="Germline status: 'positive', 'negative', 'unknown' (for sporadic filtering)"
    )
    tumor_context: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Tumor context: {tmb, hrd_score, msi_status} (for biomarker boost)"
    )
    auto_infer_interventions: bool = Field(
        default=True,
        description="Auto-add interventions from top-ranked drugs in efficacy_predictions"
    )
    # Feature flags (Enhancement 8: Last Minute Enhancements)
    show_all_trials: bool = Field(
        default=False,
        description="Show all trials regardless of mechanism fit (Manager P4: clinician control)"
    )
    allow_runtime_moa_tagging: bool = Field(
        default=False,
        description="Allow runtime MoA tagging (Manager P3: Gemini OFFLINE ONLY, this is fallback only)"
    )
    use_trial_intelligence_pipeline: bool = Field(
        default=False,
        description="Use trial intelligence pipeline for eligibility scoring (optional but recommended)"
    )
    # Feature flags (Last Minute Enhancements)
    show_all_trials: bool = Field(
        default=False,
        description="Show all trials regardless of mechanism fit (Manager P4: clinician control)"
    )
    allow_runtime_moa_tagging: bool = Field(
        default=False,
        description="Allow runtime MoA tagging (Manager P3: Gemini OFFLINE ONLY, this is fallback only)"
    )
    use_trial_intelligence_pipeline: bool = Field(
        default=False,
        description="Use trial intelligence pipeline for eligibility scoring (optional but recommended)"
    )


class AdvancedTrialQueryResponse(BaseModel):
    """Response for advanced trial query"""
    success: bool
    total_found: int
    trials: List[TrialDetail]
    query_method: str  # "api_direct", "semantic", "hybrid"
    provenance: Dict[str, Any]
    mechanism_fit_disabled: Optional[bool] = None
    mechanism_fit_message: Optional[str] = None


def _extract_interventions_from_efficacy_predictions(
    efficacy_predictions: Dict[str, Any],
    auto_infer: bool = True
) -> List[str]:
    """Extract intervention keywords from efficacy predictions."""
    if not auto_infer or not efficacy_predictions:
        return []
    
    interventions = []
    drugs = efficacy_predictions.get('drugs', [])
    
    if drugs:
        # Sort by efficacy score
        sorted_drugs = sorted(drugs, key=lambda x: x.get('efficacy', 0), reverse=True)
        top_drugs = sorted_drugs[:5]  # Top 5 drugs
        
        # Look up MoA from DRUG_MECHANISM_DB
        from api.services.client_dossier.dossier_generator import get_drug_mechanism
        
        for drug in top_drugs:
            drug_name = drug.get('name', '')
            if drug_name:
                mechanism_info = get_drug_mechanism(drug_name)
                mechanism = mechanism_info.get('mechanism', '').lower()
                
                # Map MoA to intervention keywords
                if 'parp' in mechanism:
                    interventions.append('PARP inhibitor')
                elif 'checkpoint' in mechanism or 'pd-1' in mechanism or 'pd-l1' in mechanism:
                    interventions.append('checkpoint inhibitor')
                elif 'atr' in mechanism or 'atm' in mechanism:
                    interventions.append('ATR/ATM inhibitor')
                elif 'vegf' in mechanism or 'angiogenesis' in mechanism:
                    interventions.append('anti-angiogenic')
    
    return list(set(interventions))  # Deduplicate


def _convert_pathway_scores_to_mechanism_vector(
    pathway_scores: Dict[str, float],
    tumor_context: Optional[Dict[str, Any]] = None
) -> List[float]:
    """
    Convert pathway scores to 6D or 7D mechanism vector.
    
    Uses the pathway_to_mechanism_vector service.
    """
    from api.services.pathway_to_mechanism_vector import convert_pathway_scores_to_mechanism_vector
    
    mechanism_vector, _ = convert_pathway_scores_to_mechanism_vector(
        pathway_scores=pathway_scores,
        tumor_context=tumor_context,
        use_7d=False  # Default to 6D per Manager C7, auto-detects 7D if HER2 present
    )
    
    return mechanism_vector


@router.post("/advanced-query", response_model=AdvancedTrialQueryResponse)
async def advanced_trial_query(request: AdvancedTrialQueryRequest = Body(...)):
    """
    Advanced trial query endpoint for complex multi-criteria searches.
    
    Supports:
    - Direct ClinicalTrials.gov API queries
    - Semantic search via AstraDB
    - Mechanism fit ranking
    - Efficacy prediction integration
    - Sporadic cancer filtering
    """
    try:
        start_time = datetime.now()
        provenance = {
            "query_timestamp": start_time.isoformat(),
            "services_used": [],
            "mechanism_fit_applied": False,
            "mechanism_vector_source": None
        }
        
        all_trials = []
        query_method = "hybrid"
        
        # Step 1: Direct API queries using CTGovQueryBuilder
        if request.conditions:
            builder = CTGovQueryBuilder()
            
            # Add conditions
            for condition in request.conditions:
                builder.add_condition(condition)
            
            # Add interventions (including auto-inferred from efficacy predictions)
            interventions = request.interventions.copy()
            if request.auto_infer_interventions and request.efficacy_predictions:
                inferred = _extract_interventions_from_efficacy_predictions(
                    request.efficacy_predictions,
                    request.auto_infer_interventions
                )
                interventions.extend(inferred)
                provenance["auto_inferred_interventions"] = inferred
            
            for intervention in interventions:
                builder.add_intervention(intervention)
            
            # Add status, phases, study type
            builder.add_status(request.status)
            if request.phases:
                builder.add_phase(request.phases)
            builder.add_study_type(request.study_type)
            
            # Add keywords
            for keyword in request.keywords:
                builder.add_keyword(keyword)
            
            # Add geo
            if request.geo:
                builder.add_geo(request.geo)
            
            # Execute query
            api_trials = await execute_query(builder, max_results=request.max_results)
            all_trials.extend(api_trials)
            provenance["services_used"].append("ClinicalTrials.gov API")
            query_method = "api_direct"
        
        # Step 2: Semantic search (if enabled)
        if request.use_semantic_search:
            agent = AutonomousTrialAgent()
            
            # Build patient data for agent
            patient_data = {
                "disease": request.conditions[0] if request.conditions else "cancer",
                "mutations": [{"gene": mut} for mut in request.mutations],
                "efficacy_predictions": request.efficacy_predictions,
                "pathway_scores": request.pathway_scores,
                "germline_status": request.germline_status,
                "tumor_context": request.tumor_context
            }
            
            # Search using agent
            search_results = await agent.search_for_patient(
                patient_data=patient_data,
                germline_status=request.germline_status,
                tumor_context=request.tumor_context,
                top_k=request.max_results
            )
            
            semantic_trials = search_results.get("matched_trials", [])
            all_trials.extend(semantic_trials)
            provenance["services_used"].append("AstraDB Semantic Search")
            if query_method == "api_direct":
                query_method = "hybrid"
            else:
                query_method = "semantic"
        
        # Step 3: Deduplicate by NCT ID
        seen_ids = set()
        unique_trials = []
        for trial in all_trials:
            nct_id = trial.get('nct_id') or trial.get('nctId') or trial.get('protocolSection', {}).get('identificationModule', {}).get('nctId')
            if nct_id and nct_id not in seen_ids:
                seen_ids.add(nct_id)
                unique_trials.append(trial)
        
        # Step 3.5: Apply trial intelligence pipeline (if enabled - Enhancement 8)
        if request.use_trial_intelligence_pipeline and unique_trials:
            try:
                from api.services.trial_intelligence_universal.pipeline import TrialIntelligencePipeline
                from api.services.trial_intelligence_universal.profile_adapter import adapt_patient_profile
                
                # Build patient profile from request
                patient_profile = {
                    "disease": request.conditions[0] if request.conditions else "cancer",
                    "mutations": [{"gene": mut} for mut in request.mutations],
                    "germline_status": request.germline_status,
                    "tumor_context": request.tumor_context
                }
                
                # Adapt profile for pipeline
                adapted_profile = adapt_patient_profile(patient_profile)
                
                # Run pipeline
                pipeline = TrialIntelligencePipeline()
                pipeline_results = []
                for trial in unique_trials[:50]:  # Limit to 50 for performance
                    try:
                        result = pipeline.run_pipeline(trial, adapted_profile)
                        if result:
                            # Merge pipeline results back into trial
                            trial['_composite_score'] = result.get('_composite_score', trial.get('_composite_score'))
                            trial['eligibility_score'] = result.get('eligibility_score', trial.get('eligibility_score'))
                            trial['pipeline_metadata'] = result.get('metadata', {})
                            pipeline_results.append(trial)
                    except Exception as e:
                        logger.warning(f"Pipeline failed for trial {trial.get('nct_id', 'UNKNOWN')}: {e}")
                        pipeline_results.append(trial)  # Keep trial even if pipeline fails
                
                # Replace unique_trials with pipeline-processed results
                unique_trials = pipeline_results + unique_trials[50:]  # Keep remaining trials
                provenance["trial_intelligence_pipeline_applied"] = True
                provenance["pipeline_trials_processed"] = len(pipeline_results)
                
            except Exception as e:
                logger.warning(f"Trial intelligence pipeline not available: {e}")
                provenance["trial_intelligence_pipeline_error"] = str(e)
                # Continue without pipeline
        
        # Step 4: Extract mechanism vector (if needed for mechanism fit ranking)
        mechanism_vector = request.mechanism_vector
        mechanism_fit_disabled = False
        mechanism_fit_message = None
        
        if request.enable_mechanism_fit:
            if mechanism_vector:
                # Use provided vector
                provenance["mechanism_vector_source"] = "provided"
            elif request.pathway_scores:
                # Convert pathway scores to mechanism vector
                mechanism_vector = _convert_pathway_scores_to_mechanism_vector(
                    request.pathway_scores,
                    request.tumor_context
                )
                provenance["mechanism_vector_source"] = "pathway_scores"
            elif request.efficacy_predictions:
                # Extract from efficacy predictions provenance
                provenance_data = request.efficacy_predictions.get('provenance', {})
                confidence_breakdown = provenance_data.get('confidence_breakdown', {})
                pathway_disruption = confidence_breakdown.get('pathway_disruption', {})
                if pathway_disruption:
                    mechanism_vector = _convert_pathway_scores_to_mechanism_vector(
                        pathway_disruption,
                        request.tumor_context
                    )
                    provenance["mechanism_vector_source"] = "efficacy_predictions"
            
            # Check if mechanism vector is all zeros (Manager C7 fallback)
            if not mechanism_vector or all(v == 0.0 for v in mechanism_vector):
                mechanism_fit_disabled = True
                mechanism_fit_message = "awaiting NGS; eligibility-only ranking shown"
                provenance["mechanism_fit_applied"] = False
            else:
                provenance["mechanism_fit_applied"] = True
        
        # Step 5: Apply mechanism fit ranking (if enabled and vector available)
        # Manager P4: If show_all_trials=True, bypass mechanism fit filtering but still rank
        if request.show_all_trials:
            provenance["show_all_trials_enabled"] = True
            provenance["mechanism_fit_filtering_bypassed"] = True
        
        if request.enable_mechanism_fit and mechanism_vector and not mechanism_fit_disabled and not request.show_all_trials:
            try:
                from api.services.mechanism_fit_ranker import MechanismFitRanker
                from api.services.trial_data_enricher import extract_moa_vector_for_trial
                from api.services.pathway_to_mechanism_vector import convert_moa_dict_to_vector
                
                ranker = MechanismFitRanker(alpha=0.7, beta=0.3)  # Manager's P4 formula
                
                # Prepare trials for ranker: ensure eligibility_score and moa_vector exist
                prepared_trials = []
                for trial in unique_trials:
                    # Extract or compute eligibility score
                    eligibility_score = (
                        trial.get('_composite_score') or  # From trial intelligence pipeline
                        trial.get('eligibility_score') or
                        trial.get('match_score') or
                        trial.get('optimization_score') or
                        0.7  # Conservative default
                    )
                    
                    # Extract or compute moa_vector
                    moa_vector = trial.get('moa_vector')
                    if not moa_vector:
                        # Priority 1: Offline-tagged vectors from trial_moa_vectors.json (provider-agnostic)
                        moa_dict, moa_metadata = extract_moa_vector_for_trial(
                            trial,
                            allow_runtime_keyword_fallback=request.allow_runtime_moa_tagging
                        )
                        if moa_dict:
                            use_7d = len(mechanism_vector) == 7
                            moa_vector = convert_moa_dict_to_vector(moa_dict, use_7d=use_7d)
                            provenance.setdefault("moa_vector_sources", []).append({
                                "nct_id": trial.get('nct_id', 'UNKNOWN'),
                                "source": moa_metadata.get("source", "offline_tag")
                            })
                        
                        if not moa_vector:
                            # Default to neutral vector
                            moa_vector = [0.0] * len(mechanism_vector)
                            provenance.setdefault("moa_vector_sources", []).append({
                                "nct_id": trial.get('nct_id', 'UNKNOWN'),
                                "source": "neutral_vector"
                            })
                    
                    # Ensure moa_vector matches mechanism_vector dimension
                    if len(moa_vector) != len(mechanism_vector):
                        if len(moa_vector) == 7 and len(mechanism_vector) == 6:
                            # Drop HER2 dimension (index 4) for 6D
                            moa_vector = moa_vector[:4] + moa_vector[5:]
                        elif len(moa_vector) == 6 and len(mechanism_vector) == 7:
                            # Add HER2 dimension (index 4) for 7D
                            moa_vector = moa_vector[:4] + [0.0] + moa_vector[4:]
                        else:
                            # Pad or truncate to match
                            if len(moa_vector) < len(mechanism_vector):
                                moa_vector.extend([0.0] * (len(mechanism_vector) - len(moa_vector)))
                            else:
                                moa_vector = moa_vector[:len(mechanism_vector)]
                    
                    # Create trial dict with required fields
                    prepared_trial = trial.copy()
                    prepared_trial['eligibility_score'] = float(eligibility_score)
                    prepared_trial['moa_vector'] = moa_vector
                    prepared_trials.append(prepared_trial)
                
                # Rank trials
                ranked_results = ranker.rank_trials(
                    trials=prepared_trials,
                    sae_mechanism_vector=mechanism_vector,
                    min_eligibility=0.60,  # Manager's P4 threshold
                    min_mechanism_fit=0.50  # Manager's P4 threshold
                )
                
                # Convert TrialMechanismScore dataclass results back to trial format
                # Create a mapping from nct_id to original trial
                trial_map = {trial.get('nct_id') or trial.get('nctId') or 'UNKNOWN': trial for trial in unique_trials}
                
                ranked_trials = []
                for result in ranked_results:
                    # Find original trial
                    original_trial = trial_map.get(result.nct_id)
                    if not original_trial:
                        continue
                    
                    # Add mechanism fit scores to trial
                    original_trial['mechanism_fit_score'] = result.mechanism_fit_score
                    original_trial['combined_score'] = result.combined_score
                    original_trial['mechanism_alignment'] = result.mechanism_alignment
                    original_trial['eligibility_score'] = result.eligibility_score
                    
                    # Add "low mechanism fit" warning (Manager P4)
                    if result.mechanism_fit_score < 0.50:
                        original_trial['low_mechanism_fit_warning'] = True
                        original_trial['mechanism_boost_applied'] = False
                    else:
                        original_trial['low_mechanism_fit_warning'] = False
                        original_trial['mechanism_boost_applied'] = True
                    
                    ranked_trials.append(original_trial)
                
                # Add trials that didn't pass mechanism fit ranking (but keep them - Manager P4: never suppress)
                ranked_nct_ids = {result.nct_id for result in ranked_results}
                for trial in unique_trials:
                    nct_id = trial.get('nct_id') or trial.get('nctId') or trial.get('protocolSection', {}).get('identificationModule', {}).get('nctId', 'UNKNOWN')
                    if nct_id not in ranked_nct_ids:
                        # Trial didn't pass mechanism fit ranking, but keep it (Manager P4: never suppress)
                        trial['low_mechanism_fit_warning'] = True
                        trial['mechanism_boost_applied'] = False
                        trial['mechanism_fit_score'] = 0.0  # No mechanism fit score
                        trial['combined_score'] = trial.get('eligibility_score', 0.7)  # Use eligibility only
                        ranked_trials.append(trial)
                
                unique_trials = ranked_trials
                provenance["mechanism_fit_ranking_applied"] = True
                provenance["mechanism_fit_trials_ranked"] = len(ranked_results)
                
            except Exception as e:
                logger.error(f"Mechanism fit ranking failed: {e}", exc_info=True)
                provenance["mechanism_fit_error"] = str(e)
                # Continue without mechanism fit ranking
        
        # Step 6: Convert to TrialDetail format
        trial_details = []
        for trial in unique_trials[:request.max_results]:
            nct_id = trial.get('nct_id') or trial.get('nctId') or trial.get('protocolSection', {}).get('identificationModule', {}).get('nctId', '')
            
            # Extract basic info
            protocol_section = trial.get('protocolSection', {})
            identification = protocol_section.get('identificationModule', {})
            status_module = protocol_section.get('statusModule', {})
            design_module = protocol_section.get('designModule', {})
            
            title = identification.get('briefTitle', '') or identification.get('officialTitle', '')
            status = status_module.get('overallStatus', 'Unknown')
            phases = design_module.get('phases', [])
            phase = phases[0] if phases else 'Unknown'
            
            # Extract locations (simplified - would need full parsing)
            locations = []
            contacts_locations = protocol_section.get('contactsLocationsModule', {})
            locations_list = contacts_locations.get('locations', [])
            for loc in locations_list[:5]:  # Limit to first 5
                locations.append(LocationInfo(
                    facility=loc.get('facility', ''),
                    city=loc.get('city', ''),
                    state=loc.get('state', ''),
                    country=loc.get('country', ''),
                    status=loc.get('status', None)
                ))
            
            # Extract therapy types, enrollment criteria, genetic requirements, and PI using trial_data_enricher
            from api.services.trial_data_enricher import (
                extract_therapy_types,
                extract_enrollment_criteria,
                extract_genetic_requirements,
                extract_pi_information,
                extract_location_details
            )
            
            # Use trial_data_enricher for comprehensive extraction
            if protocol_section:
                therapy_types = extract_therapy_types(trial)
                criteria_text, inclusion_list, exclusion_list = extract_enrollment_criteria(trial)
                genetic_requirements = extract_genetic_requirements(trial)
                pi_info_dict = extract_pi_information(trial)
                enriched_locations = extract_location_details(trial)
                
                # Use enriched locations if available, otherwise use basic locations
                if enriched_locations:
                    locations = [
                        LocationInfo(
                            facility=loc.get('facility', ''),
                            city=loc.get('city', ''),
                            state=loc.get('state', ''),
                            country=loc.get('country', ''),
                            status=loc.get('status')
                        )
                        for loc in enriched_locations[:5]
                    ]
            else:
                # Fallback for trials without protocolSection (e.g., from semantic search)
                therapy_types = trial.get('therapy_types', [])
                criteria_text = trial.get('enrollment_criteria', '')
                genetic_requirements = trial.get('genetic_requirements', [])
                pi_info_dict = trial.get('principal_investigator')
            
            # Create PIInfo object
            pi_info = None
            if pi_info_dict:
                if isinstance(pi_info_dict, dict):
                    pi_info = PIInfo(
                        name=pi_info_dict.get('name', ''),
                        email=pi_info_dict.get('email'),
                        institution=pi_info_dict.get('institution'),
                        phone=pi_info_dict.get('phone')
                    )
                elif isinstance(pi_info_dict, PIInfo):
                    pi_info = pi_info_dict
            
            trial_detail = TrialDetail(
                nct_id=nct_id,
                title=title,
                phase=phase,
                status=status,
                therapy_types=therapy_types,
                locations=locations,
                enrollment_criteria=criteria_text,
                genetic_requirements=genetic_requirements,
                principal_investigator=pi_info,
                site_contact=None,  # Could be extracted from contactsLocationsModule if needed
                source_url=f"https://clinicaltrials.gov/study/{nct_id}",
                mechanism_fit_score=trial.get('mechanism_fit_score'),
                combined_score=trial.get('combined_score'),
                mechanism_alignment=trial.get('mechanism_alignment'),
                low_mechanism_fit_warning=trial.get('low_mechanism_fit_warning'),
                mechanism_boost_applied=trial.get('mechanism_boost_applied')
            )
            trial_details.append(trial_detail)
        
        # Sort by combined_score if available, else by optimization_score
        trial_details.sort(
            key=lambda x: x.combined_score if x.combined_score is not None else 0.0,
            reverse=True
        )
        
        end_time = datetime.now()
        provenance["execution_time_seconds"] = (end_time - start_time).total_seconds()
        provenance["total_trials_found"] = len(trial_details)
        
        return AdvancedTrialQueryResponse(
            success=True,
            total_found=len(trial_details),
            trials=trial_details,
            query_method=query_method,
            provenance=provenance,
            mechanism_fit_disabled=mechanism_fit_disabled,
            mechanism_fit_message=mechanism_fit_message
        )
        
    except Exception as e:
        logger.error(f"Advanced trial query failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")

