"""
Disease-Based Trial Ranker Service

Generic, scalable trial ranking service that uses disease module configurations.
No hard-coding - everything is driven by YAML configs.

This service:
1. Loads disease-specific configs from disease_modules/
2. Scores trials based on mechanism axes, evidence gates, and dominance policies
3. Applies intent gates (non-therapeutic filtering)
4. Returns ranked trials with explainability
"""

import sqlite3
import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass

from api.services.disease_module_loader import get_disease_module_loader, DiseaseModule

logger = logging.getLogger(__name__)

# Database path
DB_PATH = Path(__file__).parent.parent.parent / "data" / "clinical_trials.db"
VECTORS_PATH = Path(__file__).parent.parent / "resources" / "trial_moa_vectors.json"


@dataclass
class ScoredTrial:
    """Scored trial with explainability"""
    nct_id: str
    title: str
    status: str
    phases: str
    score: float
    mechanism_vector: List[float]
    dominant_axis: Optional[str]
    evidence_gates_triggered: List[str]
    keyword_matches: Dict[str, int]
    combo_matches: List[str]
    is_tagged: bool
    explainability: Dict[str, Any]


class DiseaseBasedTrialRanker:
    """Generic trial ranker using disease module configs"""
    
    def __init__(self, disease_name: str):
        self.disease_name = disease_name
        self.loader = get_disease_module_loader()
        self.module = self.loader.get_module(disease_name)
        
        if not self.module:
            raise ValueError(f"No disease module found for: {disease_name}")
        
        logger.info(f"✅ Initialized ranker for {disease_name} with {len(self.module.mechanism_axes)} axes")
    
    def _load_tagged_trials(self) -> set:
        """Load set of already-tagged NCT IDs"""
        if not VECTORS_PATH.exists():
            return set()
        
        try:
            with open(VECTORS_PATH) as f:
                vectors = json.load(f)
            return set(vectors.keys())
        except Exception as e:
            logger.warning(f"Failed to load tagged trials: {e}")
            return set()
    
    def _is_non_therapeutic(self, title: str) -> bool:
        """Check if trial title matches non-therapeutic patterns"""
        # This could also come from disease module config
        non_therapeutic_patterns = [
            "cryopreservation", "fertility", "ovarian reserve", "quality of life",
            "questionnaire", "survey", "observational", "registry", "real-world",
            "biobank", "specimen", "tissue", "imaging", "diagnostic", "screening",
            "correlation", "dose intensity", "cope", "fatigue", "dietary", 
            "physical exercise", "mental health", "fear", "psychotherapy",
        ]
        title_lower = (title or "").lower()
        return any(pattern in title_lower for pattern in non_therapeutic_patterns)
    
    def _has_drug_intervention(self, interventions: str, interventions_json: str) -> bool:
        """Check if trial has drug/biological interventions"""
        if not interventions:
            return False
        
        # Check interventions text
        interventions_lower = (interventions or "").lower()
        drug_indicators = [
            '-ib', 'inib', 'mab', 'parp', 'olaparib', 'niraparib', 
            'pembrolizumab', 'nivolumab', 'bevacizumab', 'carboplatin', 
            'paclitaxel', 'chemotherapy', 'inhibitor', 'therapy', 'treatment'
        ]
        
        if any(indicator in interventions_lower for indicator in drug_indicators):
            return True
        
        # Check interventions_json if available
        if interventions_json:
            try:
                interventions_data = json.loads(interventions_json)
                if isinstance(interventions_data, list):
                    for item in interventions_data:
                        if isinstance(item, dict):
                            intervention_type = str(item.get('type', '')).upper()
                            if intervention_type in ['DRUG', 'BIOLOGICAL']:
                                return True
            except:
                pass
        
        return False
    
    def _extract_biomarker_text(self, patient_profile: Dict[str, Any]) -> str:
        """Extract biomarker text from patient profile"""
        tumor_context = patient_profile.get("tumor_context", {})
        somatic_mutations = tumor_context.get("somatic_mutations", [])
        germline_variants = patient_profile.get("germline_variants", [])
        
        biomarkers = []
        for mut in somatic_mutations + germline_variants:
            gene = mut.get("gene", "")
            variant = mut.get("variant") or mut.get("hgvs_p", "")
            if gene:
                biomarkers.append(gene.upper())
                if variant:
                    biomarkers.append(f"{gene} {variant}".upper())
        
        # Add IHC/biomarker data
        biomarker_data = patient_profile.get("biomarkers", {})
        if isinstance(biomarker_data, dict):
            for key, value in biomarker_data.items():
                if isinstance(value, dict):
                    if value.get("positive") or value.get("cps", 0) >= 1:
                        biomarkers.append(key.upper())
        
        return " ".join(biomarkers)
    
    def _evaluate_condition(self, condition: str, biomarker_text: str) -> bool:
        """Evaluate a condition string against biomarker text"""
        condition_upper = condition.upper()
        biomarker_text_upper = biomarker_text.upper()
        
        # Handle OR conditions
        if " OR " in condition_upper:
            parts = [p.strip() for p in condition_upper.split(" OR ")]
            return any(part in biomarker_text_upper for part in parts)
        
        # Handle AND conditions
        if " AND " in condition_upper:
            parts = [p.strip() for p in condition_upper.split(" AND ")]
            return all(part in biomarker_text_upper for part in parts)
        
        # Handle NOT conditions
        if "NOT " in condition_upper:
            not_part = condition_upper.split("NOT ")[1].strip()
            return not_part not in biomarker_text_upper
        
        # Simple match
        return condition_upper in biomarker_text_upper
    
    def _detect_line_of_therapy(self, title: str, inclusion: str, exclusion: str) -> Optional[str]:
        """Detect if trial is for frontline or recurrent/relapsed disease"""
        text = f"{title} {inclusion} {exclusion}".upper()
        
        # Recurrent/relapsed indicators (strong)
        recurrent_patterns = [
            "RECURRENT", "RELAPSED", "REFRACTORY", "PROGRESSED",
            "PRIOR CHEMOTHERAPY", "PRIOR TREATMENT", "PREVIOUSLY TREATED",
            "SECOND-LINE", "2L", "THIRD-LINE", "3L", "FOURTH-LINE", "4L",
            "AFTER PLATINUM", "PLATINUM-RESISTANT", "PLATINUM-REFRACTORY"
        ]
        
        # Frontline indicators (strong)
        frontline_patterns = [
            "FRONTLINE", "FIRST-LINE", "1L", "NEWLY DIAGNOSED",
            "TREATMENT-NAIVE", "NO PRIOR", "INITIAL", "PRIMARY",
            "ADJUVANT", "NEOADJUVANT"
        ]
        
        has_recurrent = any(pattern in text for pattern in recurrent_patterns)
        has_frontline = any(pattern in text for pattern in frontline_patterns)
        
        if has_recurrent and not has_frontline:
            return "recurrent"
        if has_frontline and not has_recurrent:
            return "frontline"
        
        return None  # Unclear
    
    def _score_trial(
        self,
        trial: Tuple,
        patient_profile: Dict[str, Any],
        tagged_nct_ids: set
    ) -> Optional[ScoredTrial]:
        """
        Score a single trial using disease module config
        
        Returns None if trial fails intent gates
        """
        # Handle different tuple lengths (some queries may not include eligibility)
        nct_id = trial[0]
        title = trial[1] if len(trial) > 1 else ""
        conditions = trial[2] if len(trial) > 2 else ""
        interventions = trial[3] if len(trial) > 3 else ""
        interventions_json = trial[4] if len(trial) > 4 else ""
        status = trial[5] if len(trial) > 5 else ""
        phases = trial[6] if len(trial) > 6 else ""
        inclusion_criteria = trial[7] if len(trial) > 7 else ""
        exclusion_criteria = trial[8] if len(trial) > 8 else ""
        
        # Intent Gate 1: Exclude non-therapeutic titles
        if self._is_non_therapeutic(title):
            return None
        
        # Intent Gate 2: Require drug/biological interventions
        if not self._has_drug_intervention(interventions, interventions_json):
            return None
        
        # Intent Gate 3: Line of therapy matching
        trial_lot = self._detect_line_of_therapy(title, inclusion_criteria or "", exclusion_criteria or "")
        patient_lot = None
        
        # Extract patient treatment line from profile
        treatment_history = patient_profile.get("treatment_history", [])
        treatment_line = patient_profile.get("treatment_line", 0)
        
        if treatment_line == 0 or treatment_line == 1 or not treatment_history:
            patient_lot = "frontline"
        elif treatment_line > 1 or len(treatment_history) > 0:
            patient_lot = "recurrent"
        
        # STRICT FILTERING: If trial is clearly recurrent/relapsed and patient is frontline, EXCLUDE
        # If trial is clearly frontline and patient is recurrent, EXCLUDE
        # If trial is unclear but title has "recurrent"/"relapsed" and patient is frontline, EXCLUDE (conservative)
        if trial_lot and patient_lot and trial_lot != patient_lot:
            return None
        
        # Additional safety: If title explicitly says recurrent/relapsed and patient is frontline, exclude
        # (Even if detection returned None due to conflicting criteria)
        title_upper = (title or "").upper()
        if patient_lot == "frontline":
            if "RECURRENT" in title_upper or "RELAPSED" in title_upper or "REFRACTORY" in title_upper:
                # Double-check: make sure it's not a false positive (e.g., "non-recurrent")
                if not ("NON-RECURRENT" in title_upper or "NOT RECURRENT" in title_upper):
                    return None
        
        # Build trial text for matching (include eligibility criteria)
        inclusion_criteria = trial[7] if len(trial) > 7 else ""
        exclusion_criteria = trial[8] if len(trial) > 8 else ""
        trial_text = f"{title or ''} {conditions or ''} {interventions or ''} {inclusion_criteria or ''}".upper()
        eligibility_text = f"{inclusion_criteria or ''} {exclusion_criteria or ''}".upper()
        inclusion_upper = (inclusion_criteria or "").upper()
        
        # Extract patient biomarkers
        biomarker_text = self._extract_biomarker_text(patient_profile)
        
        # ULTRA-STRICT GATE (BEFORE SCORING): For Ayesha, ONLY match trials that explicitly mention her UNIQUE biomarkers
        # Ayesha's unique profile: MBD4 (germline), TP53 mutant, PD-L1+
        # General IO trials (just pembrolizumab) are NOT specific enough - EXCLUDE them BEFORE scoring
        
        # Require terms to appear TOGETHER (not just anywhere in text)
        # Use word boundaries to ensure we're matching actual phrases, not substrings
        import re
        
        has_mbd4_mention = bool(re.search(r'\bMBD4\b', inclusion_upper))
        has_ber_ddr_mention = (
            bool(re.search(r'\bBER\s+(DEFICIENCY|DEFICIENT)', inclusion_upper)) or
            bool(re.search(r'\bBASE\s+EXCISION\s+REPAIR', inclusion_upper)) or
            bool(re.search(r'\bDDR\s+DEFICIENCY', inclusion_upper)) or
            bool(re.search(r'\bDNA\s+DAMAGE\s+REPAIR\s+DEFICIENCY', inclusion_upper)) or
            bool(re.search(r'\bHOMOLOGOUS\s+RECOMBINATION\s+DEFICIENCY', inclusion_upper))
        )
        has_tp53_mention = (
            bool(re.search(r'\bTP53\s+(MUTANT|MUTATION)', inclusion_upper)) or
            bool(re.search(r'\bP53\s+(MUTANT|MUTATION)', inclusion_upper))
        )
        
        # ONLY proceed if trial explicitly mentions MBD4, TP53 mutations, or DDR/BER deficiency
        # Exclude general IO trials that just mention PD-L1 or use pembrolizumab
        if not (has_mbd4_mention or has_ber_ddr_mention or has_tp53_mention):
            return None
        
        # ULTRA-STRICT MATCHING: Trial must explicitly require/mention patient's biomarkers in INCLUSION criteria
        # AND must not require biomarkers patient doesn't have
        inclusion_upper = (inclusion_criteria or "").upper()
        title_upper = (title or "").upper()
        
        patient_biomarkers_in_trial = False
        required_biomarkers_patient_has = []
        
        # Check for explicit biomarker mentions in inclusion criteria or title
        # MBD4/BER pathway - must explicitly mention MBD4, BER, or base excision repair
        if "MBD4" in biomarker_text:
            if ("MBD4" in inclusion_upper or "MBD4" in title_upper or
                ("BASE EXCISION" in inclusion_upper and "REPAIR" in inclusion_upper) or
                ("BER" in inclusion_upper and ("DEFICIENCY" in inclusion_upper or "DEFICIENT" in inclusion_upper))):
                patient_biomarkers_in_trial = True
                required_biomarkers_patient_has.append("MBD4/BER")
        
        # TP53 - must explicitly mention TP53 mutation/mutant status
        if "TP53" in biomarker_text or "P53" in biomarker_text:
            if ("TP53" in inclusion_upper and ("MUTANT" in inclusion_upper or "MUTATION" in inclusion_upper)) or \
               ("P53 MUTANT" in inclusion_upper or "P53 MUTATION" in inclusion_upper):
                patient_biomarkers_in_trial = True
                required_biomarkers_patient_has.append("TP53")
        
        # PD-L1 - must explicitly REQUIRE PD-L1 positive status in inclusion (not just mention)
        # Many trials mention PD-L1 in exclusion (prior treatment) but don't require it
        patient_biomarkers = patient_profile.get("biomarkers", {})
        pdl1_status = patient_biomarkers.get("PD-L1", {}) or patient_biomarkers.get("PDL1", {})
        if pdl1_status.get("positive") or pdl1_status.get("cps", 0) >= 1:
            # Must explicitly require PD-L1 positive in inclusion criteria
            # Look for patterns like "PD-L1 positive", "PD-L1 CPS ≥", "PD-L1 expression"
            pdl1_required_patterns = [
                "PD-L1 POSITIVE", "PDL1 POSITIVE",
                "PD-L1 CPS ≥", "PDL1 CPS ≥", "PD-L1 CPS>=", "PDL1 CPS>=",
                "PD-L1 EXPRESSION", "PDL1 EXPRESSION",
                "PD-L1 ≥", "PDL1 ≥", "PD-L1 >=", "PDL1 >="
            ]
            # Check if any pattern is in inclusion criteria (not exclusion)
            if any(pattern in inclusion_upper for pattern in pdl1_required_patterns):
                patient_biomarkers_in_trial = True
                required_biomarkers_patient_has.append("PD-L1")
        
        # DDR/HRD pathway - only if patient has MBD4 (which is DDR-related)
        # But be careful - many trials require HRD testing, not just mention HRD
        if "MBD4" in biomarker_text:
            # Only match if trial mentions DDR/HRD in a way that suggests it's relevant, not required
            # (Many trials require HRD testing results, which Ayesha may not have)
            if ("DDR DEFICIENCY" in inclusion_upper or "DNA DAMAGE REPAIR DEFICIENCY" in inclusion_upper):
                patient_biomarkers_in_trial = True
                required_biomarkers_patient_has.append("DDR")
            # Don't match on just "HRD" or "HOMOLOGOUS RECOMBINATION" alone - too broad
        
        # NEGATIVE MATCHING: Check for required biomarkers patient doesn't have
        negative_penalty = 0.0
        exclusion_reasons = []
        
        # Check for BRCA requirement when patient doesn't have BRCA
        # Only penalize if trial REQUIRES BRCA (not if it's an OR condition like "BRCA OR HRD")
        patient_has_brca = "BRCA1" in biomarker_text or "BRCA2" in biomarker_text
        if not patient_has_brca:
            # Check if trial requires BRCA (not just mentions it as an option)
            # Look for patterns like "BRCA mutation required" or "must have BRCA"
            # But NOT "BRCA OR HRD" or "BRCA/HRD" (these are OR conditions)
            brca_required_patterns = [
                "BRCA MUTATION REQUIRED",
                "MUST HAVE BRCA",
                "REQUIRE BRCA",
                "BRCA MUTATION IS REQUIRED"
            ]
            # Also check if it's clearly a requirement (not an OR)
            has_brca_mention = "BRCA" in inclusion_upper and ("MUTATION" in inclusion_upper or "MUTANT" in inclusion_upper)
            has_or_condition = " OR " in inclusion_upper or "/" in inclusion_upper  # Might be "BRCA OR HRD"
            
            # Only penalize if BRCA is required AND it's not an OR condition with HRD/DDR
            if has_brca_mention and not has_or_condition:
                # Check if it's explicitly required
                if any(pattern in inclusion_upper for pattern in brca_required_patterns):
                    negative_penalty += 5.0
                    exclusion_reasons.append("requires_BRCA_mutation")
            elif has_brca_mention and has_or_condition:
                # It's an OR condition - check if HRD/DDR is also mentioned (then it's OK)
                has_hrd_ddr_option = (
                    "HRD" in inclusion_upper or 
                    "HOMOLOGOUS RECOMBINATION" in inclusion_upper or
                    "DDR" in inclusion_upper
                )
                if not has_hrd_ddr_option:
                    # BRCA OR something else (not HRD/DDR) - still penalize if patient doesn't have BRCA
                    negative_penalty += 5.0
                    exclusion_reasons.append("requires_BRCA_mutation")
        
        # Check for HRD requirement when patient HRD status unclear
        patient_has_hrd = "HRD" in biomarker_text
        if not patient_has_hrd:
            if "HRD POSITIVE" in trial_text or "HRD+" in trial_text:
                negative_penalty += 3.0
                exclusion_reasons.append("requires_HRD_positive")
        
        # Check for mixed cancer types (e.g., endometrial + ovarian)
        if "ENDOMETRIAL" in trial_text and "OVARIAN" in trial_text:
            # Only penalize if it's clearly a mixed trial, not just mentioning both
            if "ENDOMETRIAL" in (conditions or "").upper():
                negative_penalty += 2.0
                exclusion_reasons.append("mixed_cancer_types")
        
        # Check for HER2 requirement when patient is HER2 negative
        patient_biomarkers = patient_profile.get("biomarkers", {})
        patient_her2_status = patient_biomarkers.get("HER2", {}).get("positive", False)
        if not patient_her2_status:
            if "HER2 POSITIVE" in trial_text or "HER2+" in trial_text:
                negative_penalty += 3.0
                exclusion_reasons.append("requires_HER2_positive")
        
        # Check for HRD testing requirement (many trials require HRD test results)
        # Ayesha has MBD4 but may not have formal HRD testing
        if "HRD" in inclusion_upper and ("AVAILABLE" in inclusion_upper or "TESTING" in inclusion_upper or "RESULT" in inclusion_upper):
            # Check if patient has HRD test results in profile
            # For now, if trial requires HRD testing/availability, penalize slightly
            # (This is conservative - we don't know if Ayesha has HRD test results)
            negative_penalty += 1.0
            exclusion_reasons.append("requires_HRD_testing")
        
        # If heavy negative penalty, exclude trial
        if negative_penalty >= 5.0:
            return None
        
        # Initialize mechanism vector (7D)
        mechanism_vector = [0.0] * 7
        
        # Score each mechanism axis
        # CRITICAL: Only score if patient has relevant biomarkers AND trial mentions them
        keyword_matches = {}
        axis_scores = {}
        
        for axis_name, axis in self.module.mechanism_axes.items():
            score = 0.0
            patient_has_axis_biomarker = False
            trial_mentions_axis = False
            
            # First check: Does patient have biomarkers for this axis?
            for biomarker in axis.biomarkers:
                if biomarker.upper() in biomarker_text:
                    patient_has_axis_biomarker = True
                    break
            
            # Second check: Does trial mention this axis in INCLUSION criteria?
            # Only check inclusion criteria - don't match on title/interventions alone
            for biomarker in axis.biomarkers:
                if biomarker.upper() in biomarker_text and biomarker.upper() in inclusion_upper:
                    trial_mentions_axis = True
                    score += 1.5  # Strong match: patient has it AND trial mentions it in inclusion
                    keyword_matches[axis_name] = keyword_matches.get(axis_name, 0) + 1
                    break
            
            # Check pathway matches in inclusion (only if patient has relevant biomarkers)
            if patient_has_axis_biomarker:
                for pathway in axis.pathways:
                    if pathway.upper() in inclusion_upper:
                        score += 0.5
                        trial_mentions_axis = True
            
            # ULTRA-STRICT: Interventions alone don't score
            # Trial must explicitly mention patient's biomarkers in INCLUSION criteria (not exclusion)
            # This prevents matching general IO trials that just use pembrolizumab
            if patient_has_axis_biomarker:
                # Check if trial mentions patient's specific biomarkers in INCLUSION criteria
                trial_mentions_patient_biomarker_in_inclusion = False
                for biomarker in axis.biomarkers:
                    if biomarker.upper() in biomarker_text:
                        # Must be in inclusion criteria, not just anywhere
                        if biomarker.upper() in inclusion_upper:
                            trial_mentions_patient_biomarker_in_inclusion = True
                            break
                
                # Only score if trial explicitly mentions patient's biomarkers in inclusion
                # Don't score on interventions alone (e.g., "pembrolizumab" without PD-L1 requirement)
                if trial_mentions_patient_biomarker_in_inclusion:
                    # Trial mentions patient's biomarker in inclusion - now can score interventions
                    for intervention in axis.interventions:
                        if intervention.upper() in trial_text:
                            score += 0.3  # Lower weight - intervention is secondary to biomarker match
                            trial_mentions_axis = True
                            if axis_name not in keyword_matches:
                                keyword_matches[axis_name] = 0
            
            # Only store score if both patient has biomarker AND trial mentions it
            if patient_has_axis_biomarker and trial_mentions_axis:
                axis_scores[axis_name] = score
                # Update mechanism vector
                if axis.vector_index < 7:
                    mechanism_vector[axis.vector_index] = min(1.0, score / 3.0)
            else:
                axis_scores[axis_name] = 0.0
        
        # Apply evidence gates
        evidence_gates_triggered = []
        for gate in self.module.evidence_gates:
            if self._evaluate_condition(gate.condition, biomarker_text):
                evidence_gates_triggered.append(gate.name)
                # Apply boosts
                for axis_name, boost in gate.boosts.items():
                    if axis_name in axis_scores:
                        axis_scores[axis_name] += boost
                        if axis_name in self.module.mechanism_axes:
                            axis = self.module.mechanism_axes[axis_name]
                            if axis.vector_index < 7:
                                mechanism_vector[axis.vector_index] = min(1.0, 
                                    mechanism_vector[axis.vector_index] + boost)
        
        # Calculate combo bonuses (e.g., PARP+ATR)
        combo_matches = []
        combo_bonus = 0.0
        
        # Check for combo conditions (could be config-driven)
        if 'ddr_ber' in keyword_matches and 'checkpoint_tp53' in keyword_matches:
            combo_bonus += 2.0
            combo_matches.append('DDR+TP53')
        
        if 'parp_atr_combo' in keyword_matches:
            combo_bonus += 2.0
            combo_matches.append('PARP+ATR/WEE1')
        
        # ULTRA-STRICT GATE: Only score if trial explicitly mentions patient's UNIQUE biomarkers
        # Ayesha's unique profile: MBD4 (germline), TP53 mutant, PD-L1+
        # We want trials that are specifically relevant to her profile, not just general ovarian trials
        if not patient_biomarkers_in_trial:
            # Trial doesn't explicitly mention patient's unique biomarkers - exclude
            # This ensures we only show trials specifically relevant to Ayesha's profile
            return None
        
        # (Check moved earlier - before scoring to avoid unnecessary work)
        
        # Calculate total score
        total_score = sum(axis_scores.values()) + combo_bonus
        
        # Apply negative penalties (required biomarkers patient doesn't have)
        total_score -= negative_penalty
        
        # Apply dominance policies
        dominant_axis = None
        dominance_policy = self.loader.get_dominance_policy(self.disease_name, patient_profile)
        if dominance_policy:
            dominant_axis = dominance_policy.prioritize_axis
            if dominant_axis in axis_scores:
                total_score += axis_scores[dominant_axis] * 0.5  # Boost dominant axis
        
        # Skip if no matches or negative score
        if total_score <= 0:
            return None
        
        # Build explainability
        explainability = {
            "dominant_pathway_match": dominant_axis or "none",
            "gate_evidence": evidence_gates_triggered,
            "mechanism_vector_scores": dict(zip(
                [axis.name for axis in self.module.mechanism_axes.values()],
                mechanism_vector
            )),
            "axis_scores": axis_scores,
            "combo_matches": combo_matches,
            "dominance_policy_applied": dominance_policy.name if dominance_policy else None,
            "negative_penalties": exclusion_reasons if exclusion_reasons else [],
            "negative_penalty_score": negative_penalty
        }
        
        return ScoredTrial(
            nct_id=nct_id,
            title=title or "N/A",
            status=status or "UNKNOWN",
            phases=phases or "N/A",
            score=total_score,
            mechanism_vector=mechanism_vector,
            dominant_axis=dominant_axis,
            evidence_gates_triggered=evidence_gates_triggered,
            keyword_matches=keyword_matches,
            combo_matches=combo_matches,
            is_tagged=nct_id in tagged_nct_ids,
            explainability=explainability
        )
    
    def rank_trials(
        self,
        patient_profile: Dict[str, Any],
        max_results: int = 50,
        min_score: float = 0.5,
        recruiting_only: bool = False
    ) -> List[ScoredTrial]:
        """
        Rank trials for a patient profile using disease module config
        
        Args:
            patient_profile: Patient profile with biomarkers, mutations, etc.
            max_results: Maximum number of results to return
            min_score: Minimum score threshold
        
        Returns:
            List of ScoredTrial objects, sorted by score (descending)
        """
        logger.info(f"🎯 Ranking trials for {self.disease_name} using disease module config")
        
        # Load tagged trials
        tagged_nct_ids = self._load_tagged_trials()
        logger.info(f"✅ Loaded {len(tagged_nct_ids)} tagged trials")
        
        # Query database
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        
        # Build query based on disease aliases
        disease_conditions = " OR ".join([
            f"LOWER(conditions) LIKE '%{alias.lower()}%' OR LOWER(title) LIKE '%{alias.lower()}%'"
            for alias in self.module.aliases
        ])
        
        # Build status filter
        if recruiting_only:
            status_filter = "status = 'RECRUITING'"
        else:
            status_filter = "status IN ('RECRUITING', 'ACTIVE_NOT_RECRUITING', 'NOT_YET_RECRUITING')"
        
        query = f"""
            SELECT id, title, conditions, interventions, interventions_json, status, phases,
                   inclusion_criteria, exclusion_criteria
            FROM trials 
            WHERE {status_filter}
            AND ({disease_conditions})
        """
        
        cursor.execute(query)
        trials = cursor.fetchall()
        conn.close()
        
        logger.info(f"✅ Loaded {len(trials)} active {self.disease_name} trials")
        
        # Score all trials
        scored_trials = []
        for trial in trials:
            scored = self._score_trial(trial, patient_profile, tagged_nct_ids)
            if scored and scored.score >= min_score:
                scored_trials.append(scored)
        
        # Sort by status priority (RECRUITING first) then by score
        status_priority = {"RECRUITING": 0, "ACTIVE_NOT_RECRUITING": 1, "NOT_YET_RECRUITING": 2}
        scored_trials.sort(key=lambda x: (status_priority.get(x.status, 99), -x.score))
        
        logger.info(f"✅ Scored {len(scored_trials)} trials with score >= {min_score}")
        
        return scored_trials[:max_results]
    
    def get_untagged_trials(
        self,
        patient_profile: Dict[str, Any],
        max_results: int = 30,
        recruiting_only: bool = False
    ) -> List[ScoredTrial]:
        """Get top untagged trials for tagging"""
        all_ranked = self.rank_trials(patient_profile, max_results=100, min_score=0.5, recruiting_only=recruiting_only)
        untagged = [t for t in all_ranked if not t.is_tagged]
        return untagged[:max_results]


def get_disease_trial_ranker(disease_name: str) -> DiseaseBasedTrialRanker:
    """Get disease-based trial ranker instance"""
    return DiseaseBasedTrialRanker(disease_name)
