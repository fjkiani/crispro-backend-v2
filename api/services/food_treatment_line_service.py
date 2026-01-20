"""
Food Treatment Line Service

Computes SAE features (line appropriateness, cross-resistance, sequencing fitness)
for dietary supplements based on:
- Compound-specific rules
- Biomarker context
- Treatment history
"""

import json
import re
from pathlib import Path
from typing import Dict, Any, Optional

def normalize_treatment_line(treatment_line: Any) -> str:
    """
    Normalize treatment line format to "L1", "L2", "L3" format.
    
    Handles multiple formats:
    - "L1", "L2", "L3" → "L1", "L2", "L3"
    - "first-line", "first line", "frontline", "primary", "1l" → "L1"
    - "second-line", "second line", "2l" → "L2"
    - "third-line", "third line", "3l", "maintenance" → "L3"
    - Integer 1, 2, 3 → "L1", "L2", "L3"
    
    Args:
        treatment_line: Treatment line in any format (str, int, or None)
    
    Returns:
        Normalized treatment line string ("L1", "L2", "L3") or "L1" as default
    """
    if treatment_line is None:
        return "L1"
    
    # Handle integer input
    if isinstance(treatment_line, int):
        if treatment_line <= 1:
            return "L1"
        elif treatment_line == 2:
            return "L2"
        else:
            return "L3"
    
    # Handle string input
    if isinstance(treatment_line, str):
        line_lower = treatment_line.lower().strip()
        
        # Already in "L1", "L2", "L3" format
        if re.match(r'^l[123]$', line_lower):
            return line_lower.upper()
        
        # Extract number from "L1", "L2", etc.
        match = re.search(r'l\s*(\d+)', line_lower)
        if match:
            num = int(match.group(1))
            if num <= 1:
                return "L1"
            elif num == 2:
                return "L2"
            else:
                return "L3"
        
        # Extract number from "1l", "2l", etc.
        match = re.search(r'(\d+)\s*l', line_lower)
        if match:
            num = int(match.group(1))
            if num <= 1:
                return "L1"
            elif num == 2:
                return "L2"
            else:
                return "L3"
        
        # Extract number from standalone digits
        match = re.search(r'^(\d+)$', line_lower)
        if match:
            num = int(match.group(1))
            if num <= 1:
                return "L1"
            elif num == 2:
                return "L2"
            else:
                return "L3"
        
        # Handle text-based formats
        if any(term in line_lower for term in ['first', 'frontline', 'primary', 'initial']):
            return "L1"
        elif any(term in line_lower for term in ['second', '2nd']):
            return "L2"
        elif any(term in line_lower for term in ['third', '3rd', 'maintenance', 'salvage']):
            return "L3"
    
    # Default to L1 if unrecognized
    return "L1"

def load_supplement_rules() -> Dict[str, Any]:
    """Load supplement treatment rules from JSON file."""
    rules_file = Path(__file__).parent.parent.parent.parent.parent / ".cursor/ayesha/hypothesis_validator/data/supplement_treatment_rules.json"
    
    if rules_file.exists():
        with open(rules_file) as f:
            return json.load(f)
    else:
        # Return default rules if file doesn't exist
        return {
            "supplement_rules": {},
            "default_supplement": {
                "line_appropriateness": 0.6,
                "cross_resistance": 0.0,
                "sequencing_fitness": 0.6
            }
        }


