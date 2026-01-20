"""
Dynamic Food/Supplement Target Extraction Service

Extracts molecular targets and pathways for ANY compound using:
1. ChEMBL API (primary)
2. PubChem API (fallback)
3. LLM literature extraction (backup)
"""

import httpx
import json
from typing import Dict, List, Optional, Any
from pathlib import Path
import asyncio
import logging

# Import compound alias resolver for dynamic name resolution
from api.services.compound_alias_resolver import get_resolver as get_alias_resolver

# Try to import evidence service (graceful fallback if unavailable)
try:
    from api.services.enhanced_evidence_service import get_enhanced_evidence_service
    EVIDENCE_SERVICE_AVAILABLE = True
except ImportError:
    EVIDENCE_SERVICE_AVAILABLE = False

logger = logging.getLogger(__name__)

class DynamicFoodExtractor:
    """Extract targets and pathways for any food/supplement compound."""
    
    def __init__(self):
        self.chembl_base = "https://www.ebi.ac.uk/chembl/api/data"
        self.pubchem_base = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
        self.cache = {}  # Simple in-memory cache
        self.timeout = 15.0
        
        # Initialize dynamic alias resolver (replaces hardcoded aliases)
        self.alias_resolver = get_alias_resolver()
        logger.info("✅ Dynamic compound alias resolver initialized")
        
        # Load cancer pathway mappings
        self._load_pathway_mappings()
    
    def _load_pathway_mappings(self):
        """Load cancer mechanism pathway mappings."""
        pathway_file = Path(__file__).parent.parent.parent.parent.parent / ".cursor/ayesha/hypothesis_validator/data/cancer_pathways.json"
        
        if pathway_file.exists():
            with open(pathway_file) as f:
                self.pathway_mappings = json.load(f)
        else:
            # Default mappings (will be created if missing)
            self.pathway_mappings = {
                "cancer_mechanisms": {
                    "angiogenesis": {
                        "targets": ["VEGF", "VEGFR", "EGFR", "PDGFR", "FGF", "Angiopoietin"],
                        "pathways": ["VEGF signaling", "Angiogenesis", "Blood vessel formation"]
                    },
                    "dna_repair": {
                        "targets": ["BRCA1", "BRCA2", "PARP1", "TP53", "ATM", "ATR", "RAD51"],
                        "pathways": ["Homologous recombination", "DNA repair", "Cell cycle checkpoint"]
                    },
                    "inflammation": {
                        "targets": ["NF-κB", "COX-2", "IL-6", "TNF-α", "STAT3", "iNOS"],
                        "pathways": ["Inflammatory response", "NF-κB signaling", "JAK-STAT"]
                    },
                    "cell_cycle": {
                        "targets": ["CDK4", "CDK6", "Cyclin D1", "p21", "p27", "RB1"],
                        "pathways": ["Cell cycle progression", "G1/S checkpoint", "CDK signaling"]
                    },
                    "apoptosis": {
                        "targets": ["Bcl-2", "Bax", "Caspase-3", "p53", "Survivin", "XIAP"],
                        "pathways": ["Apoptosis", "Programmed cell death", "p53 signaling"]
                    },
                    "metabolism": {
                        "targets": ["mTOR", "PI3K", "AKT", "GLUT1", "HK2", "LDH"],
                        "pathways": ["mTOR signaling", "PI3K/AKT", "Glycolysis", "Warburg effect"]
                    }
                }
            }
    
    async def extract_targets_chembl(self, compound: str) -> Optional[Dict[str, Any]]:
        """
        Extract targets from ChEMBL API.
        
        Returns:
            {
                "targets": ["VEGF", "EGFR"],
                "mechanisms": ["VEGFR inhibitor"],
                "source": "chembl",
                "confidence": 0.9
            }
        """
        # Dynamically resolve compound alias using PubChem
        # This replaces hardcoded aliases with live API resolution
        search_term = self.alias_resolver.resolve_compound_alias(compound)
        
        logger.info(f"🔍 ChEMBL extraction: '{compound}' → '{search_term}'")
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # Search for compound - try exact match first
                search_url = f"{self.chembl_base}/molecule.json"
                params = {"molecule_synonyms__molecule_synonym__iexact": search_term}
                
                response = await client.get(search_url, params=params)
                
                # If exact match fails, try contains search
                if response.status_code != 200 or not response.json().get("molecules"):
                    params = {"molecule_synonyms__molecule_synonym__icontains": search_term.split()[0]}  # First word
                    response = await client.get(search_url, params=params)
                    
                    if response.status_code != 200 or not response.json().get("molecules"):
                        return None
                
                molecules = response.json()["molecules"]
                if not molecules:
                    return None
                
                molecule = molecules[0]
                chembl_id = molecule.get("molecule_chembl_id")
                
                # Get targets for this molecule
                targets_url = f"{self.chembl_base}/activity.json"
                targets_params = {
                    "molecule_chembl_id": chembl_id,
                    "standard_type": "IC50",  # Binding affinity data
                    "standard_value__isnull": False
                }
                
                targets_response = await client.get(targets_url, params=targets_params)
                
                if targets_response.status_code != 200:
                    return None
                
                activities = targets_response.json().get("activities", [])
                targets = []
                mechanisms = []
                
                for activity in activities:
                    target = activity.get("target_pref_name") or activity.get("target_organism")
                    if target and target not in targets:
                        targets.append(target)
                    
                    # Extract mechanism if available
                    mechanism = activity.get("mechanism_of_action_type")
                    if mechanism and mechanism not in mechanisms:
                        mechanisms.append(mechanism)
                
                if targets:
                    return {
                        "targets": targets[:10],  # Top 10 targets
                        "mechanisms": mechanisms,
                        "source": "chembl",
                        "confidence": 0.9,
                        "chembl_id": chembl_id
                    }
                
                return None
                
        except Exception as e:
            print(f"⚠️ ChEMBL extraction error for {compound}: {e}")
            return None
    
    async def extract_targets_pubchem(self, compound: str) -> Optional[Dict[str, Any]]:
        """
        Extract targets from PubChem API (fallback).
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # Search for compound
                search_url = f"{self.pubchem_base}/compound/name/{compound}/cids/JSON"
                
                response = await client.get(search_url)
                
                if response.status_code != 200:
                    return None
                
                cids = response.json().get("IdentifierList", {}).get("CID", [])
                if not cids:
                    return None
                
                cid = cids[0]
                
                # Get bioactivity targets
                bioactivity_url = f"{self.pubchem_base}/compound/cid/{cid}/bioactivity/JSON"
                bio_response = await client.get(bioactivity_url)
                
                targets = []
                if bio_response.status_code == 200:
                    bio_data = bio_response.json()
                    # Extract target names from bioactivity data
                    # (PubChem structure varies, this is simplified)
                    if "PC_BioAssayContainer" in bio_data:
                        for assay in bio_data["PC_BioAssayContainer"]:
                            target_name = assay.get("target")
                            if target_name and target_name not in targets:
                                targets.append(target_name)
                
                if targets:
                    return {
                        "targets": targets[:10],
                        "source": "pubchem",
                        "confidence": 0.7
                    }
                
                return None
                
        except Exception as e:
            print(f"⚠️ PubChem extraction error for {compound}: {e}")
            return None
    
    def _extract_targets_from_text(self, text: str) -> List[str]:
        """
        Extract molecular targets from text using keyword matching against known cancer targets.
        
        Uses deterministic keyword matching - NO LLM required.
        """
        if not text:
            return []
        
        text_lower = text.lower()
        found_targets = []
        
        # Get all known targets from pathway mappings
        all_known_targets = []
        if self.pathway_mappings and "cancer_mechanisms" in self.pathway_mappings:
            for mechanism_data in self.pathway_mappings["cancer_mechanisms"].values():
                all_known_targets.extend(mechanism_data.get("targets", []))
        
        # Also add common cancer targets not in mappings
        common_targets = [
            "VEGF", "VEGFR", "EGFR", "PDGFR", "FGF", "Angiopoietin",
            "BRCA1", "BRCA2", "PARP1", "TP53", "ATM", "ATR", "RAD51",
            "NF-κB", "NFKB", "COX-2", "COX2", "IL-6", "IL6", "TNF-α", "TNF",
            "STAT3", "JAK1", "JAK2", "CDK4", "CDK6", "Cyclin D1", "p21", "p27",
            "Bcl-2", "Bax", "Caspase-3", "Survivin", "XIAP",
            "mTOR", "PI3K", "AKT", "GLUT1", "HK2", "LDH",
            "APEX1", "POLB", "XRCC1", "OGG1", "MBD4", "MLH1", "MSH2"
        ]
        
        all_targets = list(set(all_known_targets + common_targets))
        
        # Match targets in text (case-insensitive, whole word or with common separators)
        for target in all_targets:
            target_lower = target.lower()
            # Check for target mentions (whole word or with separators like -, _, space)
            patterns = [
                target_lower,  # Exact match
                target_lower.replace("-", ""),  # Without hyphens
                target_lower.replace("_", ""),  # Without underscores
                target_lower.replace("-", " "),  # Hyphen to space
            ]
            
            for pattern in patterns:
                if pattern in text_lower:
                    # Check it's not part of a larger word
                    import re
                    if re.search(r'\b' + re.escape(pattern) + r'\b', text_lower):
                        if target not in found_targets:
                            found_targets.append(target)
                        break
        
        return found_targets
    
    def _extract_mechanisms_from_text(self, text: str) -> List[str]:
        """
        Extract mechanisms from text using keyword matching.
        
        NO LLM required - uses deterministic keyword matching.
        """
        if not text:
            return []
        
        text_lower = text.lower()
        found_mechanisms = []
        
        # Known mechanism keywords
        mechanism_keywords = {
            "angiogenesis": ["angiogenesis", "vascular", "blood vessel", "vegf", "endothelial"],
            "inflammation": ["inflammation", "inflammatory", "nf-κb", "nfkb", "cox-2", "cox2", "il-6", "tnf"],
            "dna_repair": ["dna repair", "homologous recombination", "brca", "parp", "base excision"],
            "apoptosis": ["apoptosis", "cell death", "caspase", "bcl-2", "bax"],
            "cell_cycle": ["cell cycle", "cdk", "cyclin", "g1/s", "checkpoint"],
            "metabolism": ["metabolism", "mtor", "glycolysis", "warburg", "glucose"],
            "oxidative_stress": ["oxidative stress", "ros", "reactive oxygen", "antioxidant", "glutathione"],
            "immune": ["immune", "immunity", "t-cell", "nk cell", "cytokine"]
        }
        
        for mechanism, keywords in mechanism_keywords.items():
            for keyword in keywords:
                if keyword in text_lower:
                    if mechanism not in found_mechanisms:
                        found_mechanisms.append(mechanism)
                    break
        
        return found_mechanisms
    
    async def extract_targets_llm(self, compound: str, disease: str = "ovarian cancer") -> Optional[Dict[str, Any]]:
        """
        Extract targets using evidence service literature search + KEYWORD MATCHING.
        
        NO LLM REQUIRED - uses deterministic keyword matching against known cancer targets.
        """
        if not EVIDENCE_SERVICE_AVAILABLE:
            return None
        
        try:
            evidence_service = get_enhanced_evidence_service()
            
            # Search literature
            result = await evidence_service.get_complete_evidence(
                compound=compound,
                disease=disease
            )
            
            if not result.get("papers"):
                return None
            
            # Extract abstracts and combine text
            papers = result["papers"]
            combined_text = "\n\n".join([
                f"{p.get('title', '')} {p.get('abstract', '')}"
                for p in papers[:10]  # Use top 10 papers
            ])
            
            # Extract targets using keyword matching (NO LLM)
            targets = self._extract_targets_from_text(combined_text)
            mechanisms = self._extract_mechanisms_from_text(combined_text)
            
            # Map targets to pathways
            pathway_mapping = self.map_targets_to_pathways(targets)
            pathways = pathway_mapping.get("pathways", [])
            
            # Calculate confidence based on number of matches
            confidence = min(0.3 + (len(targets) * 0.05) + (len(papers) * 0.02), 0.8)
            
            if targets or mechanisms:
                return {
                    "targets": targets[:15],  # Limit to top 15
                    "mechanisms": mechanisms[:10],
                    "pathways": pathways[:10],
                    "source": "keyword_matching_literature",
                    "confidence": confidence,
                    "papers_analyzed": len(papers),
                    "targets_found": len(targets),
                    "mechanisms_found": len(mechanisms)
                }
            else:
                # No targets found, but we searched literature
                return {
                    "targets": [],
                    "mechanisms": [],
                    "pathways": [],
                    "source": "keyword_matching_literature",
                    "confidence": 0.2,
                    "papers_analyzed": len(papers),
                    "note": "No known cancer targets found in abstracts (may need manual review)"
                }
            
        except Exception as e:
            logger.error(f"⚠️ Keyword extraction error for {compound}: {e}")
            return None
    
    def map_targets_to_pathways(self, targets: List[str]) -> Dict[str, Any]:
        """
        Map extracted targets to cancer pathways.
        
        Returns:
            {
                "pathways": ["DNA repair", "Angiogenesis"],
                "mechanisms": ["angiogenesis", "dna_repair"],
                "alignment_scores": {"angiogenesis": 0.8, "dna_repair": 0.9}
            }
        """
        pathways = []
        mechanisms = []
        alignment_scores = {}
        
        if not self.pathway_mappings or "cancer_mechanisms" not in self.pathway_mappings:
            return {
                "pathways": [],
                "mechanisms": [],
                "alignment_scores": {}
            }
        
        for mechanism_name, mechanism_data in self.pathway_mappings["cancer_mechanisms"].items():
            mechanism_targets = mechanism_data.get("targets", [])
            mechanism_pathways = mechanism_data.get("pathways", [])
            
            # Check if any targets match
            matched_targets = [t for t in targets if any(mt.lower() in t.lower() for mt in mechanism_targets)]
            
            if matched_targets:
                mechanisms.append(mechanism_name)
                pathways.extend(mechanism_pathways)
                # Score: ratio of matched targets
                alignment_scores[mechanism_name] = len(matched_targets) / len(mechanism_targets)
        
        # Deduplicate pathways
        pathways = list(set(pathways))
        
        return {
            "pathways": pathways,
            "mechanisms": mechanisms,
            "alignment_scores": alignment_scores
        }
    
    async def extract_all(self, compound: str, disease: str = "ovarian cancer") -> Dict[str, Any]:
        """
        Extract targets using all methods (ChEMBL → PubChem → LLM).
        
        Returns complete extraction result with targets, pathways, mechanisms.
        """
        # Map to specific chemical name if alias exists (for caching consistency)
        # Use dynamic alias resolver instead of hardcoded aliases
        search_term = self.alias_resolver.resolve_compound_alias(compound)
        
        # Check cache first
        cache_key = f"{search_term.lower()}_{disease.lower()}"
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        # Try ChEMBL first (most reliable) - use original compound (already mapped in extract_targets_chembl)
        result = await self.extract_targets_chembl(compound)
        
        # Fallback to PubChem
        if not result or not result.get("targets"):
            result = await self.extract_targets_pubchem(compound)
        
        # Fallback to keyword-based literature extraction (NO LLM REQUIRED)
        if not result or not result.get("targets"):
            result = await self.extract_targets_llm(compound, disease)
        
        # If still no results, return empty structure (but don't error - allow pathway matching to proceed)
        if not result or not result.get("targets"):
            result = {
                "targets": [],
                "source": "keyword_matching_literature",
                "confidence": 0.0,
                "note": f"No targets found via ChEMBL/PubChem for '{compound}' - keyword extraction attempted"
            }
        
        # Map targets to pathways
        targets = result.get("targets", [])
        pathway_mapping = self.map_targets_to_pathways(targets)
        
        # Combine results
        final_result = {
            "compound": compound,
            "targets": targets,
            "pathways": pathway_mapping["pathways"],
            "mechanisms": pathway_mapping["mechanisms"],
            "mechanism_scores": pathway_mapping["alignment_scores"],
            "source": result.get("source", "unknown"),
            "confidence": result.get("confidence", 0.0),
            "mechanisms_list": result.get("mechanisms", []),
            "error": result.get("error")
        }
        
        # Cache result
        self.cache[cache_key] = final_result
        
        return final_result


# Singleton instance
_extractor_instance = None

def get_dynamic_extractor() -> DynamicFoodExtractor:
    """Get singleton instance of dynamic extractor."""
    global _extractor_instance
    if _extractor_instance is None:
        _extractor_instance = DynamicFoodExtractor()
    return _extractor_instance

