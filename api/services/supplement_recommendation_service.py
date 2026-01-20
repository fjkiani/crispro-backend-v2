"""
Supplement Recommendation Service

Generates supplement recommendations based on:
- Drug classes and mechanisms
- Treatment line (first-line, maintenance, etc.)
- Drug-supplement interactions
- Disease-specific needs

Research Use Only - Not for Clinical Decision Making
"""

import logging
import uuid
from typing import Dict, Any, List, Optional, Set
from datetime import datetime

from api.schemas.supplements import (
    SupplementRecommendationRequest,
    SupplementRecommendationResponse,
    SupplementRecommendation,
    SupplementToAvoid,
    SupplementPriority,
    SupplementCategory
)

logger = logging.getLogger(__name__)

# Singleton instance
_supplement_service_instance = None


# Drug class → Supplement mapping
DRUG_SUPPLEMENT_MAP: Dict[str, Dict[str, Any]] = {
    "platinum": {
        "recommend": [
            {
                "supplement": "Calcium + Vitamin D",
                "category": "bone_health",
                "priority": "HIGH",
                "rationale": "Platinum agents (carboplatin, cisplatin) can cause bone loss. Calcium + D3 supplementation recommended during treatment.",
                "dosage": "Calcium 1200mg/day, Vitamin D3 2000 IU/day",
                "timing": "During treatment and for 6 months post-treatment",
                "evidence": "NCCN Survivorship Guidelines, ASCO Bone Health in Cancer",
                "confidence": 0.90
            },
            {
                "supplement": "Magnesium",
                "category": "general_health",
                "priority": "MEDIUM",
                "rationale": "Platinum-induced hypomagnesemia is common. Prophylactic magnesium supplementation may prevent severe depletion.",
                "dosage": "400mg/day",
                "timing": "During platinum-based treatment",
                "evidence": "ASCO guidelines, clinical practice",
                "confidence": 0.80
            }
        ],
        "avoid": []
    },
    "taxane": {
        "recommend": [
            {
                "supplement": "Omega-3 Fatty Acids",
                "category": "anti_inflammatory",
                "priority": "MEDIUM",
                "rationale": "Taxanes (paclitaxel, docetaxel) cause inflammation. Omega-3 may reduce treatment-related inflammation and neuropathy risk.",
                "dosage": "1000-2000mg EPA+DHA daily",
                "timing": "During treatment",
                "evidence": "Meta-analysis (n=1,200) - reduced inflammatory markers, preliminary neuropathy data",
                "confidence": 0.75
            },
            {
                "supplement": "Acetyl-L-Carnitine",
                "category": "neuroprotective",
                "priority": "LOW",
                "rationale": "May reduce taxane-induced peripheral neuropathy (preliminary evidence).",
                "dosage": "1000-2000mg/day",
                "timing": "During taxane treatment",
                "evidence": "Preliminary studies, limited evidence",
                "confidence": 0.60
            }
        ],
        "avoid": [
            {
                "supplement": "Grapefruit / Grapefruit Juice",
                "category": "drug_interaction",
                "rationale": "Inhibits CYP3A4 → increases plasma levels of taxanes (paclitaxel, docetaxel). Avoid during treatment.",
                "applicable_drugs": ["Paclitaxel", "Docetaxel"],
                "confidence": 0.95
            }
        ]
    },
    "parp_inhibitor": {
        "recommend": [
            {
                "supplement": "Calcium + Vitamin D",
                "category": "bone_health",
                "priority": "HIGH",
                "rationale": "Long-term PARP inhibitor use (maintenance) → increased bone health monitoring needed. Calcium + D3 for bone density preservation.",
                "dosage": "Calcium 1200mg/day, Vitamin D3 2000 IU/day",
                "timing": "During maintenance therapy",
                "evidence": "NCCN Survivorship Guidelines, long-term PARP use",
                "confidence": 0.85
            }
        ],
        "avoid": [
            {
                "supplement": "Grapefruit / Grapefruit Juice",
                "category": "drug_interaction",
                "rationale": "Inhibits CYP3A4 → increases plasma levels of PARP inhibitors (olaparib, niraparib, rucaparib). Avoid during treatment.",
                "applicable_drugs": ["Olaparib", "Niraparib", "Rucaparib"],
                "confidence": 0.95
            },
            {
                "supplement": "St. John's Wort",
                "category": "drug_interaction",
                "rationale": "Induces CYP3A4 → decreases PARP inhibitor levels. Avoid during treatment.",
                "applicable_drugs": ["All PARP inhibitors"],
                "confidence": 0.90
            }
        ]
    },
    "anti_vegf": {
        "recommend": [],
        "avoid": [
            {
                "supplement": "Omega-3 Fatty Acids (High Dose)",
                "category": "drug_interaction",
                "rationale": "May increase bleeding risk when combined with bevacizumab (anti-VEGF). Use with caution, monitor bleeding.",
                "applicable_drugs": ["Bevacizumab"],
                "confidence": 0.70
            }
        ]
    },
    "anthracycline": {
        "recommend": [
            {
                "supplement": "Coenzyme Q10",
                "category": "cardioprotective",
                "priority": "MEDIUM",
                "rationale": "May reduce anthracycline-induced cardiotoxicity (doxorubicin, epirubicin).",
                "dosage": "200-300mg/day",
                "timing": "During anthracycline treatment",
                "evidence": "Preliminary studies, mixed evidence",
                "confidence": 0.65
            }
        ],
        "avoid": []
    }
}

