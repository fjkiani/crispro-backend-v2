"""
Eligibility Probability Calculator

Calculates composite probability that patient is eligible.

Formula: P(eligible) = P(stage) × P(line) × P(biomarkers)

Uses literature-based estimates when biomarkers are pending.
"""

from typing import Tuple, List, Dict, Any

# Literature-based probabilities (from strategic scenarios analysis)
HER2_POS_PROB = 0.50  # 40-60% of ovarian cancers are HER2+ (use midpoint)
HRD_NEG_PROB = 0.60  # If HRD+ is 40%, then HRD- is 60%

def calculate(trial: dict, patient: Dict[str, Any]) -> Tuple[float, List[str]]:
    """
    Calculate composite eligibility probability.
    
    Returns:
        (probability, breakdown)
    """
    prob = 1.0
    breakdown = []
    
    eligibility = trial.get('eligibility_text', '').lower()
    
    # === STAGE MATCH ===
    stage_prob = calculate_stage_probability(eligibility, patient)
    prob *= stage_prob
    if stage_prob < 1.0:
        breakdown.append(f"P(stage) = {stage_prob:.2f}")
    
    # === TREATMENT LINE ===
    line_prob = calculate_line_probability(eligibility, patient)
    prob *= line_prob
    if line_prob < 1.0:
        breakdown.append(f"P(line) = {line_prob:.2f}")
    
    # === BIOMARKER GATES ===
    biomarker_prob, biomarker_breakdown = calculate_biomarker_probability(eligibility, patient)
    prob *= biomarker_prob
    breakdown.extend(biomarker_breakdown)
    
    if not breakdown:
        breakdown.append("No specific restrictions (100% eligible)")
    
    return (prob, breakdown)

def calculate_stage_probability(eligibility: str, patient: Dict[str, Any]) -> float:
    """Calculate stage match probability"""
    patient_stage = patient['disease']['stage']
    
    # Stage IV explicit
    if 'stage iv' in eligibility or 'stage 4' in eligibility:
        return 1.0
    
    # Advanced/metastatic
    if 'advanced' in eligibility or 'metastatic' in eligibility:
        return 1.0
    
    # Stage III/IV
    if ('stage iii' in eligibility or 'stage 3' in eligibility) and ('stage iv' in eligibility or 'iii-iv' in eligibility or 'iii/iv' in eligibility):
        return 1.0
    
    # Stage III only (may accept IV off-label)
    if 'stage iii' in eligibility or 'stage 3' in eligibility:
        return 0.5  # 50% chance they accept Stage IV
    
    # No stage restriction
    return 1.0

def calculate_line_probability(eligibility: str, patient: Dict[str, Any]) -> float:
    """Calculate treatment line probability"""
    patient_line = patient['treatment']['line']
    
    # Frontline/first-line/primary
    if 'first' in eligibility or 'frontline' in eligibility or 'primary' in eligibility or '1l' in eligibility:
        return 1.0
    
    # Maintenance (after first-line)
    if 'maintenance' in eligibility:
        return 0.8  # Ayesha will need maintenance after frontline
    
    # Recurrent/relapsed (Ayesha is treatment-naive)
    if 'recurrent' in eligibility or 'relapsed' in eligibility or 'platinum-resistant' in eligibility:
        return 0.2  # Low chance (she's first-line)
    
    # No line restriction
    return 1.0

def calculate_biomarker_probability(eligibility: str, patient: Dict[str, Any]) -> Tuple[float, List[str]]:
    """Calculate biomarker gate probability"""
    prob = 1.0
    breakdown = []
    
    # === HER2 CHECK ===
    if 'her2' in eligibility:
        if 'her2+' in eligibility or 'her2 positive' in eligibility or 'her2 1+' in eligibility or 'her2 2+' in eligibility or 'her2 3+' in eligibility:
            # HER2+ required
            her2_status = patient['biomarkers']['her2_status']
            if her2_status == 'UNKNOWN':
                # Use literature estimate
                prob *= HER2_POS_PROB
                breakdown.append(f"P(HER2+) = {HER2_POS_PROB:.2f} (literature, pending test)")
            elif her2_status == 'POSITIVE':
                breakdown.append("P(HER2+) = 1.00 (confirmed)")
            else:
                # HER2 negative - NOT ELIGIBLE
                prob = 0.0
                breakdown.append("P(HER2+) = 0.00 (patient is HER2-) → NOT ELIGIBLE")
        
        elif 'her2-' in eligibility or 'her2 negative' in eligibility or 'her2 0' in eligibility:
            # HER2- required
            her2_status = patient['biomarkers']['her2_status']
            if her2_status == 'UNKNOWN':
                prob *= (1 - HER2_POS_PROB)
                breakdown.append(f"P(HER2-) = {1-HER2_POS_PROB:.2f} (literature, pending test)")
            elif her2_status == 'NEGATIVE':
                breakdown.append("P(HER2-) = 1.00 (confirmed)")
            else:
                prob = 0.0
                breakdown.append("P(HER2-) = 0.00 (patient is HER2+) → NOT ELIGIBLE")
    
    # === HRD CHECK ===
    if 'hrd' in eligibility or 'homologous recombination' in eligibility:
        if 'hrd-positive' in eligibility or 'hrd+' in eligibility or 'hrd ≥' in eligibility:
            # HRD+ required
            hrd_status = patient['biomarkers']['hrd_status']
            if hrd_status == 'UNKNOWN':
                prob *= 0.40  # 40% of BRCA- are HRD+ (literature)
                breakdown.append("P(HRD+) = 0.40 (literature: BRCA- → 40% HRD+, pending test)")
            elif hrd_status in ['POSITIVE', 'HIGH']:
                breakdown.append("P(HRD+) = 1.00 (confirmed)")
            else:
                prob = 0.0
                breakdown.append("P(HRD+) = 0.00 (patient is HRD-) → NOT ELIGIBLE")
        
        elif 'hrd-negative' in eligibility or 'hrd-' in eligibility or 'hrd <' in eligibility:
            # HRD- required
            hrd_status = patient['biomarkers']['hrd_status']
            if hrd_status == 'UNKNOWN':
                prob *= HRD_NEG_PROB
                breakdown.append(f"P(HRD-) = {HRD_NEG_PROB:.2f} (literature, pending test)")
            elif hrd_status in ['NEGATIVE', 'LOW']:
                breakdown.append("P(HRD-) = 1.00 (confirmed)")
            else:
                prob = 0.0
                breakdown.append("P(HRD-) = 0.00 (patient is HRD+) → NOT ELIGIBLE")
    
    # === BRCA CHECK ===
    if 'brca' in eligibility:
        if 'brca mutation' in eligibility or 'brca+' in eligibility or 'brca1/2 positive' in eligibility:
            # BRCA+ required
            brca_status = patient['biomarkers']['germline_status']
            if brca_status == 'NEGATIVE':
                prob = 0.0
                breakdown.append("P(BRCA+) = 0.00 (patient is BRCA wildtype) → NOT ELIGIBLE")
        
        elif 'brca wildtype' in eligibility or 'brca-' in eligibility or 'brca negative' in eligibility:
            # BRCA- required (Ayesha matches!)
            breakdown.append("P(BRCA wildtype) = 1.00 (confirmed)")
    
    return (prob, breakdown)


