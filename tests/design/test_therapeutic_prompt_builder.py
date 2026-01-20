"""
Tests for TherapeuticPromptBuilder service.

Validates that prompts:
1. Contain sufficient DNA context (>=1000bp recommended)
2. Use DNA language, not English
3. Include clear design objectives
4. Specify biological constraints
5. Are mission-specific (inhibit vs activate)
"""

import pytest
from api.services.therapeutic_prompt_builder import (
    TherapeuticPromptBuilder,
    TherapeuticDesignContext,
    get_prompt_builder
)


# Sample gene sequences for testing
BRAF_SAMPLE_SEQUENCE = """
ATGAAGACTGATACTGAGAGTCAATCTTGGACAACTACATAATTTTTGTTATTTCATTTGAAGACTCTTTCAGTAATTC
CATTTGTAGTATTAATTGGAACAATGCACCTTTTTGGGACACTGGTTTAAACAATGACCCAGACAATTGTAAAGATGAA
CATCTCACAGTGGAAGGCTCTGCAGATGCTGGGGCCAATAGGTACAGATAAGTCTGCTGAACATTGGATGTGAGCATAA
TGGACAGTGTGTCAGTGTAATTAAACAGCCGAGATTCATTGTGGACCACACACTCTTCACGAGGTCATTTTTTAAAGAG
TACAAAGAAAGAATTTCATATTGAATTCAACATCTAACATTAAAATGGAAAAATGGGCATGGGATGAACTTTGTAATGG
AACTCACAACTAATGAAAAAAAAGCTTTGAAACTTTACAAAACCTACGTGAAGGTTGGAAAGGATGATATCTCCATTTT
CCCTGTATTAAAATTAGCTTTTATGACTTACAAGATCAACAATTTGTTTAATTTTTTTAAGAACACAAGTGACAAACCT
CAAAGCTATTTGATGATAGACATTCTTGATGAAAATCCAGAAGTTCCTGGATCAGATAAAAAATACATTATTAATGATT
TTCATTTTCTTGACTGGTTAGTGAGAAATCAATGATGATGCTGATGGACTTTCTAGAGATTGATAGAACAGAATTAAAT
TATAATAGAAAATGGATTCATTATATTCTGATGGGATATGTGACAATGACATTTAAAGATTTATGTTGACAGGATTTAA
GATTAAAGACAGAAACAAGAAATTAGAAACTGATGGGAAGAATTATATTGAATGATTGATAAATCAACTTCTGATAGAG
AGACAATATCAGACAACTGTTCAAACTGATGGGACCCACTCCATCGAGATTTCTCTGTAGCTAGACCAAAATCACCTAT
TTTTACTGTTTCTTTTTTAAAACTTAAATAGGAAGCCATTTAGGAAATATGTTTAAACAAATGGTAATTGGAATTATTT
TTCTTAATTGGGTCAGTTGAGATAAAAACAGCCTCAATTCTTACCATCCAC
""".replace("\n", "").strip()

# Shorter sequence for testing warnings
SHORT_SEQUENCE = "ATGAAGACTGATACTGAGAGTCAATCTTGGACAACTACATAATTTTTGTTATTTCATTTGAAGACTCTTTCAGTAATTC"


