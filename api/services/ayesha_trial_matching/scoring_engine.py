"""
Scoring Engine Module

Soft scoring boosts (Stage 2).

Calculates match score based on:
- First-line trials (+0.30)
- Stage IV specific (+0.25)
- SOC backbone (+0.20)
- Germline-negative friendly (+0.20)
- IP chemotherapy (+0.20)
- Bevacizumab (+0.15)
- CA-125 tracking (+0.15)
- NYC location (+0.15)
- Large trial (+0.10)
- Phase III (+0.10)
- Penalties for germline-BRCA-required (-0.30), distance (-0.25), Phase I (-0.20)
"""
import logging
from typing import Dict, List, Any
from api.schemas.ayesha_trials import AyeshaTrialProfile
from api.services.ca125_intelligence import CA125IntelligenceService

logger = logging.getLogger(__name__)


class ScoringEngine:
    """Soft scoring boosts for trial matching."""
    
    def __init__(self):
        self.ca125_service = CA125IntelligenceService()
    
    def calculate_match_score(
        self,
        trial: Dict[str, Any],
        profile: AyeshaTrialProfile,
        ca125_intel: Dict[str, Any]
    ) -> float:
        """
        Calculate match score with soft boosts.
        
        Starts at 0.5 base score, then applies boosts/penalties.
        Returns score clamped to [0.0, 1.0].
        """
        score = 0.5  # Base score
        
        # BOOST: First-line trial (+0.30)
        if self._boost_first_line(trial, profile):
            score += 0.30
        
        # BOOST: Stage IV specific (+0.25)
        if self._boost_stage_iv(trial, profile):
            score += 0.25
        
        # BOOST: SOC backbone (+0.20)
        if self._boost_soc_backbone(trial):
            score += 0.20
        
        # BOOST: Germline-negative friendly (+0.20)
        if self._boost_germline_negative(trial, profile):
            score += 0.20
        
        # BOOST: IP chemotherapy (+0.20)
        if self._boost_ip_chemo(trial):
            score += 0.20
        
        # BOOST: Bevacizumab (+0.15)
        if self._boost_bevacizumab(trial, profile):
            score += 0.15
        
        # BOOST: CA-125 tracking (+0.15)
        if self._boost_ca125_tracking(trial, ca125_intel):
            score += 0.15
        
        # BOOST: NYC location (+0.15)
        if self._boost_nyc_location(trial, profile):
            score += 0.15
        
        # BOOST: Large trial (+0.10)
        if self._boost_large_trial(trial):
            score += 0.10
        
        # BOOST: Phase III (+0.10)
        if self._boost_phase_iii(trial):
            score += 0.10
        
        # PENALTY: Germline BRCA required (-0.30)
        if self._penalize_germline_brca_required(trial):
            score -= 0.30
        
        # PENALTY: Distance (-0.25)
        if self._penalize_distance(trial, profile):
            score -= 0.25
        
        # PENALTY: Phase I (-0.20)
        if self._penalize_phase_i(trial):
            score -= 0.20
        
        # Clamp to [0.0, 1.0]
        return max(0.0, min(1.0, score))
    
    def _boost_first_line(self, trial: Dict, profile: AyeshaTrialProfile) -> bool:
        """Boost first-line trials (+0.30)."""
        if profile.treatment_line > 0:
            return False  # Not applicable if not treatment-naive
        
        title = (trial.get("title") or "").lower()
        desc = (trial.get("description") or "").lower()
        eligibility = (trial.get("eligibility_text") or "").lower()
        
        first_line_keywords = [
            "first-line", "frontline", "untreated",
            "newly diagnosed", "treatment-naive"
        ]
        
        all_text = f"{title} {desc} {eligibility}"
        return any(keyword in all_text for keyword in first_line_keywords)
    
    def _boost_stage_iv(self, trial: Dict, profile: AyeshaTrialProfile) -> bool:
        """Boost Stage IV specific trials (+0.25)."""
        title = (trial.get("title") or "").lower()
        desc = (trial.get("description") or "").lower()
        eligibility = (trial.get("eligibility_text") or "").lower()
        
        stage_keywords = [
            "stage iv", "stage 4", "stage ivb",
            "newly diagnosed advanced"
        ]
        
        all_text = f"{title} {desc} {eligibility}"
        return any(keyword in all_text for keyword in stage_keywords)
    
    def _boost_soc_backbone(self, trial: Dict) -> bool:
        """Boost SOC backbone (carboplatin + paclitaxel) (+0.20)."""
        interventions = trial.get("interventions", [])
        interventions_str = " ".join(interventions).lower()
        
        return "carboplatin" in interventions_str and "paclitaxel" in interventions_str
    
    def _boost_germline_negative(self, trial: Dict, profile: AyeshaTrialProfile) -> bool:
        """Boost germline-negative friendly trials (+0.20)."""
        if profile.germline_status != "NEGATIVE":
            return False
        
        title = (trial.get("title") or "").lower()
        desc = (trial.get("description") or "").lower()
        eligibility = (trial.get("eligibility_text") or "").lower()
        
        all_comers_keywords = [
            "all comers", "brca wild-type", "brca negative",
            "germline brca not required", "somatic brca"
        ]
        
        all_text = f"{title} {desc} {eligibility}"
        return any(keyword in all_text for keyword in all_comers_keywords)
    
    def _boost_ip_chemo(self, trial: Dict) -> bool:
        """Boost intraperitoneal chemotherapy (+0.20)."""
        title = (trial.get("title") or "").lower()
        desc = (trial.get("description") or "").lower()
        interventions = " ".join(trial.get("interventions", [])).lower()
        
        ip_keywords = [
            "intraperitoneal", "ip chemotherapy", "ip chemo",
            "ip administration"
        ]
        
        all_text = f"{title} {desc} {interventions}"
        return any(keyword in all_text for keyword in ip_keywords)
    
    def _boost_bevacizumab(self, trial: Dict, profile: AyeshaTrialProfile) -> bool:
        """Boost bevacizumab (anti-VEGF for ascites) (+0.15)."""
        if profile.ascites == "none":
            return False  # Not relevant if no ascites
        
        interventions = " ".join(trial.get("interventions", [])).lower()
        title = (trial.get("title") or "").lower()
        
        bev_keywords = ["bevacizumab", "avastin", "anti-vegf"]
        all_text = f"{title} {interventions}"
        
        return any(keyword in all_text for keyword in bev_keywords)
    
    def _boost_ca125_tracking(self, trial: Dict, ca125_intel: Dict) -> bool:
        """Boost CA-125 tracking trials (+0.15)."""
        boost_keywords = ca125_intel.get("boost_keywords", [])
        
        title = (trial.get("title") or "").lower()
        desc = (trial.get("description") or "").lower()
        endpoints = (trial.get("endpoints") or "").lower()
        
        all_text = f"{title} {desc} {endpoints}"
        return any(kw.lower() in all_text for kw in boost_keywords)
    
    def _boost_nyc_location(self, trial: Dict, profile: AyeshaTrialProfile) -> bool:
        """Boost NYC location trials (+0.15)."""
        locations = trial.get("locations", [])
        
        nyc_metro_states = ["ny", "nj", "ct"]
        nyc_metro_cities = [
            "new york", "manhattan", "brooklyn", "queens", "bronx",
            "newark", "jersey city", "stamford", "bridgeport"
        ]
        
        for loc in locations:
            state = (loc.get("state") or "").lower()
            city = (loc.get("city") or "").lower()
            
            if state in nyc_metro_states or any(metro_city in city for metro_city in nyc_metro_cities):
                return True
        
        return False
    
    def _boost_large_trial(self, trial: Dict) -> bool:
        """Boost large trials (>200 patients) (+0.10)."""
        # Try to extract enrollment from various fields
        enrollment = trial.get("enrollment", 0)
        if isinstance(enrollment, str):
            # Parse "200" from "200 participants"
            try:
                enrollment = int(enrollment.split()[0])
            except (ValueError, IndexError):
                enrollment = 0
        
        return enrollment > 200
    
    def _boost_phase_iii(self, trial: Dict) -> bool:
        """Boost Phase III trials (+0.10)."""
        phase = (trial.get("phase") or "").lower()
        return "phase 3" in phase or "phase iii" in phase
    
    def _penalize_germline_brca_required(self, trial: Dict) -> bool:
        """Penalize germline-BRCA-required trials (-0.30)."""
        title = (trial.get("title") or "").lower()
        desc = (trial.get("description") or "").lower()
        eligibility = (trial.get("eligibility_text") or "").lower()
        
        germline_keywords = [
            "germline brca required", "hereditary brca",
            "brca mutation carrier required"
        ]
        
        all_text = f"{title} {desc} {eligibility}"
        return any(keyword in all_text for keyword in germline_keywords)
    
    def _penalize_distance(self, trial: Dict, profile: AyeshaTrialProfile) -> bool:
        """Penalize trials >50 miles from NYC (-0.25)."""
        locations = trial.get("locations", [])
        
        if not locations:
            return False  # No location data, don't penalize
        
        # Check if ANY location is NYC metro
        nyc_metro_states = ["ny", "nj", "ct"]
        nyc_metro_cities = [
            "new york", "manhattan", "brooklyn", "queens", "bronx",
            "newark", "jersey city", "stamford", "bridgeport"
        ]
        
        for loc in locations:
            state = (loc.get("state") or "").lower()
            city = (loc.get("city") or "").lower()
            
            if state in nyc_metro_states or any(metro_city in city for metro_city in nyc_metro_cities):
                return False  # Has NYC metro location, don't penalize
        
        # All locations are outside NYC metro
        return True
    
    def _penalize_phase_i(self, trial: Dict) -> bool:
        """Penalize Phase I trials (-0.20)."""
        phase = (trial.get("phase") or "").lower()
        return "phase 1" in phase or "phase i" in phase


