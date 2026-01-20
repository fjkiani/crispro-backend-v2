"""
Tests for SafetyValidator

Validates safety checking for therapeutic sequences:
- Viral content blocking
- GC extreme filtering
- Homopolymer detection
- Toxic sequence blocking
"""

import pytest
from api.services.safety_validator import (
    SafetyValidator,
    SafetyLevel,
    get_safety_validator,
    VIRAL_BLOCKLIST,
    TOXIC_SEQUENCES
)


# Sample sequences for testing
SAFE_SEQUENCE = "ATCGATCGATCGATCGATCGATCGATCGATCGATCGATCG" * 5  # 200bp, 50% GC, no long runs
HIV_SEQUENCE = "ATGGGTGCGAGAGCGTCATCGATCGATCG" * 3  # Contains HIV pattern
SARS_SEQUENCE = "ATGTTTGTTTTTCTTGTATCGATCGATCG" * 3  # Contains SARS-CoV-2 pattern
LOW_GC_SEQUENCE = "ATATATATATATATATATATATATATATA" * 5  # 0% GC
HIGH_GC_SEQUENCE = "GCGCGCGCGCGCGCGCGCGCGCGCGCGCGC" * 5  # 100% GC
HOMOPOLYMER_SEQUENCE = "ATCGATCGAAAAAAAAATCGATCGATCG" * 3  # 9xA run


@pytest.fixture
def validator():
    return get_safety_validator()


@pytest.fixture
def lenient_validator():
    """Validator with more lenient settings for testing warnings."""
    return SafetyValidator(
        gc_min=0.10,
        gc_max=0.90,
        max_homopolymer=10
    )


class TestSafetyValidator:
    def test_validator_initialization(self):
        """Test validator initializes with correct defaults."""
        validator = get_safety_validator()
        assert validator.gc_min == 0.20
        assert validator.gc_max == 0.80
        assert validator.max_homopolymer == 6
        assert validator.enable_viral_check == True
        assert validator.enable_toxic_check == True
    
    def test_safe_sequence(self, validator: SafetyValidator):
        """Test that a safe sequence passes all checks."""
        result = validator.validate_sequence(SAFE_SEQUENCE)
        
        assert result.is_safe == True
        assert result.level == SafetyLevel.SAFE
        assert result.reason == "All safety checks passed"
        assert len(result.checks) == 4  # viral, GC, homopolymer, toxic
        assert all(check.passed for check in result.checks)
        assert len(result.recommendations) == 0
    
    def test_hiv_detection(self, validator: SafetyValidator):
        """Test HIV sequence pattern is detected and blocked."""
        result = validator.validate_sequence(HIV_SEQUENCE)
        
        assert result.is_safe == False
        assert result.level == SafetyLevel.BLOCKED
        assert "viral_content" in result.reason.lower()
        
        viral_check = next(c for c in result.checks if c.check_name == "viral_content")
        assert viral_check.passed == False
        assert viral_check.level == SafetyLevel.BLOCKED
        assert "hiv" in viral_check.details["virus_type"].lower()
    
    def test_sars_detection(self, validator: SafetyValidator):
        """Test SARS-CoV-2 sequence pattern is detected and blocked."""
        result = validator.validate_sequence(SARS_SEQUENCE)
        
        assert result.is_safe == False
        assert result.level == SafetyLevel.BLOCKED
        assert "viral_content" in result.reason.lower()
        
        viral_check = next(c for c in result.checks if c.check_name == "viral_content")
        assert viral_check.passed == False
        assert "sars" in viral_check.details["virus_type"].lower()
    
    def test_low_gc_blocked(self, validator: SafetyValidator):
        """Test low GC content sequences are blocked."""
        result = validator.validate_sequence(LOW_GC_SEQUENCE)
        
        assert result.is_safe == False
        assert result.level == SafetyLevel.BLOCKED
        assert "gc_content" in result.reason.lower()
        
        gc_check = next(c for c in result.checks if c.check_name == "gc_content")
        assert gc_check.passed == False
        assert gc_check.level == SafetyLevel.BLOCKED
        assert gc_check.details["gc_content"] == 0.0
    
    def test_high_gc_blocked(self, validator: SafetyValidator):
        """Test high GC content sequences are blocked."""
        result = validator.validate_sequence(HIGH_GC_SEQUENCE)
        
        assert result.is_safe == False
        assert result.level == SafetyLevel.BLOCKED
        assert "gc_content" in result.reason.lower()
        
        gc_check = next(c for c in result.checks if c.check_name == "gc_content")
        assert gc_check.passed == False
        assert gc_check.level == SafetyLevel.BLOCKED
        assert gc_check.details["gc_content"] == 1.0
    
    def test_homopolymer_blocked(self, validator: SafetyValidator):
        """Test long homopolymer runs are blocked."""
        result = validator.validate_sequence(HOMOPOLYMER_SEQUENCE)
        
        assert result.is_safe == False
        assert result.level == SafetyLevel.BLOCKED
        assert "homopolymer" in result.reason.lower()
        
        homopolymer_check = next(c for c in result.checks if c.check_name == "homopolymer")
        assert homopolymer_check.passed == False
        assert homopolymer_check.level == SafetyLevel.BLOCKED
        assert homopolymer_check.details["max_run"] == 9
        assert homopolymer_check.details["base"] == "A"
    
    def test_toxic_sequence_blocked(self, validator: SafetyValidator):
        """Test known toxic sequences are blocked."""
        toxic_seq = TOXIC_SEQUENCES[0]
        sequence = f"ATCGATCG{toxic_seq}ATCGATCG"
        result = validator.validate_sequence(sequence)
        
        assert result.is_safe == False
        assert result.level == SafetyLevel.BLOCKED
        assert "toxic_sequences" in result.reason.lower()
        
        toxic_check = next(c for c in result.checks if c.check_name == "toxic_sequences")
        assert toxic_check.passed == False
        assert toxic_check.level == SafetyLevel.BLOCKED
    
    def test_gc_warning_zone(self, lenient_validator: SafetyValidator):
        """Test GC content in warning zone (but not blocked)."""
        # 16.67% GC - in warning zone for lenient validator (0.15 < 0.1667 < 0.2)
        warning_seq = "ATATATATATATATATATAT" + "CGCG"  # 4 GC out of 24 = 16.67%
        warning_seq = warning_seq * 10  # Repeat to make it longer
        result = lenient_validator.validate_sequence(warning_seq)
        
        assert result.is_safe == True  # Not blocked
        assert result.level == SafetyLevel.WARNING
        
        gc_check = next(c for c in result.checks if c.check_name == "gc_content")
        assert gc_check.passed == True
        assert gc_check.level == SafetyLevel.WARNING
    
    def test_homopolymer_warning_zone(self, lenient_validator: SafetyValidator):
        """Test homopolymer in warning zone (but not blocked)."""
        # 5xA run - in warning zone for lenient validator
        warning_seq = "ATCGATCGAAAAATCGATCG" * 3
        result = lenient_validator.validate_sequence(warning_seq)
        
        assert result.is_safe == True  # Not blocked
        assert result.level == SafetyLevel.WARNING
        
        homopolymer_check = next(c for c in result.checks if c.check_name == "homopolymer")
        assert homopolymer_check.passed == True
        assert homopolymer_check.level == SafetyLevel.WARNING
    
    def test_empty_sequence(self, validator: SafetyValidator):
        """Test empty sequence is blocked."""
        result = validator.validate_sequence("")
        
        assert result.is_safe == False
        assert result.level == SafetyLevel.BLOCKED
        assert "Empty sequence" in result.reason
    
    def test_viral_check_disabled(self):
        """Test viral check can be disabled."""
        validator = get_safety_validator(enable_viral_check=False)
        result = validator.validate_sequence(HIV_SEQUENCE)
        
        # Should not include viral check
        check_names = [c.check_name for c in result.checks]
        assert "viral_content" not in check_names
    
    def test_toxic_check_disabled(self):
        """Test toxic check can be disabled."""
        validator = get_safety_validator(enable_toxic_check=False)
        toxic_seq = TOXIC_SEQUENCES[0]
        sequence = f"ATCGATCG{toxic_seq}ATCGATCG"
        result = validator.validate_sequence(sequence)
        
        # Should not include toxic check
        check_names = [c.check_name for c in result.checks]
        assert "toxic_sequences" not in check_names
    
    def test_recommendations_generated(self, validator: SafetyValidator):
        """Test recommendations are generated for failed checks."""
        result = validator.validate_sequence(LOW_GC_SEQUENCE)
        
        assert len(result.recommendations) > 0
        assert any("GC content" in rec for rec in result.recommendations)
    
    def test_multiple_failures(self, validator: SafetyValidator):
        """Test handling of multiple simultaneous failures."""
        # Combine HIV + low GC + homopolymer
        bad_seq = "ATGGGTGCGAGAGCGTCAAAAAAAAA" * 3
        result = validator.validate_sequence(bad_seq)
        
        assert result.is_safe == False
        assert result.level == SafetyLevel.BLOCKED
        
        failed_checks = [c for c in result.checks if not c.passed]
        assert len(failed_checks) >= 2  # At least viral + one other


