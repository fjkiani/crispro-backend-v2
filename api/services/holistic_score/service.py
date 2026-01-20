"""
Holistic Score Service

Main orchestration service for computing unified patient-trial-dose feasibility scores.

THE MOAT: First end-to-end patient-trial-dose optimization.
No other platform integrates mechanism-based matching with PGx safety.

Formula: Holistic Score = (0.5 × Mechanism Fit) + (0.3 × Eligibility) + (0.2 × PGx Safety)

Research Use Only - Not for Clinical Decision Making
"""

from typing import Dict, List, Optional, Any
import logging
from datetime import datetime

from .models import (
    HolisticScoreResult,
    MECHANISM_FIT_WEIGHT,
    ELIGIBILITY_WEIGHT,
    PGX_SAFETY_WEIGHT
)
from .mechanism_fit import compute_mechanism_fit
from .eligibility_scorer import compute_eligibility
from .pgx_safety import compute_pgx_safety
from .interpreter import interpret_score

logger = logging.getLogger(__name__)


class HolisticScoreService:
    """
    Computes Unified Patient-Trial-Dose Feasibility Score.
    
    THE MOAT: Answers "Will this patient THRIVE in this trial?"
    not just "Does this patient qualify?"
    """
    
    def __init__(self):
        self._mechanism_ranker = None
        self._pgx_service = None
    
    def _get_mechanism_ranker(self):
        """Lazy load mechanism fit ranker."""
        if self._mechanism_ranker is None:
            from api.services.mechanism_fit_ranker import MechanismFitRanker
            self._mechanism_ranker = MechanismFitRanker()
        return self._mechanism_ranker
    
    def _get_pgx_service(self):
        """Lazy load PGx screening service."""
        if self._pgx_service is None:
            from api.services.pgx_screening_service import get_pgx_screening_service
            self._pgx_service = get_pgx_screening_service()
        return self._pgx_service
    
    async def compute_holistic_score(
        self,
        patient_profile: Dict[str, Any],
        trial: Dict[str, Any],
        pharmacogenes: Optional[List[Dict[str, str]]] = None,
        drug: Optional[str] = None
    ) -> HolisticScoreResult:
        """
        Compute unified feasibility score for patient-trial-drug combination.
        
        Args:
            patient_profile: Patient data including:
                - mechanism_vector: 7D [DDR, MAPK, PI3K, VEGF, HER2, IO, Efflux]
                - disease: Cancer type
                - age: Patient age (optional)
                - mutations: List of mutations (optional)
                - germline_variants: List of {gene, variant} (optional)
            trial: Trial data including:
                - nct_id: Trial ID
                - moa_vector: 7D mechanism vector
                - conditions: List of conditions
                - overall_status: Recruiting status
                - eligibility_criteria: Trial criteria (optional)
            pharmacogenes: List of {gene, variant} for PGx screening
            drug: Drug name for dosing guidance (optional, extracted from trial if not provided)
        
        Returns:
            HolisticScoreResult with score, breakdown, and interpretation
        """
        caveats = []
        
        # Use germline_variants from patient if pharmacogenes not provided
        if pharmacogenes is None:
            pharmacogenes = patient_profile.get("germline_variants", [])
        
        # 1. Compute Mechanism Fit Score (0.5 weight)
        mechanism_fit_score, mechanism_alignment = compute_mechanism_fit(
            patient_profile, trial
        )
        if mechanism_fit_score is None:
            mechanism_fit_score = 0.5  # Default if no mechanism vector
            caveats.append("Mechanism vector not available - using default 0.5")
        
        # 2. Compute Eligibility Score (0.3 weight)
        eligibility_score, eligibility_breakdown = compute_eligibility(
            patient_profile, trial
        )
        
        # 3. Compute PGx Safety Score (0.2 weight)
        pgx_service = self._get_pgx_service()
        pgx_safety_score, pgx_details = await compute_pgx_safety(
            pharmacogenes, drug, trial, pgx_service
        )
        if pgx_details.get("contraindicated"):
            caveats.append(f"CONTRAINDICATED: {pgx_details.get('reason')}")
        
        # 4. Compute Holistic Score
        holistic_score = (
            MECHANISM_FIT_WEIGHT * mechanism_fit_score +
            ELIGIBILITY_WEIGHT * eligibility_score +
            PGX_SAFETY_WEIGHT * pgx_safety_score
        )
        
        # 5. Generate Interpretation
        interpretation, recommendation = interpret_score(
            holistic_score, mechanism_fit_score, eligibility_score, 
            pgx_safety_score, pgx_details, trial
        )
        
        return HolisticScoreResult(
            holistic_score=round(holistic_score, 3),
            mechanism_fit_score=round(mechanism_fit_score, 3),
            eligibility_score=round(eligibility_score, 3),
            pgx_safety_score=round(pgx_safety_score, 3),
            weights={
                "mechanism_fit": MECHANISM_FIT_WEIGHT,
                "eligibility": ELIGIBILITY_WEIGHT,
                "pgx_safety": PGX_SAFETY_WEIGHT
            },
            mechanism_alignment=mechanism_alignment,
            eligibility_breakdown=eligibility_breakdown,
            pgx_details=pgx_details,
            interpretation=interpretation,
            recommendation=recommendation,
            caveats=caveats,
            provenance={
                "service": "HolisticScoreService",
                "version": "1.0",
                "formula": "0.5×mechanism + 0.3×eligibility + 0.2×pgx_safety",
                "ruo": "Research Use Only"
            }
        )
    
    async def compute_batch(
        self,
        patient_profile: Dict[str, Any],
        trials: List[Dict[str, Any]],
        pharmacogenes: Optional[List[Dict[str, str]]] = None
    ) -> List[Dict[str, Any]]:
        """
        Compute holistic scores for multiple trials.
        
        Returns ranked list by holistic score (descending).
        """
        results = []
        
        for trial in trials:
            try:
                # Extract drug from trial for PGx screening
                drug = None
                interventions = trial.get("interventions", [])
                for intervention in interventions:
                    if isinstance(intervention, dict):
                        drug_names = intervention.get("drug_names", []) or intervention.get("drugs", [])
                        if drug_names:
                            drug = drug_names[0] if isinstance(drug_names, list) else drug_names
                            break
                
                result = await self.compute_holistic_score(
                    patient_profile=patient_profile,
                    trial=trial,
                    pharmacogenes=pharmacogenes,
                    drug=drug
                )
                
                results.append({
                    "nct_id": trial.get("nct_id", trial.get("nctId")),
                    "title": trial.get("title", trial.get("brief_title")),
                    "holistic_score": result.holistic_score,
                    "mechanism_fit_score": result.mechanism_fit_score,
                    "eligibility_score": result.eligibility_score,
                    "pgx_safety_score": result.pgx_safety_score,
                    "interpretation": result.interpretation,
                    "recommendation": result.recommendation,
                    "caveats": result.caveats
                })
            
            except Exception as e:
                logger.error(f"Failed to score trial {trial.get('nct_id')}: {e}")
                results.append({
                    "nct_id": trial.get("nct_id", trial.get("nctId")),
                    "title": trial.get("title", trial.get("brief_title")),
                    "holistic_score": 0.0,
                    "error": str(e)
                })
        
        # Sort by holistic score (descending)
        results.sort(key=lambda x: x.get("holistic_score", 0), reverse=True)
        
        return results