def get_line_specific_adjustment(compound_rule: Optional[Dict], treatment_line: str) -> Dict[str, float]:
    """
    Get treatment line-specific score adjustments.
    
    Logic:
    - Recovery supplements (post_platinum, post_chemotherapy) are MORE appropriate in L2/L3
    - General supplements (dna_repair_support, immune) are appropriate across all lines
    - Some supplements should be avoided in specific lines
    
    Returns:
        Dict with adjustment values (can be negative)
    """
    adjustment = {"line_appropriateness": 0.0, "sequencing_fitness": 0.0}
    
    if not compound_rule:
        return adjustment
    
    contexts = compound_rule.get('high_appropriateness_contexts', [])
    mechanism = compound_rule.get('mechanism', '')
    
    # Recovery supplements (NAC, L-glutamine, Alpha-lipoic acid, Magnesium, CoQ10)
    post_treatment_contexts = ['post_platinum', 'post_chemotherapy', 'post_immunotherapy', 'gi_toxicity', 'neuropathy', 'cardiac_protection']
    is_recovery_compound = any(ctx in contexts for ctx in post_treatment_contexts)
    
    # Immune/DNA repair supplements (Vitamin D, Folate, Omega-3)
    always_appropriate_mechanisms = ['dna_repair_support', 'anti_inflammatory', 'immune_support', 'dna_synthesis_support']
    is_always_appropriate = mechanism in always_appropriate_mechanisms
    
    if treatment_line in ["L2", "L3"]:
        if is_recovery_compound:
            # Big boost for recovery supplements after prior treatment
            adjustment["line_appropriateness"] = 0.15
            adjustment["sequencing_fitness"] = 0.10
        elif is_always_appropriate:
            # Small boost for general supplements in later lines (patient more depleted)
            adjustment["line_appropriateness"] = 0.05
            adjustment["sequencing_fitness"] = 0.05
    elif treatment_line == "L1":
        if is_recovery_compound:
            # Lower appropriateness - no prior therapy to recover from
            adjustment["line_appropriateness"] = -0.15
            adjustment["sequencing_fitness"] = -0.05
        else:
            # Baseline supplements fine for L1
            adjustment["line_appropriateness"] = 0.0
            adjustment["sequencing_fitness"] = 0.0
    
    return adjustment

