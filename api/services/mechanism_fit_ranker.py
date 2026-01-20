"""
Mechanism Fit Ranker Service (SAE Phase 2 - Task 6)
====================================================
Ranks clinical trials by mechanism fit using magnitude-weighted pathway alignment.

Policy Source: MANAGER_ANSWERS_TO_ZO_SAE_QUESTIONS.md (P4)
Zeta Protocol Fix: Magnitude-weighted similarity to prevent low-burden false positives.
Owner: Zo (Lead Commander)
Date: January 13, 2025 (Updated Jan 4, 2026)

Formula: combined_score = (α × eligibility_score) + (β × mechanism_fit_score)
Where:
- α = 0.7 (eligibility weight)
- β = 0.3 (mechanism fit weight)
- mechanism_fit_score = (patient_vector · trial_vector) / ||trial_vector||

CRITICAL: Requires trial MoA vectors to be pre-tagged (via Gemini offline tagging).
"""

from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any, Tuple
import math
import logging

logger = logging.getLogger(__name__)

# Manager's Policy Constants
MECHANISM_FIT_ALPHA = 0.7  # Eligibility weight (P4)
MECHANISM_FIT_BETA = 0.3   # Mechanism fit weight (P4)
MIN_ELIGIBILITY_THRESHOLD = 0.60  # Minimum eligibility to consider (P4)
MIN_MECHANISM_FIT_THRESHOLD = 0.30  # Minimum mechanism fit to boost (P4) - Adjusted for weighted fit


@dataclass
class TrialMechanismScore:
    """
    Trial scoring with mechanism fit alignment.
    
    Combines eligibility (hard/soft criteria) with SAE mechanism alignment.
    """
    nct_id: str
    title: str
    eligibility_score: float  # 0-1 from hard/soft criteria
    mechanism_fit_score: float  # 0-1 from magnitude-weighted similarity
    combined_score: float  # α × eligibility + β × mechanism_fit
    mechanism_alignment: Dict[str, float]  # Per-pathway alignment breakdown
    rank: int  # Final ranking (1 = best)
    boost_applied: bool  # True if mechanism fit boosted score
    provenance: Dict[str, Any]


