"""
SAE (Sparse Autoencoder) Service - Real Data Transformation

Transforms existing real data sources (Evo2, Insights, Toxicity, Off-Target, ClinVar, AlphaMissense)
into interpretable SAE features that explain confidence scores with full transparency.

NO MOCKS - Only real data transformations with provenance tracking.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

@dataclass
class SAEFeature:
    """
    Interpretable feature derived from real data sources.
    
    Attributes:
        id: Feature identifier (e.g., "exon_disruption")
        name: Human-readable name
        activation: Feature strength [0, 1]
        impact: "positive" (boosts confidence) or "negative" (lowers confidence)
        explanation: What this feature means biologically
        provenance: Data source (e.g., "evo2_delta_magnitude")
        threshold: Activation threshold for display (optional)
        raw_value: Original raw value before normalization (optional)
    """
    id: str
    name: str
    activation: float
    impact: str  # "positive" or "negative"
    explanation: str
    provenance: str
    threshold: Optional[float] = None
    raw_value: Optional[Any] = None
    

@dataclass
class SAEBundle:
    """
    Complete SAE feature set for a variant analysis.
    
    Attributes:
        features: List of extracted SAE features
        boosting_features: Feature IDs boosting confidence
        limiting_features: Feature IDs limiting confidence
        overall_impact: Net SAE contribution to confidence
        provenance: Full provenance tracking
    """
    features: List[SAEFeature] = field(default_factory=list)
    boosting_features: List[str] = field(default_factory=list)
    limiting_features: List[str] = field(default_factory=list)
    overall_impact: float = 0.0
    provenance: Dict[str, Any] = field(default_factory=dict)


def extract_sae_features_from_real_data(
    variant: Dict[str, Any],
    evo_scores: Optional[Dict[str, Any]] = None,
    insights: Optional[Dict[str, Any]] = None,
    pathway_disruption: Optional[Dict[str, Any]] = None,
    fusion_score: Optional[float] = None,
    clinvar_data: Optional[Dict[str, Any]] = None,
    toxicity_factors: Optional[List[Dict[str, Any]]] = None,
    offtarget_result: Optional[Dict[str, Any]] = None,
    evidence_data: Optional[Dict[str, Any]] = None,
    cohort_signals: Optional[Dict[str, Any]] = None,
    treatment_line_data: Optional[Dict[str, Any]] = None,
) -> SAEBundle:
    """
    Transform real data sources into interpretable SAE features.
    
    Core 6 Features (P2 Priority):
    1. exon_disruption (from Evo2 delta + hotspot floor)
    2. hotspot_mutation (from AlphaMissense/hotspot/ClinVar)
    3. essentiality_signal (from Insights essentiality)
    4. DNA_repair_capacity (from Toxicity pathway overlap)
    5. seed_region_quality (from Off-target heuristics)
    6. cohort_overlap (from Cohort signals)
    
    Treatment Line Features (P2 Extension):
    7. line_appropriateness (from Panel Config + NCCN)
    8. cross_resistance_risk (from Prior Therapies + Cross-Resistance Map)
    9. sequencing_fitness (from Line Fit + Cross-Resistance)
    
    Args:
        variant: Variant information (gene, position, ref, alt)
        evo_scores: Evo2 delta scores and calibration
        insights: Functionality, Chromatin, Essentiality, Regulatory
        pathway_disruption: Pathway impact scores
        fusion_score: AlphaMissense score (if available)
        clinvar_data: ClinVar classification and review status
        toxicity_factors: Toxicity risk factors
        offtarget_result: Off-target heuristic analysis
        evidence_data: Literature evidence and citations
        cohort_signals: Cohort coverage and validation
        treatment_line_data: Treatment line context (line_appropriateness, cross_resistance_risk, sequencing_fitness)
    
    Returns:
        SAEBundle with all derived features and provenance
    """
    features = []
    gene = variant.get("gene", "UNKNOWN")
    
    logger.info(f"[SAE] Extracting features for {gene} variant...")
    
    # ========================================
    # FEATURE 1: EXON_DISRUPTION
    # ========================================
    if evo_scores:
        delta = abs(evo_scores.get("delta", 0.0))
        calibrated_pct = evo_scores.get("calibrated_seq_percentile", 0.0)
        hotspot_applied = evo_scores.get("hotspot_floor_applied", False)
        
        # Use calibrated percentile if available (includes hotspot floor), else normalize delta
        exon_disruption = calibrated_pct if calibrated_pct > 0 else min(delta * 1000, 1.0)
        
        if exon_disruption > 0.05:  # Threshold for display (5% minimum)
            impact = "positive" if exon_disruption > 0.5 else "negative"
            provenance = "hotspot_calibration" if hotspot_applied else "evo2_delta_magnitude"
            
            features.append(SAEFeature(
                id="exon_disruption",
                name="Exon Disruption",
                activation=exon_disruption,
                impact=impact,
                explanation=f"Variant {'significantly disrupts' if exon_disruption > 0.7 else 'moderately disrupts' if exon_disruption > 0.4 else 'minimally disrupts'} exon structure",
                provenance=provenance,
                threshold=0.5,
                raw_value=delta
            ))
            logger.info(f"[SAE] exon_disruption: {exon_disruption:.3f} (impact: {impact}, source: {provenance})")
    
    # ========================================
    # FEATURE 2: HOTSPOT_MUTATION
    # ========================================
    hotspot_score = None
    hotspot_provenance = None
    
    # Priority 1: AlphaMissense
    if fusion_score and fusion_score > 0.5:
        hotspot_score = fusion_score
        hotspot_provenance = "alphamissense"
    
    # Priority 2: Hotspot floor from Evo2
    elif evo_scores and evo_scores.get("hotspot_floor_applied"):
        hotspot_score = evo_scores.get("calibrated_seq_percentile", 0.85)
        hotspot_provenance = "hotspot_calibration"
    
    # Priority 3: ClinVar Pathogenic
    elif clinvar_data and clinvar_data.get("classification") in ["Pathogenic", "Likely pathogenic"]:
        hotspot_score = 0.95
        hotspot_provenance = "clinvar_classification"
    
    if hotspot_score and hotspot_score > 0.5:
        features.append(SAEFeature(
            id="hotspot_mutation",
            name="Known Hotspot",
            activation=hotspot_score,
            impact="positive",
            explanation=f"Variant matches known pathogenic hotspot pattern (confidence: {hotspot_score:.2f})",
            provenance=hotspot_provenance,
            threshold=0.5,
            raw_value=hotspot_score
        ))
        logger.info(f"[SAE] hotspot_mutation: {hotspot_score:.3f} (source: {hotspot_provenance})")
    
    # ========================================
    # FEATURE 3: ESSENTIALITY_SIGNAL
    # ========================================
    if insights and "essentiality" in insights:
        essentiality = insights["essentiality"]
        
        if essentiality is not None and essentiality > 0.01:  # Show if present
            impact = "positive" if essentiality > 0.4 else "negative"
            
            # Categorize essentiality
            if essentiality > 0.7:
                category = "essential"
            elif essentiality > 0.4:
                category = "moderately essential"
            else:
                category = "non-essential"
            
            features.append(SAEFeature(
                id="essentiality_signal",
                name="Gene Essentiality",
                activation=essentiality,
                impact=impact,
                explanation=f"Variant affects {category} gene (dependency: {essentiality:.2f})",
                provenance="evo2_essentiality_endpoint",
                threshold=0.7,
                raw_value=essentiality
            ))
            logger.info(f"[SAE] essentiality_signal: {essentiality:.3f} (category: {category})")
    
    # ========================================
    # FEATURE 4: DNA_REPAIR_CAPACITY
    # ========================================
    if toxicity_factors:
        dna_repair_burden = 0.0
        repair_details = []
        
        for factor in toxicity_factors:
            factor_type = factor.get("type", "")
            detail = factor.get("detail", "")
            weight = factor.get("weight", 0.0)
            
            # Look for DNA repair pathway factors
            if factor_type == "pathway" and "DNA_REPAIR" in detail.upper():
                dna_repair_burden = max(dna_repair_burden, weight)
                repair_details.append(detail)
        
        if dna_repair_burden > 0.3:
            features.append(SAEFeature(
                id="DNA_repair_capacity",
                name="DNA Repair Burden",
                activation=dna_repair_burden,
                impact="positive",  # For platinum agents, DNA repair burden = therapeutic opportunity
                explanation=f"DNA repair pathway burden detected (score: {dna_repair_burden:.2f})",
                provenance="toxicity_pathway_mapping",
                threshold=0.5,
                raw_value={"burden": dna_repair_burden, "details": repair_details}
            ))
            logger.info(f"[SAE] DNA_repair_capacity: {dna_repair_burden:.3f}")
    
    # ========================================
    # FEATURE 5: SEED_REGION_QUALITY
    # ========================================
    if offtarget_result and "guides" in offtarget_result:
        guides = offtarget_result["guides"]
        
        if guides:
            # Calculate average heuristic score across all guides
            avg_heuristic = sum(g.get("heuristic_score", 0.0) for g in guides) / len(guides)
            
            if avg_heuristic > 0.1:
                impact = "positive" if avg_heuristic > 0.7 else "negative"
                
                # Categorize quality
                if avg_heuristic > 0.8:
                    quality = "High"
                elif avg_heuristic > 0.6:
                    quality = "Moderate"
                else:
                    quality = "Low"
                
                features.append(SAEFeature(
                    id="seed_region_quality",
                    name="CRISPR Guide Quality",
                    activation=avg_heuristic,
                    impact=impact,
                    explanation=f"CRISPR guide seed region quality: {quality} (score: {avg_heuristic:.2f})",
                    provenance="offtarget_heuristic_analysis",
                    threshold=0.7,
                    raw_value={"avg_heuristic": avg_heuristic, "guide_count": len(guides)}
                ))
                logger.info(f"[SAE] seed_region_quality: {avg_heuristic:.3f} (quality: {quality})")
    
    # ========================================
    # FEATURE 6: COHORT_OVERLAP
    # ========================================
    if cohort_signals:
        cohort_overlap = cohort_signals.get("coverage_fraction", 0.0)
        cohort_count = cohort_signals.get("cohort_count", 0)
        
        if cohort_overlap > 0.05:
            impact = "positive" if cohort_overlap > 0.2 else "negative"
            
            features.append(SAEFeature(
                id="cohort_overlap",
                name="Cohort Validation",
                activation=cohort_overlap,
                impact=impact,
                explanation=f"Variant validated in {int(cohort_overlap * 100)}% of clinical cohort",
                provenance="cohort_extraction_metadata",
                threshold=0.2,
                raw_value={"coverage": cohort_overlap, "cohorts": cohort_count}
            ))
            logger.info(f"[SAE] cohort_overlap: {cohort_overlap:.3f}")
        elif cohort_signals:  # Cohort data exists but no overlap
            features.append(SAEFeature(
                id="cohort_overlap",
                name="Cohort Validation",
                activation=0.0,
                impact="negative",
                explanation="No cohort validation available (limited real-world data)",
                provenance="cohort_extraction_metadata",
                threshold=0.2,
                raw_value={"coverage": 0.0, "cohorts": cohort_count}
            ))
            logger.info("[SAE] cohort_overlap: 0.0 (no overlap detected)")
    
    # ========================================
    # FEATURE 7: LINE_APPROPRIATENESS
    # ========================================
    if treatment_line_data:
        line_appropriateness = treatment_line_data.get("line_appropriateness", None)
        nccn_category = treatment_line_data.get("nccn_category", "unknown")
        line_rationale = treatment_line_data.get("line_rationale", "")
        
        if line_appropriateness is not None and line_appropriateness > 0.0:
            impact = "positive" if line_appropriateness >= 0.8 else "negative"
            
            # Categorize line fit
            if line_appropriateness >= 0.95:
                fit_category = "Perfect"
            elif line_appropriateness >= 0.8:
                fit_category = "Good"
            elif line_appropriateness >= 0.6:
                fit_category = "Moderate"
            else:
                fit_category = "Poor"
            
            features.append(SAEFeature(
                id="line_appropriateness",
                name="Treatment Line Fit",
                activation=line_appropriateness,
                impact=impact,
                explanation=f"{fit_category} fit for current treatment line (NCCN Category {nccn_category})",
                provenance="panel_config_nccn_metadata",
                threshold=0.8,
                raw_value={"score": line_appropriateness, "nccn": nccn_category, "rationale": line_rationale}
            ))
            logger.info(f"[SAE] line_appropriateness: {line_appropriateness:.3f} (NCCN {nccn_category}, fit: {fit_category})")
    
    # ========================================
    # FEATURE 8: CROSS_RESISTANCE_RISK
    # ========================================
    if treatment_line_data:
        cross_resistance_risk = treatment_line_data.get("cross_resistance_risk", 0.0)
        cross_resistance_rationale = treatment_line_data.get("cross_resistance_rationale", "")
        prior_therapies = treatment_line_data.get("prior_therapies", [])
        
        if cross_resistance_risk > 0.0:
            # Cross-resistance is always a limiting factor
            impact = "negative"
            
            # Categorize risk level
            if cross_resistance_risk >= 0.5:
                risk_category = "High"
            elif cross_resistance_risk >= 0.3:
                risk_category = "Moderate"
            elif cross_resistance_risk >= 0.1:
                risk_category = "Low"
            else:
                risk_category = "Minimal"
            
            features.append(SAEFeature(
                id="cross_resistance_risk",
                name="Resistance Risk",
                activation=cross_resistance_risk,
                impact=impact,
                explanation=f"{risk_category} cross-resistance risk with prior therapies ({cross_resistance_rationale})",
                provenance="cross_resistance_map",
                threshold=0.3,  # >30% is concerning
                raw_value={"risk": cross_resistance_risk, "prior_therapies": prior_therapies, "rationale": cross_resistance_rationale}
            ))
            logger.info(f"[SAE] cross_resistance_risk: {cross_resistance_risk:.3f} (risk: {risk_category})")
    
    # ========================================
    # FEATURE 9: SEQUENCING_FITNESS
    # ========================================
    if treatment_line_data:
        sequencing_fitness = treatment_line_data.get("sequencing_fitness", None)
        current_line = treatment_line_data.get("current_line", 0)
        
        if sequencing_fitness is not None and sequencing_fitness > 0.0:
            impact = "positive" if sequencing_fitness >= 0.7 else "negative"
            
            # Categorize sequencing quality
            if sequencing_fitness >= 0.9:
                seq_category = "Excellent"
            elif sequencing_fitness >= 0.7:
                seq_category = "Good"
            elif sequencing_fitness >= 0.5:
                seq_category = "Fair"
            else:
                seq_category = "Poor"
            
            features.append(SAEFeature(
                id="sequencing_fitness",
                name="Sequencing Score",
                activation=sequencing_fitness,
                impact=impact,
                explanation=f"{seq_category} sequencing fitness for line {current_line} (combines line fit + resistance risk)",
                provenance="treatment_line_integration",
                threshold=0.7,
                raw_value={"fitness": sequencing_fitness, "line": current_line}
            ))
            logger.info(f"[SAE] sequencing_fitness: {sequencing_fitness:.3f} (category: {seq_category}, line: {current_line})")
    
    # ========================================
    # CLASSIFY FEATURES & CALCULATE IMPACT
    # ========================================
    boosting = [
        f.id for f in features 
        if f.impact == "positive" and f.activation >= (f.threshold or 0.5)
    ]
    
    limiting = [
        f.id for f in features 
        if f.impact == "negative" or f.activation < (f.threshold or 0.5)
    ]
    
    # Calculate overall SAE impact (weighted)
    boost_score = 0.0
    if boosting:
        boost_score = sum(f.activation for f in features if f.id in boosting) / len(boosting)
    
    limit_score = 0.0
    if limiting:
        limit_score = sum((f.threshold or 0.5) - f.activation for f in features if f.id in limiting) / len(limiting)
    
    overall_impact = boost_score - limit_score
    
    logger.info(f"[SAE] Extracted {len(features)} features: {len(boosting)} boosting, {len(limiting)} limiting")
    logger.info(f"[SAE] Overall impact: {overall_impact:.3f}")
    
    return SAEBundle(
        features=features,
        boosting_features=boosting,
        limiting_features=limiting,
        overall_impact=overall_impact,
        provenance={
            "method": "real_data_transformation",
            "data_sources": list(set([f.provenance for f in features])),
            "feature_count": len(features),
            "boosting_count": len(boosting),
            "limiting_count": len(limiting),
            "gene": gene
        }
    )


def sae_features_to_dict(sae_bundle: SAEBundle) -> Dict[str, Any]:
    """
    Convert SAEBundle to dictionary for JSON serialization.
    
    Args:
        sae_bundle: SAEBundle object
    
    Returns:
        Dictionary representation suitable for API response
    """
    return {
        "features": [
            {
                "id": f.id,
                "name": f.name,
                "activation": f.activation,
                "impact": f.impact,
                "explanation": f.explanation,
                "provenance": f.provenance,
                "threshold": f.threshold,
                "raw_value": f.raw_value
            }
            for f in sae_bundle.features
        ],
        "boosting_features": sae_bundle.boosting_features,
        "limiting_features": sae_bundle.limiting_features,
        "overall_impact": sae_bundle.overall_impact,
        "provenance": sae_bundle.provenance
    }

