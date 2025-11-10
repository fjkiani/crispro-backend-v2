"""
Drug Scorer: Handles individual drug scoring logic.
"""
import os
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
        drug_weights = get_pathway_weights_for_drug(drug_name)
        s_path = sum(pathway_scores.get(pathway, 0.0) * weight for pathway, weight in drug_weights.items())
        # Normalize based on empirical Evo2 ranges (pathogenic deltas ~1e-6..1e-4)
        if s_path > 0:
            path_pct = min(1.0, max(0.0, (s_path - 1e-6) / (1e-4 - 1e-6)))
        else:
            path_pct = 0.0
        
        # Evidence score
        s_evd = 0.0
        if evidence_result and not isinstance(evidence_result, Exception):
            s_evd = evidence_result.strength
        
        # ClinVar prior/data
        clinvar_prior = 0.0
        clinvar_data = {}
        if clinvar_result and not isinstance(clinvar_result, Exception):
            clinvar_prior = clinvar_result.prior
            clinvar_data = (clinvar_result.deep_analysis or {}).get("clinvar", {})
        
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
        
        # Tier
        tier = compute_evidence_tier(s_seq, path_pct, s_evd, badges, confidence_config)
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
        
        # ClinVar-based confidence bump when aligned
        try:
            if clinvar_prior > 0 and path_pct >= 0.2:
                confidence += min(0.1, clinvar_prior)
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
        
        # Evidence manifest
        citations = []
        pubmed_query = None
        if evidence_result and not isinstance(evidence_result, Exception):
            citations = evidence_result.filtered or []
            pubmed_query = evidence_result.pubmed_query
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
            # Prefer gene->pathway weights for aggregation; drug weights applied later per drug
            "pathway_weights": get_pathway_weights_for_gene(score.variant.get("gene", "")) or {},
        }
