"""
Resistance Prophet Service - Backward Compatibility Shim.

This module provides backward compatibility for existing code that uses
ResistanceProphetService. It delegates to the new modular orchestrator.

DEPRECATED: This is a shim for backward compatibility.
New code should use ResistanceProphetOrchestrator directly.
"""

from typing import Dict, List, Optional
import logging

from .models import ResistancePrediction, ResistanceRiskLevel
from .orchestration.resistance_prophet_orchestrator import ResistanceProphetOrchestrator

logger = logging.getLogger(__name__)


class ResistanceProphetService:
    """
    Backward compatibility shim for ResistanceProphetService.
    
    DEPRECATED: This class delegates to ResistanceProphetOrchestrator.
    New code should use ResistanceProphetOrchestrator directly.
    
    This shim maintains the same API as the original monolithic service
    to ensure backward compatibility with existing integrations.
    """
    
    # Manager Q9: Signal detection thresholds (kept for compatibility)
    DNA_REPAIR_THRESHOLD = 0.15
    PATHWAY_ESCAPE_THRESHOLD = 0.15
    
    # Manager Q9: Risk stratification thresholds (kept for compatibility)
    HIGH_RISK_PROBABILITY = 0.70
    MEDIUM_RISK_PROBABILITY = 0.50
    MIN_SIGNALS_FOR_HIGH = 2
    
    def __init__(
        self,
        sae_service=None,
        ca125_service=None,
        treatment_line_service=None,
        resistance_playbook_service=None,
        mm_pathway_service=None
    ):
        """
        Initialize Resistance Prophet Service (shim).
        
        Args:
            sae_service: SAE feature service
            ca125_service: CA-125 intelligence service
            treatment_line_service: Treatment line service
            resistance_playbook_service: Resistance playbook service
            mm_pathway_service: MM pathway service
        """
        # Store services for compatibility
        self.sae_service = sae_service
        self.ca125_service = ca125_service
        self.treatment_line_service = treatment_line_service
        self.resistance_playbook_service = resistance_playbook_service
        self.mm_pathway_service = mm_pathway_service
        
        # Initialize new modular orchestrator
        self._orchestrator = ResistanceProphetOrchestrator(
            sae_service=sae_service,
            ca125_service=ca125_service,
            resistance_playbook_service=resistance_playbook_service,
            mm_pathway_service=mm_pathway_service,
            enable_events=True
        )
        
        logger.info("ResistanceProphetService (shim) initialized - delegating to orchestrator")
    
    async def predict_resistance(
        self,
        current_sae_features: Dict,
        baseline_sae_features: Optional[Dict] = None,
        ca125_history: Optional[List[Dict]] = None,
        treatment_history: Optional[List[Dict]] = None,
        current_drug_class: Optional[str] = None,
        expression_data: Optional[Dict[str, float]] = None
    ) -> ResistancePrediction:
        """
        Predict treatment resistance risk (OV-specific).
        
        Backward compatibility shim - delegates to orchestrator.
        
        Args:
            current_sae_features: Current SAE mechanism vector + DNA repair capacity
            baseline_sae_features: Baseline SAE features (pre-treatment if available)
            ca125_history: List of CA-125 measurements
            treatment_history: Patient treatment history
            current_drug_class: Current drug being assessed
            
        Returns:
            ResistancePrediction with risk level, signals, actions
        """
        logger.debug("ResistanceProphetService.predict_resistance() called - delegating to orchestrator")
        
        # Delegate to orchestrator
        return await self._orchestrator.predict_resistance(
            current_sae_features=current_sae_features,
            baseline_sae_features=baseline_sae_features,
            ca125_history=ca125_history,
            treatment_history=treatment_history,
            current_drug_class=current_drug_class,
            mutations=None,
            treatment_line=1,
            prior_therapies=None,
            disease="ovarian",
            expression_data=expression_data
        )
    
    async def predict_mm_resistance(
        self,
        mutations: List[Dict],
        drug_class: Optional[str] = None,
        treatment_history: Optional[List[Dict]] = None,
        treatment_line: int = 1,
        prior_therapies: Optional[List[str]] = None,
        cytogenetics: Optional[Dict[str, bool]] = None
    ) -> ResistancePrediction:
        """
        Predict MM-specific treatment resistance risk.
        
        Backward compatibility shim - delegates to orchestrator.
        
        Args:
            mutations: List of patient mutations
            drug_class: Current drug class (PI, IMiD, anti-CD38)
            treatment_history: Optional treatment history
            treatment_line: Treatment line (1, 2, 3+)
            prior_therapies: List of prior drug classes
            cytogenetics: Dict of cytogenetic abnormalities (optional)
            
        Returns:
            ResistancePrediction with MM-specific risk assessment
        """
        logger.debug("ResistanceProphetService.predict_mm_resistance() called - delegating to orchestrator")
        
        # Delegate to orchestrator
        return await self._orchestrator.predict_resistance(
            current_sae_features={},  # MM uses gene-level, not SAE features
            baseline_sae_features=None,
            ca125_history=None,
            treatment_history=treatment_history,
            current_drug_class=drug_class,
            mutations=mutations,
            treatment_line=treatment_line,
            prior_therapies=prior_therapies,
            disease="myeloma"
        )
    
    async def predict_platinum_resistance(
        self,
        mutations: List[Dict]
    ) -> ResistancePrediction:
        """
        Predict platinum resistance for ovarian cancer (gene-level).
        
        Backward compatibility shim - delegates to orchestrator.
        This is a simplified interface for platinum resistance prediction.
        
        Args:
            mutations: List of patient mutations
            
        Returns:
            ResistancePrediction with platinum resistance risk
        """
        logger.debug("ResistanceProphetService.predict_platinum_resistance() called - delegating to orchestrator")
        
        # Delegate to orchestrator (ovarian cancer, gene-level prediction)
        return await self._orchestrator.predict_resistance(
            current_sae_features={},  # Gene-level prediction
            baseline_sae_features=None,
            ca125_history=None,
            treatment_history=None,
            current_drug_class="platinum",
            mutations=mutations,
            treatment_line=1,
            prior_therapies=None,
            disease="ovarian"
        )
    
    @property
    def orchestrator(self) -> ResistanceProphetOrchestrator:
        """
        Get the underlying orchestrator.
        
        Allows direct access to the orchestrator for advanced use cases.
        """
        return self._orchestrator


# Singleton instance for backward compatibility
_resistance_prophet_service = None


def get_resistance_prophet_service(
    sae_service=None,
    ca125_service=None,
    treatment_line_service=None,
    resistance_playbook_service=None,
    mm_pathway_service=None
) -> ResistanceProphetService:
    """
    Get or create singleton ResistanceProphetService instance (shim).
    
    DEPRECATED: This function returns a backward compatibility shim.
    New code should use ResistanceProphetOrchestrator directly.
    
    Args:
        sae_service: SAE feature service
        ca125_service: CA-125 intelligence service
        treatment_line_service: Treatment line service
        resistance_playbook_service: Resistance playbook service
        mm_pathway_service: MM pathway service
        
    Returns:
        ResistanceProphetService instance (shim)
    """
    global _resistance_prophet_service
    
    if _resistance_prophet_service is None:
        _resistance_prophet_service = ResistanceProphetService(
            sae_service=sae_service,
            ca125_service=ca125_service,
            treatment_line_service=treatment_line_service,
            resistance_playbook_service=resistance_playbook_service,
            mm_pathway_service=mm_pathway_service
        )
    
    return _resistance_prophet_service
