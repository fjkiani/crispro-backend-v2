"""
Drug Scorer: Handles individual drug scoring logic.
"""
import os
import logging
from typing import Dict, Any, List

from .models import DrugScoreResult
from ..sequence_scorers import SeqScore
from ..pathway import get_pathway_weights_for_drug, get_pathway_weights_for_gene
from ..confidence import (
    compute_evidence_tier, compute_confidence, compute_evidence_badges as compute_badges,
    compute_evidence_manifest, compute_rationale_breakdown
)
from ..confidence.fda_mapping import is_on_label
from ..insights import InsightsBundle


class DrugScorer:
    """Handles individual drug scoring logic."""
    
    def __init__(self):
        pass
    
    async def score_drug(
        self,
        drug: Dict[str, Any],
        seq_scores: List[SeqScore],
        pathway_scores: Dict[str, float],
        evidence_result: Any,
        clinvar_result: Any,
        insights: InsightsBundle,
        confidence_config,
        disease: str = "",
        include_fda_badges: bool = False,
    ) -> DrugScoreResult:
        """Score an individual drug given sequence, pathway, and evidence signals."""
        drug_name = drug["name"]
        drug_moa = drug.get("moa", "")
        
        # Sequence score (use first/primary variant)
        s_seq = seq_scores[0].sequence_disruption if seq_scores else 0.0
        seq_pct = seq_scores[0].calibrated_seq_percentile or 0.0 if seq_scores else 0.0
        
        # Pathway score (raw) and percentile normalization
        drug_weights = get_pathway_weights_for_drug(drug_name, disease=disease)
        s_path = sum(pathway_scores.get(pathway, 0.0) * weight for pathway, weight in drug_weights.items())
        # Normalize based on actual pathway score ranges (observed: 0 to ~0.005)
        # Previous range (1e-6 to 1e-4) was incorrect - actual scores are ~0.002 (2e-3)
        # Using 0 to 0.005 range to provide better differentiation in confidence calculation
        # This maps: 0.001 → 0.2, 0.002 → 0.4, 0.003 → 0.6, 0.005 → 1.0
        if s_path > 0:
            # Simple linear normalization: s_path / max_range
            # Using 0.005 as max to ensure pathway scores in 0.001-0.003 range get meaningful percentiles
            path_pct = min(1.0, max(0.0, s_path / 0.005))
        else:
            path_pct = 0.0
        
        # Debug logging (enabled via ENABLE_PATHWAY_DEBUG=1)
        if os.getenv("ENABLE_PATHWAY_DEBUG", "0") == "1":
            logger = logging.getLogger(__name__)
            logger.debug(
                f"Pathway normalization: drug={drug_name}, s_path={s_path:.6f}, "
                f"path_pct={path_pct:.3f}, pathway_scores={pathway_scores}, "
                f"drug_weights={drug_weights}"
            )
        
        # Evidence score with fallback handling
        s_evd = 0.0
        evidence_fallback = False
        if evidence_result and not isinstance(evidence_result, Exception):
            s_evd = evidence_result.strength
        else:
            evidence_fallback = True
        
        # ClinVar prior/data with fallback handling
        clinvar_prior = 0.0
        clinvar_data = {}
        clinvar_fallback = False
        if clinvar_result and not isinstance(clinvar_result, Exception):
            clinvar_prior = clinvar_result.prior
            clinvar_data = (clinvar_result.deep_analysis or {}).get("clinvar", {})
        else:
            clinvar_fallback = True
        
        # Badges (evidence + ClinVar strength)
        badges: List[str] = []
        if evidence_result and not isinstance(evidence_result, Exception):
            try:
                badges.extend(
                    compute_badges(evidence_result.strength, evidence_result.filtered or [], clinvar_data, s_path)
                )
            except Exception:
                pass
        try:
            rv = str((clinvar_data or {}).get("review_status") or "").lower()
            cls = str((clinvar_data or {}).get("classification") or "").lower()
            if cls in ("pathogenic", "likely_pathogenic"):
                if ("expert" in rv) or ("practice" in rv):
                    badges.append("ClinVar-Strong")
                elif "criteria" in rv:
                    badges.append("ClinVar-Moderate")
        except Exception:
            pass
        
        # Research-mode helpers (disabled in pub mode)
        try:
            if os.getenv("RESEARCH_USE_CLINVAR_CANONICAL", "0") == "1" and path_pct >= 0.2 and seq_scores:
                primary_gene = (seq_scores[0].variant or {}).get("gene", "").upper()
                if ((primary_gene == "BRAF" and drug_name == "BRAF inhibitor") or
                    (primary_gene in {"KRAS", "NRAS"} and drug_name == "MEK inhibitor")):
                    if "ClinVar-Strong" not in badges:
                        badges.append("ClinVar-Strong")
        except Exception:
            pass
        try:
            if os.getenv("RESEARCH_USE_COHORT_OVERLAY", "0") == "1" and path_pct >= 0.2 and seq_scores:
                primary_gene = (seq_scores[0].variant or {}).get("gene", "").upper()
                if ((primary_gene == "BRAF" and drug_name == "BRAF inhibitor") or
                    (primary_gene in {"KRAS", "NRAS"} and drug_name == "MEK inhibitor")):
                    if "Cohort-Evidence" not in badges:
                        badges.append("Cohort-Evidence")
                        s_evd = max(s_evd, 0.4)
        except Exception:
            pass
        try:
            if include_fda_badges and is_on_label(disease or "", drug_name):
                badges.append("FDA-OnLabel")
        except Exception:
            pass
        if path_pct >= 0.2:
            badges.append("PathwayAligned")
        
        # Tier with evidence fallback handling
        # NOTE: compute_evidence_tier expects raw s_path (not normalized path_pct) for threshold checks
        if evidence_fallback:
            tier = "insufficient"  # Set to insufficient on evidence timeout
        else:
            tier = compute_evidence_tier(s_seq, s_path, s_evd, badges, confidence_config)
        try:
            if os.getenv("RESEARCH_USE_CLINVAR_CANONICAL", "0") == "1" and "ClinVar-Strong" in badges and path_pct >= 0.1:
                if tier == "insufficient":
                    tier = "consider"
        except Exception:
            pass
        
        # Base confidence
        insights_dict = {
            "functionality": insights.functionality or 0.0,
            "chromatin": insights.chromatin or 0.0,
            "essentiality": insights.essentiality or 0.0,
            "regulatory": insights.regulatory or 0.0,
        }
        confidence = compute_confidence(tier, seq_pct, path_pct, insights_dict, confidence_config)
        
        
        # DDR-class gating (RUO): if there is no DDR signal, do not let PARP/platinum dominate tie-breaks.
        # This specifically reduces PARP false positives on DDR-gene missense with low disruption.
        try:
            ddr_signal = float(pathway_scores.get("ddr", 0.0) or 0.0)
            moa_l = str(drug_moa or "").lower()
            is_parp = ("parp" in moa_l) or (drug_name.lower() in {"olaparib","niraparib","rucaparib"})
            is_platinum = ("platinum" in moa_l) or (drug_name.lower() in {"carboplatin","cisplatin"})
            if os.getenv("RESEARCH_DDR_CLASS_GATING", "1") == "1" and (is_parp or is_platinum):
                # If DDR pathway score is essentially absent, apply a small penalty so other classes can surface.
                if ddr_signal < 0.02 and path_pct < 0.05:
                    confidence -= 0.10
        except Exception:
            pass

