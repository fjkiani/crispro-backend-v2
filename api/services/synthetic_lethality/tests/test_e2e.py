"""
End-to-end tests for Synthetic Lethality Agent.

Tests the full pipeline:
1. API endpoint
2. Orchestrator integration
3. State management
4. Full workflow
"""
import pytest
import asyncio
import httpx
from typing import Dict, Any

# Test configuration
API_BASE = "http://127.0.0.1:8000"
TEST_TIMEOUT = 30.0


@pytest.mark.asyncio
async def test_api_endpoint():
    """Test the API endpoint directly."""
    async with httpx.AsyncClient(timeout=TEST_TIMEOUT) as client:
        response = await client.post(
            f"{API_BASE}/api/agents/synthetic_lethality",
            json={
                "disease": "ovarian_cancer",
                "mutations": [
                    {
                        "gene": "BRCA1",
                        "hgvs_p": "p.C61G",
                        "consequence": "stop_gained",
                        "chrom": "17",
                        "pos": 43044295,
                        "ref": "T",
                        "alt": "G"
                    }
                ],
                "options": {
                    "model_id": "evo2_7b",
                    "include_explanations": False,
                    "explanation_audience": "clinician"
                }
            }
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Validate response structure
        assert "synthetic_lethality_detected" in data
        assert "essentiality_scores" in data
        assert "broken_pathways" in data
        assert "recommended_drugs" in data
        assert "evo2_used" in data
        assert data["evo2_used"] is True
        
        print(f"✅ API endpoint test passed")
        print(f"   - SL detected: {data['synthetic_lethality_detected']}")
        print(f"   - Genes scored: {len(data['essentiality_scores'])}")
        print(f"   - Drugs recommended: {len(data['recommended_drugs'])}")


@pytest.mark.asyncio
async def test_api_health_check():
    """Test the health check endpoint."""
    async with httpx.AsyncClient(timeout=TEST_TIMEOUT) as client:
        response = await client.get(
            f"{API_BASE}/api/agents/synthetic_lethality/health"
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["agent"] == "SyntheticLethalityAgent"
        
        print(f"✅ Health check test passed")


@pytest.mark.asyncio
async def test_api_error_handling():
    """Test API error handling."""
    async with httpx.AsyncClient(timeout=TEST_TIMEOUT) as client:
        # Test missing disease
        response = await client.post(
            f"{API_BASE}/api/agents/synthetic_lethality",
            json={
                "mutations": [{"gene": "BRCA1"}]
            }
        )
        assert response.status_code == 400
        
        # Test missing mutations
        response = await client.post(
            f"{API_BASE}/api/agents/synthetic_lethality",
            json={
                "disease": "ovarian_cancer"
            }
        )
        assert response.status_code == 400
        
        print(f"✅ API error handling test passed")


@pytest.mark.asyncio
async def test_orchestrator_integration():
    """Test integration with orchestrator."""
    from api.services.orchestrator.orchestrator import Orchestrator
    from api.services.orchestrator.state import PatientState
    
    orchestrator = Orchestrator()
    
    # Create test state
    state = PatientState(
        patient_id="TEST-PT-001",
        disease="ovarian_cancer",
        mutations=[
            {
                "gene": "BRCA1",
                "hgvs_p": "p.C61G",
                "consequence": "stop_gained",
                "chrom": "17",
                "pos": 43044295,
                "ref": "T",
                "alt": "G"
            }
        ]
    )
    
    # Run synthetic lethality phase
    state = await orchestrator._run_synthetic_lethality_phase(state)
    
    # Validate state
    assert state.synthetic_lethality_result is not None
    result = state.synthetic_lethality_result
    
    assert "synthetic_lethality_detected" in result
    assert "essentiality_scores" in result
    assert len(result["essentiality_scores"]) > 0
    
    # Check execution tracking
    executions = [e for e in state.agent_executions if e.agent_id == "synthetic_lethality"]
    assert len(executions) > 0
    assert executions[0].status == "complete"
    
    print(f"✅ Orchestrator integration test passed")
    print(f"   - Result stored in state: {state.synthetic_lethality_result is not None}")
    print(f"   - Execution status: {executions[0].status}")


@pytest.mark.asyncio
async def test_full_pipeline():
    """Test full pipeline with multiple agents."""
    from api.services.orchestrator.orchestrator import Orchestrator
    from api.services.orchestrator.state import PatientState
    
    orchestrator = Orchestrator()
    
    # Create test state
    state = PatientState(
        patient_id="TEST-PT-002",
        disease="ovarian_cancer",
        mutations=[
            {
                "gene": "BRCA1",
                "hgvs_p": "p.C61G",
                "consequence": "stop_gained"
            },
            {
                "gene": "TP53",
                "hgvs_p": "p.R175H",
                "consequence": "missense_variant"
            }
        ]
    )
    
    # Run biomarker agent first (dependency)
    state = await orchestrator._run_biomarker_agent(state)
    assert state.biomarker_profile is not None
    
    # Run synthetic lethality agent
    state = await orchestrator._run_synthetic_lethality_phase(state)
    assert state.synthetic_lethality_result is not None
    
    # Validate results flow
    result = state.synthetic_lethality_result
    assert len(result["essentiality_scores"]) == 2
    
    print(f"✅ Full pipeline test passed")
    print(f"   - Biomarker profile: {state.biomarker_profile is not None}")
    print(f"   - SL result: {state.synthetic_lethality_result is not None}")
    print(f"   - Progress: {state.get_progress_percent()}%")


if __name__ == "__main__":
    print("🧪 Running E2E Tests...\n")
    
    try:
        asyncio.run(test_api_health_check())
        asyncio.run(test_api_endpoint())
        asyncio.run(test_api_error_handling())
        asyncio.run(test_orchestrator_integration())
        asyncio.run(test_full_pipeline())
        print("\n✅ All E2E tests completed successfully!")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()


