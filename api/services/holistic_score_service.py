"""
Unified Patient-Trial-Dose Feasibility Score Service

THE MOAT: First end-to-end patient-trial-dose optimization.
No other platform integrates mechanism-based matching with PGx safety.

Formula: Holistic Score = (0.5 × Mechanism Fit) + (0.3 × Eligibility) + (0.2 × PGx Safety)

Each component: 0.0 - 1.0
- Mechanism Fit: cosine similarity between patient 7D vector and trial MoA
- Eligibility: probability of meeting trial criteria (normalized)
- PGx Safety: inverted toxicity risk (1.0 = safe, 0.0 = contraindicated)

Research Use Only - Not for Clinical Decision Making

Owner: Zo (Lead Agent)
Created: January 2026
"""

from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any, Tuple
import logging
import math

logger = logging.getLogger(__name__)

# Manager-Approved Score Weights
MECHANISM_FIT_WEIGHT = 0.5   # Tumor-drug pathway alignment
ELIGIBILITY_WEIGHT = 0.3     # Traditional criteria
PGX_SAFETY_WEIGHT = 0.2      # Dosing tolerability

# Thresholds
CONTRAINDICATION_THRESHOLD = 0.1  # PGx adjustment ≤ 0.1 = contraindicated


@dataclass
class HolisticScoreResult:
    """Unified Patient-Trial-Dose Feasibility Score"""
    
    # Final score
    holistic_score: float  # 0.0 - 1.0
    
    # Component scores
    mechanism_fit_score: float   # 0.0 - 1.0
    eligibility_score: float     # 0.0 - 1.0
    pgx_safety_score: float      # 0.0 - 1.0
    
    # Component weights (for transparency)
    weights: Dict[str, float]
    
    # Detailed breakdown
    mechanism_alignment: Dict[str, float]  # Per-pathway alignment
    eligibility_breakdown: List[str]       # Which criteria met/failed
    pgx_details: Dict[str, Any]            # Pharmacogene details
    
    # Interpretation
    interpretation: str           # "HIGH", "MEDIUM", "LOW", "CONTRAINDICATED"
    recommendation: str           # Human-readable recommendation
    caveats: List[str]            # Warnings/caveats
    
    # Provenance
    provenance: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


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
        mechanism_fit_score, mechanism_alignment = self._compute_mechanism_fit(
            patient_profile, trial
        )
        if mechanism_fit_score is None:
            mechanism_fit_score = 0.5  # Default if no mechanism vector
            caveats.append("Mechanism vector not available - using default 0.5")
        
        # 2. Compute Eligibility Score (0.3 weight)
        eligibility_score, eligibility_breakdown = self._compute_eligibility(
            patient_profile, trial
        )
        
        # 3. Compute PGx Safety Score (0.2 weight)
        pgx_safety_score, pgx_details = await self._compute_pgx_safety(
            pharmacogenes, drug, trial
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
        interpretation, recommendation = self._interpret_score(
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
    
    def _dict_to_vector(self, moa_dict: Dict[str, float]) -> List[float]:
        """Convert MoA dict to 7D array in canonical order."""
        order = ["ddr", "mapk", "pi3k", "vegf", "her2", "io", "efflux"]
        return [moa_dict.get(k, moa_dict.get(k.upper(), 0.0)) for k in order]
    
    def _compute_mechanism_fit(
        self,
        patient_profile: Dict[str, Any],
        trial: Dict[str, Any]
    ) -> Tuple[Optional[float], Dict[str, float]]:
        """
        Compute mechanism fit score from 7D vectors.
        
        Handles both array format [0.95, 0.0, ...] and dict format {"ddr": 0.95, ...}
        Uses magnitude-weighted cosine similarity from mechanism_fit_ranker.
        """
        patient_vector = patient_profile.get("mechanism_vector")
        trial_moa = trial.get("moa_vector")
        
        if not patient_vector or not trial_moa:
            return None, {}
        
        # Convert dict to array if needed (trials agent returns dict format)
        if isinstance(trial_moa, dict):
            trial_moa = self._dict_to_vector(trial_moa)
        if isinstance(patient_vector, dict):
            patient_vector = self._dict_to_vector(patient_vector)
        
        # Ensure vectors are same length (7D expected)
        if len(patient_vector) != len(trial_moa):
            logger.warning(
                f"Vector length mismatch: patient={len(patient_vector)}, "
                f"trial={len(trial_moa)}"
            )
            return None, {}
        
        # L2 normalize
        patient_norm = self._l2_normalize(patient_vector)
        trial_norm = self._l2_normalize(trial_moa)
        
        # Cosine similarity
        score = sum(p * t for p, t in zip(patient_norm, trial_norm))
        score = max(0.0, min(1.0, score))  # Clamp to [0, 1]
        
        # Pathway alignment breakdown
        pathway_names = ["DDR", "MAPK", "PI3K", "VEGF", "HER2", "IO", "Efflux"]
        alignment = {}
        for i, name in enumerate(pathway_names[:len(patient_vector)]):
            # Product of normalized values shows alignment strength
            alignment[name] = round(patient_norm[i] * trial_norm[i], 3)
        
        return round(score, 3), alignment
    
    def _l2_normalize(self, vector: List[float]) -> List[float]:
        """L2 normalize a vector."""
        magnitude = math.sqrt(sum(x * x for x in vector))
        if magnitude == 0:
            return [0.0] * len(vector)
        return [x / magnitude for x in vector]
    
    def _compute_eligibility(
        self,
        patient_profile: Dict[str, Any],
        trial: Dict[str, Any]
    ) -> Tuple[float, List[str]]:
        """
        Compute eligibility score from hard/soft criteria.
        
        Returns normalized 0-1 score and breakdown of criteria.
        """
        breakdown = []
        score_components = []
        
        # 1. Recruiting status (HARD GATE)
        status = trial.get("overall_status", "").upper()
        if "RECRUITING" in status or "ACTIVE" in status:
            breakdown.append("✅ Recruiting/Active")
            score_components.append(1.0)
        else:
            breakdown.append("❌ Not recruiting")
            score_components.append(0.0)  # Hard fail
        
        # 2. Disease match
        patient_disease = str(patient_profile.get("disease", "")).lower()
        trial_conditions = [str(c).lower() for c in trial.get("conditions", [])]
        
        if any(patient_disease in c or c in patient_disease for c in trial_conditions):
            breakdown.append("✅ Disease match")
            score_components.append(1.0)
        elif trial_conditions:
            breakdown.append("⚠️ Disease match uncertain")
            score_components.append(0.5)
        else:
            breakdown.append("⚠️ No conditions listed")
            score_components.append(0.7)
        
        # 3. Age eligibility
        patient_age = patient_profile.get("age")
        min_age_str = trial.get("minimum_age", "")
        max_age_str = trial.get("maximum_age", "")
        
        if patient_age:
            try:
                min_age = int(min_age_str.replace("Years", "").replace("years", "").strip()) if min_age_str else 0
                max_age = int(max_age_str.replace("Years", "").replace("years", "").strip()) if max_age_str else 120
                
                if min_age <= patient_age <= max_age:
                    breakdown.append(f"✅ Age eligible ({patient_age} in {min_age}-{max_age})")
                    score_components.append(1.0)
                else:
                    breakdown.append(f"❌ Age ineligible ({patient_age} not in {min_age}-{max_age})")
                    score_components.append(0.0)  # Hard fail
            except (ValueError, TypeError):
                breakdown.append("⚠️ Age criteria unclear")
                score_components.append(0.7)
        else:
            breakdown.append("⚠️ Patient age not provided")
            score_components.append(0.7)
        
        # 4. Location match (if patient has location)
        patient_location = patient_profile.get("location", {})
        trial_locations = trial.get("locations", [])
        
        if patient_location and trial_locations:
            patient_state = patient_location.get("state", "").upper()
            trial_states = [loc.get("state", "").upper() for loc in trial_locations if isinstance(loc, dict)]
            
            if patient_state in trial_states:
                breakdown.append(f"✅ Location match ({patient_state})")
                score_components.append(1.0)
            else:
                breakdown.append(f"⚠️ Location distant (patient: {patient_state})")
                score_components.append(0.5)
        
        # 5. Biomarker requirements
        patient_mutations = [m.get("gene", "").upper() for m in patient_profile.get("mutations", [])]
        biomarker_reqs = trial.get("biomarker_requirements", [])
        
        if biomarker_reqs:
            matched = sum(1 for req in biomarker_reqs if req.upper() in patient_mutations)
            bio_score = matched / len(biomarker_reqs)
            
            if bio_score >= 0.8:
                breakdown.append(f"✅ Biomarkers match ({matched}/{len(biomarker_reqs)})")
            elif bio_score >= 0.5:
                breakdown.append(f"⚠️ Partial biomarker match ({matched}/{len(biomarker_reqs)})")
            else:
                breakdown.append(f"❌ Biomarker mismatch ({matched}/{len(biomarker_reqs)})")
            score_components.append(bio_score)
        
        # Calculate weighted average
        if score_components:
            # Check for hard fails (any 0.0 makes overall 0.0)
            if 0.0 in score_components:
                final_score = 0.0
                breakdown.append("⛔ HARD CRITERIA FAILED")
            else:
                final_score = sum(score_components) / len(score_components)
        else:
            final_score = 0.5
            breakdown.append("⚠️ Insufficient data for eligibility assessment")
        
        return round(final_score, 3), breakdown
    
    async def _compute_pgx_safety(
        self,
        pharmacogenes: Optional[List[Dict[str, str]]],
        drug: Optional[str],
        trial: Dict[str, Any]
    ) -> Tuple[float, Dict[str, Any]]:
        """
        Compute PGx safety score from pharmacogene variants.
        
        Returns inverted adjustment factor:
        - 1.0 = no variants (fully safe)
        - 0.5 = 50% dose reduction needed
        - 0.0 = contraindicated
        """
        # Try to get drug from trial interventions if not provided
        if not drug:
            interventions = trial.get("interventions", [])
            for intervention in interventions:
                if isinstance(intervention, dict):
                    drug_names = intervention.get("drug_names", []) or intervention.get("drugs", [])
                    if drug_names:
                        drug = drug_names[0] if isinstance(drug_names, list) else drug_names
                        break
        
        if not pharmacogenes:
            return 1.0, {
                "status": "not_screened", 
                "reason": "No germline variants provided",
                "contraindicated": False
            }
        
        if not drug:
            return 1.0, {
                "status": "not_screened",
                "reason": "No drug specified for PGx screening",
                "contraindicated": False
            }
        
        details = {
            "drug": drug,
            "variants_screened": [],
            "contraindicated": False,
            "dose_adjustments": []
        }
        
        min_adjustment = 1.0
        
        try:
            pgx_service = self._get_pgx_service()
            
            # Screen each pharmacogene
            for pgx in pharmacogenes:
                gene = pgx.get("gene", "")
                variant = pgx.get("variant", "")
                
                if not gene:
                    continue
                
                # Use PGx screening service
                screening_result = await pgx_service.screen_drugs(
                    drugs=[{"name": drug}],
                    germline_variants=[pgx],
                    treatment_line=None,
                    prior_therapies=None,
                    disease=None
                )
                
                drug_result = screening_result.get(drug, {})
                adjustment = drug_result.get("adjustment_factor", 1.0)
                tier = drug_result.get("toxicity_tier", "LOW")
                
                details["variants_screened"].append({
                    "gene": gene,
                    "variant": variant,
                    "toxicity_tier": tier,
                    "adjustment_factor": adjustment
                })
                
                if adjustment <= CONTRAINDICATION_THRESHOLD:
                    details["contraindicated"] = True
                    details["reason"] = f"{gene} {variant}: Contraindicated for {drug}"
                    min_adjustment = 0.0
                elif adjustment < min_adjustment:
                    min_adjustment = adjustment
                    reduction_pct = int((1 - adjustment) * 100)
                    details["dose_adjustments"].append(
                        f"{gene} {variant}: {reduction_pct}% dose reduction for {drug}"
                    )
        
        except Exception as e:
            logger.error(f"PGx screening failed: {e}")
            return 1.0, {
                "status": "error",
                "reason": f"PGx screening failed: {str(e)}",
                "contraindicated": False
            }
        
        details["pgx_safety_score"] = min_adjustment
        return min_adjustment, details
    
    def _interpret_score(
        self,
        holistic_score: float,
        mechanism_fit: float,
        eligibility: float,
        pgx_safety: float,
        pgx_details: Dict[str, Any],
        trial: Dict[str, Any]
    ) -> Tuple[str, str]:
        """Generate interpretation and recommendation."""
        
        nct_id = trial.get("nct_id", trial.get("nctId", "this trial"))
        
        # Check for hard contraindication
        if pgx_details.get("contraindicated"):
            return "CONTRAINDICATED", (
                f"⛔ CONTRAINDICATED for {nct_id}: {pgx_details.get('reason')}. "
                f"Consider alternative trial without this drug class or enroll "
                f"with modified protocol (pre-approved dose adjustment)."
            )
        
        # Check for hard eligibility fail
        if eligibility <= 0.0:
            return "INELIGIBLE", (
                f"❌ INELIGIBLE for {nct_id}: Patient does not meet hard eligibility "
                f"criteria (recruiting status, age, or other requirements). "
                f"Consider alternative trials."
            )
        
        # Interpret holistic score
        if holistic_score >= 0.8:
            return "HIGH", (
                f"✅ HIGH PROBABILITY for {nct_id} (score: {holistic_score:.2f}). "
                f"Strong mechanism alignment ({mechanism_fit:.2f}), meets eligibility "
                f"({eligibility:.2f}), and no significant PGx concerns ({pgx_safety:.2f}). "
                f"Recommend proceeding with enrollment."
            )
        
        elif holistic_score >= 0.6:
            concerns = []
            if mechanism_fit < 0.6:
                concerns.append(f"moderate mechanism fit ({mechanism_fit:.2f})")
            if eligibility < 0.8:
                concerns.append(f"eligibility concerns ({eligibility:.2f})")
            if pgx_safety < 0.8:
                concerns.append(f"dose adjustment may be needed ({pgx_safety:.2f})")
            
            concern_str = ", ".join(concerns) if concerns else "borderline scores"
            return "MEDIUM", (
                f"⚠️ MODERATE PROBABILITY for {nct_id} (score: {holistic_score:.2f}). "
                f"Proceed with caution due to: {concern_str}. "
                f"Consider additional workup before enrollment."
            )
        
        elif holistic_score >= 0.4:
            return "LOW", (
                f"⚠️ LOW PROBABILITY for {nct_id} (score: {holistic_score:.2f}). "
                f"Significant concerns: mechanism fit={mechanism_fit:.2f}, "
                f"eligibility={eligibility:.2f}, PGx safety={pgx_safety:.2f}. "
                f"Consider alternative trials with better alignment."
            )
        
        else:
            return "VERY_LOW", (
                f"❌ VERY LOW PROBABILITY for {nct_id} (score: {holistic_score:.2f}). "
                f"Poor alignment across multiple dimensions. "
                f"Recommend alternative trial search."
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


# Factory function
_holistic_service_instance = None

def get_holistic_score_service() -> HolisticScoreService:
    """Get singleton instance of HolisticScoreService."""
    global _holistic_service_instance
    if _holistic_service_instance is None:
        _holistic_service_instance = HolisticScoreService()
    return _holistic_service_instance
