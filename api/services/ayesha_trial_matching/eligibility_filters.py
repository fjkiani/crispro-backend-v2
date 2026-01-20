"""
Eligibility Filters Module

Hard eligibility filters (Stage 1 - MUST-MATCH criteria).

Filters trials based on:
- Disease type (ovarian/peritoneal/gynecologic)
- Stage (IV/advanced/metastatic)
- Treatment line (first-line/untreated)
- Status (Recruiting/Active)
- Location (NYC metro: NY/NJ/CT)
- Exclusions (recurrent-only, germline-BRCA-required, etc.)
"""
import logging
from typing import Dict, List, Any, Optional
from api.services.hybrid_trial_search import HybridTrialSearchService
from api.schemas.ayesha_trials import AyeshaTrialProfile

logger = logging.getLogger(__name__)


class EligibilityFilters:
    """Hard eligibility filters for Ayesha's trials."""
    
    def __init__(self):
        self.search_service = HybridTrialSearchService()
    
    async def apply_hard_filters(
        self,
        profile: AyeshaTrialProfile
    ) -> List[Dict[str, Any]]:
        """
        Apply all hard eligibility filters.
        
        Returns trials that MUST match:
        - Disease: ovarian/peritoneal/gynecologic
        - Stage: IV/advanced/metastatic
        - Treatment line: first-line/untreated
        - Status: Recruiting/Active
        - Location: NYC metro (NY/NJ/CT)
        - NOT: recurrent-only, germline-BRCA-required
        """
        try:
            # Build search query for HybridTrialSearchService
            query = "ovarian cancer first-line Stage IV"
            patient_context = {
                "condition": profile.disease,
                "disease_category": "ovarian_cancer",
                "location_state": "NY"  # NYC metro
            }
            
            # Call HybridTrialSearchService (already supports germline_status!)
            candidate_trials = await self.search_service.search_optimized(
                query=query,
                patient_context=patient_context,
                germline_status="negative",  # ✅ Already supported!
                tumor_context={},  # Empty for now (NGS pending)
                top_k=50  # Get 50 candidates for filtering
            )
            
            logger.info(f"🔍 Found {len(candidate_trials)} candidates from HybridTrialSearchService")
            
            # Apply additional hard filters
            filtered_trials = []
            excluded_count = 0
            
            for trial in candidate_trials:
                # Filter by disease
                if not self._filter_by_disease(trial, profile):
                    excluded_count += 1
                    continue
                
                # Filter by stage
                if not self._filter_by_stage(trial, profile):
                    excluded_count += 1
                    continue
                
                # Filter by treatment line
                if not self._filter_by_treatment_line(trial, profile):
                    excluded_count += 1
                    continue
                
                # Filter by status
                if not self._filter_by_status(trial):
                    excluded_count += 1
                    continue
                
                # Filter by location (NYC metro)
                if not self._filter_by_location(trial, profile):
                    excluded_count += 1
                    continue
                
                # Filter exclusions
                if self._filter_exclusions(trial, profile):
                    excluded_count += 1
                    continue
                
                # Trial passed all hard filters
                filtered_trials.append(trial)
            
            logger.info(f"✅ Hard filters: {len(filtered_trials)} passed, {excluded_count} excluded")
            
            return filtered_trials
            
        except Exception as e:
            logger.error(f"❌ Hard filter application failed: {e}")
            return []
    
    def _filter_by_disease(self, trial: Dict, profile: AyeshaTrialProfile) -> bool:
        """Filter by disease type."""
        title = (trial.get("title") or "").lower()
        desc = (trial.get("description") or "").lower()
        eligibility = (trial.get("eligibility_text") or "").lower()
        
        disease_keywords = [
            "ovarian cancer", "ovarian carcinoma",
            "peritoneal cancer", "peritoneal carcinoma",
            "gynecologic malignancy", "gynecologic cancer",
            "fallopian tube cancer"
        ]
        
        all_text = f"{title} {desc} {eligibility}"
        return any(keyword in all_text for keyword in disease_keywords)
    
    def _filter_by_stage(self, trial: Dict, profile: AyeshaTrialProfile) -> bool:
        """Filter by stage (IV/advanced/metastatic)."""
        title = (trial.get("title") or "").lower()
        desc = (trial.get("description") or "").lower()
        eligibility = (trial.get("eligibility_text") or "").lower()
        
        stage_keywords = [
            "stage iv", "stage 4", "stage ivb",
            "advanced", "metastatic", "newly diagnosed advanced"
        ]
        
        all_text = f"{title} {desc} {eligibility}"
        return any(keyword in all_text for keyword in stage_keywords)
    
    def _filter_by_treatment_line(self, trial: Dict, profile: AyeshaTrialProfile) -> bool:
        """Filter by treatment line (first-line/untreated)."""
        if profile.treatment_line > 0:
            # If not treatment-naive, allow later-line trials
            return True
        
        title = (trial.get("title") or "").lower()
        desc = (trial.get("description") or "").lower()
        eligibility = (trial.get("eligibility_text") or "").lower()
        
        first_line_keywords = [
            "first-line", "frontline", "untreated",
            "newly diagnosed", "treatment-naive",
            "no prior therapy"
        ]
        
        # Exclude recurrent-only trials
        recurrent_keywords = [
            "recurrent", "relapsed", "refractory",
            "prior therapy required", "second-line"
        ]
        
        all_text = f"{title} {desc} {eligibility}"
        
        # Must have first-line keywords
        has_first_line = any(keyword in all_text for keyword in first_line_keywords)
        
        # Must NOT be recurrent-only
        is_recurrent_only = all(keyword in all_text for keyword in ["recurrent", "only"])
        
        return has_first_line and not is_recurrent_only
    
    def _filter_by_status(self, trial: Dict) -> bool:
        """Filter by trial status (Recruiting/Active)."""
        status = (trial.get("status") or "").lower()
        return status in ["recruiting", "active, not recruiting", "active"]
    
    def _filter_by_location(self, trial: Dict, profile: AyeshaTrialProfile) -> bool:
        """Filter by location (NYC metro: NY/NJ/CT)."""
        locations = trial.get("locations", [])
        
        if not locations:
            # If no location data, include (may be telehealth)
            return True
        
        # Check for NYC metro states
        nyc_metro_states = ["ny", "nj", "ct"]
        
        for loc in locations:
            state = (loc.get("state") or "").lower()
            city = (loc.get("city") or "").lower()
            
            # Check state
            if state in nyc_metro_states:
                return True
            
            # Check city (NYC metro cities)
            nyc_metro_cities = [
                "new york", "manhattan", "brooklyn", "queens", "bronx",
                "newark", "jersey city", "stamford", "bridgeport"
            ]
            if any(metro_city in city for metro_city in nyc_metro_cities):
                return True
        
        return False
    
    def _filter_exclusions(self, trial: Dict, profile: AyeshaTrialProfile) -> bool:
        """
        Filter out trials with exclusion criteria.
        
        Returns True if trial should be EXCLUDED.
        """
        title = (trial.get("title") or "").lower()
        desc = (trial.get("description") or "").lower()
        eligibility = (trial.get("eligibility_text") or "").lower()
        
        all_text = f"{title} {desc} {eligibility}"
        
        # Exclude: Germline BRCA required
        germline_brca_keywords = [
            "germline brca required", "hereditary brca",
            "brca mutation carrier", "lynch syndrome required",
            "family history required"
        ]
        if any(keyword in all_text for keyword in germline_brca_keywords):
            logger.debug(f"Excluded trial {trial.get('nct_id')}: Requires germline BRCA")
            return True
        
        # Exclude: Recurrent-only (if treatment-naive)
        if profile.treatment_line == 0:
            if "recurrent only" in all_text or "relapsed only" in all_text:
                logger.debug(f"Excluded trial {trial.get('nct_id')}: Recurrent-only")
                return True
        
        return False