class TestSafetyValidatorIntegration:
    def test_guide_rna_validation(self, validator: SafetyValidator):
        """Test validation of a typical guide RNA sequence."""
        # Realistic 20bp guide RNA (50% GC, no long runs)
        guide_rna = "GATCGATCGATCGATCGATC"
        result = validator.validate_sequence(guide_rna)
        
        assert result.is_safe == True
        assert result.level == SafetyLevel.SAFE
    
    def test_protein_coding_validation(self, validator: SafetyValidator):
        """Test validation of a protein coding sequence."""
        # Realistic protein coding sequence (moderate GC, no issues)
        coding_seq = "ATGAGTGCTATCGGTACTGCTAGCTAGCGTACGTACGTA" * 5
        result = validator.validate_sequence(coding_seq)
        
        assert result.is_safe == True
    
    def test_batch_validation(self, validator: SafetyValidator):
        """Test validating multiple sequences."""
        sequences = [
            SAFE_SEQUENCE,
            HIV_SEQUENCE,
            LOW_GC_SEQUENCE,
            HOMOPOLYMER_SEQUENCE
        ]
        
        results = [validator.validate_sequence(seq) for seq in sequences]
        
        # First should pass, others should fail
        assert results[0].is_safe == True
        assert all(not r.is_safe for r in results[1:])
    
    def test_context_passing(self, validator: SafetyValidator):
        """Test passing context to validator."""
        context = {
            "target_gene": "BRAF",
            "disease": "melanoma",
            "therapeutic_type": "guide_rna"
        }
        result = validator.validate_sequence(SAFE_SEQUENCE, context=context)
        
        # Context doesn't affect validation logic, but should not cause errors
        assert result.is_safe == True