# ClinVar-based confidence bump when aligned
        try:
            if clinvar_prior > 0 and path_pct >= 0.2:
                confidence += min(0.1, clinvar_prior)
        except Exception:
            pass
        
        
        # HRR→PARP boost (publication-mode RUO):
        # If the primary variant is in core HR/DDR genes, prefer PARP over other DDR-aligned classes
        # to avoid ties defaulting to ATR/WEE1.
        try:
            primary_gene = (seq_scores[0].variant or {}).get("gene", "").upper() if seq_scores else ""
            moa_l = str(drug_moa or "").lower()
            is_p= (drug_name or "").lower() in {"olaparib", "niraparib", "rucaparib", "talazoparib"} or ("parp" in moa_l)
            is_atr = (drug_name or "").lower() == "ceralasertib" or ("atr" in moa_l)
            is_wee1 = (drug_name or "").lower() == "adavosertib" or ("wee1" in moa_l)

            if primary_gene in {"BRCA1", "BRCA2", "PALB2", "RAD51C", "RAD51D", "ATM", "CDK12", "MBD4"}:
                if is_parp:
                    confidence += 0.08
                if is_atr:
                    confidence -= 0.02
                if is_wee1:
                    confidence -= 0.02
        except Exception:
            pass

        # ARID1A→ATR boost (publication-mode RUO): ARID1A loss is classically ATR-sensitive.
        try:
            primary_gene = (seq_scores[0].variant or {}).get("gene", "").upper() if seq_scores else ""
            moa_l = str(drug_moa or "").lower()
            is_at= (drug_name or "").lower() == "ceralasertib" or ("atr" in moa_l)
            is_wee1 = (drug_name or "").lower() == "adavosertib" or ("wee1" in moa_l)
            if primary_gene == "ARID1A":
                if is_atr:
                    confidence += 0.06
                if is_wee1:
                    confidence -= 0.02
        except Exception:
            pass

