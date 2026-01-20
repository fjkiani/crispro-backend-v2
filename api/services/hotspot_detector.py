"""
Hotspot Mutation Detector Service (P0 Fix #3)
==============================================
Detects COSMIC hotspot mutations (KRAS/BRAF/NRAS) for pathway-specific trial recommendations.

Policy Source: MANAGER_ANSWERS_TO_ZO_SAE_QUESTIONS.md (C2)
Owner: Zo (Lead Commander)
Date: January 13, 2025

Manager's Policy (C2):
- Hotspot detection: use COSMIC/hardcoded list (e.g., KRAS G12C/G12D/G12V, NRAS Q61, BRAF V600E)
- SAE `hotspot_mutation` may assist but cannot override COSMIC
- Hotspot present but MAPK burden low (<0.40) ⇒ show trials but no monotherapy boost
- Boost only if burden ≥0.40; full boost at ≥0.70
"""

import json
import os
import logging
import re
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Load COSMIC hotspots at module initialization
COSMIC_HOTSPOTS = {}
try:
    hotspots_path = os.path.join(
        os.path.dirname(__file__), 
        "../resources/cosmic_hotspots.json"
    )
    if os.path.exists(hotspots_path):
        with open(hotspots_path, "r") as f:
            COSMIC_HOTSPOTS = json.load(f)
        logger.info(f"✅ Loaded COSMIC hotspots for {len(COSMIC_HOTSPOTS)} genes")
    else:
        logger.warning(f"⚠️ COSMIC hotspots file not found: {hotspots_path}")
except Exception as e:
    logger.error(f"❌ Failed to load COSMIC hotspots: {e}")
    COSMIC_HOTSPOTS = {}


@dataclass
class HotspotResult:
    """
    Hotspot detection result.
    
    Attributes:
        is_hotspot: True if mutation is a COSMIC hotspot
        gene: Gene symbol (e.g., "KRAS")
        mutation: AA change (e.g., "G12D")
        cosmic_id: COSMIC identifier
        evidence: "highly_recurrent" or "recurrent"
        frequency: Frequency in cancer (0-1)
        pathway: Affected pathway (e.g., "MAPK")
        cancers: Cancer types where hotspot observed
        source: Data source ("COSMIC v98")
    """
    is_hotspot: bool
    gene: Optional[str] = None
    mutation: Optional[str] = None
    cosmic_id: Optional[str] = None
    evidence: Optional[str] = None
    frequency: Optional[float] = None
    pathway: Optional[str] = None
    cancers: Optional[List[str]] = None
    source: Optional[str] = None


