"""
Sequence Processor: Handles sequence scoring orchestration.
"""
import os
from typing import Dict, Any, List

from .models import EfficacyRequest
from ..sequence_scorers import FusionAMScorer, Evo2Scorer, MassiveOracleScorer, SeqScore
from api.config import get_feature_flags


class SequenceProcessor:
    """Handles sequence scoring using appropriate scorers."""
    
    def __init__(self, fusion_scorer: FusionAMScorer = None,
                 evo_scorer: Evo2Scorer = None,
                 massive_scorer: MassiveOracleScorer = None):
        self.fusion_scorer = fusion_scorer or FusionAMScorer()
        self.evo_scorer = evo_scorer or Evo2Scorer()
        self.massive_scorer = massive_scorer or MassiveOracleScorer()
    
    async def score_sequences(self, request: EfficacyRequest, feature_flags: Dict[str, Any]) -> List[SeqScore]:
        """Score sequences using appropriate scorer."""
        fusion_url = os.getenv("FUSION_AM_URL")
        disable_fusion = feature_flags.get("disable_fusion", False)
        disable_evo2 = feature_flags.get("disable_evo2", False)
        
        # Try Fusion first (ONLY for GRCh38 missense variants)
        if fusion_url and not disable_fusion:
            try:
                # P0 Gate: Only use Fusion for GRCh38 missense variants
                fusion_eligible = []
                for m in request.mutations:
                    build = str(m.get("build", "")).lower()
                    consequence = str(m.get("consequence", "")).lower()
                    # Check if variant is GRCh38 and missense
                    is_grch38 = build in ["grch38", "hg38", "38"]
                    is_missense = "missense" in consequence
                    if is_grch38 and is_missense:
                        fusion_eligible.append(m)
                
                if fusion_eligible:
                    scores = await self.fusion_scorer.score(fusion_eligible)
                    if scores:
                        return scores
            except Exception:
                pass
        
        # Try Evo2
        if not disable_evo2:
            try:
                window_flanks = [4096, 8192, 16384] if request.options.get("adaptive", True) else [4096]
                ensemble = False  # hard-disable multi-model to 1B only
                # Force exon scan when ablation includes S (default) to capture missense impact
                force_exon = True
                import logging
                logger = logging.getLogger(__name__)
                logger.info(f"🔬 Attempting Evo2 scoring for {len(request.mutations)} mutations with model {request.model_id}")
                scores = await self.evo_scorer.score(
                    request.mutations, request.model_id, window_flanks, ensemble, force_exon_scan=force_exon
                )
                if scores:
                    logger.info(f"✅ Evo2 scoring successful: {len(scores)} scores returned")
                    return scores
                else:
                    logger.warning(f"⚠️ Evo2 scoring returned empty results")
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"❌ Evo2 scoring failed: {e}", exc_info=True)
                pass
        
        # Try Massive Oracle if enabled
        massive_impact = request.options.get("massive_impact", False)
        massive_real = request.options.get("massive_real_context", False)
        enable_massive = feature_flags.get("enable_massive_modes", False)
        
        if enable_massive:
            if massive_real:
                try:
                    scores = await self.massive_scorer.score_real_context(request.mutations)
                    if scores:
                        return scores
                except Exception:
                    pass
            
            if massive_impact:
                try:
                    scores = await self.massive_scorer.score_synthetic(request.mutations)
                    if scores:
                        return scores
                except Exception:
                    pass
        
        return []



        return []


