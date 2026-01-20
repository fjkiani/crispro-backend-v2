#!/usr/bin/env python3
"""
Standalone test script for Advanced Trial Query System
Run from oncology-backend-minimal directory: python3 test_advanced_queries_standalone.py
"""
import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_pathway_to_mechanism_vector():
    """Test pathway score to mechanism vector conversion."""
    print("\n🧪 Testing pathway_to_mechanism_vector...")
    try:
        from api.services.pathway_to_mechanism_vector import (
            normalize_pathway_name,
            convert_pathway_scores_to_mechanism_vector,
            validate_mechanism_vector,
            convert_moa_dict_to_vector
        )
        
        # Test normalization
        assert normalize_pathway_name("DNA Repair") == "ddr"
        assert normalize_pathway_name("RAS/MAPK") == "ras_mapk"
        assert normalize_pathway_name("TP53") == "ddr"
        print("  ✅ Pathway name normalization works")
        
        # Test conversion
        pathway_scores = {"ddr": 0.85, "ras_mapk": 0.20, "pi3k": 0.10}
        tumor_context = {"tmb": 25.0, "msi_status": "MSS"}
        vector, dimension = convert_pathway_scores_to_mechanism_vector(
            pathway_scores, tumor_context, use_7d=False
        )
        assert len(vector) == 6
        assert dimension == "6D"
        assert vector[0] == 0.85  # DDR
        assert vector[4] == 1.0   # IO (TMB >= 20)
        print("  ✅ Pathway to mechanism vector conversion works")
        
        # Test validation
        valid_vector = [0.85, 0.20, 0.10, 0.0, 1.0, 0.0]
        is_valid, error = validate_mechanism_vector(valid_vector, expected_dimension=6)
        assert is_valid == True
        print("  ✅ Mechanism vector validation works")
        
        # Test MoA dict conversion
        moa_dict = {"ddr": 0.9, "mapk": 0.0, "pi3k": 0.1}
        vector = convert_moa_dict_to_vector(moa_dict, use_7d=False)
        assert len(vector) == 6
        assert vector[0] == 0.9
        print("  ✅ MoA dict to vector conversion works")
        
        return True
    except Exception as e:
        print(f"  ❌ Failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_ctgov_query_builder():
    """Test ClinicalTrials.gov query builder."""
    print("\n🧪 Testing CTGovQueryBuilder...")
    try:
        from api.services.ctgov_query_builder import CTGovQueryBuilder
        
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
        print("  ✅ Query builder works")
        
        # Test specialized queries
        builder2 = CTGovQueryBuilder()
        params2 = builder2.build_dna_repair_query(
            ["ovarian cancer"], ["MBD4"], ["PARP inhibitor"]
        )
        assert "query.cond" in params2
        print("  ✅ Specialized query methods work")
        
        return True
    except Exception as e:
        print(f"  ❌ Failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_autonomous_agent():
    """Test enhanced autonomous agent."""
    print("\n🧪 Testing AutonomousTrialAgent...")
    try:
        from api.services.autonomous_trial_agent import AutonomousTrialAgent
        
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
        print("  ✅ DNA repair detection works")
        
        # Check query generation
        queries = agent.generate_search_queries(context)
        assert len(queries) >= 5
        assert any("DNA repair" in q for q in queries)
        assert any("basket" in q.lower() for q in queries)
        print(f"  ✅ Query generation works ({len(queries)} queries generated)")
        
        return True
    except Exception as e:
        print(f"  ❌ Failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_trial_data_enricher():
    """Test trial data enricher."""
    print("\n🧪 Testing TrialDataEnricher...")
    try:
        from api.services.trial_data_enricher import (
            extract_pi_information,
            extract_genetic_requirements,
            extract_therapy_types
        )
        
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
        print("  ✅ PI information extraction works")
        
        # Test genetic requirements
        genetic_reqs = extract_genetic_requirements(trial_data)
        assert "BRCA mutation" in genetic_reqs
        print("  ✅ Genetic requirements extraction works")
        
        # Test therapy types
        therapy_types = extract_therapy_types(trial_data)
        assert "PARP inhibitor" in therapy_types
        print("  ✅ Therapy type extraction works")
        
        return True
    except Exception as e:
        print(f"  ❌ Failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_efficacy_prediction_integration():
    """Test efficacy prediction integration."""
    print("\n🧪 Testing Efficacy Prediction Integration...")
    try:
        from api.services.autonomous_trial_agent import AutonomousTrialAgent
        
        agent = AutonomousTrialAgent()
        
        patient_data = {
            "disease": "ovarian cancer",
            "mutations": [{"gene": "BRCA1"}],
            "efficacy_predictions": {
                "drugs": [
                    {"name": "olaparib", "efficacy": 0.85, "confidence": 0.75},
                    {"name": "niraparib", "efficacy": 0.80, "confidence": 0.70}
                ],
                "provenance": {
                    "confidence_breakdown": {
                        "pathway_disruption": {
                            "ddr": 0.85,
                            "ras_mapk": 0.20
                        }
                    }
                }
            }
        }
        
        context = agent.extract_patient_context(patient_data)
        
        # Check intervention preferences extracted
        assert len(context.get("intervention_preferences", [])) > 0
        assert "PARP inhibitor" in context["intervention_preferences"]
        print("  ✅ Efficacy prediction integration works")
        
        # Check pathway scores extracted
        assert context.get("pathway_scores") is not None
        assert context["pathway_scores"].get("ddr") == 0.85
        print("  ✅ Pathway scores extraction works")
        
        return True
    except Exception as e:
        print(f"  ❌ Failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("=" * 60)
    print("🧪 ADVANCED TRIAL QUERY SYSTEM - TEST SUITE")
    print("=" * 60)
    
    results = []
    
    results.append(("Pathway to Mechanism Vector", test_pathway_to_mechanism_vector()))
    results.append(("CTGovQueryBuilder", test_ctgov_query_builder()))
    results.append(("AutonomousTrialAgent", test_autonomous_agent()))
    results.append(("TrialDataEnricher", test_trial_data_enricher()))
    results.append(("Efficacy Prediction Integration", test_efficacy_prediction_integration()))
    
    print("\n" + "=" * 60)
    print("📊 TEST RESULTS SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())