class MechanismFitRanker:
    """
    Ranks trials by combining eligibility with SAE mechanism alignment.
    
    Manager Policy: MANAGER_ANSWERS_TO_ZO_SAE_QUESTIONS.md (P4)
    Zeta Protocol: Magnitude-weighted similarity to ensure clinical safety.
    
    Process:
    1. Compute magnitude-weighted similarity: (patient_vector · trial_vector) / ||trial_vector||
    2. Combine: (0.7 × eligibility) + (0.3 × mechanism_fit)
    3. Apply minimum thresholds (eligibility ≥0.60, mechanism_fit ≥0.30)
    4. Sort by combined score (descending)
    """
    
    def __init__(self, alpha: float = MECHANISM_FIT_ALPHA, beta: float = MECHANISM_FIT_BETA):
        """
        Initialize ranker with Manager's approved weights.
        
        Args:
            alpha: Eligibility weight (default: 0.7)
            beta: Mechanism fit weight (default: 0.3)
        """
        self.alpha = alpha
        self.beta = beta
        self.logger = logger
    
    def rank_trials(
        self,
        trials: List[Dict[str, Any]],
        sae_mechanism_vector: List[float],
        min_eligibility: float = MIN_ELIGIBILITY_THRESHOLD,
        min_mechanism_fit: float = MIN_MECHANISM_FIT_THRESHOLD
    ) -> List[TrialMechanismScore]:
        """
        Rank trials by magnitude-weighted mechanism fit + eligibility.
        
        Args:
            trials: List of trial dicts with 'eligibility_score' and 'moa_vector'
            sae_mechanism_vector: [DDR, MAPK, PI3K, VEGF, HER2, IO, Efflux] (7D)
            min_eligibility: Minimum eligibility threshold (default: 0.60)
            min_mechanism_fit: Minimum mechanism fit threshold (default: 0.30)
        
        Returns:
            Sorted list of TrialMechanismScore (descending by combined_score)
        """
        scored_trials = []
        
        for trial in trials:
            # Extract eligibility score (from hard/soft filters)
            eligibility_score = trial.get("eligibility_score", 0.0)
            
            # Skip if below minimum eligibility
            if eligibility_score < min_eligibility:
                self.logger.debug(f"Trial {trial.get('nct_id')} below min eligibility ({eligibility_score:.2f} < {min_eligibility})")
                continue
            
            # Extract trial MoA vector (pre-tagged via Gemini)
            trial_moa_vector = trial.get("moa_vector", [])
            
            # Handle missing MoA vector (default to zero vector)
            if not trial_moa_vector or len(trial_moa_vector) != len(sae_mechanism_vector):
                self.logger.warning(f"Trial {trial.get('nct_id')} missing or invalid moa_vector (expected {len(sae_mechanism_vector)}D)")
                trial_moa_vector = [0.0] * len(sae_mechanism_vector)
            
            # Compute magnitude-weighted mechanism fit (Zeta Protocol Fix)
            # This avoids magnitude-invariance flaws of pure cosine similarity.
            mechanism_fit_score = self._calculate_weighted_fit(sae_mechanism_vector, trial_moa_vector)
            
            # Skip if below minimum mechanism fit
            if mechanism_fit_score < min_mechanism_fit:
                self.logger.debug(f"Trial {trial.get('nct_id')} below min mechanism fit ({mechanism_fit_score:.2f} < {min_mechanism_fit})")
                continue
            
            # Combine scores (Manager's formula: α × eligibility + β × mechanism_fit)
            combined_score = (self.alpha * eligibility_score) + (self.beta * mechanism_fit_score)
            
            # Per-pathway alignment breakdown
            mechanism_alignment = self._compute_pathway_alignment(
                sae_mechanism_vector, 
                trial_moa_vector
            )
            
            # Provenance
            provenance = {
                "formula": f"({self.alpha} × eligibility) + ({self.beta} × weighted_mechanism_fit)",
                "eligibility_score": eligibility_score,
                "mechanism_fit_score": mechanism_fit_score,
                "combined_score": combined_score,
                "sae_vector": sae_mechanism_vector,
                "trial_moa_vector": trial_moa_vector,
                "thresholds": {
                    "min_eligibility": min_eligibility,
                    "min_mechanism_fit": min_mechanism_fit
                },
                "zeta_protocol": "Magnitude-weighted similarity (Option 1)"
            }
            
            scored_trials.append(TrialMechanismScore(
                nct_id=trial.get("nct_id", "UNKNOWN"),
                title=trial.get("title", "Unknown Trial"),
                eligibility_score=eligibility_score,
                mechanism_fit_score=mechanism_fit_score,
                combined_score=combined_score,
                mechanism_alignment=mechanism_alignment,
                rank=0,  # Will be set after sorting
                boost_applied=mechanism_fit_score >= min_mechanism_fit,
                provenance=provenance
            ))
        
        # Sort by combined score (descending)
        scored_trials.sort(key=lambda x: x.combined_score, reverse=True)
        
        # Assign ranks
        for i, trial in enumerate(scored_trials):
            trial.rank = i + 1
        
        return scored_trials
    
    def _calculate_weighted_fit(self, patient_vector: List[float], trial_vector: List[float]) -> float:
        """
        Compute magnitude-weighted mechanism fit (Zeta Protocol Fix - Option 1).
        
        Formula: fit = (patient_vector · trial_vector) / ||trial_vector||
        
        This prevents low-burden patients (e.g., DDR=0.1) from matching high-intensity 
        trials (e.g., DDR=0.9) with a score of 1.0.
        """
        if len(patient_vector) != len(trial_vector):
            self.logger.error(f"Vector dimension mismatch: {len(patient_vector)} vs {len(trial_vector)}")
            return 0.0
            
        # Dot product
        dot_product = sum(p * t for p, t in zip(patient_vector, trial_vector))
        
        # Normalize by trial magnitude only
        trial_magnitude = math.sqrt(sum(t**2 for t in trial_vector))
        
        if trial_magnitude == 0.0:
            return 0.0
            
        # Weighted fit
        fit = dot_product / trial_magnitude
        
        # Clamp to [0, 1]
        return max(0.0, min(1.0, fit))

    def _compute_pathway_alignment(
        self, 
        sae_vector: List[float], 
        trial_moa_vector: List[float]
    ) -> Dict[str, float]:
        """
        Compute per-pathway alignment breakdown.
        """
        pathway_names = ["DDR", "MAPK", "PI3K", "VEGF", "HER2", "IO", "Efflux"]
        
        alignment = {}
        for i, pathway in enumerate(pathway_names):
            if i < len(sae_vector) and i < len(trial_moa_vector):
                # Per-pathway contribution
                alignment[pathway] = sae_vector[i] * trial_moa_vector[i]
            else:
                alignment[pathway] = 0.0
        
        return alignment


# Singleton instance
_mechanism_fit_ranker = None

def get_mechanism_fit_ranker() -> MechanismFitRanker:
    """Get singleton Mechanism Fit Ranker instance"""
    global _mechanism_fit_ranker
    if _mechanism_fit_ranker is None:
        _mechanism_fit_ranker = MechanismFitRanker()
    return _mechanism_fit_ranker


def rank_trials_by_mechanism(
    trials: List[Dict[str, Any]],
    sae_mechanism_vector: List[float],
    min_eligibility: float = MIN_ELIGIBILITY_THRESHOLD,
    min_mechanism_fit: float = MIN_MECHANISM_FIT_THRESHOLD
) -> List[Dict[str, Any]]:
    """
    Convenience function for ranking trials by mechanism fit.
    """
    ranker = get_mechanism_fit_ranker()
    scored_trials = ranker.rank_trials(
        trials=trials,
        sae_mechanism_vector=sae_mechanism_vector,
        min_eligibility=min_eligibility,
        min_mechanism_fit=min_mechanism_fit
    )
    return [asdict(trial) for trial in scored_trials]