class HotspotDetector:
    """
    Detects COSMIC hotspot mutations for pathway-specific intelligence.
    
    Manager Policy: C2 (MANAGER_ANSWERS_TO_ZO_SAE_QUESTIONS.md)
    
    Process:
    1. Parse HGVS protein change (e.g., "p.G12D" → "G12D")
    2. Check against COSMIC hotspot database
    3. Return hotspot details if found
    """
    
    def __init__(self):
        """Initialize hotspot detector with COSMIC database."""
        self.hotspots = COSMIC_HOTSPOTS
        self.logger = logger
    
    def detect_hotspot(self, gene: str, hgvs_p: Optional[str]) -> HotspotResult:
        """
        Detect if mutation is a COSMIC hotspot.
        
        Args:
            gene: Gene symbol (e.g., "KRAS", "BRAF", "NRAS")
            hgvs_p: HGVS protein change (e.g., "p.G12D", "G12D", "V600E")
        
        Returns:
            HotspotResult with is_hotspot=True if mutation is in COSMIC database
        
        Manager Policy:
        - Use COSMIC/hardcoded list for authoritative hotspot detection
        - SAE `hotspot_mutation` may assist but cannot override COSMIC
        
        Examples:
            >>> detector = HotspotDetector()
            >>> result = detector.detect_hotspot("KRAS", "p.G12D")
            >>> assert result.is_hotspot == True
            >>> assert result.pathway == "MAPK"
        """
        if not gene or not hgvs_p:
            return HotspotResult(is_hotspot=False)
        
        # Normalize gene name
        gene = gene.upper().strip()
        
        # Parse HGVS protein change to extract AA change
        aa_change = self._parse_hgvs(hgvs_p)
        if not aa_change:
            return HotspotResult(is_hotspot=False)
        
        # Check if gene is in COSMIC database
        if gene not in self.hotspots:
            self.logger.debug(f"Gene {gene} not in COSMIC hotspots database")
            return HotspotResult(is_hotspot=False)
        
        # Check if mutation is a hotspot
        gene_hotspots = self.hotspots[gene]
        if aa_change in gene_hotspots:
            hotspot_data = gene_hotspots[aa_change]
            
            self.logger.info(f"✅ Hotspot detected: {gene} {aa_change} (COSMIC: {hotspot_data.get('evidence')})")
            
            return HotspotResult(
                is_hotspot=True,
                gene=gene,
                mutation=aa_change,
                cosmic_id=hotspot_data.get("cosmic_id"),
                evidence=hotspot_data.get("evidence"),
                frequency=hotspot_data.get("frequency_in_cancer"),
                pathway=hotspot_data.get("pathway"),
                cancers=hotspot_data.get("cancers"),
                source=hotspot_data.get("source")
            )
        
        self.logger.debug(f"Mutation {gene} {aa_change} not in COSMIC hotspots")
        return HotspotResult(is_hotspot=False)
    
    def _parse_hgvs(self, hgvs_p: str) -> Optional[str]:
        """
        Parse HGVS protein change to extract AA change.
        
        Handles formats:
        - "p.G12D" → "G12D"
        - "G12D" → "G12D"
        - "p.Val600Glu" → "V600E" (3-letter to 1-letter conversion)
        
        Returns:
            AA change string (e.g., "G12D", "V600E") or None if invalid
        """
        if not hgvs_p:
            return None
        
        hgvs_p = hgvs_p.strip()
        
        # Remove "p." prefix if present
        if hgvs_p.startswith("p."):
            hgvs_p = hgvs_p[2:]
        
        # Pattern 1: Simple format (G12D, V600E)
        simple_pattern = r'^([A-Z])(\d+)([A-Z])$'
        match = re.match(simple_pattern, hgvs_p)
        if match:
            return hgvs_p  # Already in correct format
        
        # Pattern 2: 3-letter format (Val600Glu, Gly12Asp)
        three_letter_pattern = r'^([A-Z][a-z]{2})(\d+)([A-Z][a-z]{2})$'
        match = re.match(three_letter_pattern, hgvs_p)
        if match:
            ref_3letter = match.group(1)
            position = match.group(2)
            alt_3letter = match.group(3)
            
            # Convert 3-letter to 1-letter
            ref_1letter = self._three_to_one_letter(ref_3letter)
            alt_1letter = self._three_to_one_letter(alt_3letter)
            
            if ref_1letter and alt_1letter:
                return f"{ref_1letter}{position}{alt_1letter}"
        
        # If no pattern matches, return as-is (may fail hotspot check)
        self.logger.warning(f"Could not parse HGVS: {hgvs_p}")
        return hgvs_p
    
    def _three_to_one_letter(self, three_letter: str) -> Optional[str]:
        """
        Convert 3-letter amino acid code to 1-letter code.
        
        Examples:
            Val → V
            Gly → G
            Glu → E
        """
        aa_map = {
            "Ala": "A", "Arg": "R", "Asn": "N", "Asp": "D", "Cys": "C",
            "Gln": "Q", "Glu": "E", "Gly": "G", "His": "H", "Ile": "I",
            "Leu": "L", "Lys": "K", "Met": "M", "Phe": "F", "Pro": "P",
            "Ser": "S", "Thr": "T", "Trp": "W", "Tyr": "Y", "Val": "V"
        }
        return aa_map.get(three_letter)
    
    def detect_batch(self, mutations: List[Dict[str, Any]]) -> Dict[str, HotspotResult]:
        """
        Detect hotspots for a batch of mutations.
        
        Args:
            mutations: List of mutations with "gene" and "hgvs_p" fields
        
        Returns:
            Dict mapping mutation key to HotspotResult
            Key format: "{gene}:{hgvs_p}"
        
        Example:
            >>> mutations = [
            ...     {"gene": "KRAS", "hgvs_p": "p.G12D"},
            ...     {"gene": "BRAF", "hgvs_p": "p.V600E"}
            ... ]
            >>> results = detector.detect_batch(mutations)
            >>> assert results["KRAS:p.G12D"].is_hotspot == True
        """
        results = {}
        
        for mut in mutations:
            gene = mut.get("gene")
            hgvs_p = mut.get("hgvs_p")
            
            key = f"{gene}:{hgvs_p}"
            results[key] = self.detect_hotspot(gene, hgvs_p)
        
        return results


# Module-level convenience function
def detect_hotspot_mutation(gene: str, hgvs_p: Optional[str]) -> Dict[str, Any]:
    """
    Convenience function for hotspot detection.
    
    Args:
        gene: Gene symbol (e.g., "KRAS")
        hgvs_p: HGVS protein change (e.g., "p.G12D")
    
    Returns:
        Dict with hotspot detection result
        {
            "is_hotspot": bool,
            "gene": str,
            "mutation": str,
            "cosmic_id": str,
            "evidence": "highly_recurrent" | "recurrent",
            "frequency": float,
            "pathway": "MAPK",
            "cancers": List[str],
            "source": "COSMIC v98"
        }
    
    Example:
        >>> result = detect_hotspot_mutation("KRAS", "p.G12D")
        >>> assert result["is_hotspot"] == True
        >>> assert result["pathway"] == "MAPK"
    """
    detector = HotspotDetector()
    hotspot_result = detector.detect_hotspot(gene, hgvs_p)
    
    # Convert dataclass to dict
    return {
        "is_hotspot": hotspot_result.is_hotspot,
        "gene": hotspot_result.gene,
        "mutation": hotspot_result.mutation,
        "cosmic_id": hotspot_result.cosmic_id,
        "evidence": hotspot_result.evidence,
        "frequency": hotspot_result.frequency,
        "pathway": hotspot_result.pathway,
        "cancers": hotspot_result.cancers,
        "source": hotspot_result.source
    }







