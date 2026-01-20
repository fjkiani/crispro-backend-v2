"""
Unit tests for Nutrition Agent.

Tests the integration of MOAT features (toxicity mitigation) and
LLM enhancement (Phase 3) in the nutrition planning agent.
"""

import pytest
import asyncio
from typing import List, Dict

from .nutrition_agent import NutritionAgent, NutritionPlan


@pytest.mark.asyncio
async def test_nutrition_agent_no_drugs():
    """Test nutrition agent with no current drugs."""
    agent = NutritionAgent(enable_llm=False)
    
    plan = await agent.generate_nutrition_plan(
        patient_id="test_001",
        mutations=[],
        germline_genes=[],
        current_drugs=[],
        disease="ovarian_cancer"
    )
    
    assert plan.patient_id == "test_001"
    assert plan.treatment == "unknown"
    assert len(plan.supplements) == 0
    assert plan.provenance['method'] == 'no_drugs'


@pytest.mark.asyncio
async def test_nutrition_agent_carboplatin_brca1():
    """Test nutrition agent with carboplatin + BRCA1 variant."""
    agent = NutritionAgent(enable_llm=False)
    
    mutations = [{'gene': 'BRCA1', 'chrom': '17', 'pos': 41276045}]
    germline_genes = ['BRCA1']
    current_drugs = ['carboplatin']
    
    plan = await agent.generate_nutrition_plan(
        patient_id="test_002",
        mutations=mutations,
        germline_genes=germline_genes,
        current_drugs=current_drugs,
        disease="ovarian_cancer"
    )
    
    assert plan.treatment == "carboplatin"
    assert len(plan.supplements) > 0
    
    # Should have DNA repair supplements (NAC, Vitamin D, Folate)
    supplement_names = [s.name.lower() for s in plan.supplements]
    assert any('nac' in name or 'n-acetyl' in name for name in supplement_names)
    assert any('vitamin d' in name for name in supplement_names)
    
    # Check timing rules
    assert 'post_infusion' in plan.timing_rules.get('general', '').lower() or \
           'post-chemo' in str(plan.timing_rules.values()).lower()
    
    # Check provenance
    assert plan.provenance['drug_moa'] == 'platinum_agent'
    assert 'dna_repair' in plan.provenance.get('pathway_overlap', {})


@pytest.mark.asyncio
async def test_nutrition_agent_doxorubicin_cardio():
    """Test nutrition agent with doxorubicin (cardiotoxicity)."""
    agent = NutritionAgent(enable_llm=False)
    
    current_drugs = ['doxorubicin']
    
    plan = await agent.generate_nutrition_plan(
        patient_id="test_003",
        mutations=[],
        germline_genes=[],
        current_drugs=current_drugs,
        disease="breast_cancer"
    )
    
    assert plan.treatment == "doxorubicin"
    
    # Should have cardiometabolic supplements (CoQ10, Carnitine, Magnesium)
    supplement_names = [s.name.lower() for s in plan.supplements]
    assert any('coq10' in name or 'ubiquinol' in name for name in supplement_names)
    
    # Check timing rules for cardioprotection
    assert 'cardioprotection' in plan.timing_rules or \
           'coq10' in str(plan.timing_rules.values()).lower()


@pytest.mark.asyncio
async def test_nutrition_agent_drug_interactions():
    """Test drug-food interaction detection."""
    agent = NutritionAgent(enable_llm=False)
    
    current_drugs = ['olaparib']
    
    plan = await agent.generate_nutrition_plan(
        patient_id="test_004",
        mutations=[],
        germline_genes=[],
        current_drugs=current_drugs,
        disease="ovarian_cancer"
    )
    
    # Should detect CYP3A4 interactions
    interaction_foods = [i.food.lower() for i in plan.drug_food_interactions]
    assert any('grapefruit' in food for food in interaction_foods)
    
    # Should have foods to avoid
    avoid_foods = [f.food.lower() for f in plan.foods_to_avoid]
    assert any('grapefruit' in food for food in avoid_foods)


@pytest.mark.asyncio
async def test_nutrition_plan_to_dict():
    """Test NutritionPlan serialization to dict."""
    agent = NutritionAgent(enable_llm=False)
    
    plan = await agent.generate_nutrition_plan(
        patient_id="test_005",
        mutations=[{'gene': 'BRCA1'}],
        germline_genes=['BRCA1'],
        current_drugs=['carboplatin'],
        disease="ovarian_cancer"
    )
    
    plan_dict = plan.to_dict()
    
    assert plan_dict['patient_id'] == "test_005"
    assert plan_dict['treatment'] == "carboplatin"
    assert isinstance(plan_dict['supplements'], list)
    assert isinstance(plan_dict['foods_to_prioritize'], list)
    assert isinstance(plan_dict['drug_food_interactions'], list)
    assert isinstance(plan_dict['timing_rules'], dict)
    assert isinstance(plan_dict['provenance'], dict)
    
    # Check supplement structure
    if plan_dict['supplements']:
        supp = plan_dict['supplements'][0]
        assert 'name' in supp
        assert 'dosage' in supp
        assert 'timing' in supp
        assert 'mechanism' in supp


@pytest.mark.asyncio
async def test_nutrition_agent_llm_enhancement():
    """Test LLM enhancement (Phase 3) - graceful fallback if LLM unavailable."""
    agent = NutritionAgent(enable_llm=True)
    
    plan = await agent.generate_nutrition_plan(
        patient_id="test_006",
        mutations=[{'gene': 'BRCA1'}],
        germline_genes=['BRCA1'],
        current_drugs=['carboplatin'],
        disease="ovarian_cancer"
    )
    
    # Should still generate plan even if LLM fails
    assert plan.treatment == "carboplatin"
    assert len(plan.supplements) > 0
    
    # Check if LLM enhancement was attempted (may be False if LLM unavailable)
    for supp in plan.supplements:
        # LLM fields should exist (may be None if LLM failed)
        assert hasattr(supp, 'llm_rationale')
        assert hasattr(supp, 'patient_summary')
        assert hasattr(supp, 'llm_enhanced')


if __name__ == "__main__":
    # Run basic test
    async def run_test():
        agent = NutritionAgent(enable_llm=False)
        plan = await agent.generate_nutrition_plan(
            patient_id="test_manual",
            mutations=[{'gene': 'BRCA1'}],
            germline_genes=['BRCA1'],
            current_drugs=['carboplatin'],
            disease="ovarian_cancer"
        )
        print(f"✅ Nutrition plan generated for {plan.treatment}")
        print(f"   Supplements: {len(plan.supplements)}")
        print(f"   Foods to prioritize: {len(plan.foods_to_prioritize)}")
        print(f"   Drug interactions: {len(plan.drug_food_interactions)}")
        print(f"   Timing rules: {len(plan.timing_rules)}")
    
    asyncio.run(run_test())





