#!/usr/bin/env python3
"""
End-to-End Orchestrator Pipeline Test

Tests the complete orchestrator pipeline from file upload to care plan generation.
Validates all agents execute correctly and state is properly managed.

Deliverable: End-to-End Testing (Item 1)
"""

import pytest
import asyncio
import sys
from pathlib import Path
from typing import Dict, Any

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.services.orchestrator import Orchestrator, PatientState, StatePhase
from api.services.orchestrator.state_store import get_state_store


class TestOrchestratorE2EPipeline:
    """End-to-end tests for the orchestrator pipeline."""
    
    @pytest.fixture
    def orchestrator(self):
        """Create a fresh orchestrator for each test."""
        return Orchestrator()
    
    @pytest.fixture
    def sample_mutations(self):
        """Sample mutations for testing."""
        return [
            {
                "gene": "KRAS",
                "hgvs_p": "p.G12D",
                "hgvs_c": "c.35G>A",
                "chrom": "12",
                "pos": 25398284,
                "ref": "G",
                "alt": "A",
                "consequence": "missense_variant",
                "vaf": 0.45
            },
            {
                "gene": "TP53",
                "hgvs_p": "p.R175H",
                "hgvs_c": "c.524G>A",
                "chrom": "17",
                "pos": 7673802,
                "ref": "G",
                "alt": "A",
                "consequence": "missense_variant",
                "vaf": 0.32
            }
        ]
    
    @pytest.mark.asyncio
    async def test_full_pipeline_with_mutations(self, orchestrator, sample_mutations):
        """Test full pipeline execution with direct mutations."""
        # Run pipeline
        state = await orchestrator.run_full_pipeline(
            mutations=sample_mutations,
            disease="ovarian",
            patient_id="TEST-E2E-001"
        )
        
        # Verify state progression
        assert state.phase == StatePhase.COMPLETE, f"Expected COMPLETE, got {state.phase}"
        assert state.patient_id == "TEST-E2E-001"
        assert state.disease == "ovarian"
        assert len(state.mutations) == 2
        
        # Verify mutations are stored
        assert state.mutations[0]["gene"] == "KRAS"
        assert state.mutations[1]["gene"] == "TP53"
        
        # Verify agent outputs exist
        assert state.biomarker_profile is not None, "Biomarker profile should be populated"
        assert state.drug_ranking is not None, "Drug ranking should be populated"
        assert len(state.drug_ranking) > 0, "Should have at least one drug ranked"
        
        # Verify mechanism vector is populated
        assert state.mechanism_vector is not None
        assert len(state.mechanism_vector) == 7, "Mechanism vector should be 7D"
        assert any(v > 0 for v in state.mechanism_vector), "At least one pathway should be active"
        
        # Verify trial matches exist
        assert state.trial_matches is not None, "Trial matches should be populated"
        
        # Verify nutrition plan exists
        assert state.nutrition_plan is not None, "Nutrition plan should be populated"
        
        print(f"✅ Pipeline complete: {len(state.drug_ranking)} drugs ranked, {len(state.trial_matches)} trials matched")
    
    @pytest.mark.asyncio
    async def test_pipeline_state_progression(self, orchestrator, sample_mutations):
        """Test that state progresses through all phases correctly."""
        state = await orchestrator.run_full_pipeline(
            mutations=sample_mutations,
            disease="ovarian",
            patient_id="TEST-E2E-002"
        )
        
        # Check history shows progression
        assert len(state.history) > 0, "Should have execution history"
        
        # Verify agents executed
        agent_names = [exec.agent_name for exec in state.agent_executions]
        expected_agents = ["biomarker", "resistance", "drug_efficacy", "trial_matching", "nutrition"]
        
        for agent in expected_agents:
            assert agent in agent_names, f"Agent {agent} should have executed"
        
        print(f"✅ State progression verified: {len(state.history)} state updates")
    
    @pytest.mark.asyncio
    async def test_drug_ranking_structure(self, orchestrator, sample_mutations):
        """Test that drug ranking has correct structure."""
        state = await orchestrator.run_full_pipeline(
            mutations=sample_mutations,
            disease="ovarian",
            patient_id="TEST-E2E-003"
        )
        
        assert state.drug_ranking is not None
        assert len(state.drug_ranking) > 0
        
        # Check first drug structure
        top_drug = state.drug_ranking[0]
        assert "drug_name" in top_drug or "name" in top_drug, "Drug should have name"
        assert "efficacy_score" in top_drug or "score" in top_drug, "Drug should have efficacy score"
        
        # Verify scores are in valid range
        score = top_drug.get("efficacy_score") or top_drug.get("score", 0)
        assert 0 <= score <= 1, f"Efficacy score should be 0-1, got {score}"
        
        print(f"✅ Drug ranking structure verified: {len(state.drug_ranking)} drugs")
    
    @pytest.mark.asyncio
    async def test_mechanism_vector_extraction(self, orchestrator, sample_mutations):
        """Test that mechanism vector is correctly extracted from pathway scores."""
        state = await orchestrator.run_full_pipeline(
            mutations=sample_mutations,
            disease="ovarian",
            patient_id="TEST-E2E-004"
        )
        
        assert state.mechanism_vector is not None
        assert len(state.mechanism_vector) == 7
        
        # Mechanism vector should be [DDR, MAPK, PI3K, VEGF, HER2, IO, Efflux]
        # With KRAS G12D, we should see MAPK pathway active
        mapk_score = state.mechanism_vector[1]  # MAPK is index 1
        assert mapk_score > 0, f"MAPK pathway should be active for KRAS G12D, got {mapk_score}"
        
        print(f"✅ Mechanism vector verified: MAPK={mapk_score:.3f}")
    
    @pytest.mark.asyncio
    async def test_error_handling(self, orchestrator):
        """Test that pipeline handles errors gracefully."""
        # Test with invalid mutations
        try:
            state = await orchestrator.run_full_pipeline(
                mutations=[{"gene": "INVALID"}],  # Missing required fields
                disease="ovarian",
                patient_id="TEST-E2E-005"
            )
            # Should either complete with warnings or raise specific error
            assert state is not None
        except Exception as e:
            # If it raises, should be a specific error, not a generic one
            assert "mutation" in str(e).lower() or "invalid" in str(e).lower()
        
        print("✅ Error handling verified")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])













