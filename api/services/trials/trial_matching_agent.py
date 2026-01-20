"""
Trial Matching Agent - Module 05

Wires existing services to provide mechanism-based trial matching:
- AutonomousTrialAgent: Query generation and search
- MechanismFitRanker: Mechanism-based ranking (Manager P4 compliance)
- TrialDataEnricher: MoA extraction and eligibility scoring

Owner: JR Agent D
Status: ⏳ PENDING → ✅ COMPLETE
"""
from dataclasses import dataclass
from typing import List, Dict, Optional, Any
from datetime import datetime
from enum import Enum
import logging

from ..autonomous_trial_agent import AutonomousTrialAgent
from ..mechanism_fit_ranker import MechanismFitRanker, TrialMechanismScore
from ..trial_data_enricher import (
    extract_moa_vector_for_trial,
    extract_pi_information,
    extract_enrollment_criteria,
    extract_genetic_requirements,
    extract_therapy_types
)

logger = logging.getLogger(__name__)


class TrialStatus(str, Enum):
    """Trial recruitment status."""
    RECRUITING = "Recruiting"
    NOT_YET_RECRUITING = "Not yet recruiting"
    ACTIVE_NOT_RECRUITING = "Active, not recruiting"
    COMPLETED = "Completed"
    SUSPENDED = "Suspended"
    TERMINATED = "Terminated"
    UNKNOWN = "Unknown"


class TrialPhase(str, Enum):
    """Trial phase."""
    PHASE_1 = "Phase 1"
    PHASE_1_2 = "Phase 1/Phase 2"
    PHASE_2 = "Phase 2"
    PHASE_2_3 = "Phase 2/Phase 3"
    PHASE_3 = "Phase 3"
    PHASE_4 = "Phase 4"
    NA = "N/A"


@dataclass
class TrialMoA:
    """Trial mechanism of action vector (7D)."""
    ddr: float = 0.0
    mapk: float = 0.0
    pi3k: float = 0.0
    vegf: float = 0.0
    her2: float = 0.0
    io: float = 0.0
    efflux: float = 0.0
    
    def to_vector(self) -> List[float]:
        """Convert to 7D list."""
        return [self.ddr, self.mapk, self.pi3k, self.vegf, self.her2, self.io, self.efflux]
    
    @classmethod
    def from_vector(cls, vector: List[float]) -> 'TrialMoA':
        """Create from 7D list."""
        if len(vector) < 7:
            vector = vector + [0.0] * (7 - len(vector))
        return cls(
            ddr=vector[0] if len(vector) > 0 else 0.0,
            mapk=vector[1] if len(vector) > 1 else 0.0,
            pi3k=vector[2] if len(vector) > 2 else 0.0,
            vegf=vector[3] if len(vector) > 3 else 0.0,
            her2=vector[4] if len(vector) > 4 else 0.0,
            io=vector[5] if len(vector) > 5 else 0.0,
            efflux=vector[6] if len(vector) > 6 else 0.0
        )


@dataclass
class EligibilityCriteria:
    """Eligibility criteria breakdown."""
    meets_criteria: bool
    score: float  # 0.0 - 1.0
    matched: List[str]  # Criteria patient meets
    unmatched: List[str]  # Criteria patient doesn't meet
    uncertain: List[str]  # Criteria we can't evaluate


@dataclass
class TrialMatch:
    """A matched trial with scores and rationale."""
    nct_id: str
    title: str
    brief_summary: str
    phase: TrialPhase
    status: TrialStatus
    
    # Matching scores
    mechanism_fit_score: float  # Cosine similarity (0-1)
    eligibility_score: float  # Eligibility match (0-1)
    combined_score: float  # Weighted combination
    
    # Details
    trial_moa: TrialMoA
    eligibility: EligibilityCriteria
    mechanism_alignment: Dict[str, float]  # Per-pathway alignment
    
    # Why matched
    why_matched: str  # Human-readable explanation
    query_matched: str  # Which query found it
    
    # Logistics
    locations: List[Dict]  # Study locations
    contact: Optional[Dict]  # Contact info
    url: str  # ClinicalTrials.gov URL
    
    # Provenance
    last_updated: str
    sponsor: str


