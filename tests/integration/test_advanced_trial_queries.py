"""
Tests for Advanced Trial Query System

Tests Phase 1-5 implementations:
- Enhanced autonomous agent query generation
- CTGovQueryBuilder
- Advanced query endpoint
- Mechanism fit ranking
- Trial data enrichment
"""
import pytest
from api.services.autonomous_trial_agent import AutonomousTrialAgent
from api.services.ctgov_query_builder import CTGovQueryBuilder
from api.services.pathway_to_mechanism_vector import (
    convert_pathway_scores_to_mechanism_vector,
    normalize_pathway_name,
    validate_mechanism_vector,
    convert_moa_dict_to_vector
)
from api.services.trial_data_enricher import (
    extract_pi_information,
    extract_genetic_requirements,
    extract_therapy_types
)


def test_autonomous_agent_query_generation():
    """Test enhanced query generation with DNA repair mutations."""
    agent = AutonomousTrialAgent()
    
    patient_data = {
        "disease": "ovarian cancer",
        "mutations": [{"gene": "MBD4"}, {"gene": "TP53"}],
        "germline_status": "negative",
        "tumor_context": {"tmb": 10.5, "hrd_score": 0.65}
    }
    
    context = agent.extract_patient_context(patient_data)
    
    # Check DNA repair detection
    assert context["has_dna_repair"] == True
    assert "MBD4" in context["dna_repair_mutations"]
    assert "TP53" in context["dna_repair_mutations"]
    
    # Check query generation
    queries = agent.generate_search_queries(context)
    assert len(queries) >= 5  # Should generate 5-10 queries
    assert any("DNA repair" in q for q in queries)
    assert any("basket" in q.lower() for q in queries)


def test_ctgov_query_builder():
    """Test ClinicalTrials.gov query builder."""
    builder = CTGovQueryBuilder()
    
    builder.add_condition("ovarian cancer")
    builder.add_intervention("PARP inhibitor")
    builder.add_status(["RECRUITING", "NOT_YET_RECRUITING"])
    builder.add_phase(["PHASE1", "PHASE2", "PHASE3"])
    builder.add_keyword("DNA repair")
    
    params = builder.build()
    
    assert "query.cond" in params
    assert "query.intr" in params
    assert "filter.overallStatus" in params
    assert "filter.phase" in params


def test_pathway_to_mechanism_vector():
    """Test pathway score to mechanism vector conversion."""
    pathway_scores = {
        "ddr": 0.85,
        "ras_mapk": 0.20,
        "pi3k": 0.10
    }
    
    tumor_context = {"tmb": 25.0, "msi_status": "MSS"}
    
    vector, dimension = convert_pathway_scores_to_mechanism_vector(
        pathway_scores,
        tumor_context,
        use_7d=False
    )
    
    assert len(vector) == 6
    assert dimension == "6D"
    assert vector[0] == 0.85  # DDR
    assert vector[1] == 0.20  # MAPK
    assert vector[4] == 1.0   # IO (TMB >= 20)


def test_pathway_name_normalization():
    """Test pathway name normalization."""
    assert normalize_pathway_name("DNA Repair") == "ddr"
    assert normalize_pathway_name("RAS/MAPK") == "ras_mapk"
    assert normalize_pathway_name("PI3K") == "pi3k"
    assert normalize_pathway_name("TP53") == "ddr"  # TP53 maps to DDR


def test_mechanism_vector_validation():
    """Test mechanism vector validation."""
    valid_vector = [0.85, 0.20, 0.10, 0.0, 1.0, 0.0]
    is_valid, error = validate_mechanism_vector(valid_vector, expected_dimension=6)
    assert is_valid == True
    assert error is None
    
    invalid_vector = [0.85, 0.20, 0.10, 0.0, 1.5, 0.0]  # Value > 1.0
    is_valid, error = validate_mechanism_vector(invalid_vector)
    assert is_valid == False
    assert "out of range" in error


def test_moa_dict_conversion():
    """Test MoA dict to vector conversion."""
    moa_dict = {"ddr": 0.9, "mapk": 0.0, "pi3k": 0.1}
    vector = convert_moa_dict_to_vector(moa_dict, use_7d=False)
    
    assert len(vector) == 6
    assert vector[0] == 0.9  # DDR
    assert vector[1] == 0.0  # MAPK
    assert vector[2] == 0.1  # PI3K


def test_trial_data_enrichment():
    """Test trial data enrichment."""
    # Mock trial data structure
    trial_data = {
        "protocolSection": {
            "identificationModule": {
                "nctId": "NCT12345678",
                "briefTitle": "Test Trial"
            },
            "contactsLocationsModule": {
                "overallOfficial": [{
                    "role": "PRINCIPAL_INVESTIGATOR",
                    "name": "Dr. Jane Smith",
                    "email": "jane.smith@example.com",
                    "affiliation": "Test Hospital"
                }],
                "locations": [{
                    "facility": "Test Hospital",
                    "city": "New York",
                    "state": "NY",
                    "country": "United States"
                }]
            },
            "armsInterventionsModule": {
                "interventions": [{
                    "type": "DRUG",
                    "name": "olaparib"
                }]
            },
            "eligibilityModule": {
                "inclusionCriteria": "BRCA1/2 mutation required",
                "exclusionCriteria": "None"
            }
        }
    }
    
    # Test PI extraction
    pi_info = extract_pi_information(trial_data)
    assert pi_info is not None
    assert pi_info["name"] == "Dr. Jane Smith"
    
    # Test genetic requirements
    genetic_reqs = extract_genetic_requirements(trial_data)
    assert "BRCA mutation" in genetic_reqs
    
    # Test therapy types
    therapy_types = extract_therapy_types(trial_data)
    assert "PARP inhibitor" in therapy_types


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


