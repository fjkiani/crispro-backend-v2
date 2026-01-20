"""
Eligibility Scorer

Computes eligibility score from hard/soft criteria (recruiting status, disease match, age, location, biomarkers).
"""

from typing import Dict, List, Any, Tuple


def compute_eligibility(
    patient_profile: Dict[str, Any],
    trial: Dict[str, Any]
) -> Tuple[float, List[str]]:
    """
    Compute eligibility score from hard/soft criteria.
    
    Returns normalized 0-1 score and breakdown of criteria.
    
    Args:
        patient_profile: Patient data with disease, age, location, mutations
        trial: Trial data with overall_status, conditions, age requirements, locations, biomarker_requirements
    
    Returns:
        Tuple of (eligibility_score, eligibility_breakdown_list)
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