def compute_food_treatment_line_features(
    compound: str,
    disease_context: Dict[str, Any],
    treatment_history: Optional[Dict[str, Any]]
) -> Dict[str, float]:
    """
    Compute SAE features for dietary supplements.
    
    Returns:
        {
            "line_appropriateness": 0.9,
            "cross_resistance": 0.0,
            "sequencing_fitness": 0.85
        }
    """
    
    # Normalize treatment line format if provided
    if treatment_history and 'current_line' in treatment_history:
        treatment_history['current_line'] = normalize_treatment_line(treatment_history['current_line'])
    
    # Load rules
    rules_data = load_supplement_rules()
    supplement_rules = rules_data.get("supplement_rules", {})
    default_supplement = rules_data.get("default_supplement", {
        "line_appropriateness": 0.6,
        "cross_resistance": 0.0,
        "sequencing_fitness": 0.6
    })
    
    # Find matching rule (check compound name and common aliases)
    compound_rule = None
    compound_lower = compound.lower()
    
    for rule_name, rule_data in supplement_rules.items():
        if compound_lower in rule_name.lower() or rule_name.lower() in compound_lower:
            compound_rule = rule_data
            break
    
    # If no match, try to match by mechanism keywords
    if not compound_rule:
        # Try to infer from compound name
        if "vitamin d" in compound_lower or "d3" in compound_lower:
            # Look for DNA repair related rules
            for rule_name, rule_data in supplement_rules.items():
                if rule_data.get("mechanism") == "dna_repair_support":
                    compound_rule = rule_data
                    break
        elif "nac" in compound_lower or "n-acetylcysteine" in compound_lower:
            for rule_name, rule_data in supplement_rules.items():
                if rule_data.get("mechanism") == "oxidative_stress_recovery":
                    compound_rule = rule_data
                    break
    
    # Use compound rule or default
    if compound_rule:
        # Check for line-specific scores first (Phase 4 enhancement)
        line_specific = compound_rule.get("line_specific_scores", {})
        current_line = treatment_history.get('current_line', 'L1') if treatment_history else 'L1'
        
        if current_line in line_specific:
            # Use line-specific scores if available
            default_scores = line_specific[current_line]
            # Ensure all required fields are present
            default_scores = {
                "line_appropriateness": default_scores.get("line_appropriateness", 0.6),
                "cross_resistance": default_scores.get("cross_resistance", 0.0),
                "sequencing_fitness": default_scores.get("sequencing_fitness", 0.6)
            }
        else:
            # Fall back to default_scores
            default_scores = compound_rule.get("default_scores", default_supplement)
    else:
        # Default supplement IS the default_scores object
        default_scores = default_supplement if isinstance(default_supplement, dict) else {
            "line_appropriateness": 0.6,
            "cross_resistance": 0.0,
            "sequencing_fitness": 0.6
        }
    
    # Start with default scores
    scores = {
        "line_appropriateness": default_scores.get("line_appropriateness", 0.6),
        "cross_resistance": default_scores.get("cross_resistance", 0.0),
        "sequencing_fitness": default_scores.get("sequencing_fitness", 0.6)
    }
    
    # Check if we used line_specific_scores (Phase 4 enhancement)
    # If so, skip the adjustment function to avoid double-adjustment
    used_line_specific = False
    if compound_rule:
        line_specific = compound_rule.get("line_specific_scores", {})
        current_line = treatment_history.get('current_line', 'L1') if treatment_history else 'L1'
        if current_line in line_specific:
            used_line_specific = True
    
    # Apply treatment line-specific adjustments ONLY if we didn't use line_specific_scores
    if not used_line_specific:
        current_line = treatment_history.get('current_line', 'L1') if treatment_history else 'L1'
        line_adjustments = get_line_specific_adjustment(compound_rule, current_line)
        
        scores['line_appropriateness'] = max(0.1, min(1.0, 
            scores['line_appropriateness'] + line_adjustments['line_appropriateness']))
        scores['sequencing_fitness'] = max(0.1, min(1.0, 
            scores['sequencing_fitness'] + line_adjustments['sequencing_fitness']))
    
    # Apply biomarker gates (boost if context matches)
    if compound_rule:
        biomarkers = disease_context.get('biomarkers', {})
        biomarker_gates = compound_rule.get('biomarker_gates', {})
        
        for key, expected_value in biomarker_gates.items():
            if biomarkers.get(key) == expected_value:
                # Boost line appropriateness if biomarker matches
                scores['line_appropriateness'] = min(scores['line_appropriateness'] + 0.1, 1.0)
        
        # Also check pathways for context
        pathways_disrupted = disease_context.get('pathways_disrupted', [])
        high_appropriateness_contexts = compound_rule.get('high_appropriateness_contexts', [])
        
        # Check for pathway matches
        if 'dna_repair' in high_appropriateness_contexts or 'dna_repair_deficient' in high_appropriateness_contexts:
            if any('dna repair' in p.lower() for p in pathways_disrupted):
                scores['line_appropriateness'] = min(scores['line_appropriateness'] + 0.1, 1.0)
        
        if 'chronic_inflammation' in high_appropriateness_contexts:
            if any('inflammation' in p.lower() for p in pathways_disrupted):
                scores['line_appropriateness'] = min(scores['line_appropriateness'] + 0.1, 1.0)
    
    # Apply treatment history gates
    if treatment_history:
        prior_therapies = treatment_history.get('prior_therapies', [])
        
        if compound_rule:
            contexts = compound_rule.get('high_appropriateness_contexts', [])
            
            # Check if any prior therapy matches high-appropriateness context
            if 'post_platinum' in contexts and any('platin' in t.lower() for t in prior_therapies):
                scores['line_appropriateness'] = min(scores['line_appropriateness'] + 0.1, 1.0)
            
            if 'post_chemotherapy' in contexts and len(prior_therapies) > 0:
                scores['line_appropriateness'] = min(scores['line_appropriateness'] + 0.05, 1.0)
        
        # General rule: supplements generally safe to sequence
        scores['sequencing_fitness'] = min(scores.get('sequencing_fitness', 0.6) + 0.1, 1.0)
    
    return scores

