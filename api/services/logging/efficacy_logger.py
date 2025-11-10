"""
Efficacy Logger: Specialized logging for efficacy runs.
"""
from typing import Dict, Any, List
from .models import EfficacyRunData
from .supabase_client import LoggingService


class EfficacyLogger:
    """Logger for efficacy run data."""
    
    def __init__(self, logging_service: LoggingService):
        self.logging_service = logging_service
    
    async def log_run(self, run_data: EfficacyRunData) -> bool:
        """
        Log efficacy run to Supabase.
        
        Args:
            run_data: Efficacy run data
            
        Returns:
            True if logged successfully, False otherwise
        """
        if not self.logging_service.is_available():
            return False
        
        try:
            # Convert to dictionary format expected by Supabase
            supabase_data = {
                "run_signature": run_data.run_signature,
                "request": run_data.request,
                "sequence_details": run_data.sequence_details,
                "pathway_scores": run_data.pathway_scores,
                "scoring_strategy": run_data.scoring_strategy,
                "weights_snapshot": run_data.weights_snapshot,
                "gates_snapshot": run_data.gates_snapshot,
                "feature_flags_snapshot": run_data.feature_flags_snapshot,
                "operational_mode": run_data.operational_mode,
                "confidence_tier": run_data.confidence_tier,
                "drug_count": run_data.drug_count,
                "insights": run_data.insights,
            }
            
            return await self.logging_service.log_evidence_run(supabase_data)
            
        except Exception:
            # Don't fail the request if logging fails
            return False
    
    def create_run_data(self, run_signature: str, request: Dict[str, Any],
                       seq_scores: List[Dict[str, Any]], pathway_scores: Dict[str, float],
                       scoring_strategy: Dict[str, Any], drugs_out: List[Dict[str, Any]],
                       insights: Dict[str, Any], config: Dict[str, Any]) -> EfficacyRunData:
        """
        Create efficacy run data for logging.
        
        Args:
            run_signature: Run signature
            request: Original request
            seq_scores: Sequence scores
            pathway_scores: Pathway scores
            scoring_strategy: Scoring strategy
            drugs_out: Drug results
            insights: Insights data
            config: Configuration
            
        Returns:
            EfficacyRunData object
        """
        return EfficacyRunData(
            run_signature=run_signature,
            request=request,
            sequence_details=seq_scores,
            pathway_scores=pathway_scores,
            scoring_strategy=scoring_strategy,
            weights_snapshot=config.get("weights", {}),
            gates_snapshot=config.get("evidence_gates", {}),
            feature_flags_snapshot=config.get("feature_flags", {}),
            operational_mode=config.get("operational_mode", "research"),
            confidence_tier="supported" if any(d.get("meets_evidence_gate") for d in drugs_out) else "insufficient",
            drug_count=len(drugs_out),
            insights=insights
        )



