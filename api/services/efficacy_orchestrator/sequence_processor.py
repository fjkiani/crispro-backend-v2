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
        
        # Try Fusion first
        if fusion_url and not disable_fusion:
            try:
                scores = await self.fusion_scorer.score(request.mutations)
                if scores:
                    return scores
            except Exception:
                pass
        
        # Try Evo2
        if not disable_evo2:
            try:
                window_flanks = [4096, 8192, 16384, 25000] if request.options.get("adaptive", True) else [4096]
                ensemble = request.options.get("ensemble", True)
                scores = await self.evo_scorer.score(request.mutations, request.model_id, window_flanks, ensemble)
                if scores:
                    return scores
            except Exception:
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


