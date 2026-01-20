"""
SAE Feature Computation Service (Phase 2)
==========================================
Implements Manager's Policy for post-NGS SAE-driven features.

Policy Source: MANAGER_ANSWERS_TO_ZO_SAE_QUESTIONS.md (C1-C10)
Owner: Zo (Lead Commander)
Date: January 13, 2025

CRITICAL: This service ONLY runs when tumor NGS data exists.
Pre-NGS behavior handled by Phase 1 services (next_test_recommender, hint_tiles, mechanism_map).
"""

from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any, Tuple
import logging

from api.services.hotspot_detector import detect_hotspot_mutation  # ⚔️ P0 FIX #3 (Jan 13, 2025)
from api.services.pathway_to_mechanism_vector import convert_pathway_scores_to_mechanism_vector  # ⚔️ P0 FIX: Use conversion function for TP53→DDR mapping

logger = logging.getLogger(__name__)

# Manager's Policy Constants (MANAGER_ANSWERS_TO_ZO_SAE_QUESTIONS.md)
# These are APPROVED thresholds; do not modify without Manager authorization

# C1, C2: Pathway burden thresholds
PATHWAY_THRESHOLD_HIGH = 0.70
PATHWAY_THRESHOLD_MODERATE = 0.40

# C3: Essentiality weight for HRR genes
HRR_GENES = ["BRCA1", "BRCA2", "PALB2", "RAD51C", "RAD51D", "BRIP1", "BARD1", "ATM"]
ESSENTIALITY_CONTRIBUTION_WEIGHT = 0.15  # Modest lift

# C4: Exon disruption scoring threshold
EXON_DISRUPTION_THRESHOLD = 0.65  # Only apply when essentiality > 0.65

# C5: DNA Repair Capacity formula (Manager's exact formula)
# ⚔️ MANAGER APPROVED: 0.6/0.2/0.2 weights (Jan 13, 2025)
# DO NOT MODIFY WITHOUT MANAGER AUTHORIZATION
DNA_REPAIR_CAPACITY_WEIGHTS = {
    "pathway_ddr": 0.60,         # Manager's C1 (was 0.50) ⚔️ FIXED
    "essentiality_hrr": 0.20,    # Manager's C1 (was 0.30) ⚔️ FIXED
    "exon_disruption": 0.20      # Manager's C1, C4 (was "functionality") ⚔️ FIXED
}

# C6: Mechanism fit (cosine similarity) thresholds
MECHANISM_FIT_MIN_THRESHOLD = 0.50
MECHANISM_FIT_ALPHA = 0.7  # Eligibility weight
MECHANISM_FIT_BETA = 0.3   # Mechanism fit weight

# C7: Resistance detection (2-of-3 trigger rule)
RESISTANCE_HRD_DROP_THRESHOLD = 15  # HRD drop >= 15 points
RESISTANCE_DNA_REPAIR_DROP_THRESHOLD = 0.20  # DNA repair drop >= 0.20
# CA-125 inadequate response handled by ca125_intelligence service

# C8: Hint tile priority order (Manager's policy)
HINT_PRIORITY_ORDER = ["next_test", "trial_matched", "monitoring", "avoid"]

# C9: Mechanism Map color thresholds (post-NGS only)
MECHANISM_MAP_COLOR_THRESHOLDS = {
    "green": 0.70,   # High burden
    "yellow": 0.40   # Moderate burden
}


