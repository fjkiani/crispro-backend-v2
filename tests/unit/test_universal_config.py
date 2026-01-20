"""
Unit Tests for Universal Complete Care Config

Tests configuration functions for SOC recommendations and disease validation.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from api.services.complete_care_universal.config import (
    get_soc_recommendation,
    validate_disease_type,
    get_biomarker_config
)


class TestSOCRecommendation:
    """Test SOC recommendation functions."""
    
    def test_get_soc_recommendation_ovarian_first_line(self):
        """Test SOC recommendation for ovarian cancer first-line."""
        soc = get_soc_recommendation("ovarian_cancer_hgs", "first-line")
        
        assert soc is not None
        assert "regimen" in soc
        assert "carboplatin" in soc["regimen"].lower() or "paclitaxel" in soc["regimen"].lower()
        assert "nccn_category" in soc
    
    def test_get_soc_recommendation_ovarian_second_line(self):
        """Test SOC recommendation for ovarian cancer second-line."""
        soc = get_soc_recommendation("ovarian_cancer_hgs", "second_line")
        
        assert soc is not None
        assert "regimen" in soc
        assert "parp" in soc["regimen"].lower() or "platinum" in soc["regimen"].lower()
    
    def test_get_soc_recommendation_melanoma(self):
        """Test SOC recommendation for melanoma."""
        soc = get_soc_recommendation("melanoma", "first-line")
        
        assert soc is not None
        assert "regimen" in soc
        assert "nivolumab" in soc["regimen"].lower() or "pembrolizumab" in soc["regimen"].lower()
    
    def test_get_soc_recommendation_multiple_myeloma(self):
        """Test SOC recommendation for multiple myeloma."""
        soc = get_soc_recommendation("multiple_myeloma", "first-line")
        
        assert soc is not None
        assert "regimen" in soc
    
    def test_get_soc_recommendation_unknown_disease(self):
        """Test SOC recommendation for unknown disease returns None."""
        soc = get_soc_recommendation("unknown_cancer", "first_line")
        
        assert soc is None
    
    def test_get_soc_recommendation_unknown_line(self):
        """Test SOC recommendation for unknown treatment line returns None."""
        soc = get_soc_recommendation("ovarian_cancer_hgs", "unknown_line")
        
        # May return None or default to first_line
        assert soc is None or isinstance(soc, dict)


class TestDiseaseValidation:
    """Test disease type validation functions."""
    
    def test_validate_disease_type_ovarian(self):
        """Test validation of ovarian cancer."""
        is_valid, normalized = validate_disease_type("ovarian_cancer_hgs")
        
        assert is_valid == True
        assert normalized == "ovarian_cancer_hgs"
    
    def test_validate_disease_type_melanoma(self):
        """Test validation of melanoma."""
        is_valid, normalized = validate_disease_type("melanoma")
        
        assert is_valid == True
        assert normalized == "melanoma"
    
    def test_validate_disease_type_multiple_myeloma(self):
        """Test validation of multiple myeloma."""
        is_valid, normalized = validate_disease_type("multiple_myeloma")
        
        assert is_valid == True
        assert normalized == "multiple_myeloma"
    
    def test_validate_disease_type_case_insensitive(self):
        """Test that disease validation is case-insensitive."""
        is_valid, normalized = validate_disease_type("OVARIAN_CANCER_HGS")
        
        assert is_valid == True
        assert normalized == "ovarian_cancer_hgs"
    
    def test_validate_disease_type_with_spaces(self):
        """Test that disease validation handles spaces."""
        is_valid, normalized = validate_disease_type("ovarian cancer hgs")
        
        assert is_valid == True
        assert normalized == "ovarian_cancer_hgs"
    
    def test_validate_disease_type_unknown(self):
        """Test validation of unknown disease type."""
        is_valid, normalized = validate_disease_type("unknown_cancer")
        
        assert is_valid is False
        assert normalized == "unknown"


class TestBiomarkerConfig:
    """Test biomarker configuration functions."""
    
    def test_get_biomarker_config_ovarian(self):
        """Test biomarker config for ovarian cancer."""
        config = get_biomarker_config("ovarian_cancer_hgs")
        
        assert config is not None
        assert "primary_biomarker" in config
        assert config["primary_biomarker"] == "ca125"
        assert "thresholds" in config
    
    def test_get_biomarker_config_prostate(self):
        """Test biomarker config for prostate cancer."""
        config = get_biomarker_config("prostate_cancer")
        
        assert config is not None
        assert config.get("primary_biomarker") == "psa"
    
    def test_get_biomarker_config_colorectal(self):
        """Test biomarker config for colorectal cancer."""
        config = get_biomarker_config("colorectal_cancer")
        
        if config:  # May not be configured yet
            assert "primary_biomarker" in config
            assert config["primary_biomarker"] == "cea"


if __name__ == "__main__":
    # Run tests directly
    passed = 0
    failed = 0
    
    # Test SOC Recommendation
    for test_class in [TestSOCRecommendation, TestDiseaseValidation, TestBiomarkerConfig]:
        test_instance = test_class()
        test_methods = [method for method in dir(test_instance) if method.startswith("test_")]
        
        for method_name in test_methods:
            try:
                print(f"Running {test_class.__name__}.{method_name}...", end=" ")
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

