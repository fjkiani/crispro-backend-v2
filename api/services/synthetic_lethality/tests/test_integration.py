"""
Integration tests for Synthetic Lethality Agent.

Tests the agent's integration with:
- Evo2 service
- LLM service
- Orchestrator
- State management
"""
import pytest
import asyncio
from typing import Dict, Any

from ..sl_agent import SyntheticLethalityAgent
from ..models import SyntheticLethalityRequest, MutationInput, SLOptions


@pytest.mark.asyncio
async def test_agent_basic_functionality():
    """Test basic agent functionality with BRCA1 mutation."""
    agent = SyntheticLethalityAgent()
    
    request = SyntheticLethalityRequest(
        disease="ovarian_cancer",
        mutations=[
            MutationInput(
                gene="BRCA1",
                hgvs_p="p.C61G",
                consequence="stop_gained",
                chrom="17",
                pos=43044295,
                ref="T",
                alt="G"
            )
        ],
        options=SLOptions(
            model_id="evo2_7b",
            include_explanations=False,  # Skip LLM for faster test
            explanation_audience="clinician"
        )
    )
    
    result = await agent.analyze(request)
    
    # Assertions
    assert result is not None
    assert result.disease == "ovarian_cancer"
    assert len(result.essentiality_scores) == 1
    assert result.essentiality_scores[0].gene == "BRCA1"
    assert result.essentiality_scores[0].essentiality_score >= 0.0
    assert result.essentiality_scores[0].essentiality_score <= 1.0
    assert len(result.broken_pathways) > 0
    assert result.calculation_time_ms > 0
    assert result.evo2_used is True
    
    print(f"✅ Basic functionality test passed")
    print(f"   - Essentiality score: {result.essentiality_scores[0].essentiality_score}")
    print(f"   - Broken pathways: {len(result.broken_pathways)}")
    print(f"   - Calculation time: {result.calculation_time_ms}ms")


@pytest.mark.asyncio
async def test_agent_multi_mutation():
    """Test agent with multiple mutations (MBD4 + TP53)."""
    agent = SyntheticLethalityAgent()
    
    request = SyntheticLethalityRequest(
        disease="ovarian_cancer",
        mutations=[
            MutationInput(
                gene="MBD4",
                hgvs_p="p.K403fs",
                consequence="frameshift_variant",
                chrom="3",
                pos=129247696,
                ref="A",
                alt="AA"
            ),
            MutationInput(
                gene="TP53",
                hgvs_p="p.R175H",
                consequence="missense_variant",
                chrom="17",
                pos=7673802,
                ref="G",
                alt="A"
            )
        ],
        options=SLOptions(
            include_explanations=False
        )
    )
    
    result = await agent.analyze(request)
    
    # Assertions
    assert len(result.essentiality_scores) == 2
    assert any(s.gene == "MBD4" for s in result.essentiality_scores)
    assert any(s.gene == "TP53" for s in result.essentiality_scores)
    
    # MBD4 should have high essentiality (frameshift)
    mbd4_score = next(s for s in result.essentiality_scores if s.gene == "MBD4")
    assert mbd4_score.essentiality_score >= 0.5  # Frameshift should be high
    
    # Should detect synthetic lethality
    assert result.synthetic_lethality_detected is True or len(result.essential_pathways) > 0
    
    print(f"✅ Multi-mutation test passed")
    print(f"   - MBD4 score: {mbd4_score.essentiality_score}")
    print(f"   - TP53 score: {next(s for s in result.essentiality_scores if s.gene == 'TP53').essentiality_score}")
    print(f"   - SL detected: {result.synthetic_lethality_detected}")


@pytest.mark.asyncio
async def test_pathway_mapping():
    """Test pathway mapping functionality."""
    agent = SyntheticLethalityAgent()
    
    request = SyntheticLethalityRequest(
        disease="ovarian_cancer",
        mutations=[
            MutationInput(
                gene="BRCA1",
                hgvs_p="p.C61G",
                consequence="stop_gained"
            )
        ],
        options=SLOptions(include_explanations=False)
    )
    
    result = await agent.analyze(request)
    
    # Should map BRCA1 to HR pathway
    hr_pathway = next((p for p in result.broken_pathways if p.pathway_id == "HR"), None)
    assert hr_pathway is not None, "BRCA1 should map to HR pathway"
    assert hr_pathway.status.value in ["non_functional", "compromised"]
    assert "BRCA1" in hr_pathway.genes_affected
    
    print(f"✅ Pathway mapping test passed")
    print(f"   - HR pathway status: {hr_pathway.status.value}")
    print(f"   - Disruption score: {hr_pathway.disruption_score}")


@pytest.mark.asyncio
async def test_drug_recommendations():
    """Test drug recommendation functionality."""
    agent = SyntheticLethalityAgent()
    
    request = SyntheticLethalityRequest(
        disease="ovarian_cancer",
        mutations=[
            MutationInput(
                gene="BRCA1",
                hgvs_p="p.C61G",
                consequence="stop_gained"
            )
        ],
        options=SLOptions(include_explanations=False)
    )
    
    result = await agent.analyze(request)
    
    # Should recommend PARP inhibitors for HR-deficient
    if result.synthetic_lethality_detected:
        assert len(result.recommended_drugs) > 0
        parp_drugs = [d for d in result.recommended_drugs if "PARP" in d.drug_class or "parp" in d.drug_name.lower()]
        assert len(parp_drugs) > 0, "Should recommend PARP inhibitors for HR-deficient"
        
        print(f"✅ Drug recommendation test passed")
        print(f"   - Recommended drugs: {len(result.recommended_drugs)}")
        print(f"   - PARP inhibitors: {[d.drug_name for d in parp_drugs]}")
        print(f"   - Top recommendation: {result.suggested_therapy}")
    else:
        print(f"⚠️  SL not detected, skipping drug recommendation test")


@pytest.mark.asyncio
async def test_error_handling():
    """Test error handling with invalid input."""
    agent = SyntheticLethalityAgent()
    
    # Test with missing gene
    request = SyntheticLethalityRequest(
        disease="ovarian_cancer",
        mutations=[
            MutationInput(
                gene="",  # Empty gene
                hgvs_p="p.C61G"
            )
        ],
        options=SLOptions(include_explanations=False)
    )
    
    # Should handle gracefully
    result = await agent.analyze(request)
    assert result is not None
    # Should return empty or default scores
    
    print(f"✅ Error handling test passed")


if __name__ == "__main__":
    # Run tests
    asyncio.run(test_agent_basic_functionality())
    asyncio.run(test_agent_multi_mutation())
    asyncio.run(test_pathway_mapping())
    asyncio.run(test_drug_recommendations())
    asyncio.run(test_error_handling())
    print("\n✅ All integration tests completed")


