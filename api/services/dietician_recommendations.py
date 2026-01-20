"""
Dietician Recommendations Service

Provides comprehensive, actionable recommendations for food/supplement use:
- Dosage (with citations)
- Timing (best time of day, with/without food)
- Meal planning (foods to combine/avoid)
- Drug interactions (check against medication list)
- Lab monitoring (what to track)
- Safety alerts (contraindications)
"""

import json
import re
from typing import Dict, List, Optional, Any
from pathlib import Path

# Try to import LLM service
try:
    from api.services.llm_literature_service import get_llm_service
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False

class DieticianRecommendationsService:
    """Generate dietician-grade recommendations for food/supplement use."""
    
    def __init__(self):
        # Load drug interaction database (simple lookup for common interactions)
        self.drug_interactions = self._load_interaction_db()
        
        # Load safety database
        self.safety_db = self._load_safety_db()
    
    def _load_interaction_db(self) -> Dict[str, List[str]]:
        """Load drug-food interaction database."""
        interaction_file = Path(__file__).parent.parent.parent.parent.parent / ".cursor/ayesha/hypothesis_validator/data/drug_interactions.json"
        
        if interaction_file.exists():
            with open(interaction_file) as f:
                return json.load(f)
        else:
            # Default interactions (common ones)
            return {
                "warfarin": ["Vitamin K-rich foods", "Green tea", "Ginger", "Ginkgo"],
                "digoxin": ["Vitamin D (high doses)", "Hawthorn", "Licorice"],
                "aspirin": ["Ginger", "Turmeric", "Ginkgo", "Fish oil"],
                "chemotherapy": ["Grapefruit", "St. John's Wort", "Green tea (high doses)"],
                "blood_thinners": ["Ginger", "Turmeric", "Fish oil", "Garlic", "Ginkgo"]
            }
    
    def _load_safety_db(self) -> Dict[str, Dict[str, Any]]:
        """Load safety database (contraindications, precautions)."""
        safety_file = Path(__file__).parent.parent.parent.parent.parent / ".cursor/ayesha/hypothesis_validator/data/safety_database.json"
        
        if safety_file.exists():
            with open(safety_file) as f:
                return json.load(f)
        else:
            # Default safety info
            return {
                "Vitamin D": {
                    "max_dose": "10000 IU/day",
                    "contraindications": ["Hypercalcemia", "Kidney stones"],
                    "monitoring": ["Serum 25(OH)D", "Calcium levels"],
                    "timing": "With meals containing fat"
                },
                "NAC": {
                    "max_dose": "3000mg/day",
                    "contraindications": ["Asthma (high doses)"],
                    "monitoring": ["Liver function"],
                    "timing": "With food to reduce nausea"
                }
            }
    
    def extract_dosage_from_evidence(self, papers: List[Dict], compound: str) -> Dict[str, Any]:
        """
        Extract dosage information from paper abstracts using regex + optional LLM.
        
        Returns:
            {
                "recommended_dose": "2000-4000 IU daily",
                "dose_range": {"min": 2000, "max": 4000, "unit": "IU"},
                "frequency": "daily",
                "duration": "ongoing",
                "citations": ["PMID:12345678"],
                "target_level": "40-60 ng/mL (serum 25(OH)D)"
            }
        """
        import re
        
        dosage_info = {
            "recommended_dose": "",
            "dose_range": {},
            "frequency": "daily",
            "duration": "ongoing",
            "citations": [],
            "target_level": ""
        }
        
        # Try LLM extraction first (if available and papers exist)
        if LLM_AVAILABLE and len(papers) > 0:
            try:
                llm_service = get_llm_service()
                
                # Get LLM search result for this compound
                # Note: This is async, but we're in a sync method
                # For now, we'll use regex fallback, LLM can be added in async version
                pass  # LLM extraction would go here if async wrapper available
            except Exception as e:
                print(f"⚠️ LLM dosage extraction not available in sync context: {e}")
        
        # Fallback: Regex extraction from abstracts
        for paper in papers[:5]:
            abstract = paper.get("abstract", "")
            title = paper.get("title", "")
            text = (abstract + " " + title).lower()
            
            # Common dosage patterns with regex
            patterns = [
                # Range patterns: "2000-4000 IU", "100-200 mg"
                (r'(\d+[-–]\d+)\s*(mg|iu|g|mcg|mcg|μg)', self._parse_dose_range),
                # Single dose: "2000 IU", "100 mg"
                (r'(\d+(?:\.\d+)?)\s*(mg|iu|g|mcg|mcg|μg)\s*(?:daily|per day|/day)', self._parse_single_dose),
                # Decimal: "2.5 mg", "0.5 g"
                (r'(\d+\.\d+)\s*(mg|iu|g|mcg|μg)', self._parse_single_dose),
            ]
            
            for pattern, parser in patterns:
                matches = re.finditer(pattern, text, re.IGNORECASE)
                for match in matches:
                    dose_str = match.group(1)
                    unit = match.group(2).upper()
                    pmid = paper.get("pmid", "")
                    
                    # Parse the dose
                    parsed = parser(dose_str, unit)
                    if parsed:
                        dosage_info["recommended_dose"] = parsed.get("recommended_dose", "")
                        dosage_info["dose_range"] = parsed.get("dose_range", {})
                        dosage_info["frequency"] = parsed.get("frequency", "daily")
                        if pmid:
                            dosage_info["citations"].append(pmid)
                        
                        # Found a dose, return it
                        return dosage_info
        
        # No dose found, return empty structure
        return dosage_info
    
    def _parse_dose_range(self, dose_str: str, unit: str) -> Optional[Dict[str, Any]]:
        """Parse dose range like '2000-4000'."""
        try:
            if '-' in dose_str or '–' in dose_str:
                parts = re.split(r'[-–]', dose_str)
                if len(parts) == 2:
                    min_val = float(parts[0])
                    max_val = float(parts[1])
                    return {
                        "recommended_dose": f"{int(min_val)}-{int(max_val)} {unit}",
                        "dose_range": {"min": min_val, "max": max_val, "unit": unit},
                        "frequency": "daily"
                    }
        except:
            pass
        return None
    
    def _parse_single_dose(self, dose_str: str, unit: str) -> Optional[Dict[str, Any]]:
        """Parse single dose like '2000'."""
        try:
            val = float(dose_str)
            return {
                "recommended_dose": f"{int(val) if val.is_integer() else val} {unit}",
                "dose_range": {"min": val, "max": val, "unit": unit},
                "frequency": "daily"
            }
        except:
            pass
        return None
    
    def check_drug_interactions(
        self,
        compound: str,
        medications: List[str] = None
    ) -> Dict[str, Any]:
        """
        Check for drug-food interactions.
        
        Returns:
            {
                "interactions": [
                    {"drug": "warfarin", "compound": "Vitamin K", "severity": "moderate", "action": "Monitor INR"}
                ],
                "warnings": [...],
                "safe": True/False
            }
        """
        if not medications:
            return {
                "interactions": [],
                "warnings": [],
                "safe": True
            }
        
        interactions = []
        warnings = []
        
        compound_lower = compound.lower()
        
        for med in medications:
            med_lower = med.lower()
            
            # Check interaction database
            for drug, interacting_compounds in self.drug_interactions.items():
                if drug.lower() in med_lower:
                    for interacting in interacting_compounds:
                        if interacting.lower() in compound_lower:
                            interactions.append({
                                "drug": med,
                                "compound": compound,
                                "severity": "moderate",  # Would be from database
                                "action": f"Monitor for interactions with {med}",
                                "evidence": "Clinical database"
                            })
            
            # Specific known interactions
            if "warfarin" in med_lower and any(x in compound_lower for x in ["vitamin k", "green tea", "ginger"]):
                interactions.append({
                    "drug": med,
                    "compound": compound,
                    "severity": "high",
                    "action": "Avoid or monitor INR closely",
                    "evidence": "Known interaction"
                })
            
            if "chemotherapy" in med_lower and "grapefruit" in compound_lower:
                warnings.append("Grapefruit may interfere with chemotherapy metabolism")
        
        return {
            "interactions": interactions,
            "warnings": warnings,
            "safe": len(interactions) == 0 and len(warnings) == 0
        }
    
    def generate_timing_recommendations(self, compound: str, evidence: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate timing recommendations.
        
        Returns:
            {
                "best_time": "morning with breakfast",
                "with_food": True/False,
                "timing_rationale": "...",
                "meal_suggestions": [...]
            }
        """
        timing = {
            "best_time": "As directed",
            "with_food": True,
            "timing_rationale": "",
            "meal_suggestions": []
        }
        
        compound_lower = compound.lower()
        
        # Fat-soluble vitamins
        if any(x in compound_lower for x in ["vitamin d", "vitamin a", "vitamin e", "vitamin k"]):
            timing.update({
                "best_time": "Morning with breakfast",
                "with_food": True,
                "timing_rationale": "Fat-soluble vitamins require dietary fat for optimal absorption",
                "meal_suggestions": ["Eggs", "Avocado", "Nuts", "Oily fish"]
            })
        
        # Water-soluble vitamins
        elif any(x in compound_lower for x in ["vitamin c", "b vitamin", "folate", "b12"]):
            timing.update({
                "best_time": "Morning with food",
                "with_food": True,
                "timing_rationale": "Take with food to reduce stomach upset",
                "meal_suggestions": ["Breakfast", "Any meal"]
            })
        
        # Minerals
        elif any(x in compound_lower for x in ["calcium", "magnesium", "iron", "zinc"]):
            timing.update({
                "best_time": "Evening (for sleep) or with meals)",
                "with_food": True,
                "timing_rationale": "Some minerals (magnesium) may promote sleep",
                "meal_suggestions": ["Dinner", "Bedtime snack"]
            })
        
        # Herbal supplements
        elif any(x in compound_lower for x in ["curcumin", "turmeric", "green tea", "ginger"]):
            timing.update({
                "best_time": "With meals",
                "with_food": True,
                "timing_rationale": "Reduce gastrointestinal side effects",
                "meal_suggestions": ["Any meal", "Add to food/drinks"]
            })
        
        # LLM FALLBACK for unknown compounds
        if timing["best_time"] == "As directed" and LLM_AVAILABLE:
            try:
                # Try to extract from evidence if available
                evidence_text = ""
                if evidence and evidence.get("papers"):
                    # Use paper abstracts for context
                    papers = evidence.get("papers", [])[:3]
                    abstracts = " ".join([p.get("abstract", "")[:200] for p in papers])
                    evidence_text = abstracts
                
                # For sync context, use simple pattern matching from evidence
                # Full LLM would require async wrapper
                if evidence_text:
                    text_lower = evidence_text.lower()
                    # Check for timing mentions in papers
                    if any(x in text_lower for x in ["morning", "breakfast", "empty stomach"]):
                        timing.update({
                            "best_time": "Morning",
                            "with_food": "empty stomach" not in text_lower,
                            "timing_rationale": "Based on literature review",
                            "meal_suggestions": []
                        })
                    elif any(x in text_lower for x in ["evening", "bedtime", "night"]):
                        timing.update({
                            "best_time": "Evening",
                            "with_food": True,
                            "timing_rationale": "Based on literature review",
                            "meal_suggestions": []
                        })
                    elif "with food" in text_lower or "with meals" in text_lower:
                        timing.update({
                            "best_time": "With meals",
                            "with_food": True,
                            "timing_rationale": "Based on literature review",
                            "meal_suggestions": []
                        })
                
                # If still no match, keep generic "As directed"
            except Exception as e:
                print(f"⚠️ LLM timing generation failed: {e}")
        
        return timing
    
    def generate_lab_monitoring(self, compound: str, safety_db: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Generate lab monitoring recommendations.
        
        Returns:
            {
                "labs_to_monitor": [
                    {"lab": "Serum 25(OH)D", "frequency": "q3-6 months", "target": "40-60 ng/mL"}
                ],
                "monitoring_rationale": "..."
            }
        """
        if safety_db is None:
            safety_db = self.safety_db
        
        compound_lower = compound.lower()
        labs = []
        
        # Check safety database
        for compound_name, safety_info in safety_db.items():
            if compound_name.lower() in compound_lower:
                monitoring = safety_info.get("monitoring", [])
                for lab in monitoring:
                    labs.append({
                        "lab": lab,
                        "frequency": "q3-6 months",  # Would be from database
                        "target": safety_info.get("target_range", "")
                    })
        
        # Default recommendations based on compound type
        if not labs:
            if "vitamin d" in compound_lower:
                labs.append({
                    "lab": "Serum 25(OH)D",
                    "frequency": "q3-6 months",
                    "target": "40-60 ng/mL"
                })
            elif "folate" in compound_lower:
                labs.append({
                    "lab": "Serum folate",
                    "frequency": "q6 months",
                    "target": "Normal range"
                })
        
        return {
            "labs_to_monitor": labs,
            "monitoring_rationale": f"Monitor {compound} levels and safety parameters"
        }
    
    def generate_complete_recommendations(
        self,
        compound: str,
        evidence: Dict[str, Any],
        patient_medications: List[str] = None,
        disease_context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Generate complete dietician recommendations.
        
        Returns comprehensive recommendation package.
        """
        # Extract dosage
        dosage = self.extract_dosage_from_evidence(evidence.get("papers", []), compound)
        
        # Check interactions
        interactions = self.check_drug_interactions(compound, patient_medications)
        
        # Timing recommendations
        timing = self.generate_timing_recommendations(compound, evidence)
        
        # Lab monitoring
        monitoring = self.generate_lab_monitoring(compound)
        
        # Safety info
        safety_info = self.safety_db.get(compound, {})
        
        # Meal planning suggestions
        meal_planning = self._generate_meal_planning(compound, evidence)
        
        return {
            "compound": compound,
            "dosage": dosage,
            "timing": timing,
            "interactions": interactions,
            "monitoring": monitoring,
            "safety": {
                "max_dose": safety_info.get("max_dose", ""),
                "contraindications": safety_info.get("contraindications", []),
                "precautions": safety_info.get("precautions", []),
                "pregnancy": safety_info.get("pregnancy_safety", "Unknown")
            },
            "meal_planning": meal_planning,
            "patient_instructions": self._generate_patient_instructions(compound, dosage, timing, interactions)
        }
    
    def _generate_meal_planning(self, compound: str, evidence: Dict[str, Any]) -> Dict[str, Any]:
        """Generate meal planning suggestions."""
        compound_lower = compound.lower()
        
        suggestions = {
            "combine_with": [],
            "avoid_with": [],
            "food_sources": [],
            "supplement_form": "recommended"
        }
        
        # Food sources
        if "vitamin d" in compound_lower:
            suggestions["food_sources"] = ["Fatty fish", "Egg yolks", "Fortified dairy"]
        elif "omega-3" in compound_lower:
            suggestions["food_sources"] = ["Salmon", "Mackerel", "Walnuts", "Flaxseed"]
        elif "curcumin" in compound_lower:
            suggestions["food_sources"] = ["Turmeric spice", "Curry dishes"]
        
        # Combine suggestions
        if any(x in compound_lower for x in ["vitamin d", "fat"]):
            suggestions["combine_with"] = ["Healthy fats (avocado, nuts)"]
        
        # Avoid suggestions
        if "iron" in compound_lower:
            suggestions["avoid_with"] = ["Calcium supplements", "Tea/coffee (within 1 hour)"]
        
        return suggestions
    
    def _generate_patient_instructions(
        self,
        compound: str,
        dosage: Dict[str, Any],
        timing: Dict[str, Any],
        interactions: Dict[str, Any]
    ) -> str:
        """Generate plain-language patient instructions."""
        instructions = f"Take {dosage.get('recommended_dose', 'as directed')} of {compound}"
        
        if timing.get("with_food"):
            instructions += f" {timing.get('best_time', 'with meals')}"
        
        if interactions.get("warnings"):
            instructions += f"\n\n⚠️ Warnings: {'; '.join(interactions['warnings'])}"
        
        if interactions.get("interactions"):
            instructions += f"\n\n⚠️ Drug interactions detected - consult your doctor"
        
        return instructions


# Singleton
_dietician_service_instance = None

def get_dietician_service() -> DieticianRecommendationsService:
    """Get singleton instance."""
    global _dietician_service_instance
    if _dietician_service_instance is None:
        _dietician_service_instance = DieticianRecommendationsService()
    return _dietician_service_instance