class TestTherapeuticPromptBuilder:
    """Test suite for TherapeuticPromptBuilder."""
    
    def test_initialization(self):
        """Test prompt builder initialization."""
        builder = TherapeuticPromptBuilder()
        
        assert builder is not None
        assert "gc_content_min" in builder.default_constraints
        assert builder.default_constraints["min_context_length"] == 1000
    
    def test_singleton_pattern(self):
        """Test that get_prompt_builder returns same instance."""
        builder1 = get_prompt_builder()
        builder2 = get_prompt_builder()
        
        assert builder1 is builder2
    
    def test_guide_rna_prompt_structure(self):
        """Test CRISPR guide RNA prompt structure."""
        builder = get_prompt_builder()
        
        prompt = builder.build_guide_rna_prompt(
            target_gene="BRAF",
            target_sequence=BRAF_SAMPLE_SEQUENCE,
            pam_site="NGG",
            mechanism="inhibit"
        )
        
        # Assertions
        assert len(prompt) > 500, "Prompt too short"
        assert "CRISPR Guide RNA Design" in prompt
        assert "BRAF" in prompt
        assert "INHIBIT" in prompt
        assert "NGG" in prompt
        assert "20bp spacer" in prompt
        assert "GC content: 40-60%" in prompt
        
        # Check for DNA context
        dna_bases = set("ATCG")
        dna_count = sum(1 for c in prompt.upper() if c in dna_bases)
        assert dna_count > 100, "Insufficient DNA context"
    
    def test_guide_rna_prompt_short_sequence_warning(self):
        """Test warning for short target sequences."""
        builder = get_prompt_builder()
        
        # Use short sequence (should trigger warning)
        prompt = builder.build_guide_rna_prompt(
            target_gene="BRAF",
            target_sequence=SHORT_SEQUENCE,
            pam_site="NGG",
            mechanism="inhibit"
        )
        
        # Should still generate prompt, but with warning logged
        assert len(prompt) > 0
        assert "BRAF" in prompt
    
    def test_protein_therapeutic_prompt_structure(self):
        """Test therapeutic protein prompt structure."""
        builder = get_prompt_builder()
        
        binding_sites = {
            "ATP_binding": "Position 100-120",
            "Substrate_binding": "Position 200-250"
        }
        
        prompt = builder.build_protein_therapeutic_prompt(
            target_gene="PIK3CA",
            disease="ovarian_cancer",
            mechanism="inhibit",
            gene_context=BRAF_SAMPLE_SEQUENCE,  # Using BRAF as example context
            binding_sites=binding_sites
        )
        
        # Assertions
        assert len(prompt) > 500
        assert "Therapeutic Protein Design" in prompt
        assert "PIK3CA" in prompt
        assert "ovarian_cancer" in prompt
        assert "INHIBIT" in prompt
        assert "ATP_binding" in prompt
        assert "Substrate_binding" in prompt
        assert "50-200 amino acids" in prompt
        
        # Check for DNA context
        assert "ATGAAGACTGATACTGAGAGTCAATC" in prompt.upper()
    
    def test_protein_therapeutic_prompt_no_binding_sites(self):
        """Test protein prompt without binding site information."""
        builder = get_prompt_builder()
        
        prompt = builder.build_protein_therapeutic_prompt(
            target_gene="PIK3CA",
            disease="ovarian_cancer",
            mechanism="activate",
            gene_context=BRAF_SAMPLE_SEQUENCE,
            binding_sites=None
        )
        
        # Should still generate valid prompt
        assert len(prompt) > 500
        assert "PIK3CA" in prompt
        assert "ACTIVATE" in prompt
        # Should not have binding sites section
        assert "Known Binding Sites" not in prompt
    
    def test_peptide_therapeutic_prompt_structure(self):
        """Test peptide therapeutic prompt structure."""
        builder = get_prompt_builder()
        
        prompt = builder.build_peptide_therapeutic_prompt(
            target_protein="EGFR",
            disease="lung_cancer",
            binding_pocket="ATCGATCGATCGATCG"
        )
        
        # Assertions
        assert len(prompt) > 300
        assert "Peptide Therapeutic Design" in prompt
        assert "EGFR" in prompt
        assert "lung_cancer" in prompt
        assert "ATCGATCGATCGATCG" in prompt
        assert "10-30 amino acids" in prompt
    
    def test_peptide_therapeutic_prompt_no_pocket(self):
        """Test peptide prompt without binding pocket."""
        builder = get_prompt_builder()
        
        prompt = builder.build_peptide_therapeutic_prompt(
            target_protein="EGFR",
            disease="lung_cancer",
            binding_pocket=None
        )
        
        # Should still generate valid prompt
        assert len(prompt) > 200
        assert "EGFR" in prompt
        # Should not have pocket section
        assert "Target Binding Pocket Context" not in prompt
    
    def test_prompt_quality_validation_good_prompt(self):
        """Test validation of high-quality prompt."""
        builder = get_prompt_builder()
        
        # Generate a good prompt
        prompt = builder.build_guide_rna_prompt(
            target_gene="BRAF",
            target_sequence=BRAF_SAMPLE_SEQUENCE,
            pam_site="NGG",
            mechanism="inhibit"
        )
        
        # Validate
        result = builder.validate_prompt_quality(prompt)
        
        assert result["is_valid"] == True
        assert result["has_dna_context"] == True
        assert result["has_objective"] == True
        assert len(result["warnings"]) == 0
    
    def test_prompt_quality_validation_short_prompt(self):
        """Test validation failure for short prompt."""
        builder = get_prompt_builder()
        
        short_prompt = "Generate guide RNA for BRAF"
        
        result = builder.validate_prompt_quality(short_prompt)
        
        assert result["is_valid"] == False
        assert len(result["warnings"]) > 0
        assert any("too short" in w.lower() for w in result["warnings"])
    
    def test_prompt_quality_validation_no_dna_context(self):
        """Test validation failure for prompt without DNA context."""
        builder = get_prompt_builder()
        
        # English-only prompt (no DNA sequence)
        english_prompt = """
        Design Objective: Create a therapeutic protein that inhibits BRAF.
        Target: BRAF V600E mutation.
        Constraints: High affinity, low toxicity.
        """ * 5  # Make it long enough
        
        result = builder.validate_prompt_quality(english_prompt)
        
        assert result["is_valid"] == False
        assert result["has_dna_context"] == False
        assert any("lacks DNA" in w for w in result["warnings"])
    
    def test_guide_rna_mechanism_variants(self):
        """Test guide RNA prompts for both inhibit and activate."""
        builder = get_prompt_builder()
        
        # Test inhibit (knockout)
        inhibit_prompt = builder.build_guide_rna_prompt(
            target_gene="BRAF",
            target_sequence=BRAF_SAMPLE_SEQUENCE,
            mechanism="inhibit"
        )
        assert "INHIBIT" in inhibit_prompt
        
        # Test activate (CRISPRa)
        activate_prompt = builder.build_guide_rna_prompt(
            target_gene="BRAF",
            target_sequence=BRAF_SAMPLE_SEQUENCE,
            mechanism="activate"
        )
        assert "ACTIVATE" in activate_prompt
    
    def test_prompt_dna_content_ratio(self):
        """Test that prompts have sufficient DNA content."""
        builder = get_prompt_builder()
        
        prompt = builder.build_protein_therapeutic_prompt(
            target_gene="PIK3CA",
            disease="ovarian_cancer",
            mechanism="inhibit",
            gene_context=BRAF_SAMPLE_SEQUENCE
        )
        
        # Calculate DNA content ratio
        dna_bases = set("ATCG")
        dna_count = sum(1 for c in prompt.upper() if c in dna_bases)
        dna_ratio = dna_count / len(prompt)
        
        # Should have at least 30% DNA bases
        assert dna_ratio >= 0.30, f"DNA content too low: {dna_ratio:.2%}"


