"""
Therapeutic Prompt Builder Service

Builds rich, context-aware prompts for Evo2 therapeutic generation.

Key Principles:
1. DNA language, not English (Evo2 is trained on sequences)
2. Rich biological context (gene sequences, binding sites, pathways)
3. Clear constraints (GC content, homopolymers, viral content)
4. Mission-specific objectives (inhibit vs activate)

This service prevents "junk DNA" generation by providing high-quality prompts.
"""

import logging
from typing import Dict, Optional, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class TherapeuticDesignContext:
    """Context for therapeutic design."""
    target_gene: str
    disease: str
    mechanism: str  # "inhibit" or "activate"
    gene_sequence: str  # Full or partial gene sequence
    binding_sites: Optional[Dict[str, any]] = None
    pathways: Optional[List[str]] = None
    constraints: Optional[Dict[str, any]] = None


class TherapeuticPromptBuilder:
    """
    Builds context-rich prompts for Evo2 therapeutic generation.
    
    Prevents "junk DNA" by providing:
    - Rich biological context (>=1000bp)
    - DNA language (not English)
    - Clear design constraints
    - Mission-specific objectives
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Default constraints
        self.default_constraints = {
            "gc_content_min": 0.40,
            "gc_content_max": 0.60,
            "max_homopolymer": 4,
            "avoid_viral": True,
            "min_context_length": 1000
        }
    
    def build_guide_rna_prompt(
        self,
        target_gene: str,
        target_sequence: str,
        pam_site: str = "NGG",
        mechanism: str = "inhibit"
    ) -> str:
        """
        Build prompt for CRISPR guide RNA generation.
        
        Args:
            target_gene: Target gene name (e.g., "BRAF")
            target_sequence: Target gene sequence context (>=1000bp)
            pam_site: PAM sequence (default: NGG for SpCas9)
            mechanism: "inhibit" (knockout) or "activate" (CRISPRa)
        
        Returns:
            DNA-context prompt for Evo2
        """
        
        # Validate context length
        if len(target_sequence) < self.default_constraints["min_context_length"]:
            self.logger.warning(
                f"Target sequence too short ({len(target_sequence)}bp). "
                f"Minimum {self.default_constraints['min_context_length']}bp recommended."
            )
        
        # Extract upstream context (for Evo2 to "see" gene structure)
        upstream_context = target_sequence[:500] if len(target_sequence) >= 500 else target_sequence
        
        # Build DNA-language prompt
        prompt = f"""# CRISPR Guide RNA Design
# Target Gene: {target_gene}
# Mechanism: {mechanism.upper()}
# PAM Site: {pam_site}

# Upstream Gene Context (DNA sequence for Evo2 understanding):
{upstream_context}

# Design Objective: Generate guide RNA sequence
# Constraints:
# - Length: 20bp spacer
# - GC content: 40-60%
# - No homopolymers >4bp
# - Must target coding region
# - PAM site: {pam_site}

# Guide RNA Candidate:
"""
        
        return prompt
    
    def build_protein_therapeutic_prompt(
        self,
        target_gene: str,
        disease: str,
        mechanism: str,
        gene_context: str,
        binding_sites: Optional[Dict] = None
    ) -> str:
        """
        Build prompt for therapeutic protein generation.
        
        Args:
            target_gene: Target gene name
            disease: Disease context
            mechanism: "inhibit" or "activate"
            gene_context: Target gene sequence (>=1000bp)
            binding_sites: Known binding sites (optional)
        
        Returns:
            DNA-context prompt for Evo2
        """
        
        # Validate context
        if len(gene_context) < self.default_constraints["min_context_length"]:
            self.logger.warning(f"Gene context too short: {len(gene_context)}bp")
        
        # Extract key regions
        context_window = gene_context[:1000]
        
        # Build DNA-language prompt
        prompt = f"""# Therapeutic Protein Design
# Target: {target_gene}
# Disease: {disease}
# Mechanism: {mechanism.upper()}

# Target Gene Context (DNA sequence):
{context_window}
"""
        
        # Add binding site information if available
        if binding_sites:
            prompt += f"\n# Known Binding Sites:\n"
            for site_name, site_info in binding_sites.items():
                prompt += f"# - {site_name}: {site_info}\n"
        
        prompt += f"""
# Design Objective: Generate therapeutic protein sequence
# Constraints:
# - Protein length: 50-200 amino acids
# - Target binding affinity: High
# - GC content (DNA level): 40-60%
# - No homopolymers >4bp
# - Mechanism: {mechanism}

# Therapeutic Protein Sequence (DNA):
"""
        
        return prompt
    
    def build_peptide_therapeutic_prompt(
        self,
        target_protein: str,
        disease: str,
        binding_pocket: Optional[str] = None
    ) -> str:
        """
        Build prompt for peptide therapeutic generation.
        
        Args:
            target_protein: Target protein name
            disease: Disease context
            binding_pocket: Known binding pocket sequence (optional)
        
        Returns:
            DNA-context prompt for Evo2
        """
        
        prompt = f"""# Peptide Therapeutic Design
# Target Protein: {target_protein}
# Disease: {disease}

"""
        
        if binding_pocket:
            prompt += f"""# Target Binding Pocket Context:
{binding_pocket}

"""
        
        prompt += f"""# Design Objective: Generate peptide therapeutic
# Constraints:
# - Peptide length: 10-30 amino acids
# - High binding affinity to target
# - GC content (DNA level): 40-60%
# - Bioavailable and stable

# Therapeutic Peptide Sequence (DNA):
"""
        
        return prompt
    
    def validate_prompt_quality(self, prompt: str) -> Dict[str, any]:
        """
        Validate prompt quality before sending to Evo2.
        
        Checks:
        - Sufficient length (>=500 chars)
        - Contains DNA sequence context
        - Has clear design objective
        
        Returns:
            Validation result with warnings
        """
        
        result = {
            "is_valid": True,
            "warnings": [],
            "length": len(prompt),
            "has_dna_context": False,
            "has_objective": False
        }
        
        # Check length
        if len(prompt) < 500:
            result["warnings"].append(
                f"Prompt too short ({len(prompt)} chars). Minimum 500 recommended."
            )
        
        # Check for DNA context (look for ATCG patterns)
        dna_chars = set("ATCG")
        dna_content = sum(1 for c in prompt.upper() if c in dna_chars)
        if dna_content / len(prompt) > 0.3:  # >30% DNA bases
            result["has_dna_context"] = True
        else:
            result["warnings"].append("Prompt lacks DNA sequence context")
        
        # Check for design objective
        if "Design Objective" in prompt or "Generate" in prompt:
            result["has_objective"] = True
        else:
            result["warnings"].append("Prompt lacks clear design objective")
        
        # Overall validation
        if len(result["warnings"]) > 0:
            result["is_valid"] = False
            self.logger.warning(f"Prompt validation failed: {result['warnings']}")
        
        return result


# Singleton instance
_prompt_builder_instance = None


def get_prompt_builder() -> TherapeuticPromptBuilder:
    """Get singleton prompt builder instance."""
    global _prompt_builder_instance
    if _prompt_builder_instance is None:
        _prompt_builder_instance = TherapeuticPromptBuilder()
    return _prompt_builder_instance





