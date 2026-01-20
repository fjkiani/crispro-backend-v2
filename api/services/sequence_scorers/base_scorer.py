"""
Base Scorer Interface

Defines common interface for all sequence scorers (Evo2, FusionAM, MassiveOracle, BRCA classifier, etc.).

This interface enables clean integration of new scorers into the sequence processor
without code duplication or messy conditional logic.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional

from .models import SeqScore


class BaseScorer(ABC):
    """
    Abstract base class for all sequence scorers.
    
    All scorers must implement:
    - score(): Score one or more variants
    - is_available(): Check if scorer is available (for fallback chain)
    
    Optional methods:
    - score_variant(): Score single variant (convenience method)
    - score_batch(): Score multiple variants (may be same as score())
    """
    
    @abstractmethod
    async def score(
        self,
        mutations: List[Dict[str, Any]],
        model_id: Optional[str] = None,
        **kwargs
    ) -> List[SeqScore]:
        """
        Score variants and return SeqScore objects.
        
        Args:
            mutations: List of variant dictionaries with keys like:
                - gene: str
                - chrom: str
                - pos: int
                - ref: str
                - alt: str
                - hgvs_p: str (optional)
                - hgvs_c: str (optional)
            model_id: Model identifier (optional, scorer-specific)
            **kwargs: Additional scorer-specific parameters
        
        Returns:
            List of SeqScore objects (one per mutation)
        
        Raises:
            Exception: If scoring fails (will trigger fallback chain)
        """
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if scorer is available (for fallback chain).
        
        Returns:
            True if scorer is available, False otherwise
        
        Note:
            If False, sequence processor will try next scorer in fallback chain.
            Should check service availability, model loading, etc.
        """
        pass
    
    async def score_variant(
        self,
        mutation: Dict[str, Any],
        model_id: Optional[str] = None,
        **kwargs
    ) -> Optional[SeqScore]:
        """
        Score a single variant (convenience method).
        
        Args:
            mutation: Single variant dictionary
            model_id: Model identifier (optional)
            **kwargs: Additional scorer-specific parameters
        
        Returns:
            SeqScore object or None if scoring fails
        """
        results = await self.score([mutation], model_id=model_id, **kwargs)
        return results[0] if results else None
    
    async def score_batch(
        self,
        mutations: List[Dict[str, Any]],
        model_id: Optional[str] = None,
        **kwargs
    ) -> List[SeqScore]:
        """
        Score multiple variants (may be same as score()).
        
        Args:
            mutations: List of variant dictionaries
            model_id: Model identifier (optional)
            **kwargs: Additional scorer-specific parameters
        
        Returns:
            List of SeqScore objects
        """
        return await self.score(mutations, model_id=model_id, **kwargs)
    
    def get_scorer_name(self) -> str:
        """
        Get scorer name for logging/debugging.
        
        Returns:
            Scorer name (e.g., "Evo2Scorer", "FusionAMScorer")
        """
        return self.__class__.__name__



