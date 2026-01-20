"""
Safety service for toxicity risk and off-target preview.

Implements conservative, RUO-focused risk assessment using:
- S: Gene essentiality/regulatory (optional)
- P: MoA → toxicity pathway overlap
- E: ClinVar pharmacogene priors
"""

import uuid
import math
from typing import List, Dict, Any
from datetime import datetime

from api.schemas.safety import (
    ToxicityRiskRequest, ToxicityRiskResponse, ToxicityFactor,
    OffTargetPreviewRequest, OffTargetPreviewResponse,
    GuideRNA, GuideRNAScore
)
from api.services.toxicity_pathway_mappings import (
    is_pharmacogene, get_pharmacogene_risk_weight,
    compute_pathway_overlap, get_moa_toxicity_weights,
    get_mitigating_foods  # THE MOAT
)


class SafetyService:
    """Service for toxicity risk assessment and off-target preview."""
    
    def __init__(self):
        pass
    
    async def compute_toxicity_risk(self, request: ToxicityRiskRequest) -> ToxicityRiskResponse:
        """
        Compute toxicity risk score based on germline variants, drug MoA, and clinical context.
        
        Conservative approach: Flag potential risks rather than miss them.
        """
        run_id = str(uuid.uuid4())
        factors: List[ToxicityFactor] = []
        
        # Extract germline genes
        germline_genes = []
        for variant in request.patient.germlineVariants:
            if variant.gene:
                germline_genes.append(variant.gene)
        
        # Factor 1: Pharmacogene variants (E signal)
        pharmacogene_weight = 0.0
        for gene in germline_genes:
            if is_pharmacogene(gene):
                weight = get_pharmacogene_risk_weight(gene)
                pharmacogene_weight = max(pharmacogene_weight, weight)  # Take max for multiple PGx genes
                factors.append(ToxicityFactor(
                    type="germline",
                    detail=f"Germline variant in pharmacogene {gene} (affects drug metabolism)",
                    weight=weight,
                    confidence=0.7  # Conservative confidence for static PGx list
                ))
        
        # Factor 2: MoA → Toxicity pathway overlap (P signal)
        pathway_weight = 0.0
        pathway_overlaps = {}  # Store for mitigating foods calculation (THE MOAT)
        if request.candidate.moa and germline_genes:
            pathway_overlaps = compute_pathway_overlap(germline_genes, request.candidate.moa)
            for pathway, overlap_score in pathway_overlaps.items():
                if overlap_score > 0.1:  # Only include meaningful overlaps
                    pathway_weight += overlap_score
                    factors.append(ToxicityFactor(
                        type="pathway",
                        detail=f"MoA overlaps {pathway.replace('_', ' ')} pathway (germline variants present)",
                        weight=overlap_score,
                        confidence=0.6  # Moderate confidence for pathway inference
                    ))
        
        # Factor 3: Disease/tissue context (optional, conservative)
        tissue_weight = 0.0
        if request.context.tissue:
            # Placeholder: Could integrate tissue-specific expression data
            # For now, just add small weight for tissue awareness
            tissue_weight = 0.05
            factors.append(ToxicityFactor(
                type="tissue",
                detail=f"Tissue-specific risk for {request.context.tissue} (preliminary)",
                weight=tissue_weight,
                confidence=0.3  # Low confidence without expression data
            ))
        
        # Compute overall risk score (sum of factors, capped at 1.0)
        raw_score = pharmacogene_weight + pathway_weight + tissue_weight
        risk_score = min(1.0, raw_score)
        
        # Compute overall confidence (weighted average of factor confidences)
        if factors:
            total_weight = sum(f.weight for f in factors)
            confidence = sum(f.confidence * f.weight for f in factors) / total_weight if total_weight > 0 else 0.5
        else:
            confidence = 0.5  # Baseline confidence when no factors detected
        
        # Conservative adjustment: Lower confidence for high-risk assessments (need more validation)
        if risk_score > 0.5:
            confidence *= 0.8
        
        # Generate plain-English reason
        if not factors:
            reason = "No germline toxicity factors detected (limited data available)"
        elif pharmacogene_weight > 0 and pathway_weight > 0:
            reason = f"Germline pharmacogene variants + MoA pathway overlap (risk score: {risk_score:.2f})"
        elif pharmacogene_weight > 0:
            reason = f"Germline pharmacogene variants detected (affects drug metabolism)"
        elif pathway_weight > 0:
            reason = f"MoA overlaps toxicity pathways with germline variants"
        else:
            reason = f"Minor toxicity signals detected (low confidence)"
        
        # Provenance
        provenance = {
            "run_id": run_id,
            "profile": request.options.get("profile", "baseline"),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "methods": ["toxicity_v1", "pgx_static_list", "pathway_overlap"],
            "cache": "miss",
            "germline_genes_analyzed": len(germline_genes),
            "factors_detected": len(factors)
        }
        
        # Evidence (placeholder for P1, citations in P2)
        evidence = {
            "citations": [],
            "badges": [],
            "note": "Evidence integration in development (P2)"
        }
        
        # THE MOAT: Get mitigating foods based on detected toxicity pathways
        mitigating_foods = get_mitigating_foods(pathway_overlaps) if pathway_overlaps else []
        
        return ToxicityRiskResponse(
            risk_score=risk_score,
            confidence=confidence,
            reason=reason,
            factors=factors,
            mitigating_foods=mitigating_foods,  # THE MOAT
            evidence=evidence,
            provenance=provenance
        )
    
    async def preview_off_targets(self, request: OffTargetPreviewRequest) -> OffTargetPreviewResponse:
        """
        Heuristic off-target preview for guide RNAs (P1: No genome alignment yet).
        
        Scores based on:
        - GC content (optimal 40-60%)
        - Homopolymer runs (>4bp is risky)
        - Seed region quality (12bp PAM-proximal region)
        """
        run_id = str(uuid.uuid4())
        scored_guides: List[GuideRNAScore] = []
        
        for guide in request.guides:
            seq = guide.seq.upper()
            
            # 1) GC content
            gc_count = seq.count('G') + seq.count('C')
            gc_content = gc_count / len(seq) if len(seq) > 0 else 0.0
            
            # GC score: Optimal 0.4-0.6, penalize extremes
            if 0.4 <= gc_content <= 0.6:
                gc_score = 1.0
            elif gc_content < 0.3 or gc_content > 0.7:
                gc_score = 0.3  # High penalty
            else:
                # Linear decay from optimal range
                if gc_content < 0.4:
                    gc_score = 0.3 + 0.7 * (gc_content - 0.3) / 0.1
                else:
                    gc_score = 0.3 + 0.7 * (0.7 - gc_content) / 0.1
            
            # 2) Homopolymer detection (runs of 5+ same nucleotide)
            homopolymer = False
            homopolymer_penalty = 1.0
            for nuc in ['A', 'T', 'G', 'C']:
                if nuc * 5 in seq:
                    homopolymer = True
                    homopolymer_penalty = 0.5  # 50% penalty
                    break
            
            # 3) Seed region quality (last 12bp, PAM-proximal)
            # Higher GC in seed is good for specificity
            seed = seq[-12:] if len(seq) >= 12 else seq
            seed_gc_count = seed.count('G') + seed.count('C')
            seed_gc = seed_gc_count / len(seed) if len(seed) > 0 else 0.0
            seed_quality = min(1.0, seed_gc / 0.5)  # Optimal seed GC ~50%
            
            # 4) Overall heuristic score (weighted combination)
            heuristic_score = (
                0.4 * gc_score +
                0.3 * seed_quality +
                0.3 * homopolymer_penalty
            )
            
            # 5) Risk level classification
            if heuristic_score >= 0.7:
                risk_level = "low"
            elif heuristic_score >= 0.5:
                risk_level = "medium"
            else:
                risk_level = "high"
            
            # 6) Generate warnings
            warnings = []
            if gc_content < 0.3:
                warnings.append("Very low GC content (<30%) - may have poor binding")
            elif gc_content > 0.7:
                warnings.append("Very high GC content (>70%) - may have off-target effects")
            if homopolymer:
                warnings.append("Contains homopolymer run (5+ same nucleotide) - synthesis/binding risk")
            if seed_quality < 0.5:
                warnings.append("Low GC in seed region - reduced specificity")
            if len(seq) != 20:
                warnings.append(f"Non-standard length ({len(seq)}bp, standard is 20bp)")
            
            scored_guides.append(GuideRNAScore(
                seq=seq,
                pam=guide.pam,
                gc_content=gc_content,
                gc_score=gc_score,
                homopolymer=homopolymer,
                homopolymer_penalty=homopolymer_penalty,
                seed_quality=seed_quality,
                heuristic_score=heuristic_score,
                risk_level=risk_level,
                warnings=warnings
            ))
        
        # Summary stats
        if scored_guides:
            avg_score = sum(g.heuristic_score for g in scored_guides) / len(scored_guides)
            low_risk_count = sum(1 for g in scored_guides if g.risk_level == "low")
            summary = {
                "total_guides": len(scored_guides),
                "avg_heuristic_score": round(avg_score, 3),
                "low_risk_count": low_risk_count,
                "medium_risk_count": sum(1 for g in scored_guides if g.risk_level == "medium"),
                "high_risk_count": sum(1 for g in scored_guides if g.risk_level == "high"),
            }
        else:
            summary = {"total_guides": 0}
        
        # Provenance
        provenance = {
            "run_id": run_id,
            "profile": request.options.get("profile", "baseline"),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "methods": ["offtarget_heuristic_v1"],
            "cache": "miss",
            "note": "Heuristic scoring only (no genome alignment yet)"
        }
        
        return OffTargetPreviewResponse(
            guides=scored_guides,
            summary=summary,
            provenance=provenance,
            note="Heuristic preview only (RUO). Genome-wide alignment in development."
        )


# Singleton instance
_safety_service = SafetyService()

def get_safety_service() -> SafetyService:
    """Get singleton safety service instance."""
    return _safety_service
