"""
Integration Tests for MOAT Orchestrator

Tests the full pipeline with sample patient data.
"""

import pytest
import asyncio
from datetime import datetime

import sys
sys.path.insert(0, '.')

from api.services.orchestrator import Orchestrator, PatientState, StatePhase
from api.services.orchestrator.state_store import StateStore


@pytest.fixture
def orchestrator():
    """Create a fresh orchestrator for each test."""
    return Orchestrator()


@pytest.fixture
def sample_mm_mutations():
    """Sample Multiple Myeloma mutations."""
    return [
        {"gene": "DIS3", "hgvs_p": "p.C562Y", "vaf": 0.45},
        {"gene": "TP53", "hgvs_p": "p.R175H", "vaf": 0.32}
    ]


@pytest.fixture
def sample_ov_mutations():
    """Sample Ovarian Cancer mutations."""
    return [
        {"gene": "NF1", "hgvs_p": "p.R1513*", "vaf": 0.38},
        {"gene": "KRAS", "hgvs_p": "p.G12D", "vaf": 0.55},
        {"gene": "BRCA1", "hgvs_p": "p.E1685fs", "vaf": 0.48}
    ]


class TestPatientState:
    """Test PatientState class."""
    
    def test_create_state(self):
        """Test creating a new patient state."""
        state = PatientState(patient_id="TEST-001")
        
        assert state.patient_id == "TEST-001"
        assert state.phase == StatePhase.INITIALIZED
        assert state.mutations == []
        assert state.mechanism_vector == [0.0] * 7
    
    def test_update_state(self):
        """Test updating state with audit trail."""
        state = PatientState(patient_id="TEST-001")
        
        state.update("phase", StatePhase.ANALYZING, "orchestrator", "Starting analysis")
        
        assert state.phase == StatePhase.ANALYZING
        assert len(state.history) == 1
        assert state.history[0].agent == "orchestrator"
    
    def test_progress_tracking(self):
        """Test progress percentage calculation."""
        state = PatientState(patient_id="TEST-001")
        
        # Start with 0%
        assert state.get_progress_percent() == 0
        
        # Add some completed agents
        execution = state.start_agent("biomarker")
        execution.complete({})
        
        assert state.get_progress_percent() > 0
    
    def test_alert_management(self):
        """Test adding alerts."""
        from api.services.orchestrator.state import AlertSeverity
        
        state = PatientState(patient_id="TEST-001")
        
        state.add_alert(
            alert_type="test_alert",
            message="Test message",
            severity=AlertSeverity.WARNING,
            source_agent="test"
        )
        
        assert len(state.alerts) == 1
        assert state.alerts[0].alert_type == "test_alert"


class TestOrchestrator:
    """Test Orchestrator class."""
    
    @pytest.mark.asyncio
    async def test_run_pipeline_with_mm_mutations(self, orchestrator, sample_mm_mutations):
        """Test running full pipeline with MM mutations."""
        state = await orchestrator.run_full_pipeline(
            mutations=sample_mm_mutations,
            disease="myeloma",
            patient_id="TEST-MM-001",
            treatment_line=2,
            prior_therapies=["proteasome_inhibitor"],
            cytogenetics={"del_17p": True}
        )
        
        # Verify state
        assert state.patient_id == "TEST-MM-001"
        assert state.disease == "myeloma"
        assert state.phase == StatePhase.COMPLETE
        
        # Verify mutations stored
        assert len(state.mutations) == 2
        assert state.mutations[0]["gene"] == "DIS3"
        
        # Verify agents ran
        completed = state.get_completed_agents()
        assert "biomarker" in completed
        assert "resistance" in completed
        
        # Verify resistance prediction
        assert state.resistance_prediction is not None
        
        # Verify care plan generated
        assert state.care_plan is not None
    
    @pytest.mark.asyncio
    async def test_run_pipeline_with_ov_mutations(self, orchestrator, sample_ov_mutations):
        """Test running full pipeline with OV mutations."""
        state = await orchestrator.run_full_pipeline(
            mutations=sample_ov_mutations,
            disease="ovarian",
            patient_id="TEST-OV-001"
        )
        
        # Verify state
        assert state.patient_id == "TEST-OV-001"
        assert state.disease == "ovarian"
        assert state.phase == StatePhase.COMPLETE
        
        # Verify biomarker calculation
        assert state.biomarker_profile is not None
        
        # Check HRD status (BRCA1 should trigger HRD+)
        if state.biomarker_profile:
            assert state.biomarker_profile.get("hrd", {}).get("status") == "HRD+"
    
    @pytest.mark.asyncio
    async def test_get_state(self, orchestrator, sample_mm_mutations):
        """Test retrieving patient state."""
        # Run pipeline
        state = await orchestrator.run_full_pipeline(
            mutations=sample_mm_mutations,
            disease="myeloma",
            patient_id="TEST-GET-001"
        )
        
        # Retrieve state
        retrieved = await orchestrator.get_state("TEST-GET-001")
        
        assert retrieved is not None
        assert retrieved.patient_id == "TEST-GET-001"
        assert retrieved.phase == StatePhase.COMPLETE
    
    @pytest.mark.asyncio
    async def test_skip_agents(self, orchestrator, sample_mm_mutations):
        """Test skipping specific agents."""
        state = await orchestrator.run_full_pipeline(
            mutations=sample_mm_mutations,
            disease="myeloma",
            patient_id="TEST-SKIP-001",
            skip_agents=["nutrition", "trial_matching"]
        )
        
        completed = state.get_completed_agents()
        assert "nutrition" not in completed
        assert "trial_matching" not in completed
        assert "biomarker" in completed
        assert "resistance" in completed
    
    @pytest.mark.asyncio
    async def test_error_handling(self, orchestrator):
        """Test error handling with invalid data."""
        # Should raise error with no mutations or file
        with pytest.raises(ValueError):
            await orchestrator.run_full_pipeline(
                mutations=[],
                disease="myeloma",
                patient_id="TEST-ERROR-001"
            )


class TestStateStore:
    """Test StateStore class."""
    
    @pytest.mark.asyncio
    async def test_save_and_retrieve(self):
        """Test saving and retrieving state."""
        store = StateStore(storage_dir="data/test_patient_states")
        
        state = PatientState(patient_id="TEST-STORE-001")
        state.disease = "myeloma"
        state.phase = StatePhase.ANALYZING
        
        # Save
        await store.save(state)
        
        # Retrieve
        retrieved = await store.get("TEST-STORE-001")
        
        assert retrieved is not None
        assert retrieved.patient_id == "TEST-STORE-001"
        assert retrieved.disease == "myeloma"
    
    @pytest.mark.asyncio
    async def test_list_all(self):
        """Test listing all states."""
        store = StateStore(storage_dir="data/test_patient_states")
        
        # Create some states
        for i in range(3):
            state = PatientState(patient_id=f"TEST-LIST-{i:03d}")
            await store.save(state)
        
        # List
        states = await store.get_all(limit=10)
        
        assert len(states) >= 3


def run_tests():
    """Run all tests."""
    pytest.main([__file__, "-v", "--asyncio-mode=auto"])


if __name__ == "__main__":
    run_tests()