@dataclass
class SAEFeatures:
    """
    SAE Feature Bundle (Post-NGS)
    
    Computed from:
    - Insights Bundle (functionality, chromatin, essentiality, regulatory)
    - Pathway Scores (P from S/P/E)
    - Tumor Context (HRD, TMB, MSI, somatic mutations)
    - Treatment History
    - CA-125 Intelligence
    
    Manager Policy: MANAGER_ANSWERS_TO_ZO_SAE_QUESTIONS.md (C1-C10)
    """
    # Core Features (C1, C2)
    dna_repair_capacity: float  # 0-1, Manager's formula (C5)
    pathway_burden_ddr: float   # 0-1
    pathway_burden_mapk: float  # 0-1
    pathway_burden_pi3k: float  # 0-1
    pathway_burden_vegf: float  # 0-1
    pathway_burden_her2: float  # 0-1, HER2 pathway (BONUS: HER2 trial validation)
    io_eligible: bool           # TMB >= 20 OR MSI-High
    cross_resistance_risk: float  # 0-1
    
    # Enhanced Features (C3, C4)
    essentiality_hrr_genes: float  # 0-1, avg essentiality for HRR genes
    exon_disruption_score: float   # 0-1, only if essentiality > 0.65
    
    # ⚔️ P0 FIX #3: Hotspot Mutation Detection (Manager's C2 - Jan 13, 2025)
    hotspot_mutation: bool  # True if KRAS/BRAF/NRAS COSMIC hotspot detected
    hotspot_details: Optional[Dict[str, Any]]  # COSMIC hotspot details (gene, mutation, pathway, frequency)
    
    # Mechanism Vector (7D for cosine similarity with trial MoA)
    mechanism_vector: List[float]  # [DDR, MAPK, PI3K, VEGF, HER2, IO, Efflux]
    
    # Resistance Detection (C7)
    resistance_signals: Dict[str, Any]  # 2-of-3 trigger logic
    
    # Provenance
    provenance: Dict[str, Any]