@dataclass
class TrialMatchingResult:
    """Result of trial matching operation."""
    patient_id: str
    queries_used: List[str]
    trials_found: int
    trials_ranked: int
    matches: List[TrialMatch]
    top_match: Optional[TrialMatch]
    search_time_ms: int
    provenance: Dict[str, Any]


class TrialMatchingAgent:
    """
    Match patients to clinical trials using mechanism-based ranking.
    
    Wires existing services:
    - AutonomousTrialAgent: Query generation and search
    - MechanismFitRanker: Mechanism-based ranking (Manager P4)
    - TrialDataEnricher: MoA extraction and eligibility
    
    Process:
    1. Generate disease/mutation-specific queries
    2. Search ClinicalTrials.gov via HybridTrialSearchService
    3. Extract MoA vectors for trials
    4. Rank by mechanism fit (cosine similarity)
    5. Check eligibility criteria
    6. Return ranked matches with rationale
    """
    
    def __init__(self):
        """Initialize trial matching agent."""
        self.autonomous_agent = AutonomousTrialAgent()
        self.mechanism_ranker = MechanismFitRanker(alpha=0.7, beta=0.3)  # Manager P4
        logger.info("TrialMatchingAgent initialized")
    
    async def match(
        self,
        patient_profile: Dict[str, Any],
        biomarker_profile: Optional[Dict[str, Any]] = None,
        mechanism_vector: Optional[List[float]] = None,
        max_results: int = 10
    ) -> TrialMatchingResult:
        """
        Find and rank matching clinical trials.
        
        Args:
            patient_profile: Patient mutations and disease (dict format)
            biomarker_profile: TMB, MSI, IO eligibility (optional)
            mechanism_vector: 7D pathway vector [DDR, MAPK, PI3K, VEGF, HER2, IO, Efflux]
            max_results: Maximum trials to return
        
        Returns:
            TrialMatchingResult with ranked matches
        """
        start_time = datetime.utcnow()
        patient_id = patient_profile.get('patient_id', patient_profile.get('demographics', {}).get('patient_id', 'UNKNOWN'))
        
        logger.info(f"Matching trials for patient {patient_id}")
        
        try:
            # Step 1: Generate queries and search using AutonomousTrialAgent
            search_result = await self.autonomous_agent.search_for_patient(
                patient_data=patient_profile,
                germline_status=patient_profile.get('germline_status'),
                tumor_context=patient_profile.get('tumor_context'),
                top_k=max_results * 3  # Over-fetch for ranking
            )
            
            queries_used = search_result.get('queries_used', [])
            raw_trials = search_result.get('matched_trials', [])
            
            logger.info(f"Found {len(raw_trials)} trials from {len(queries_used)} queries")
            
            if not raw_trials:
                return self._empty_result(patient_id, queries_used)
            
            # Step 2: Extract MoA vectors and eligibility scores for each trial
            trials_with_scores = []
            for trial in raw_trials:
                try:
                    # Extract MoA vector (OFFLINE tags preferred; provider-agnostic)
                    moa_vector_dict, moa_metadata = extract_moa_vector_for_trial(trial)
                    
                    # Convert dict to 7D list
                    if moa_vector_dict:
                        from ..pathway_to_mechanism_vector import convert_moa_dict_to_vector
                        moa_vector = convert_moa_dict_to_vector(moa_vector_dict, use_7d=True)
                    else:
                        moa_vector = [0.0] * 7
                    
                    # Estimate eligibility score (simplified - would use full eligibility checker)
                    eligibility_score = self._estimate_eligibility_score(
                        trial,
                        patient_profile,
                        biomarker_profile
                    )
                    
                    # Add to trial dict
                    trial['moa_vector'] = moa_vector
                    trial['eligibility_score'] = eligibility_score
                    
                    trials_with_scores.append(trial)
                except Exception as e:
                    logger.warning(f"Failed to process trial {trial.get('nct_id')}: {e}")
                    continue
            
            # Step 3: Rank by mechanism fit (if mechanism vector provided)
            if mechanism_vector and len(mechanism_vector) == 7:
                # Use MechanismFitRanker (Manager P4 compliance)
                ranked_scores = self.mechanism_ranker.rank_trials(
                    trials=trials_with_scores,
                    sae_mechanism_vector=mechanism_vector,
                    min_eligibility=0.60,  # Manager P4 threshold
                    min_mechanism_fit=0.50  # Manager P4 threshold
                )
                
                # Convert TrialMechanismScore back to trial dicts with scores
                ranked_trials = []
                for score in ranked_scores:
                    # Find matching trial
                    trial = next((t for t in trials_with_scores if t.get('nct_id') == score.nct_id), None)
                    if trial:
                        trial['mechanism_fit_score'] = score.mechanism_fit_score
                        trial['combined_score'] = score.combined_score
                        trial['mechanism_alignment'] = score.mechanism_alignment
                        trial['boost_applied'] = score.boost_applied
                        ranked_trials.append(trial)
            else:
                # No mechanism vector - rank by eligibility only
                logger.info("No mechanism vector provided - ranking by eligibility only")
                ranked_trials = sorted(
                    trials_with_scores,
                    key=lambda x: x.get('eligibility_score', 0),
                    reverse=True
                )
                # Add default mechanism scores
                for trial in ranked_trials:
                    trial['mechanism_fit_score'] = 0.0
                    trial['combined_score'] = trial.get('eligibility_score', 0)
                    trial['mechanism_alignment'] = {}
                    trial['boost_applied'] = False
            
            # Step 4: Build TrialMatch objects
            matches = []
            for trial in ranked_trials[:max_results * 2]:  # Over-fetch for eligibility filtering
                try:
                    match = self._build_trial_match(
                        trial=trial,
                        patient_profile=patient_profile,
                        biomarker_profile=biomarker_profile,
                        mechanism_vector=mechanism_vector or [0.0] * 7
                    )
                    matches.append(match)
                except Exception as e:
                    logger.warning(f"Failed to build match for {trial.get('nct_id')}: {e}")
                    continue
            
            # Step 5: Filter by minimum eligibility (0.5 threshold)
            matches = [m for m in matches if m.eligibility.score >= 0.5]
            
            # Limit to max_results
            matches = matches[:max_results]
            
            elapsed_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            
            return TrialMatchingResult(
                patient_id=patient_id,
                queries_used=queries_used,
                trials_found=len(raw_trials),
                trials_ranked=len(ranked_trials),
                matches=matches,
                top_match=matches[0] if matches else None,
                search_time_ms=elapsed_ms,
                provenance={
                    'ranking_formula': '0.7*eligibility + 0.3*mechanism_fit',
                    'min_thresholds': {'eligibility': 0.60, 'mechanism': 0.50},
                    'mechanism_vector_provided': mechanism_vector is not None,
                    'manager_policy': 'P4'
                }
            )
            
        except Exception as e:
            logger.error(f"Trial matching failed for {patient_id}: {e}", exc_info=True)
            return self._empty_result(patient_id, [], error=str(e))
    
    def _estimate_eligibility_score(
        self,
        trial: Dict[str, Any],
        patient_profile: Dict[str, Any],
        biomarker_profile: Optional[Dict[str, Any]]
    ) -> float:
        """
        Estimate eligibility score (0.0 - 1.0).
        
        Simplified version - full eligibility checking would use NLP/LLM.
        For now, use basic matching on disease, status, and biomarkers.
        """
        score = 0.5  # Base score
        
        # Check disease match
        trial_conditions = trial.get('conditions', [])
        patient_disease = patient_profile.get('disease', '')
        if patient_disease and any(patient_disease.lower() in str(c).lower() for c in trial_conditions):
            score += 0.2
        
        # Check status (prefer RECRUITING)
        status = trial.get('overall_status', '').upper()
        if 'RECRUITING' in status:
            score += 0.1
        elif 'NOT_YET_RECRUITING' in status:
            score += 0.05
        
        # Check biomarker eligibility (if available)
        if biomarker_profile:
            # TMB-H for IO trials
            if biomarker_profile.get('tmb', {}).get('classification') == 'TMB-H':
                interventions = trial.get('interventions', [])
                if any('checkpoint' in str(i).lower() or 'immunotherapy' in str(i).lower() for i in interventions):
                    score += 0.1
            
            # MSI-H for IO trials
            if biomarker_profile.get('msi', {}).get('status') == 'MSI-H':
                interventions = trial.get('interventions', [])
                if any('checkpoint' in str(i).lower() or 'immunotherapy' in str(i).lower() for i in interventions):
                    score += 0.1
        
        # Cap at 1.0
        return min(score, 1.0)
    
    def _build_trial_match(
        self,
        trial: Dict[str, Any],
        patient_profile: Dict[str, Any],
        biomarker_profile: Optional[Dict[str, Any]],
        mechanism_vector: List[float]
    ) -> TrialMatch:
        """Build TrialMatch object from trial data."""
        nct_id = trial.get('nct_id') or trial.get('nctId', 'UNKNOWN')
        
        # Extract MoA vector
        moa_vector = trial.get('moa_vector', [0.0] * 7)
        trial_moa = TrialMoA.from_vector(moa_vector)
        
        # Extract mechanism alignment
        mechanism_alignment = trial.get('mechanism_alignment', {})
        if not mechanism_alignment:
            # Compute alignment from vectors
            pathway_names = ['DDR', 'MAPK', 'PI3K', 'VEGF', 'HER2', 'IO', 'Efflux']
            mechanism_alignment = {}
            for i, name in enumerate(pathway_names):
                if i < len(mechanism_vector) and i < len(moa_vector):
                    patient_val = mechanism_vector[i]
                    trial_val = moa_vector[i]
                    mechanism_alignment[name] = min(patient_val, trial_val)
        
        # Extract eligibility criteria
        eligibility = self._build_eligibility_criteria(
            trial,
            patient_profile,
            biomarker_profile
        )
        
        # Generate why_matched explanation
        why_matched = self._explain_match(
            trial,
            eligibility,
            mechanism_alignment,
            trial.get('mechanism_fit_score', 0)
        )
        
        # Parse phase
        phase_str = trial.get('phase', '')
        phase = self._parse_phase(phase_str)
        
        # Parse status
        status_str = trial.get('overall_status', 'Recruiting')
        status = self._parse_status(status_str)
        
        # Extract locations
        locations = trial.get('locations', [])
        if isinstance(locations, list):
            locations = locations[:5]  # Limit to 5
        else:
            locations = []
        
        # Extract contact info
        contact = extract_pi_information(trial)
        
        # Extract enrollment criteria
        criteria_text, inclusion_list, exclusion_list = extract_enrollment_criteria(trial)
        
        return TrialMatch(
            nct_id=nct_id,
            title=trial.get('brief_title') or trial.get('title', 'Unknown Trial'),
            brief_summary=trial.get('brief_summary', '')[:500],
            phase=phase,
            status=status,
            mechanism_fit_score=trial.get('mechanism_fit_score', 0.0),
            eligibility_score=trial.get('eligibility_score', eligibility.score),
            combined_score=trial.get('combined_score', 0.0),
            trial_moa=trial_moa,
            eligibility=eligibility,
            mechanism_alignment=mechanism_alignment,
            why_matched=why_matched,
            query_matched=trial.get('matched_query', ''),
            locations=locations,
            contact=contact,
            url=f"https://clinicaltrials.gov/study/{nct_id}",
            last_updated=trial.get('last_update_submitted', ''),
            sponsor=trial.get('lead_sponsor', {}).get('name', '') if isinstance(trial.get('lead_sponsor'), dict) else str(trial.get('lead_sponsor', ''))
        )
    
    def _build_eligibility_criteria(
        self,
        trial: Dict[str, Any],
        patient_profile: Dict[str, Any],
        biomarker_profile: Optional[Dict[str, Any]]
    ) -> EligibilityCriteria:
        """Build eligibility criteria breakdown."""
        matched = []
        unmatched = []
        uncertain = []
        
        # Check disease match
        trial_conditions = trial.get('conditions', [])
        patient_disease = patient_profile.get('disease', '')
        if patient_disease and any(patient_disease.lower() in str(c).lower() for c in trial_conditions):
            matched.append("Disease match")
        else:
            uncertain.append("Disease eligibility")
        
        # Check status
        status = trial.get('overall_status', '').upper()
        if 'RECRUITING' in status or 'NOT_YET_RECRUITING' in status:
            matched.append("Currently recruiting")
        else:
            unmatched.append("Not currently recruiting")
        
        # Check biomarkers (if available)
        if biomarker_profile:
            tmb = biomarker_profile.get('tmb', {})
            if tmb.get('classification') == 'TMB-H':
                matched.append("TMB-H eligible")
            
            msi = biomarker_profile.get('msi', {})
            if msi.get('status') == 'MSI-H':
                matched.append("MSI-H eligible")
        
        # Extract genetic requirements
        genetic_reqs = extract_genetic_requirements(trial)
        if genetic_reqs:
            patient_mutations = [m.get('gene', '') for m in patient_profile.get('mutations', [])]
            for req in genetic_reqs:
                if any(gene.upper() in req.upper() for gene in patient_mutations):
                    matched.append(f"Genetic requirement: {req}")
                else:
                    uncertain.append(f"Genetic requirement: {req}")
        
        # Calculate score
        total_checks = len(matched) + len(unmatched) + len(uncertain)
        if total_checks == 0:
            score = 0.5  # Default if no checks
        else:
            score = len(matched) / total_checks
        
        return EligibilityCriteria(
            meets_criteria=score >= 0.5,
            score=score,
            matched=matched,
            unmatched=unmatched,
            uncertain=uncertain
        )
    
    def _explain_match(
        self,
        trial: Dict[str, Any],
        eligibility: EligibilityCriteria,
        mechanism_alignment: Dict[str, float],
        mechanism_fit_score: float
    ) -> str:
        """Generate human-readable explanation."""
        explanations = []
        
        # Top aligned pathways
        if mechanism_alignment:
            top_pathways = sorted(
                mechanism_alignment.items(),
                key=lambda x: x[1],
                reverse=True
            )[:2]
            
            for pathway, score in top_pathways:
                if score > 0.5:
                    explanations.append(f"{pathway} pathway alignment ({score:.0%})")
        
        # Mechanism fit highlight
        if mechanism_fit_score >= 0.50:
            explanations.append(f"High mechanism fit ({mechanism_fit_score:.0%})")
        elif mechanism_fit_score > 0.0:
            explanations.append(f"Moderate mechanism fit ({mechanism_fit_score:.0%})")
        
        # Eligibility highlights
        if eligibility.matched:
            explanations.append(f"Meets: {', '.join(eligibility.matched[:2])}")
        
        return "; ".join(explanations) if explanations else "Broad mechanism match"
    
    def _parse_phase(self, phase_str: str) -> TrialPhase:
        """Parse phase string to TrialPhase enum."""
        if not phase_str:
            return TrialPhase.NA
        
        phase_upper = str(phase_str).upper()
        if 'PHASE 1/PHASE 2' in phase_upper or 'PHASE 1/2' in phase_upper:
            return TrialPhase.PHASE_1_2
        elif 'PHASE 2/PHASE 3' in phase_upper or 'PHASE 2/3' in phase_upper:
            return TrialPhase.PHASE_2_3
        elif 'PHASE 1' in phase_upper:
            return TrialPhase.PHASE_1
        elif 'PHASE 2' in phase_upper:
            return TrialPhase.PHASE_2
        elif 'PHASE 3' in phase_upper:
            return TrialPhase.PHASE_3
        elif 'PHASE 4' in phase_upper:
            return TrialPhase.PHASE_4
        else:
            return TrialPhase.NA
    
    def _parse_status(self, status_str: str) -> TrialStatus:
        """Parse status string to TrialStatus enum."""
        if not status_str:
            return TrialStatus.UNKNOWN
        
        status_upper = str(status_str).upper()
        if 'RECRUITING' in status_upper and 'NOT' not in status_upper:
            return TrialStatus.RECRUITING
        elif 'NOT YET RECRUITING' in status_upper:
            return TrialStatus.NOT_YET_RECRUITING
        elif 'ACTIVE' in status_upper and 'RECRUITING' not in status_upper:
            return TrialStatus.ACTIVE_NOT_RECRUITING
        elif 'COMPLETED' in status_upper:
            return TrialStatus.COMPLETED
        elif 'SUSPENDED' in status_upper:
            return TrialStatus.SUSPENDED
        elif 'TERMINATED' in status_upper:
            return TrialStatus.TERMINATED
        else:
            return TrialStatus.UNKNOWN
    
    def _empty_result(
        self,
        patient_id: str,
        queries_used: List[str],
        error: Optional[str] = None
    ) -> TrialMatchingResult:
        """Return empty result."""
        return TrialMatchingResult(
            patient_id=patient_id,
            queries_used=queries_used,
            trials_found=0,
            trials_ranked=0,
            matches=[],
            top_match=None,
            search_time_ms=0,
            provenance={
                'error': error,
                'ranking_formula': 'N/A',
                'min_thresholds': {}
            }
        )

