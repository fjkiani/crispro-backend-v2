"""
Match Orchestrator Module

Coordinate all modules into complete matching workflow.

Orchestrates:
1. Eligibility filters (hard filters)
2. Scoring engine (soft boosts)
3. Reasoning generator (transparent why-matched)
4. Sorting and top 10 selection
"""
import logging
from typing import Dict, List, Any
from api.schemas.ayesha_trials import AyeshaTrialProfile, AyeshaTrialMatch, AyeshaTrialSearchResponse
from api.services.ayesha_trial_matching.eligibility_filters import EligibilityFilters
from api.services.ayesha_trial_matching.scoring_engine import ScoringEngine
from api.services.ayesha_trial_matching.reasoning_generator import ReasoningGenerator
from api.services.ca125_intelligence import CA125IntelligenceService

logger = logging.getLogger(__name__)


class MatchOrchestrator:
    """Orchestrate complete trial matching workflow."""
    
    def __init__(self):
        self.eligibility_filters = EligibilityFilters()
        self.scoring_engine = ScoringEngine()
        self.reasoning_generator = ReasoningGenerator()
        self.ca125_service = CA125IntelligenceService()
    
    async def match_trials_for_ayesha(
        self,
        profile: AyeshaTrialProfile
    ) -> AyeshaTrialSearchResponse:
        """
        Complete trial matching workflow for Ayesha.
        
        Returns top 10 ranked trials with transparent reasoning.
        """
        try:
            logger.info(f"🎯 Starting trial matching for Ayesha: Stage {profile.stage}, CA-125 {profile.ca125}")
            
            # Step 1: Apply hard eligibility filters
            eligible_trials = await self.eligibility_filters.apply_hard_filters(profile)
            logger.info(f"✅ Hard filters: {len(eligible_trials)} trials passed")
            
            if not eligible_trials:
                logger.warning("⚠️ No trials passed hard filters")
                return AyeshaTrialSearchResponse(
                    trials=[],
                    total_screened=0,
                    ca125_intelligence=self.ca125_service.analyze(profile.ca125),
                    provenance={
                        "filters_applied": "stage_IV + first_line + germline_negative + NYC + recruiting",
                        "boost_strategy": "ca125_tracking + bulk_disease + IP_chemo + bevacizumab",
                        "awaiting_ngs": ["somatic_brca", "tumor_hrd", "tmb", "msi"]
                    }
                )
            
            # Step 2: Get CA-125 intelligence
            ca125_intel = self.ca125_service.analyze(profile.ca125)  # Uses simplified analyze() method
            
            # Step 3: Score and generate reasoning for each trial
            scored_trials = []
            for trial in eligible_trials:
                # Calculate match score
                match_score = self.scoring_engine.calculate_match_score(
                    trial, profile, ca125_intel
                )
                
                # Generate reasoning
                reasoning = self.reasoning_generator.generate_complete_reasoning(
                    trial, profile, ca125_intel, match_score
                )
                
                # Build trial match
                trial_match = AyeshaTrialMatch(
                    nct_id=trial.get("nct_id") or "Unknown",
                    title=trial.get("title") or "No Title",
                    phase=trial.get("phase") or "Unknown",
                    status=trial.get("status") or "Unknown",
                    interventions=trial.get("interventions", []),
                    locations=trial.get("locations", []),
                    match_score=match_score,
                    reasoning=reasoning,
                    contact_name=None,  # Leave blank per manager's decision
                    contact_phone=None,
                    contact_email=None,
                    source_url=f"https://clinicaltrials.gov/study/{trial.get('nct_id', '')}" if trial.get("nct_id") else None,
                    optimization_score=trial.get("optimization_score")
                )
                
                scored_trials.append(trial_match)
            
            # Step 4: Sort by match score (descending)
            scored_trials.sort(key=lambda t: t.match_score, reverse=True)
            
            # Step 5: Return top 10
            top_10 = scored_trials[:10]
            
            logger.info(f"✅ Trial matching complete: {len(top_10)} trials returned")
            
            return AyeshaTrialSearchResponse(
                trials=top_10,
                total_screened=len(eligible_trials),
                ca125_intelligence=ca125_intel,
                provenance={
                    "filters_applied": "stage_IV + first_line + germline_negative + NYC + recruiting",
                    "boost_strategy": "ca125_tracking + bulk_disease + IP_chemo + bevacizumab",
                    "awaiting_ngs": ["somatic_brca", "tumor_hrd", "tmb", "msi"]
                }
            )
            
        except Exception as e:
            logger.error(f"❌ Trial matching failed: {e}", exc_info=True)
            raise

