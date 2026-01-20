"""
Food S/P/E Integration Service

Aggregates Sequence/Pathway/Evidence + SAE for food validation.
Simpler than drug efficacy_orchestrator (compound-focused, not variant-focused).
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Any

# Phase 1 Service Imports
from api.services.compound_alias_resolver import get_resolver as get_alias_resolver
from api.services.compound_calibration import CompoundCalibrationService

# Load universal disease pathway database (TCGA-weighted pathways)
UNIVERSAL_DB_PATH = Path(__file__).parent.parent / "resources" / "universal_disease_pathway_database.json"

# Cache for universal database
_UNIVERSAL_DB_CACHE = None

# Singleton calibrator instance
_CALIBRATOR_INSTANCE = None

def get_calibrator() -> CompoundCalibrationService:
    """Get singleton calibrator instance."""
    global _CALIBRATOR_INSTANCE
    if _CALIBRATOR_INSTANCE is None:
        _CALIBRATOR_INSTANCE = CompoundCalibrationService()
    return _CALIBRATOR_INSTANCE

class FoodSPEIntegrationService:
    """
    Aggregate S/P/E + SAE for food validation.
    
    Simpler than drug efficacy_orchestrator (compound-focused, not variant-focused).
    """
    
    def __init__(self):
        """Initialize service and load universal database + Phase 1 services."""
        self._universal_db = self._load_universal_database()
        
        # Phase 1: Alias Resolver
        self.alias_resolver = get_alias_resolver()
        
        # Phase 1: Calibration Service
        self.calibrator = get_calibrator()
    
    def _load_universal_database(self) -> Dict[str, Any]:
        """Load universal disease pathway database with TCGA weights."""
        global _UNIVERSAL_DB_CACHE
        if _UNIVERSAL_DB_CACHE is not None:
            return _UNIVERSAL_DB_CACHE
        
        if UNIVERSAL_DB_PATH.exists():
            try:
                with open(UNIVERSAL_DB_PATH) as f:
                    _UNIVERSAL_DB_CACHE = json.load(f)
                return _UNIVERSAL_DB_CACHE
            except Exception as e:
                print(f"⚠️ Failed to load universal database: {e}")
                return {}
        else:
            print(f"⚠️ Universal database not found: {UNIVERSAL_DB_PATH}")
            return {}
    
    def _get_disease_pathway_weights(self, disease: str) -> Dict[str, float]:
        """
        Get TCGA-weighted pathway frequencies for a disease.
        
        Returns dict mapping pathway_name -> weight (0.0-1.0)
        Falls back to 0.75 default if pathway not found.
        """
        if not self._universal_db:
            return {}
        
        disease_key = disease.lower().replace(' ', '_')
        disease_data = self._universal_db.get('diseases', {}).get(disease_key, {})
        pathways = disease_data.get('pathways', {})
        
        # Extract weights from pathway data
        weights = {}
        for pathway_name, pathway_data in pathways.items():
            if isinstance(pathway_data, dict):
                weight = pathway_data.get('weight', 0.75)  # Default fallback
            else:
                weight = pathway_data if isinstance(pathway_data, (int, float)) else 0.75
            weights[pathway_name] = weight
        
        return weights
    
    def _normalize_pathway_name(self, pathway_name: str) -> str:
        """
        Normalize pathway names for matching.
        
        Maps common pathway name variations to database keys.
        """
        pathway_lower = pathway_name.lower().replace(' ', '_').replace('-', '_')
        
        # Common mappings
        mappings = {
            # DNA repair
            'dna_repair': 'hrd_ddr',
            'homologous_recombination': 'hrd_ddr',
            'hrd': 'hrd_ddr',
            'ddr': 'hrd_ddr',
            
            # PI3K/AKT/mTOR
            'pi3k': 'pi3k_akt_mtor',
            'pik3ca': 'pi3k_akt_mtor',
            'akt': 'pi3k_akt_mtor',
            'mtor': 'pi3k_akt_mtor',
            'pi3k_akt_mtor': 'pi3k_akt_mtor',
            
            # RAS/MAPK
            'ras': 'ras_mapk',
            'mapk': 'ras_mapk',
            'ras_mapk': 'ras_mapk',
            'kras': 'ras_mapk',
            'kras_signaling': 'ras_mapk',
            'braf': 'ras_mapk',
            'ras_mapk_braf': 'ras_mapk',
            
            # Estrogen/Hormone receptor
            'estrogen': 'er_pr_signaling',
            'estrogen_signaling': 'er_pr_signaling',
            'hormone_receptor': 'er_pr_signaling',
            'er_signaling': 'er_pr_signaling',
            'er_pr': 'er_pr_signaling',
            'er_pr_signaling': 'er_pr_signaling',
            'androgen': 'er_pr_signaling',  # Androgen signaling often related to hormone receptors
            
            # Other pathways
            'nfkb': 'nfkb',
            'inflammation': 'nfkb',
            'tp53': 'tp53',
            'p53': 'tp53',
            'cell_cycle': 'cell_cycle',
            'angiogenesis': 'angiogenesis',
            'vegf': 'angiogenesis',
            'egfr': 'egfr_signaling',
            'her2': 'her2_signaling',
            'her2_signaling': 'her2_signaling',
            'erbb2': 'her2_signaling',
            'wnt': 'wnt_beta_catenin',
            'beta_catenin': 'wnt_beta_catenin',
        }
        
        # Try direct match first
        if pathway_lower in mappings:
            return mappings[pathway_lower]
        
        # Try partial match
        for key, mapped in mappings.items():
            if key in pathway_lower:
                return mapped
        
        # Return normalized version
        return pathway_lower
    
    async def compute_spe_score(
        self,
        compound: str,
        targets: List[str],
        pathways: List[str],
        disease_context: Dict[str, Any],
        evidence_grade: str,  # From LLM: "STRONG"/"MODERATE"/"WEAK"/"INSUFFICIENT"
        treatment_history: Optional[Dict] = None,
        evo2_enabled: bool = False
    ) -> Dict[str, Any]:
        """
        Compute S/P/E + SAE score.
        
        Formula:
        - S (Sequence): Evo2 plausibility (0.4 weight) OR neutral 0.5 if disabled
        - P (Pathway): Alignment score (0.3 weight)
        - E (Evidence): Literature grade (0.3 weight)
        - SAE: Treatment line features (boosts confidence)
        
        PHASE 2 ENHANCEMENTS:
        - Dynamic compound alias resolution (PubChem)
        - Calibrated confidence scoring (percentile ranking)
        - Enhanced provenance tracking
        
        Returns comprehensive scoring with confidence modulation.
        """
        
        # [PHASE 2 STEP 1] Resolve compound alias
        original_compound = compound
        canonical_compound = self.alias_resolver.resolve_compound_alias(compound)
        
        # Use canonical name for all downstream processing
        compound_for_processing = canonical_compound
        
        # [1] SEQUENCE (S)
        if evo2_enabled:
            # Phase 2: Will integrate Evo2 plausibility service
            try:
                from api.services.evo2_food_plausibility import get_evo2_food_plausibility_service
                evo2_service = get_evo2_food_plausibility_service()
                evo2_result = await evo2_service.compute_biological_plausibility(
                    compound=compound,
                    targets=targets,
                    disease_context=disease_context,
                    pathways=pathways
                )
                sequence_score = evo2_result.get('overall_plausibility', 0.5)
            except Exception as e:
                print(f"⚠️ Evo2 service error: {e}")
                sequence_score = 0.5
                evo2_result = {"method": "disabled", "error": str(e)}
        else:
            sequence_score = 0.5  # Neutral (Phase 1)
            evo2_result = {"method": "disabled"}
        
        # [2] PATHWAY (P) - Now using TCGA-weighted alignment
        disease = disease_context.get('disease', '')
        pathway_weights = self._get_disease_pathway_weights(disease)
        
        pathway_score = self._compute_pathway_alignment(
            compound_pathways=pathways,
            disease_pathways=disease_context.get('pathways_disrupted', []),
            disease_pathway_weights=pathway_weights
        )
        
        # [3] EVIDENCE (E)
        evidence_score = self._convert_evidence_grade(evidence_grade)
        
        # [4] SAE (computed externally, passed via treatment_history)
        # We'll get SAE features from treatment line service
        
        # [5] Aggregate S/P/E
        overall_score = (
            sequence_score * 0.4 +
            pathway_score * 0.3 +
            evidence_score * 0.3
        )
        
        # [6] Get SAE features (computed externally)
        sae_features = None
        if treatment_history:
            try:
                from api.services.food_treatment_line_service import compute_food_treatment_line_features
                sae_features = compute_food_treatment_line_features(
                    compound=compound,
                    disease_context=disease_context,
                    treatment_history=treatment_history
                )
            except Exception as e:
                print(f"⚠️ SAE computation error: {e}")
        
        # [7] Confidence modulation
        confidence = self._compute_confidence(
            sequence_score=sequence_score,
            pathway_score=pathway_score,
            evidence_score=evidence_score,
            evo2_result=evo2_result if evo2_enabled else None,
            sae_features=sae_features,
            disease_context=disease_context
        )
        
        # [8] Classify verdict
        verdict = self._classify_verdict(overall_score, confidence)
        
        # [PHASE 2 STEP 2] Calibrate score to percentile
        disease = disease_context.get('disease', '')
        calibrated_percentile = self.calibrator.get_percentile(
            compound_for_processing.lower().replace(" ", "_"),
            disease,
            overall_score
        )
        
        # [PHASE 2 STEP 3] Human-readable interpretation
        interpretation = self._interpret_percentile(calibrated_percentile) if calibrated_percentile else None
        
        return {
            "overall_score": round(overall_score, 3),
            "confidence": round(confidence, 3),
            "verdict": verdict,
            # PHASE 2: Calibrated scoring
            "spe_percentile": round(calibrated_percentile, 3) if calibrated_percentile else None,
            "interpretation": interpretation,
            # Existing fields
            "spe_breakdown": {
                "sequence": round(sequence_score, 3),
                "pathway": round(pathway_score, 3),
                "evidence": round(evidence_score, 3)
            },
            "sae_features": sae_features or {},
            "evo2_analysis": evo2_result if evo2_enabled else {"enabled": False},
            # PHASE 2: Enhanced provenance
            "provenance": {
                "compound_resolution": {
                    "original": original_compound,
                    "canonical": canonical_compound,
                    "source": "pubchem" if original_compound != canonical_compound else "direct"
                },
                "calibration": {
                    "available": calibrated_percentile is not None,
                    "sample_size": None,  # Will be populated from calibrator metadata
                    "source": "empirical_run_history" if calibrated_percentile else None
                },
                "tcga_weights": {
                    "used": bool(pathway_weights),
                    "disease": disease,
                    "pathways_matched": len([p for p in pathways if self._normalize_pathway_name(p) in pathway_weights]),
                    "pathway_weights": pathway_weights  # Include actual weights for frontend display
                }
            }
        }
    
    def _interpret_percentile(self, percentile: float) -> str:
        """
        Human-readable interpretation of calibrated percentile.
        
        PHASE 2: Makes scores understandable for Ayesha.
        """
        if percentile >= 0.90:
            return "Exceptional (top 10%)"
        elif percentile >= 0.75:
            return "High (top 25%)"
        elif percentile >= 0.50:
            return "Above average (top 50%)"
        elif percentile >= 0.25:
            return "Below average (bottom 50%)"
        else:
            return "Low (bottom 25%)"
    
    def _compute_pathway_alignment(
        self, 
        compound_pathways: List[str],
        disease_pathways: List[str],
        disease_pathway_weights: Optional[Dict[str, float]] = None
    ) -> float:
        """
        Score pathway alignment (compound vs disease) using TCGA-weighted frequencies.
        
        NEW: Uses TCGA pathway weights from universal_disease_pathway_database.json
        - Matched pathways: score = TCGA weight (0.0-1.0)
        - Unmatched pathways: score = 0.2 (baseline)
        - Weighted average across all compound pathways
        
        Falls back to binary matching (0.75 default) if weights not available.
        """
        if not compound_pathways:
            return 0.5  # Neutral if unknown
        
        # Use TCGA weights if available
        if disease_pathway_weights:
            weighted_scores = []
            matched_pathways = []
            
            for comp_path in compound_pathways:
                comp_path_normalized = self._normalize_pathway_name(comp_path)
                best_match_score = 0.2  # Default for unmatched
                best_match_pathway = None
                
                # Try to match compound pathway to disease pathways
                for disease_path in disease_pathways:
                    disease_path_normalized = self._normalize_pathway_name(disease_path)
                    
                    # Strategy 1: Check if normalized names match exactly
                    if comp_path_normalized == disease_path_normalized:
                        weight = disease_pathway_weights.get(disease_path_normalized, 0.75)
                        # Use this weight if it's the best match so far (or if no match found yet)
                        if best_match_pathway is None or weight > best_match_score:
                            best_match_score = weight
                            best_match_pathway = disease_path_normalized
                            continue
                    
                    # Strategy 2: Check if normalized compound pathway is in disease pathway name
                    if comp_path_normalized in disease_path_normalized or disease_path_normalized in comp_path_normalized:
                        weight = disease_pathway_weights.get(disease_path_normalized, 0.75)
                        # Use this weight if it's the best match so far (or if no match found yet)
                        if best_match_pathway is None or weight > best_match_score:
                            best_match_score = weight
                            best_match_pathway = disease_path_normalized
                            continue
                    
                    # Strategy 3: Check for keyword overlap (original strings)
                    comp_words = set(comp_path.lower().split())
                    disease_words = set(disease_path.lower().split())
                    
                    if comp_words & disease_words:  # Intersection found
                        # Get TCGA weight for this pathway
                        weight = disease_pathway_weights.get(disease_path_normalized, 0.75)
                        # Use this weight if it's the best match so far (or if no match found yet)
                        if best_match_pathway is None or weight > best_match_score:
                            best_match_score = weight
                            best_match_pathway = disease_path_normalized
                
                weighted_scores.append(best_match_score)
                if best_match_pathway:
                    matched_pathways.append(best_match_pathway)
            
            # Weighted average
            pathway_score = sum(weighted_scores) / len(weighted_scores) if weighted_scores else 0.5
            
            return pathway_score
        else:
            # Fallback to binary matching (old behavior)
            aligned_count = 0
            for comp_path in compound_pathways:
                for disease_path in disease_pathways:
                    comp_words = set(comp_path.lower().split())
                    disease_words = set(disease_path.lower().split())
                    
                    if comp_words & disease_words:  # Intersection
                        aligned_count += 1
                        break
            
            alignment_ratio = aligned_count / len(compound_pathways) if compound_pathways else 0
            score = alignment_ratio * 1.0 + (1 - alignment_ratio) * 0.2
            
            return score
    
    def _convert_evidence_grade(self, grade: str) -> float:
        """Convert literature grade to 0-1 score."""
        mapping = {
            "STRONG": 0.9,
            "MODERATE": 0.6,
            "WEAK": 0.3,
            "INSUFFICIENT": 0.1
        }
        return mapping.get(grade.upper(), 0.5)
    
    def _compute_confidence(
        self,
        sequence_score: float,
        pathway_score: float,
        evidence_score: float,
        evo2_result: Optional[Dict],
        sae_features: Optional[Dict],
        disease_context: Dict
    ) -> float:
        """
        Compute confidence with multi-stage modulation.
        
        Formula:
        - Base = (S+P+E)/3
        - Evo2 boost: +0.05 per HIGH plausibility target
        - SAE boost: (line_app + seq_fit) × 0.05
        - Biomarker boost: +0.05 if matches
        - Final = min(base + boosts, 0.95)
        """
        
        base = (sequence_score + pathway_score + evidence_score) / 3.0
        
        # Evo2 boost
        evo2_boost = 0.0
        if evo2_result and 'target_analysis' in evo2_result:
            high_plausibility = [
                t for t in evo2_result['target_analysis']
                if t.get('plausibility') == 'HIGH'
            ]
            evo2_boost = min(len(high_plausibility) * 0.05, 0.15)
        
        # SAE boost (if provided)
        sae_boost = 0.0
        if sae_features:
            line_app = sae_features.get('line_appropriateness', 0)
            seq_fit = sae_features.get('sequencing_fitness', 0)
            sae_boost = (line_app + seq_fit) * 0.05
        
        # Biomarker boost
        biomarker_boost = 0.0
        biomarkers = disease_context.get('biomarkers', {})
        
        # Check for HRD + DNA repair pathway match
        pathways_disrupted = disease_context.get('pathways_disrupted', [])
        if biomarkers.get('HRD') == 'POSITIVE':
            if any('dna repair' in p.lower() for p in pathways_disrupted):
                biomarker_boost += 0.05
        
        tmb_value = biomarkers.get('TMB', 0)
        # Handle TMB as string or int
        if isinstance(tmb_value, str):
            try:
                tmb_value = float(tmb_value) if tmb_value.upper() != 'UNKNOWN' else 0
            except (ValueError, AttributeError):
                tmb_value = 0
        if tmb_value >= 10:
            biomarker_boost += 0.03
        
        final = min(base + evo2_boost + sae_boost + biomarker_boost, 0.95)
        
        return final
    
    def _classify_verdict(self, score: float, confidence: float) -> str:
        """
        Classify verdict based on score AND confidence.
        
        Thresholds:
        - SUPPORTED: score ≥0.65 AND confidence ≥0.70
        - WEAK_SUPPORT: score ≥0.45 AND confidence ≥0.50
        - NOT_SUPPORTED: otherwise
        """
        
        if score >= 0.65 and confidence >= 0.70:
            return "SUPPORTED"
        elif score >= 0.45 and confidence >= 0.50:
            return "WEAK_SUPPORT"
        else:
            return "NOT_SUPPORTED"

