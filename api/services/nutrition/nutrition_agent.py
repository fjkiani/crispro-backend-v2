"""
Nutrition Agent - Toxicity-Aware Nutrition Planning

Generates personalized nutrition plans based on:
1. Drug toxicity pathways (MOAT integration)
2. Germline variants
3. Treatment context
4. LLM-enhanced rationales (Phase 3)

This implements Module 06 from MOAT orchestration and integrates
Phase 3 LLM enhancement capabilities.
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
import asyncio

from ..toxicity_pathway_mappings import (
    compute_pathway_overlap,
    get_mitigating_foods,
    get_drug_moa,
    DRUG_TO_MOA
)
from ..llm_toxicity_service import generate_toxicity_rationale


@dataclass
class Supplement:
    """Supplement recommendation."""
    name: str
    dosage: str
    timing: str  # "post_infusion", "daily", "with_food"
    mechanism: str
    evidence_level: str
    pathway: str = ""
    llm_rationale: Optional[str] = None
    patient_summary: Optional[str] = None
    llm_enhanced: bool = False


@dataclass
class FoodRecommendation:
    """Food recommendation."""
    food: str
    reason: str
    frequency: str
    category: str  # "prioritize", "include", "limit"


@dataclass
class DrugInteraction:
    """Drug-food interaction."""
    drug: str
    food: str
    interaction_type: str  # "avoid", "caution", "timing"
    mechanism: str
    severity: str


@dataclass
class NutritionPlan:
    """Complete nutrition plan."""
    patient_id: str
    treatment: str
    supplements: List[Supplement]
    foods_to_prioritize: List[FoodRecommendation]
    foods_to_avoid: List[FoodRecommendation]
    drug_food_interactions: List[DrugInteraction]
    timing_rules: Dict[str, str]
    provenance: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'patient_id': self.patient_id,
            'treatment': self.treatment,
            'supplements': [
                {
                    'name': s.name,
                    'dosage': s.dosage,
                    'timing': s.timing,
                    'mechanism': s.mechanism,
                    'evidence_level': s.evidence_level,
                    'pathway': s.pathway,
                    'llm_rationale': s.llm_rationale,
                    'patient_summary': s.patient_summary,
                    'llm_enhanced': s.llm_enhanced
                }
                for s in self.supplements
            ],
            'foods_to_prioritize': [
                {
                    'food': f.food,
                    'reason': f.reason,
                    'frequency': f.frequency,
                    'category': f.category
                }
                for f in self.foods_to_prioritize
            ],
            'foods_to_avoid': [
                {
                    'food': f.food,
                    'reason': f.reason,
                    'frequency': f.frequency,
                    'category': f.category
                }
                for f in self.foods_to_avoid
            ],
            'drug_food_interactions': [
                {
                    'drug': d.drug,
                    'food': d.food,
                    'interaction_type': d.interaction_type,
                    'mechanism': d.mechanism,
                    'severity': d.severity
                }
                for d in self.drug_food_interactions
            ],
            'timing_rules': self.timing_rules,
            'provenance': self.provenance
        }


class NutritionAgent:
    """Generate toxicity-aware nutrition plans."""
    
    def __init__(self, enable_llm: bool = True):
        """
        Initialize nutrition agent.
        
        Args:
            enable_llm: Whether to enable LLM enhancement (Phase 3)
        """
        self.enable_llm = enable_llm
    
    async def generate_nutrition_plan(
        self,
        patient_id: str,
        mutations: List[Dict[str, Any]],
        germline_genes: List[str],
        current_drugs: List[str],
        disease: Optional[str] = None,
        treatment_line: Optional[str] = None
    ) -> NutritionPlan:
        """
        Generate nutrition plan based on patient context.
        
        Args:
            patient_id: Patient identifier
            mutations: List of mutation dicts with 'gene' field
            germline_genes: List of genes with germline variants
            current_drugs: List of current drug names
            disease: Cancer type (e.g., "ovarian_cancer")
            treatment_line: Treatment line (e.g., "first-line")
        
        Returns:
            NutritionPlan with recommendations
        """
        # Extract primary treatment drug
        primary_drug = current_drugs[0] if current_drugs else None
        if not primary_drug:
            # Return empty plan if no drugs
            return NutritionPlan(
                patient_id=patient_id,
                treatment="unknown",
                supplements=[],
                foods_to_prioritize=[],
                foods_to_avoid=[],
                drug_food_interactions=[],
                timing_rules={},
                provenance={'method': 'no_drugs'}
            )
        
        # Get drug MoA
        drug_moa = get_drug_moa(primary_drug)
        
        # Compute toxicity pathway overlap (germline-aware)
        pathway_overlap = compute_pathway_overlap(germline_genes, drug_moa) if germline_genes else {}
        
        # For drugs with inherent toxicity (e.g., anthracyclines), add baseline pathway risk
        # even without germline variants
        if not pathway_overlap and drug_moa != "unknown":
            from ..toxicity_pathway_mappings import get_moa_toxicity_weights
            moa_weights = get_moa_toxicity_weights(drug_moa)
            # Use baseline weights (scaled down) for inherent drug toxicity
            pathway_overlap = {k: v * 0.5 for k, v in moa_weights.items() if v > 0.5}
        
        # Get mitigating foods (THE MOAT)
        mitigating_foods = get_mitigating_foods(pathway_overlap) if pathway_overlap else []
        
        # Convert to Supplement objects with optional LLM enhancement
        supplements = []
        for food in mitigating_foods:
            supplement = Supplement(
                name=food['compound'],
                dosage=food.get('dose', ''),
                timing=food.get('timing', 'daily'),
                mechanism=food.get('mechanism', ''),
                evidence_level=food.get('evidence_tier', 'MODERATE'),
                pathway=food.get('pathway', '')
            )
            
            # LLM Enhancement (Phase 3) - optional
            if self.enable_llm:
                try:
                    llm_result = await generate_toxicity_rationale(
                        compound=food['compound'],
                        drug_name=primary_drug,
                        drug_moa=drug_moa,
                        toxicity_pathway=food.get('pathway', ''),
                        germline_genes=germline_genes,
                        cancer_type=disease or "cancer",
                        treatment_phase=treatment_line or "active treatment",
                        base_mechanism=food.get('mechanism', ''),
                        timing=food.get('timing', ''),
                        dose=food.get('dose', '')
                    )
                    supplement.llm_rationale = llm_result.get('rationale')
                    supplement.patient_summary = llm_result.get('patient_summary')
                    supplement.llm_enhanced = llm_result.get('llm_enhanced', False)
                except Exception as e:
                    # Graceful fallback - continue without LLM
                    supplement.llm_enhanced = False
            
            supplements.append(supplement)
        
        # Generate food recommendations (prioritize foods that support pathways)
        foods_to_prioritize = self._get_priority_foods(pathway_overlap, disease)
        
        # Generate foods to avoid (drug interactions)
        foods_to_avoid = self._get_avoid_foods(primary_drug, drug_moa)
        
        # Check drug-food interactions
        drug_food_interactions = self._check_interactions(current_drugs)
        
        # Generate timing rules
        timing_rules = self._get_timing_rules(primary_drug, drug_moa, supplements)
        
        return NutritionPlan(
            patient_id=patient_id,
            treatment=primary_drug,
            supplements=supplements,
            foods_to_prioritize=foods_to_prioritize,
            foods_to_avoid=foods_to_avoid,
            drug_food_interactions=drug_food_interactions,
            timing_rules=timing_rules,
            provenance={
                'method': 'toxicity_aware_moat',
                'drug_moa': drug_moa,
                'pathway_overlap': pathway_overlap,
                'germline_genes_analyzed': len(germline_genes),
                'llm_enhanced': self.enable_llm
            }
        )
    
    def _get_priority_foods(
        self,
        pathway_overlap: Dict[str, float],
        disease: Optional[str]
    ) -> List[FoodRecommendation]:
        """Get foods to prioritize based on pathway overlap."""
        recommendations = []
        
        # DNA repair pathway foods
        if pathway_overlap.get('dna_repair', 0) > 0.3:
            recommendations.append(FoodRecommendation(
                food='Cruciferous vegetables (broccoli, kale)',
                reason='Sulforaphane supports DNA repair pathways',
                frequency='Daily',
                category='prioritize'
            ))
            recommendations.append(FoodRecommendation(
                food='Berries (blueberries, strawberries)',
                reason='Antioxidants support DNA repair',
                frequency='Daily',
                category='include'
            ))
        
        # Inflammation pathway foods
        if pathway_overlap.get('inflammation', 0) > 0.3:
            recommendations.append(FoodRecommendation(
                food='Fatty fish (salmon, mackerel)',
                reason='Omega-3 reduces inflammation',
                frequency='2-3x per week',
                category='prioritize'
            ))
            recommendations.append(FoodRecommendation(
                food='Turmeric',
                reason='Curcumin is anti-inflammatory',
                frequency='Daily',
                category='include'
            ))
        
        # Cardiometabolic pathway foods
        if pathway_overlap.get('cardiometabolic', 0) > 0.3:
            recommendations.append(FoodRecommendation(
                food='Nuts and seeds',
                reason='Support cardiovascular health',
                frequency='Daily',
                category='include'
            ))
        
        return recommendations
    
    def _get_avoid_foods(self, drug: str, drug_moa: str) -> List[FoodRecommendation]:
        """Get foods to avoid based on drug interactions."""
        avoid_list = []
        
        # CYP3A4 interactions
        if drug_moa in ['PARP_inhibitor', 'checkpoint_inhibitor']:
            avoid_list.append(FoodRecommendation(
                food='Grapefruit',
                reason='CYP3A4 inhibition - affects drug metabolism',
                frequency='Avoid',
                category='limit'
            ))
            avoid_list.append(FoodRecommendation(
                food='St. John\'s Wort',
                reason='CYP3A4 inducer - reduces drug efficacy',
                frequency='Avoid',
                category='limit'
            ))
        
        # High antioxidants during platinum therapy (may protect tumor)
        if drug_moa == 'platinum_agent':
            avoid_list.append(FoodRecommendation(
                food='High-dose antioxidants during infusion',
                reason='May reduce platinum efficacy',
                frequency='Avoid during infusion',
                category='limit'
            ))
        
        return avoid_list
    
    def _check_interactions(self, drugs: List[str]) -> List[DrugInteraction]:
        """Check for drug-food interactions."""
        interactions = []
        
        for drug in drugs:
            drug_moa = get_drug_moa(drug)
            
            # CYP3A4 interactions
            if drug_moa in ['PARP_inhibitor', 'checkpoint_inhibitor']:
                interactions.append(DrugInteraction(
                    drug=drug,
                    food='Grapefruit',
                    interaction_type='avoid',
                    mechanism='CYP3A4 inhibition',
                    severity='moderate'
                ))
            
            # 5-FU and DPYD variants (if detected, would be in germline_genes)
            if '5-FU' in drug or 'fluorouracil' in drug.lower():
                interactions.append(DrugInteraction(
                    drug=drug,
                    food='DPYD variant carriers - avoid 5-FU',
                    interaction_type='caution',
                    mechanism='DPYD deficiency increases toxicity',
                    severity='high'
                ))
        
        return interactions
    
    def _get_timing_rules(
        self,
        drug: str,
        drug_moa: str,
        supplements: List[Supplement]
    ) -> Dict[str, str]:
        """Generate timing rules for supplements."""
        rules = {}
        
        # General rules
        rules['general'] = 'Take supplements with food unless otherwise specified'
        
        # Drug-specific rules
        if drug_moa == 'platinum_agent':
            rules['during_infusion'] = 'Avoid high-dose antioxidants during infusion'
            rules['post_infusion'] = 'NAC and other antioxidants recommended post-infusion'
        
        if drug_moa == 'anthracycline':
            rules['cardioprotection'] = 'CoQ10 should be taken continuously during anthracycline therapy'
        
        # Supplement-specific timing
        for supp in supplements:
            if 'post-chemo' in supp.timing.lower() or 'post-infusion' in supp.timing.lower():
                rules[supp.name.lower()] = f'{supp.name}: Take after chemotherapy, not during infusion'
            elif 'continuous' in supp.timing.lower():
                rules[supp.name.lower()] = f'{supp.name}: Take daily throughout treatment'
        
        return rules


# Singleton instance
_nutrition_agent_instance: Optional[NutritionAgent] = None


def get_nutrition_agent(enable_llm: bool = True) -> NutritionAgent:
    """Get singleton nutrition agent instance."""
    global _nutrition_agent_instance
    if _nutrition_agent_instance is None:
        _nutrition_agent_instance = NutritionAgent(enable_llm=enable_llm)
    return _nutrition_agent_instance

