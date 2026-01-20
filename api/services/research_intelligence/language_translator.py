"""
Patient Language Translator

Translates technical terms to patient-friendly language.
Supports persona-specific translation (patient, doctor, r&d).
"""

from typing import Dict, Optional


class PatientLanguageTranslator:
    """Translates technical terms to patient-friendly language."""
    
    TRANSLATIONS = {
        # Mechanisms
        "NF-kB inhibition": "Reduces inflammation",
        "DDR pathway": "DNA repair system",
        "Apoptosis": "Programmed cell death (cancer cell elimination)",
        "Autophagy": "Cellular cleanup process",
        "Angiogenesis inhibition": "Blocks blood vessel formation to tumors",
        "Cell cycle arrest": "Stops cancer cell division",
        "DNA damage response": "DNA repair system",
        
        # Pathways
        "PI3K pathway": "Cell growth and survival pathway",
        "MAPK pathway": "Cell signaling pathway",
        "VEGF pathway": "Blood vessel formation pathway",
        "HER2 pathway": "Cell growth receptor pathway",
        "mTOR pathway": "Cell growth and metabolism pathway",
        "Wnt pathway": "Cell development pathway",
        
        # Terms
        "Mechanism of action": "How it works",
        "Evidence tier": "How strong is the evidence",
        "Biomarker": "Biological indicator",
        "Toxicity": "Side effects",
        "Efficacy": "How well it works",
        "Pharmacogenomics": "How your genes affect drug response",
        "Cross-resistance": "Resistance to multiple treatments",
        "Treatment line": "Stage of treatment",
        "Prognosis": "Expected outcome",
        "Metastasis": "Cancer spread",
        
        # Evidence Tiers
        "Supported": "Strong evidence - multiple studies support this",
        "Consider": "Moderate evidence - some studies support this",
        "Insufficient": "Limited evidence - more research needed",
        
        # Safety Terms
        "Low risk": "Low risk of side effects",
        "Moderate risk": "Moderate risk of side effects",
        "High risk": "High risk of side effects",
        "Toxicity mitigation": "Ways to reduce side effects"
    }
    
    def translate_mechanism(self, mechanism: str) -> str:
        """Translate mechanism to patient-friendly language."""
        # Direct translation
        if mechanism in self.TRANSLATIONS:
            return self.TRANSLATIONS[mechanism]
        
        # Pattern-based translation
        mechanism_lower = mechanism.lower()
        if "inhibition" in mechanism_lower:
            base = mechanism.replace("inhibition", "").strip()
            return f"Blocks {base}"
        if "pathway" in mechanism_lower:
            base = mechanism.replace("pathway", "process").strip()
            return f"Affects {base}"
        if "activation" in mechanism_lower:
            base = mechanism.replace("activation", "").strip()
            return f"Activates {base}"
        if "suppression" in mechanism_lower:
            base = mechanism.replace("suppression", "").strip()
            return f"Suppresses {base}"
        
        # Fallback: return as-is with explanation
        return f"{mechanism} (biological process)"
    
    def translate_pathway(self, pathway: str) -> str:
        """Translate pathway to patient-friendly language."""
        if pathway in self.TRANSLATIONS:
            return self.TRANSLATIONS[pathway]
        return pathway
    
    def translate_evidence_tier(self, tier: str) -> str:
        """Translate evidence tier to patient-friendly language."""
        return self.TRANSLATIONS.get(tier, tier)
    
    def translate_for_persona(self, text: str, persona: str) -> str:
        """Translate text based on persona."""
        if persona == "patient":
            # Apply all translations
            translated = text
            for technical, friendly in self.TRANSLATIONS.items():
                if technical in translated:
                    translated = translated.replace(technical, friendly)
            return translated
        # doctor and r&d keep technical terms
        return text
    
    def translate_dict(self, data: Dict[str, Any], persona: str) -> Dict[str, Any]:
        """Translate dictionary values based on persona."""
        if persona != "patient":
            return data
        
        translated = {}
        for key, value in data.items():
            if isinstance(value, str):
                translated[key] = self.translate_for_persona(value, persona)
            elif isinstance(value, list):
                translated[key] = [
                    self.translate_for_persona(item, persona) if isinstance(item, str) else item
                    for item in value
                ]
            elif isinstance(value, dict):
                translated[key] = self.translate_dict(value, persona)
            else:
                translated[key] = value
        
        return translated

