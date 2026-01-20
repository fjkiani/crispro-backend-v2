"""
Reasoning Generator Module

Generate transparent reasoning for why a trial matches (Stage 4).

Generates:
- Why eligible (hard filter matches)
- Why good fit (soft boost explanations)
- Conditional requirements (NGS-gated features)
- Red flags (warnings/concerns)
- Evidence tier (STANDARD/SUPPORTED/INVESTIGATIONAL)
- Enrollment likelihood (HIGH/MEDIUM/LOW)
"""
import logging
from typing import Dict, List, Any
from api.schemas.ayesha_trials import AyeshaTrialProfile, TrialMatchReasoning
from api.services.ayesha_trial_matching.scoring_engine import ScoringEngine

logger = logging.getLogger(__name__)


class ReasoningGenerator:
    """Generate transparent reasoning for trial matches."""
    
    def __init__(self):
        self.scoring_engine = ScoringEngine()
    
    def generate_complete_reasoning(
        self,
        trial: Dict[str, Any],
        profile: AyeshaTrialProfile,
        ca125_intel: Dict[str, Any],
        match_score: float
    ) -> TrialMatchReasoning:
        """
        Generate complete reasoning for a trial match.
        
        Returns TrialMatchReasoning with all sections populated.
        """
        why_eligible = self._generate_why_eligible(trial, profile)
        why_good_fit = self._generate_why_good_fit(trial, profile, ca125_intel, match_score)
        conditional_requirements = self._generate_conditional_requirements(trial, profile)
        red_flags = self._generate_red_flags(trial, profile)
        
        evidence_tier = self._determine_evidence_tier(trial)
        enrollment_likelihood = self._determine_enrollment_likelihood(
            why_eligible, why_good_fit, conditional_requirements, red_flags
        )
        
        return TrialMatchReasoning(
            match_score=match_score,
            why_eligible=why_eligible,
            why_good_fit=why_good_fit,
            conditional_requirements=conditional_requirements,
            red_flags=red_flags,
            evidence_tier=evidence_tier,
            enrollment_likelihood=enrollment_likelihood,
            ca125_intelligence=ca125_intel,
            germline_context={
                "status": profile.germline_status,
                "brca": profile.germline_brca,
                "implication": "Sporadic cancer - focus on tumor biomarkers, not germline"
            }
        )
    
    def _generate_why_eligible(self, trial: Dict, profile: AyeshaTrialProfile) -> List[str]:
        """Generate why eligible reasons (hard filter matches)."""
        reasons = []
        
        # Disease match
        title = (trial.get("title") or "").lower()
        desc = (trial.get("description") or "").lower()
        all_text = f"{title} {desc}"
        
        if any(kw in all_text for kw in ["ovarian cancer", "peritoneal cancer", "gynecologic"]):
            reasons.append("✅ Accepts ovarian/peritoneal/gynecologic cancer")
        
        # Stage match
        if any(kw in all_text for kw in ["stage iv", "stage 4", "advanced", "metastatic"]):
            reasons.append(f"✅ Accepts Stage {profile.stage} (advanced/metastatic)")
        
        # Treatment line match
        if profile.treatment_line == 0:
            if any(kw in all_text for kw in ["first-line", "frontline", "untreated", "newly diagnosed"]):
                reasons.append("✅ First-line therapy (you're treatment-naive)")
        
        # Status match
        status = (trial.get("status") or "").lower()
        if "recruiting" in status or "active" in status:
            reasons.append("✅ Currently recruiting or active")
        
        # Location match
        locations = trial.get("locations", [])
        nyc_metro_states = ["ny", "nj", "ct"]
        for loc in locations:
            state = (loc.get("state") or "").lower()
            if state in nyc_metro_states:
                city = loc.get("city", "Unknown")
                facility = loc.get("facility", "Unknown")
                reasons.append(f"✅ NYC metro location: {facility}, {city}")
                break
        
        # Germline status match
        if profile.germline_status == "NEGATIVE":
            if "germline brca" not in all_text or "all comers" in all_text:
                reasons.append("✅ Germline BRCA not required (you're germline-negative)")
        
        return reasons
    
    def _generate_why_good_fit(
        self,
        trial: Dict,
        profile: AyeshaTrialProfile,
        ca125_intel: Dict,
        match_score: float
    ) -> List[str]:
        """Generate why good fit reasons (soft boost explanations)."""
        reasons = []
        
        # First-line boost
        if self.scoring_engine._boost_first_line(trial, profile):
            reasons.append("🎯 First-line therapy (you're treatment-naive)")
        
        # Stage IV boost
        if self.scoring_engine._boost_stage_iv(trial, profile):
            reasons.append("🎯 Stage IV specific protocol")
        
        # SOC backbone boost
        if self.scoring_engine._boost_soc_backbone(trial):
            reasons.append("🎯 Standard-of-care chemotherapy backbone (carboplatin + paclitaxel)")
        
        # Germline-negative boost
        if self.scoring_engine._boost_germline_negative(trial, profile):
            reasons.append("🎯 Accepts germline BRCA-negative (your status)")
        
        # IP chemo boost
        if self.scoring_engine._boost_ip_chemo(trial):
            reasons.append("🎯 Intraperitoneal chemo (targets your peritoneal disease)")
        
        # Bevacizumab boost
        if self.scoring_engine._boost_bevacizumab(trial, profile):
            reasons.append("🎯 Bevacizumab (targets ascites and peritoneal disease)")
        
        # CA-125 tracking boost
        if self.scoring_engine._boost_ca125_tracking(trial, ca125_intel):
            reasons.append(f"🎯 Tracks CA-125 response (your marker is {profile.ca125})")
        
        # NYC location boost
        if self.scoring_engine._boost_nyc_location(trial, profile):
            locations = trial.get("locations", [])
            nyc_sites = [
                f"{loc.get('facility', 'Unknown')}, {loc.get('city', 'Unknown')}"
                for loc in locations
                if (loc.get("state") or "").lower() in ["ny", "nj", "ct"]
            ]
            if nyc_sites:
                reasons.append(f"📍 NYC metro location: {nyc_sites[0]}")
        
        # Large trial boost
        if self.scoring_engine._boost_large_trial(trial):
            reasons.append("🎯 Large trial (>200 patients) - more established")
        
        # Phase III boost
        if self.scoring_engine._boost_phase_iii(trial):
            reasons.append("🎯 Phase III trial - highest evidence level")
        
        return reasons
    
    def _generate_conditional_requirements(
        self,
        trial: Dict,
        profile: AyeshaTrialProfile
    ) -> List[str]:
        """Generate conditional requirements (NGS-gated features)."""
        requirements = []
        
        title = (trial.get("title") or "").lower()
        desc = (trial.get("description") or "").lower()
        eligibility = (trial.get("eligibility_text") or "").lower()
        all_text = f"{title} {desc} {eligibility}"
        
        # HRD testing
        if "hrd" in all_text or "homologous recombination" in all_text:
            if profile.tumor_hrd_score is None:
                requirements.append("⚠️ May require HRD testing when tumor NGS returns")
        
        # Somatic BRCA
        if "somatic brca" in all_text or ("brca" in all_text and "somatic" in all_text):
            if profile.somatic_brca is None:
                requirements.append("⚠️ May require somatic BRCA testing (tumor NGS pending)")
        
        # TMB
        if "tmb" in all_text or "tumor mutational burden" in all_text:
            if profile.tmb is None:
                requirements.append("⚠️ May require TMB testing (tumor NGS pending)")
        
        # MSI
        if "msi" in all_text or "microsatellite instability" in all_text:
            if profile.msi_status is None:
                requirements.append("⚠️ May require MSI testing (tumor NGS pending)")
        
        # Performance status (clinical, not NGS)
        if "ecog" in all_text or "performance status" in all_text:
            requirements.append("⚠️ Performance status ≥1 required (confirm with oncologist)")
        
        return requirements
    
    def _generate_red_flags(
        self,
        trial: Dict,
        profile: AyeshaTrialProfile
    ) -> List[str]:
        """Generate red flags (warnings/concerns)."""
        flags = []
        
        title = (trial.get("title") or "").lower()
        desc = (trial.get("description") or "").lower()
        eligibility = (trial.get("eligibility_text") or "").lower()
        all_text = f"{title} {desc} {eligibility}"
        
        # Germline BRCA required
        if self.scoring_engine._penalize_germline_brca_required(trial):
            flags.append("❌ Requires germline BRCA (you're germline-negative)")
        
        # Phase I
        if self.scoring_engine._penalize_phase_i(trial):
            flags.append("⚠️ Phase I trial (higher risk, less established)")
        
        # Distance penalty
        if self.scoring_engine._penalize_distance(trial, profile):
            flags.append("⚠️ No NYC metro locations (may require travel)")
        
        return flags
    
    def _determine_evidence_tier(self, trial: Dict) -> str:
        """Determine evidence tier."""
        phase = (trial.get("phase") or "").lower()
        
        if "phase 3" in phase or "phase iii" in phase:
            return "STANDARD"
        elif "phase 2" in phase or "phase ii" in phase:
            return "SUPPORTED"
        else:
            return "INVESTIGATIONAL"
    
    def _determine_enrollment_likelihood(
        self,
        why_eligible: List[str],
        why_good_fit: List[str],
        conditional_requirements: List[str],
        red_flags: List[str]
    ) -> str:
        """Determine enrollment likelihood."""
        eligible_count = len(why_eligible) + len(why_good_fit)
        concern_count = len(conditional_requirements) + len(red_flags)
        
        if eligible_count >= 5 and concern_count == 0:
            return "HIGH"
        elif eligible_count >= 3 and concern_count <= 2:
            return "MEDIUM"
        else:
            return "LOW"


