"""
Unit Tests for Universal Profile Adapter

Tests the profile adapter functions that convert simple profiles to full format.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from api.services.complete_care_universal.profile_adapter import (
    adapt_simple_to_full_profile,
    is_simple_profile
)


class TestProfileAdapter:
    """Test profile adapter functions."""
    
    def test_is_simple_profile_detects_simple_format(self):
        """Test that is_simple_profile correctly identifies simple format."""
        simple_profile = {
            "patient_id": "test_001",
            "name": "Test Patient",
            "disease": "ovarian_cancer_hgs",
            "treatment_line": "first-line",
            "location": "New York"
        }
        
        assert is_simple_profile(simple_profile) == True
    
    def test_is_simple_profile_detects_full_format(self):
        """Test that is_simple_profile correctly identifies full format."""
        full_profile = {
            "patient_id": "test_001",
            "demographics": {
                "name": "Test Patient",
                "age": 45,
                "sex": "female"
            },
            "disease": {
                "type": "ovarian_cancer_hgs",
                "stage": "IVB"
            },
            "treatment": {
                "line": "first-line"
            },
            "logistics": {
                "location": "New York"
            }
        }
        
        assert is_simple_profile(full_profile) == False
    
    def test_adapt_simple_to_full_with_string_disease(self):
        """Test adaptation with disease as string."""
        simple_profile = {
            "patient_id": "test_001",
            "name": "Test Patient",
            "disease": "ovarian_cancer_hgs",
            "stage": "IVB",
            "treatment_line": "first-line",
            "location": "New York",
            "zip_code": "10001",
            "age": 45,
            "sex": "female",
            "biomarkers": {
                "ca125_value": 1500.0
            }
        }
        
        full_profile = adapt_simple_to_full_profile(simple_profile)
        
        assert full_profile["demographics"]["patient_id"] == "test_001"
        assert full_profile["demographics"]["name"] == "Test Patient"
        assert full_profile["demographics"]["age"] == 45
        assert full_profile["demographics"]["sex"] == "female"
        assert full_profile["disease"]["type"] == "ovarian_cancer_hgs"
        assert full_profile["disease"]["stage"] == "IVB"
        assert full_profile["treatment"]["line"] == "first-line"
        assert full_profile["logistics"]["location"] == "New York"
        assert full_profile["logistics"]["zip_code"] == "10001"
        assert full_profile["biomarkers"]["ca125_value"] == 1500.0
    
    def test_adapt_simple_to_full_with_dict_disease(self):
        """Test adaptation with disease as dict."""
        simple_profile = {
            "patient_id": "test_002",
            "name": "Test Patient 2",
            "disease": {
                "type": "melanoma",
                "stage": "III"
            },
            "treatment_line": "second-line",
            "location": "Los Angeles"
        }
        
        full_profile = adapt_simple_to_full_profile(simple_profile)
        
        assert full_profile["disease"]["type"] == "melanoma"
        assert full_profile["disease"]["stage"] == "III"
        assert full_profile["treatment"]["line"] == "second-line"
    
    def test_adapt_simple_to_full_with_tumor_context(self):
        """Test adaptation preserves tumor_context."""
        simple_profile = {
            "patient_id": "test_003",
            "name": "Test Patient 3",
            "disease": "ovarian_cancer_hgs",
            "treatment_line": "first-line",
            "location": "New York",
            "tumor_context": {
                "somatic_mutations": [
                    {
                        "gene": "BRCA1",
                        "hgvs_p": "p.Arg1835Ter"
                    }
                ],
                "hrd_score": 35.0
            }
        }
        
        full_profile = adapt_simple_to_full_profile(simple_profile)
        
        assert "tumor_context" in full_profile
        assert len(full_profile["tumor_context"]["somatic_mutations"]) == 1
        assert full_profile["tumor_context"]["somatic_mutations"][0]["gene"] == "BRCA1"
        assert full_profile["tumor_context"]["hrd_score"] == 35.0
    
    def test_adapt_simple_to_full_with_missing_fields(self):
        """Test adaptation handles missing optional fields gracefully."""
        minimal_profile = {
            "patient_id": "test_004",
            "disease": "ovarian_cancer_hgs",
            "treatment_line": "first-line"
        }
        
        full_profile = adapt_simple_to_full_profile(minimal_profile)
        
        assert full_profile["demographics"]["patient_id"] == "test_004"
        assert full_profile["demographics"]["name"] == "Patient test_004"  # Default name
        assert full_profile["disease"]["type"] == "ovarian_cancer_hgs"
        assert full_profile["disease"]["stage"] == "Unknown"  # Default stage
        assert full_profile["treatment"]["line"] == "first-line"
        assert full_profile["logistics"]["location"] == "Unknown"  # Default location
    
    def test_adapt_simple_to_full_preserves_all_fields(self):
        """Test that all fields from simple profile are preserved."""
        simple_profile = {
            "patient_id": "test_005",
            "name": "Complete Test Patient",
            "disease": "multiple_myeloma",
            "stage": "III",
            "treatment_line": "first-line",
            "location": "Boston",
            "zip_code": "02115",
            "age": 60,
            "sex": "male",
            "biomarkers": {
                "m_protein": 2.5,
                "light_chain": 150.0
            },
            "tumor_context": {
                "somatic_mutations": [
                    {"gene": "KRAS", "hgvs_p": "p.G12D"}
                ]
            }
        }
        
        full_profile = adapt_simple_to_full_profile(simple_profile)
        
        # Verify all fields are present
        assert full_profile["demographics"]["patient_id"] == "test_005"
        assert full_profile["demographics"]["name"] == "Complete Test Patient"
        assert full_profile["demographics"]["age"] == 60
        assert full_profile["demographics"]["sex"] == "male"
        assert full_profile["disease"]["type"] == "multiple_myeloma"
        assert full_profile["disease"]["stage"] == "III"
        assert full_profile["treatment"]["line"] == "first-line"
        assert full_profile["logistics"]["location"] == "Boston"
        assert full_profile["logistics"]["zip_code"] == "02115"
        assert "m_protein" in full_profile["biomarkers"]
        assert "light_chain" in full_profile["biomarkers"]
        assert len(full_profile["tumor_context"]["somatic_mutations"]) == 1


if __name__ == "__main__":
    # Run tests directly
    test_instance = TestProfileAdapter()
    test_methods = [method for method in dir(test_instance) if method.startswith("test_")]
    
    passed = 0
    failed = 0
    
    for method_name in test_methods:
        try:
            print(f"Running {method_name}...", end=" ")
            getattr(test_instance, method_name)()
            print("✅ PASSED")
            passed += 1
        except AssertionError as e:
            print(f"❌ FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"❌ ERROR: {e}")
            failed += 1
    
    print(f"\n✅ Passed: {passed}, ❌ Failed: {failed}")
    sys.exit(1 if failed > 0 else 0)