class TestTherapeuticDesignContext:
    """Test TherapeuticDesignContext dataclass."""
    
    def test_context_creation(self):
        """Test creating design context."""
        context = TherapeuticDesignContext(
            target_gene="BRAF",
            disease="ovarian_cancer",
            mechanism="inhibit",
            gene_sequence=BRAF_SAMPLE_SEQUENCE,
            binding_sites={"ATP": "Position 100-120"},
            pathways=["MAPK", "PI3K"],
            constraints={"gc_min": 0.4, "gc_max": 0.6}
        )
        
        assert context.target_gene == "BRAF"
        assert context.disease == "ovarian_cancer"
        assert context.mechanism == "inhibit"
        assert len(context.gene_sequence) > 0
        assert "ATP" in context.binding_sites
        assert "MAPK" in context.pathways
        assert context.constraints["gc_min"] == 0.4


# Integration tests
class TestPromptBuilderIntegration:
    """Integration tests for prompt builder with Evo2 service."""
    
    def test_full_guide_rna_workflow(self):
        """Test complete guide RNA generation workflow."""
        builder = get_prompt_builder()
        
        # 1. Build prompt
        prompt = builder.build_guide_rna_prompt(
            target_gene="BRAF",
            target_sequence=BRAF_SAMPLE_SEQUENCE,
            pam_site="NGG",
            mechanism="inhibit"
        )
        
        # 2. Validate prompt
        validation = builder.validate_prompt_quality(prompt)
        
        # 3. Assert workflow success
        assert validation["is_valid"] == True
        assert len(prompt) > 500  # Rich context (adjusted for guide RNA)
        
        # Ready for Evo2 generation
        print(f"\n✅ Generated {len(prompt)}-char prompt for BRAF guide RNA")
        print(f"   DNA content: {validation['has_dna_context']}")
        print(f"   Design objective: {validation['has_objective']}")
    
    def test_full_protein_therapeutic_workflow(self):
        """Test complete protein therapeutic generation workflow."""
        builder = get_prompt_builder()
        
        # 1. Build prompt with full context
        prompt = builder.build_protein_therapeutic_prompt(
            target_gene="PIK3CA",
            disease="ovarian_cancer",
            mechanism="inhibit",
            gene_context=BRAF_SAMPLE_SEQUENCE,
            binding_sites={
                "ATP_binding": "Position 100-120",
                "Catalytic_site": "Position 200-250"
            }
        )
        
        # 2. Validate
        validation = builder.validate_prompt_quality(prompt)
        
        # 3. Assert success
        assert validation["is_valid"] == True
        assert "PIK3CA" in prompt
        assert "ATP_binding" in prompt
        
        print(f"\n✅ Generated {len(prompt)}-char prompt for PIK3CA inhibitor")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