class SAEFeatureService:
    """
    SAE Feature Computation Service (Phase 2)
    
    Implements Manager's exact policy for post-NGS SAE features.
    Integrates with:
    - Insights Bundle (functionality, chromatin, essentiality, regulatory)
    - Pathway Scores (P from efficacy router)
    - Tumor Context (HRD, TMB, MSI, somatic mutations)
    - Treatment History
    - CA-125 Intelligence
    """
    
    def __init__(self):
        self.logger = logger
    
    def compute_sae_features(
        self,
        insights_bundle: Dict[str, Any],
        pathway_scores: Dict[str, float],
        tumor_context: Dict[str, Any],
        treatment_history: Optional[List[Dict]] = None,
        ca125_intelligence: Optional[Dict] = None,
        previous_hrd_score: Optional[float] = None,
        previous_dna_repair_capacity: Optional[float] = None,
        sae_features: Optional[Dict[str, Any]] = None
    ) -> SAEFeatures:
        """
        Compute SAE Features (Post-NGS Only)
        
        Manager Policy: MANAGER_ANSWERS_TO_ZO_SAE_QUESTIONS.md (C1-C10)
        
        Args:
            insights_bundle: From /api/insights/predict_* (4 chips)
            pathway_scores: From efficacy router (P scores per pathway)
            tumor_context: TumorContext with HRD, TMB, MSI, somatic mutations
            treatment_history: List of prior treatments
            ca125_intelligence: From CA-125 service
            previous_hrd_score: Previous HRD score (for resistance detection)
            previous_dna_repair_capacity: Previous DNA repair capacity (for resistance detection)
            sae_features: Optional true SAE features from Evo2 layer 26 activations (Phase 1 - diagnostics only)
        
        Returns:
            SAEFeatures dataclass with all computed features
        """
        # Extract somatic mutations from tumor context
        somatic_mutations = tumor_context.get("somatic_mutations", [])
        genes = [m.get("gene") for m in somatic_mutations if m.get("gene")]
        
        # C3: Essentiality for HRR genes
        # Debug: Log insights_bundle essentiality value
        insights_essentiality = insights_bundle.get("essentiality", "MISSING")
        self.logger.info(f"🔍 [SAE DEBUG] insights_bundle.essentiality = {insights_essentiality}")
        essentiality_hrr = self._compute_essentiality_hrr(insights_bundle, genes)
        self.logger.info(f"🔍 [SAE DEBUG] computed essentiality_hrr = {essentiality_hrr}")
        
        # C4: Exon disruption score (only if essentiality > 0.65)
        exon_disruption_score = self._compute_exon_disruption_score(
            insights_bundle, 
            genes, 
            essentiality_hrr
        )
        
        # ⚔️ P0 FIX #3: Hotspot Mutation Detection (Manager's C2 - Jan 13, 2025)
        # Detect KRAS/BRAF/NRAS hotspot mutations for MEK/RAF trial recommendations
        hotspot_mutation = False
        hotspot_details = None
        for mut in somatic_mutations:
            gene = mut.get("gene")
            hgvs_p = mut.get("hgvs_p") or mut.get("protein_change")
            
            if gene and hgvs_p:
                hotspot_result = detect_hotspot_mutation(gene, hgvs_p)
                if hotspot_result.get("is_hotspot"):
                    hotspot_mutation = True
                    hotspot_details = hotspot_result
                    logger.info(f"⚔️ P0 Fix #3: Hotspot detected - {gene} {hotspot_result.get('mutation')} (COSMIC)")
                    break  # Only report first hotspot found
        
        # C1, C2: Pathway burden
        pathway_burden_ddr = pathway_scores.get("ddr", 0.0)
        pathway_burden_mapk = pathway_scores.get("mapk", 0.0)
        pathway_burden_pi3k = pathway_scores.get("pi3k", 0.0)
        pathway_burden_vegf = pathway_scores.get("vegf", 0.0)
        pathway_burden_her2 = pathway_scores.get("her2", 0.0)  # BONUS: HER2 pathway for NCT06819007
        
        # C5: DNA Repair Capacity (Manager's exact formula)
        # ⚔️ MANAGER APPROVED: Use exon_disruption_score (C4), not functionality (Jan 13, 2025)
        dna_repair_capacity = self._compute_dna_repair_capacity(
            pathway_burden_ddr,
            essentiality_hrr,
            exon_disruption_score  # ⚔️ FIXED: was insights_bundle.get("functionality", 0.0)
        )
        
        # IO eligibility
        tmb = tumor_context.get("tmb_score", 0.0)
        msi_status = tumor_context.get("msi_status", "Unknown")
        io_eligible = (tmb >= 20) or (msi_status == "MSI-High")
        
        # Cross-resistance risk (simplified for Phase 2)
        cross_resistance_risk = self._compute_cross_resistance_risk(treatment_history)
        
        # Mechanism vector (7D for cosine similarity) - Use conversion function for TP53→DDR mapping
        # ⚔️ P0 FIX: Use convert_pathway_scores_to_mechanism_vector for proper TP53→DDR (50% contribution)
        pathway_scores_dict = {
            "ddr": pathway_burden_ddr,
            "mapk": pathway_burden_mapk,
            "pi3k": pathway_burden_pi3k,
            "vegf": pathway_burden_vegf,
            "her2": pathway_burden_her2,
            # Note: TP53 contribution to DDR is handled inside conversion function (50% mapping)
            # If TP53 is in pathway_scores, it will be automatically mapped to DDR with 50% weight
        }
        
        # Build tumor context for IO calculation
        tumor_context_for_io = {
            "tmb": tmb if tmb else 0.0,
            "msi_status": msi_status if msi_status else ""
        }
        
        # Convert pathway scores to 7D mechanism vector [DDR, MAPK, PI3K, VEGF, HER2, IO, Efflux]
        mechanism_vector_base, dimension_used = convert_pathway_scores_to_mechanism_vector(
            pathway_scores_dict,
            tumor_context=tumor_context_for_io,
            use_7d=True  # Force 7D to include HER2
        )
        
        # Override Efflux dimension (6th index) with cross-resistance risk
        # The conversion function doesn't handle Efflux, so we set it manually
        if len(mechanism_vector_base) >= 7:
            mechanism_vector_base[6] = cross_resistance_risk
        else:
            # Fallback: extend vector if needed
            while len(mechanism_vector_base) < 7:
                mechanism_vector_base.append(0.0)
            mechanism_vector_base[6] = cross_resistance_risk
        
        mechanism_vector = mechanism_vector_base
        
        # C7: Resistance detection (2-of-3 trigger rule)
        resistance_signals = self._detect_resistance(
            tumor_context.get("hrd_score", 0.0),
            previous_hrd_score,
            dna_repair_capacity,
            previous_dna_repair_capacity,
            ca125_intelligence
        )
        
        # Provenance
        provenance = {
            "data_sources": {
                "insights_bundle": "Functionality, Chromatin, Essentiality, Regulatory",
                "pathway_scores": "P from efficacy router",
                "tumor_context": f"HRD={tumor_context.get('hrd_score')}, TMB={tmb}, MSI={msi_status}",
                "treatment_history": f"{len(treatment_history) if treatment_history else 0} treatments",
                "ca125_intelligence": "Included" if ca125_intelligence else "Not available"
            },
            "insights_bundle_values": {
                "functionality": insights_bundle.get("functionality"),
                "chromatin": insights_bundle.get("chromatin"),
                "essentiality": insights_bundle.get("essentiality"),
                "regulatory": insights_bundle.get("regulatory")
            },
            "manager_policy": "MANAGER_ANSWERS_TO_ZO_SAE_QUESTIONS.md (C1-C10)",
            "thresholds": {
                "pathway_high": PATHWAY_THRESHOLD_HIGH,
                "pathway_moderate": PATHWAY_THRESHOLD_MODERATE,
                "essentiality_contribution_weight": ESSENTIALITY_CONTRIBUTION_WEIGHT,
                "exon_disruption_threshold": EXON_DISRUPTION_THRESHOLD,
                "mechanism_fit_alpha": MECHANISM_FIT_ALPHA,
                "mechanism_fit_beta": MECHANISM_FIT_BETA
            },
            "sae": "proxy"  # Default: proxy SAE features from insights+pathway
        }
        
        # Phase 2: Optional True SAE Pathway Scores (ENABLE_TRUE_SAE_PATHWAYS flag)
        # If true SAE features provided and flag enabled, use TRUE SAE pathway scores instead of proxy
        if sae_features is not None:
            try:
                from ..config import get_feature_flags
                flags = get_feature_flags()
                
                if flags.get("enable_true_sae_pathways", False):
                    # Compute SAE diagnostics from 32K feature vector
                    sae_diagnostics = self._compute_sae_diagnostics(sae_features)
                    
                    # Use TRUE SAE pathway scores (with fallback to proxy)
                    pathway_burden_ddr = sae_diagnostics.get("ddr_sae_score", pathway_burden_ddr) or pathway_burden_ddr
                    pathway_burden_mapk = sae_diagnostics.get("mapk_sae_score", pathway_burden_mapk) or pathway_burden_mapk
                    pathway_burden_pi3k = sae_diagnostics.get("pi3k_sae_score", pathway_burden_pi3k) or pathway_burden_pi3k
                    pathway_burden_vegf = sae_diagnostics.get("vegf_sae_score", pathway_burden_vegf) or pathway_burden_vegf
                    pathway_burden_her2 = sae_diagnostics.get("her2_sae_score", pathway_burden_her2) or pathway_burden_her2
                    tp53_sae_score = sae_diagnostics.get("tp53_sae_score", 0.0) or 0.0
                    
                    # Update mechanism vector with TRUE SAE scores
                    mechanism_vector_base, dimension_used = convert_pathway_scores_to_mechanism_vector(
                        {
                            "ddr": pathway_burden_ddr,
                            "mapk": pathway_burden_mapk,
                            "pi3k": pathway_burden_pi3k,
                            "vegf": pathway_burden_vegf,
                            "her2": pathway_burden_her2,
                            "tp53": tp53_sae_score
                        },
                        tumor_context=tumor_context,
                        tmb=tmb,
                        msi_status=msi_status,
                        use_7d=True
                    )
                    mechanism_vector = mechanism_vector_base
                    
                    # DNA repair capacity: Use SAE DDR score + proxy essentiality/exon
                    dna_repair_capacity = (
                        0.60 * pathway_burden_ddr +
                        0.20 * essentiality_hrr +
                        0.20 * exon_disruption_score
                    )
                    
                    # Update provenance
                    provenance["sae"] = "true_sae"
                    provenance["sae_diagnostics"] = sae_diagnostics
                    provenance["sae_version"] = sae_features.get("provenance", {}).get("sae_version", "unknown")
                    provenance["mapping_version"] = sae_diagnostics.get("mapping_version", "unknown")
                    
                    logger.info(f"✅ Using TRUE SAE pathway scores (mapping: {sae_diagnostics.get('mapping_version', 'unknown')})")
                    logger.info(f"   DDR: {pathway_burden_ddr:.3f}, MAPK: {pathway_burden_mapk:.3f}, DNA Repair: {dna_repair_capacity:.3f}")
                elif flags.get("enable_true_sae", False):
                    # Compute SAE diagnostics from 32K feature vector (diagnostics only)
                    sae_diagnostics = self._compute_sae_diagnostics(sae_features)
                    
                    # Add to provenance (diagnostics only - no scoring changes)
                    provenance["sae"] = "proxy+true"
                    provenance["sae_diagnostics"] = sae_diagnostics
                    provenance["sae_version"] = sae_features.get("provenance", {}).get("sae_version", "unknown")
                    
                    logger.info(f"✅ True SAE diagnostics computed: ddr_score={sae_diagnostics.get('ddr_sae_score', 0.0):.3f}, io_score={sae_diagnostics.get('io_sae_score', 0.0):.3f}")
                else:
                    logger.debug("True SAE features provided but flags disabled, using proxy only")
            except Exception as e:
                logger.warning(f"Failed to compute true SAE pathway scores: {e}. Using proxy features only.")
        
        return SAEFeatures(
            dna_repair_capacity=dna_repair_capacity,
            pathway_burden_ddr=pathway_burden_ddr,
            pathway_burden_mapk=pathway_burden_mapk,
            pathway_burden_pi3k=pathway_burden_pi3k,
            pathway_burden_vegf=pathway_burden_vegf,
            pathway_burden_her2=pathway_burden_her2,  # BONUS: HER2 pathway integration
            io_eligible=io_eligible,
            cross_resistance_risk=cross_resistance_risk,
            essentiality_hrr_genes=essentiality_hrr,
            exon_disruption_score=exon_disruption_score,
            hotspot_mutation=hotspot_mutation,  # ⚔️ P0 FIX #3 (Jan 13, 2025)
            hotspot_details=hotspot_details,    # ⚔️ P0 FIX #3 (Jan 13, 2025)
            mechanism_vector=mechanism_vector,
            resistance_signals=resistance_signals,
            provenance=provenance
        )
    
    def _load_sae_feature_mapping(self) -> Dict[str, Any]:
        """
        Load SAE feature→pathway mapping from resources.
        
        Returns:
            Mapping dict with pathway definitions and feature indices
        """
        from pathlib import Path
        import json
        
        mapping_file = Path(__file__).parent.parent / "resources" / "sae_feature_mapping.json"
        
        if not mapping_file.exists():
            logger.warning(f"SAE feature mapping file not found: {mapping_file}. Using placeholder mappings.")
            return {}
        
        try:
            with open(mapping_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load SAE feature mapping: {e}. Using placeholder mappings.")
            return {}
    
    def _compute_sae_diagnostics(self, sae_features: Dict[str, Any]) -> Dict[str, Any]:
        """
        Phase 1: Compute diagnostic scores from true SAE features (32K-dim vector).
        
        This is a DIAGNOSTIC-ONLY function. It does NOT change proxy SAE scoring.
        Instead, it provides transparency into what true SAE features suggest.
        
        Uses real feature→pathway mapping from Sprint 1/2 biomarker analysis.
        
        Args:
            sae_features: True SAE features from /api/sae/extract_features
                {
                    "features": List[float],  # 32K-dim
                    "top_features": List[{"index": int, "value": float}],  # Top k=64
                    "stats": {...},
                    "provenance": {...}
                }
        
        Returns:
            {
                "ddr_sae_score": float,  # 0-1, DDR signature strength
                "io_sae_score": float,   # 0-1, IO eligibility signature strength
                "mapk_sae_score": float, # 0-1, MAPK pathway signature
                "pi3k_sae_score": float | None,  # 0-1, PI3K pathway (if mapped)
                "tp53_sae_score": float | None,  # 0-1, TP53 pathway (if mapped)
                "top_feature_indices": List[int],  # Top k=64 feature indices
                "sparsity": float,
                "mapping_version": str,
                "note": "Diagnostics only - not used for scoring in Phase 1"
            }
        """
        # Extract top features for transparency
        top_features = sae_features.get("top_features", [])
        top_feature_indices = [f["index"] for f in top_features[:10]]  # Top 10 for display
        
        # Extract stats
        stats = sae_features.get("stats", {})
        sparsity = stats.get("sparsity", 0.0)
        
        # Load feature→pathway mapping
        mapping = self._load_sae_feature_mapping()
        pathways = mapping.get("pathways", {})
        mapping_version = mapping.get("metadata", {}).get("version", "unknown")
        
        diagnostics = {
            "top_feature_indices": top_feature_indices,
            "sparsity": sparsity,
            "mapping_version": mapping_version,
            "note": "Diagnostics only - not used for scoring in Phase 1"
        }
        
        # Compute pathway scores from mapped features
        for pathway_name, pathway_data in pathways.items():
            feature_indices = pathway_data.get("feature_indices", [])
            
            if not feature_indices:
                diagnostics[f"{pathway_name}_sae_score"] = None
                continue
            
            # Aggregate feature activations for this pathway
            # Use top_features if available, otherwise use full features array
            pathway_activation = 0.0
            pathway_count = 0
            
            feature_indices_set = set(feature_indices)
            
            # Check top_features first (more efficient)
            for top_feat in top_features:
                idx = top_feat.get("index")
                if idx in feature_indices_set:
                    pathway_activation += abs(top_feat.get("value", 0.0))
                    pathway_count += 1
            
            # If we have full features array, also check it
            full_features = sae_features.get("features", [])
            if full_features and len(full_features) == 32768:
                for idx in feature_indices:
                    if idx < len(full_features):
                        pathway_activation += abs(full_features[idx])
                        pathway_count += 1
            
            # Normalize by number of mapped features
            if pathway_count > 0:
                # Normalize to 0-1 range (heuristic: divide by expected max activation)
                score = min(1.0, pathway_activation / (pathway_count * 2.0))
                diagnostics[f"{pathway_name}_sae_score"] = float(score)
            else:
                diagnostics[f"{pathway_name}_sae_score"] = 0.0
        
        # Ensure standard pathway names are present (for backward compatibility)
        if "ddr_sae_score" not in diagnostics:
            diagnostics["ddr_sae_score"] = diagnostics.get("ddr_sae_score", 0.0)
        if "io_sae_score" not in diagnostics:
            diagnostics["io_sae_score"] = diagnostics.get("io_sae_score", 0.0)
        if "mapk_sae_score" not in diagnostics:
            diagnostics["mapk_sae_score"] = diagnostics.get("mapk_sae_score", 0.0)
        
        # Compute DDR_bin score from diamond features (9 features mapped to DDR pathway)
        # DDR_bin = average activation of diamond features
        diamond_features = []
        for feature_data in mapping.get("features", []):
            feature_mapping = feature_data.get("mapping", {})
            if feature_mapping.get("hypothesis") == "DDR_bin":
                diamond_features.append(feature_data.get("feature_index"))
        
        if diamond_features:
            ddr_bin_activation = 0.0
            ddr_bin_count = 0
            
            diamond_features_set = set(diamond_features)
            
            # Check top_features first (more efficient)
            for top_feat in top_features:
                idx = top_feat.get("index")
                if idx in diamond_features_set:
                    ddr_bin_activation += abs(top_feat.get("value", 0.0))
                    ddr_bin_count += 1
            
            # If we have full features array, also check it
            full_features = sae_features.get("features", [])
            if full_features and len(full_features) == 32768:
                for idx in diamond_features:
                    if idx < len(full_features):
                        ddr_bin_activation += abs(full_features[idx])
                        ddr_bin_count += 1
            
            # Normalize to 0-1 range
            if ddr_bin_count > 0:
                ddr_bin_score = min(1.0, ddr_bin_activation / (len(diamond_features) * 2.0))
                diagnostics["ddr_bin_score"] = float(ddr_bin_score)
            else:
                diagnostics["ddr_bin_score"] = 0.0
        else:
            diagnostics["ddr_bin_score"] = 0.0
        
        return diagnostics
    
    def _compute_essentiality_hrr(
        self, 
        insights_bundle: Dict[str, Any], 
        genes: List[str]
    ) -> float:
        """
        C3: Essentiality contribution for HRR genes
        
        Manager Policy: Average essentiality across HRR genes in patient's profile.
        Weight: 0.15 (modest lift)
        """
        hrr_genes_in_profile = [g for g in genes if g in HRR_GENES]
        
        if not hrr_genes_in_profile:
            return 0.0
        
        # Average essentiality scores for HRR genes
        essentiality_scores = []
        for gene in hrr_genes_in_profile:
            # Insights bundle should have per-gene essentiality
            # For now, use overall essentiality as proxy
            ess_value = insights_bundle.get("essentiality", 0.0)
            essentiality_scores.append(ess_value)
            self.logger.info(f"🔍 [SAE DEBUG] Gene {gene}: essentiality={ess_value} from insights_bundle")
        
        computed_essentiality = sum(essentiality_scores) / len(essentiality_scores) if essentiality_scores else 0.0
        self.logger.info(f"🔍 [SAE DEBUG] Final essentiality_hrr = {computed_essentiality} (avg of {len(essentiality_scores)} HRR genes)")
        return computed_essentiality
    
    def _compute_exon_disruption_score(
        self, 
        insights_bundle: Dict[str, Any], 
        genes: List[str],
        essentiality_hrr: float
    ) -> float:
        """
        C4: Exon disruption scoring
        
        Manager Policy: Only apply when essentiality > 0.65.
        Uses Evo2 multi-window + exon-context scoring.
        """
        if essentiality_hrr < EXON_DISRUPTION_THRESHOLD:
            return 0.0
        
        # Use regulatory insight as proxy for exon disruption
        # (Evo2 exon-context scoring via regulatory endpoint)
        computed_exon_disruption = insights_bundle.get("regulatory", 0.0)
        return computed_exon_disruption
    
    def _compute_dna_repair_capacity(
        self,
        pathway_burden_ddr: float,
        essentiality_hrr: float,
        exon_disruption: float
    ) -> float:
        """
        C5: DNA Repair Capacity (Manager's exact formula)
        
        ⚔️ MANAGER APPROVED FORMULA (Jan 13, 2025):
        Formula: (0.6 × pathway_DDR) + (0.2 × essentiality_HRR_genes) + (0.2 × exon_disruption_score)
        
        Args:
            pathway_burden_ddr: DDR pathway burden (0-1)
            essentiality_hrr: Average essentiality for HRR genes (0-1)
            exon_disruption: Exon disruption score from C4 (0-1)
        
        Manager Policy: MANAGER_ANSWERS_TO_ZO_SAE_QUESTIONS.md (C1, C5)"
        """
        dna_repair_capacity = (
            DNA_REPAIR_CAPACITY_WEIGHTS["pathway_ddr"] * pathway_burden_ddr +
            DNA_REPAIR_CAPACITY_WEIGHTS["essentiality_hrr"] * essentiality_hrr +
            DNA_REPAIR_CAPACITY_WEIGHTS["exon_disruption"] * exon_disruption
        )
        return dna_repair_capacity
    
    def _compute_cross_resistance_risk(
        self, 
        treatment_history: Optional[List[Dict]]
    ) -> float:
        """
        Compute cross-resistance risk based on treatment history.
        
        Simplified for Phase 2:
        - 0.0 if no prior treatments
        - 0.3 if 1 prior treatment
        - 0.6 if 2 prior treatments
        - 0.9 if 3+ prior treatments
        
        Future: Integrate ABCB1 efflux markers, drug class overlaps.
        """
        if not treatment_history:
            return 0.0
        
        num_treatments = len(treatment_history)
        
        if num_treatments == 1:
            return 0.3
        elif num_treatments == 2:
            return 0.6
        else:
            return 0.9
    
    def _detect_resistance(
        self,
        current_hrd: float,
        previous_hrd: Optional[float],
        current_dna_repair: float,
        previous_dna_repair: Optional[float],
        ca125_intelligence: Optional[Dict]
    ) -> Dict[str, Any]:
        """
        C7: Resistance detection (2-of-3 trigger rule)
        
        Manager Policy: Trigger resistance alert if 2 of 3 conditions met:
        1. HRD drop >= 15 points
        2. DNA repair capacity drop >= 0.20
        3. CA-125 inadequate response (from ca125_intelligence)
        
        Returns:
            Dict with trigger status and reasons
        """
        triggers = []
        reasons = []
        
        # Trigger 1: HRD drop
        if previous_hrd is not None:
            hrd_drop = previous_hrd - current_hrd
            if hrd_drop >= RESISTANCE_HRD_DROP_THRESHOLD:
                triggers.append("hrd_drop")
                reasons.append(f"HRD dropped {hrd_drop:.0f} points (threshold: {RESISTANCE_HRD_DROP_THRESHOLD})")
        
        # Trigger 2: DNA repair capacity drop
        if previous_dna_repair is not None:
            dna_repair_drop = previous_dna_repair - current_dna_repair
            if dna_repair_drop >= RESISTANCE_DNA_REPAIR_DROP_THRESHOLD:
                triggers.append("dna_repair_drop")
                reasons.append(f"DNA repair capacity dropped {dna_repair_drop:.2f} (threshold: {RESISTANCE_DNA_REPAIR_DROP_THRESHOLD})")
        
        # Trigger 3: CA-125 inadequate response
        if ca125_intelligence:
            resistance_rule = ca125_intelligence.get("resistance_rule", {})
            if resistance_rule.get("triggered"):
                triggers.append("ca125_inadequate")
                reasons.append("CA-125 inadequate response or on-therapy rise")
        
        # 2-of-3 rule
        resistance_detected = len(triggers) >= 2
        
        return {
            "resistance_detected": resistance_detected,
            "triggers": triggers,
            "reasons": reasons,
            "policy": "2-of-3 trigger rule (MANAGER_ANSWERS_TO_ZO_SAE_QUESTIONS.md C7)"
        }


# Singleton instance
_sae_feature_service = None

def get_sae_feature_service() -> SAEFeatureService:
    """Get singleton SAE Feature Service instance"""
    global _sae_feature_service
    if _sae_feature_service is None:
        _sae_feature_service = SAEFeatureService()
    return _sae_feature_service


def compute_sae_features(
    insights_bundle: Dict[str, Any],
    pathway_scores: Dict[str, float],
    tumor_context: Dict[str, Any],
    treatment_history: Optional[List[Dict]] = None,
    ca125_intelligence: Optional[Dict] = None,
    previous_hrd_score: Optional[float] = None,
    previous_dna_repair_capacity: Optional[float] = None
) -> Dict[str, Any]:
    """
    Convenience function for computing SAE features.
    
    Returns dict representation of SAEFeatures.
    """
    service = get_sae_feature_service()
    features = service.compute_sae_features(
        insights_bundle=insights_bundle,
        pathway_scores=pathway_scores,
        tumor_context=tumor_context,
        treatment_history=treatment_history,
        ca125_intelligence=ca125_intelligence,
        previous_hrd_score=previous_hrd_score,
        previous_dna_repair_capacity=previous_dna_repair_capacity
    )
    return asdict(features)

