"""
Tests for Therapy Fit Configuration

Tests disease validation, normalization, and default model selection.
"""

import pytest
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.services.therapy_fit.config import (
    validate_disease_type,
    get_default_model,
    DISEASE_MAPPINGS,
    DEFAULT_MODELS
)


class TestDiseaseValidation:
    """Test disease validation and normalization."""
    
    def test_mm_abbreviation(self):
        """Test MM abbreviation normalizes to multiple_myeloma."""
        is_valid, normalized = validate_disease_type("MM")
        assert is_valid is True
        assert normalized == "multiple_myeloma"
    
    def test_case_insensitive(self):
        """Test case-insensitive disease matching."""
        is_valid, normalized = validate_disease_type("Ovarian Cancer")
        assert is_valid is True
        assert normalized == "ovarian_cancer"
    
    def test_hgsoc_abbreviation(self):
        """Test hgsoc abbreviation normalizes to ovarian_cancer_hgs."""
        is_valid, normalized = validate_disease_type("hgsoc")
        assert is_valid is True
        assert normalized == "ovarian_cancer_hgs"
    
    def test_crc_abbreviation(self):
        """Test CRC abbreviation normalizes to colorectal_cancer."""
        is_valid, normalized = validate_disease_type("CRC")
        assert is_valid is True
        assert normalized == "colorectal_cancer"
    
    def test_invalid_disease(self):
        """Test invalid disease returns False with normalized form."""
        is_valid, normalized = validate_disease_type("invalid_disease")
        assert is_valid is False
        assert normalized == "invalid_disease"


class TestDefaultModelSelection:
    """Test default model selection."""
    
    def test_default_model_for_ovarian(self):
        """Test default model for ovarian cancer."""
        model = get_default_model("ovarian")
        assert model == "evo2_1b"
    
    def test_default_model_for_mm(self):
        """Test default model for multiple myeloma."""
        model = get_default_model("MM")
        assert model == "evo2_1b"
    
    def test_default_model_fallback(self):
        """Test default model fallback for unknown disease."""
        model = get_default_model("unknown_disease")
        assert model == "evo2_1b"  # Default fallback


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