# Treatment line specific recommendations
TREATMENT_LINE_SUPPLEMENTS: Dict[str, List[Dict[str, Any]]] = {
    "first_line": [
        {
            "supplement": "Multivitamin (General)",
            "category": "general_health",
            "priority": "MEDIUM",
            "rationale": "First-line chemotherapy can deplete multiple vitamins/minerals. General multivitamin supports overall nutritional status.",
            "dosage": "Standard multivitamin daily",
            "timing": "During treatment",
            "evidence": "Clinical practice, general nutrition support",
            "confidence": 0.70
        }
    ],
    "maintenance": [
        {
            "supplement": "Calcium + Vitamin D",
            "category": "bone_health",
            "priority": "HIGH",
            "rationale": "Long-term maintenance therapy (PARP inhibitors, etc.) → increased bone health monitoring needed.",
            "dosage": "Calcium 1200mg/day, Vitamin D3 2000 IU/day",
            "timing": "During maintenance therapy",
            "evidence": "NCCN Survivorship Guidelines",
            "confidence": 0.85
        }
    ]
}


class SupplementRecommendationService:
    """Service for generating supplement recommendations"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    async def generate_recommendations(
        self,
        request: SupplementRecommendationRequest
    ) -> SupplementRecommendationResponse:
        """
        Generate supplement recommendations based on drugs + treatment line.
        
        Args:
            request: SupplementRecommendationRequest with drugs, treatment_line, disease
        
        Returns:
            SupplementRecommendationResponse with recommendations and avoid list
        """
        run_id = str(uuid.uuid4())
        recommendations: List[SupplementRecommendation] = []
        avoid_list: List[SupplementToAvoid] = []
        seen_supplements: Set[str] = set()
        
        # Normalize treatment line
        treatment_line = self._normalize_treatment_line(request.treatment_line)
        
        # 1. Extract drug classes from drugs
        drug_classes: Set[str] = set()
        drug_names: List[str] = []
        for drug in request.drugs:
            drug_name = drug.get("name", "").lower()
            drug_class = drug.get("class", "").lower()
            drug_names.append(drug.get("name", ""))
            
            # Map common drug names to classes
            if "platinum" in drug_class or "carboplatin" in drug_name or "cisplatin" in drug_name:
                drug_classes.add("platinum")
            if "taxane" in drug_class or "paclitaxel" in drug_name or "docetaxel" in drug_name:
                drug_classes.add("taxane")
            if "parp" in drug_class or any(p in drug_name for p in ["olaparib", "niraparib", "rucaparib"]):
                drug_classes.add("parp_inhibitor")
            if "vegf" in drug_class or "bevacizumab" in drug_name:
                drug_classes.add("anti_vegf")
            if "anthracycline" in drug_class or any(a in drug_name for a in ["doxorubicin", "epirubicin"]):
                drug_classes.add("anthracycline")
        
        # 2. Generate recommendations from drug classes
        for drug_class in drug_classes:
            if drug_class in DRUG_SUPPLEMENT_MAP:
                mapping = DRUG_SUPPLEMENT_MAP[drug_class]
                
                # Add recommendations
                for rec in mapping.get("recommend", []):
                    supplement_name = rec["supplement"]
                    if supplement_name not in seen_supplements:
                        seen_supplements.add(supplement_name)
                        recommendations.append(
                            SupplementRecommendation(
                                supplement=rec["supplement"],
                                category=SupplementCategory(rec["category"]),
                                priority=SupplementPriority(rec["priority"]),
                                rationale=rec["rationale"],
                                dosage=rec.get("dosage"),
                                timing=rec.get("timing"),
                                evidence=rec.get("evidence"),
                                drug_interactions=[],
                                confidence=rec.get("confidence", 0.75)
                            )
                        )
                
                # Add avoid list
                for avoid in mapping.get("avoid", []):
                    supplement_name = avoid["supplement"]
                    if supplement_name not in [a.supplement for a in avoid_list]:
                        # Check if applicable to current drugs
                        applicable_drugs = avoid.get("applicable_drugs", [])
                        if not applicable_drugs or any(ad.lower() in dn.lower() for ad in applicable_drugs for dn in drug_names):
                            avoid_list.append(
                                SupplementToAvoid(
                                    supplement=avoid["supplement"],
                                    category=SupplementCategory(avoid["category"]),
                                    rationale=avoid["rationale"],
                                    applicable_drugs=applicable_drugs,
                                    confidence=avoid.get("confidence", 0.75)
                                )
                            )
        
        # 3. Add treatment-line-specific recommendations
        treatment_line_specific: Dict[str, List[SupplementRecommendation]] = {}
        if treatment_line in TREATMENT_LINE_SUPPLEMENTS:
            line_recs = TREATMENT_LINE_SUPPLEMENTS[treatment_line]
            line_recommendations = []
            for rec in line_recs:
                supplement_name = rec["supplement"]
                if supplement_name not in seen_supplements:
                    seen_supplements.add(supplement_name)
                    line_recommendations.append(
                        SupplementRecommendation(
                            supplement=rec["supplement"],
                            category=SupplementCategory(rec["category"]),
                            priority=SupplementPriority(rec["priority"]),
                            rationale=rec["rationale"],
                            dosage=rec.get("dosage"),
                            timing=rec.get("timing"),
                            evidence=rec.get("evidence"),
                            drug_interactions=[],
                            confidence=rec.get("confidence", 0.75)
                        )
                    )
            if line_recommendations:
                treatment_line_specific[treatment_line] = line_recommendations
        
        # 4. Special handling for omega-3 + bevacizumab (bleeding risk)
        if "anti_vegf" in drug_classes:
            # Find omega-3 in recommendations and add warning
            for rec in recommendations:
                if "omega-3" in rec.supplement.lower() or "omega3" in rec.supplement.lower():
                    rec.drug_interactions.append(
                        "May increase bleeding risk with bevacizumab - monitor bleeding, use with caution"
                    )
                    rec.confidence = min(rec.confidence, 0.70)  # Lower confidence due to interaction
        
        # 5. Sort recommendations by priority
        priority_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
        recommendations.sort(key=lambda r: (priority_order.get(r.priority.value, 3), -r.confidence))
        
        # 6. Build provenance
        provenance = {
            "run_id": run_id,
            "generated_at": datetime.utcnow().isoformat(),
            "drug_classes_detected": list(drug_classes),
            "treatment_line": treatment_line,
            "sources": ["DrugBank", "NCCN Survivorship Guidelines", "ASCO Bone Health Guidelines", "Clinical Practice"],
            "note": "Recommendations based on drug classes and treatment line. Always consult oncologist before starting supplements."
        }
        
        self.logger.info(
            f"✅ Supplement recommendations: {len(recommendations)} recommended, {len(avoid_list)} to avoid, "
            f"drug_classes={drug_classes}, treatment_line={treatment_line}"
        )
        
        return SupplementRecommendationResponse(
            recommendations=recommendations,
            avoid=avoid_list,
            treatment_line_specific=treatment_line_specific if treatment_line_specific else None,
            provenance=provenance
        )
    
    def _normalize_treatment_line(self, treatment_line: Optional[str]) -> str:
        """Normalize treatment line to standard format"""
        if not treatment_line:
            return "first_line"
        
        # Handle edge cases like "No", "None", etc.
        line_lower = str(treatment_line).lower().strip()
        if line_lower in ["no", "none", "null", "n/a", "na", ""]:
            return "first_line"
        
        if any(x in line_lower for x in ["first", "1l", "1-l", "frontline", "primary", "either"]):
            return "first_line"
        elif any(x in line_lower for x in ["maintenance"]):
            return "maintenance"
        elif any(x in line_lower for x in ["second", "2l", "2-l", "recurrent"]):
            return "second_line"
        elif any(x in line_lower for x in ["third", "3l", "3-l"]):
            return "third_line"
        else:
            return "first_line"  # Default


def get_supplement_recommendation_service() -> SupplementRecommendationService:
    """Get singleton instance of supplement recommendation service"""
    global _supplement_service_instance
    if _supplement_service_instance is None:
        _supplement_service_instance = SupplementRecommendationService()
    return _supplement_service_instance