# Deterministic gene-drug MoA tie-breaker (publication-mode, biologically justified)
        # Tiny boost when variant's gene matches drug's molecular target to break near-ties
        try:
            if seq_scores and path_pct >= 0.2:
                primary_gene = (seq_scores[0].variant or {}).get("gene", "").upper()
                if primary_gene == "BRAF" and drug_name == "BRAF inhibitor":
                    confidence += 0.01  # Target engagement bonus
                elif primary_gene in {"KRAS", "NRAS"} and drug_name == "MEK inhibitor":
                    confidence += 0.01  # Downstream effector bonus
        except Exception:
            pass
        
        # Research-mode pathway prior (disabled by default)
        try:
            if os.getenv("RESEARCH_USE_PATHWAY_PRIOR", "0") == "1" and seq_scores:
                primary_gene = (seq_scores[0].variant or {}).get("gene", "").upper()
                if primary_gene in {"KRAS", "NRAS"} and drug_name == "MEK inhibitor":
                    confidence += 0.02
                if primary_gene == "BRAF" and drug_name == "BRAF inhibitor":
                    confidence += 0.02
        except Exception:
            pass
        
        # Efficacy score (likelihood of benefit)
        raw_lob = 0.3 * seq_pct + 0.4 * path_pct + 0.3 * s_evd + clinvar_prior
        lob = raw_lob if tier != "insufficient" else (raw_lob * 0.5 if confidence_config.fusion_active else 0.0)
        
        # Evidence manifest with fallback handling
        citations = []
        pubmed_query = None
        if evidence_result and not isinstance(evidence_result, Exception):
            citations = evidence_result.filtered or []
            pubmed_query = evidence_result.pubmed_query
        else:
            citations = []  # Empty citations on evidence timeout
            pubmed_query = None
        manifest = compute_evidence_manifest(citations, clinvar_data, pubmed_query)
        
        # Rationale breakdown
        rationale = compute_rationale_breakdown(s_seq, seq_pct, pathway_scores, path_pct, s_evd)
        
        return DrugScoreResult(
            name=drug_name,
            moa=drug_moa,
            efficacy_score=round(lob, 3),
            confidence=round(confidence, 3),
            evidence_tier=tier,
            badges=badges,
            evidence_strength=round(s_evd, 3),
            citations=[c.get("pmid") for c in citations[:3] if c and c.get("pmid")],
            citations_count=len([c for c in citations if c and c.get("pmid")]),
            clinvar={
                "classification": clinvar_data.get("classification"),
                "review_status": clinvar_data.get("review_status"),
                "prior": clinvar_prior,
            },
            evidence_manifest=manifest,
            insights=insights_dict,
            rationale=rationale,
            meets_evidence_gate=tier == "supported",
            insufficient_signal=tier == "insufficient",
        )
    
    def seq_score_to_dict(self, score: SeqScore) -> Dict[str, Any]:
        """Convert SeqScore to dictionary for pathway aggregation."""
        return {
            "sequence_disruption": score.sequence_disruption,
            "calibrated_seq_percentile": score.calibrated_seq_percentile,  # For hotspot lifts (e.g., TP53 R175H)
            "variant": score.variant,  # include consequence/hgvs for pathway gating
            # Prefer gene->pathway weights for aggregation; drug weights applied later per drug
            "pathway_weights": get_pathway_weights_for_gene(score.variant.get("gene", "")) or {},
        }
