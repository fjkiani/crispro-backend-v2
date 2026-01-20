"""
Kinetic Biomarker Base Class.

Abstract base class for KELIM-like kinetic biomarkers (CA-125, PSA, future markers).
Supports hierarchical architecture for disease-specific implementations.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class KineticBiomarkerBase(ABC):
    """
    Base class for KELIM-like kinetic biomarkers.
    
    Supports: CA-125 (ovary), PSA (prostate), future markers (CEA, CA15-3, etc.)
    """
    
    def __init__(self, disease_site: str, marker: str, config: Dict[str, Any]):
        """
        Initialize kinetic biomarker.
        
        Args:
            disease_site: Disease site (ovarian, prostate, etc.)
            marker: Marker name (ca125, psa, etc.)
            config: Configuration dict from kinetic_biomarker_config.py
        """
        self.disease_site = disease_site
        self.marker = marker
        self.config = config
        self.class_name = config.get("class", "ELIM_RATE_CONSTANT_K")
        self.marker_name = config.get("marker_name", marker.upper())
        self.use_cases = config.get("use_cases", [])
        self.evidence_level = config.get("evidence_level", "EXPLORATORY")
        self.data_requirements = config.get("data_requirements", {})
        self.cutoffs = config.get("cutoffs", {})
        self.categories = config.get("categories", {})
    
    @abstractmethod
    def compute_k_value(
        self,
        marker_values: List[Dict[str, Any]],
        treatment_start_date: datetime
    ) -> Dict[str, Any]:
        """
        Compute KELIM-like elimination rate constant K.
        
        Args:
            marker_values: List of marker measurements with dates and values.
                Each dict must have: date (datetime/str), value (float)
            treatment_start_date: Start date of treatment regimen
        
        Returns:
            {
                "k_value": float,  # Computed K value (or None if cannot compute)
                "category": str,   # "favorable", "intermediate", "unfavorable" (or None)
                "measurements_used": int,  # Number of measurements used
                "time_window_days": int,  # Actual time window covered
                "modeling_approach": str,  # "mixed_effects", "log_linear", etc.
                "confidence": float,  # 0.0-1.0 confidence in K value
                "warnings": List[str],  # Data quality warnings
                "error": Optional[str]  # Error message if computation failed
            }
        """
        pass
    
    def validate_data_requirements(
        self,
        marker_values: List[Dict[str, Any]],
        treatment_start_date: datetime
    ) -> Dict[str, Any]:
        """
        Validate that marker data meets requirements for K computation.
        
        Args:
            marker_values: List of marker measurements
            treatment_start_date: Treatment start date
        
        Returns:
            {
                "valid": bool,
                "warnings": List[str],
                "measurements_in_window": int,
                "has_baseline": bool,
                "time_window_days": int
            }
        """
        min_measurements = self.data_requirements.get("min_measurements", 3)
        time_window_days = self.data_requirements.get("time_window_days", 100)
        requires_baseline = self.data_requirements.get("requires_baseline", True)
        baseline_window_days = self.data_requirements.get("baseline_window_days", 30)
        
        # Filter measurements within time window
        window_end = treatment_start_date + timedelta(days=time_window_days)
        measurements_in_window = []
        
        for m in marker_values:
            m_date = self._parse_date(m.get("date"))
            m_value = m.get("value")
            
            if m_date and m_value is not None:
                if treatment_start_date <= m_date <= window_end:
                    measurements_in_window.append(m)
        
        # Check for baseline (within baseline_window_days before treatment start, or at treatment start)
        baseline_start = treatment_start_date - timedelta(days=baseline_window_days)
        has_baseline = any(
            self._parse_date(m.get("date")) >= baseline_start and
            self._parse_date(m.get("date")) <= treatment_start_date  # Allow baseline at treatment start
            for m in marker_values
            if self._parse_date(m.get("date")) and m.get("value") is not None
        )
        
        valid = len(measurements_in_window) >= min_measurements
        if requires_baseline:
            valid = valid and has_baseline
        
        warnings = []
        if len(measurements_in_window) < min_measurements:
            warnings.append(
                f"Insufficient measurements in first {time_window_days} days: "
                f"{len(measurements_in_window)} < {min_measurements}"
            )
        if requires_baseline and not has_baseline:
            warnings.append(
                f"Missing baseline measurement within {baseline_window_days} days before treatment start"
            )
        
        return {
            "valid": valid,
            "warnings": warnings,
            "measurements_in_window": len(measurements_in_window),
            "has_baseline": has_baseline,
            "time_window_days": time_window_days
        }
    
    def categorize_k_value(self, k_value: Optional[float]) -> Optional[str]:
        """
        Categorize K value into favorable/intermediate/unfavorable.
        
        Args:
            k_value: Computed K value (or None)
        
        Returns:
            Category string ("favorable", "intermediate", "unfavorable") or None
        """
        if k_value is None:
            return None
        
        favorable_cutoff = self.cutoffs.get("favorable", 1.0)
        intermediate_cutoff = self.cutoffs.get("intermediate", 0.5)
        
        if k_value >= favorable_cutoff:
            return "favorable"
        elif k_value >= intermediate_cutoff:
            return "intermediate"
        else:
            return "unfavorable"
    
    def _parse_date(self, date_value: Union[str, datetime, None]) -> Optional[datetime]:
        """
        Parse date value into datetime object.
        
        Args:
            date_value: Date value (datetime, ISO string, or None)
        
        Returns:
            datetime object or None if cannot parse
        """
        if date_value is None:
            return None
        
        if isinstance(date_value, datetime):
            return date_value
        
        if isinstance(date_value, str):
            try:
                # Try ISO format first
                return datetime.fromisoformat(date_value.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                try:
                    # Try common date formats
                    for fmt in ["%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%m/%d/%Y", "%d/%m/%Y"]:
                        try:
                            return datetime.strptime(date_value, fmt)
                        except ValueError:
                            continue
                except Exception:
                    pass
        
        return None
    
    def get_evidence_level(self, use_case: str) -> str:
        """
        Get evidence level for a specific use case.
        
        Args:
            use_case: Use case ("prognostic", "predictive", "therapeutic")
        
        Returns:
            Evidence level ("validated", "exploratory", "unknown")
        """
        validation_status = self.config.get("validation_status", {})
        return validation_status.get(use_case, "unknown")
    
    def is_validated_for_use_case(self, use_case: str) -> bool:
        """
        Check if biomarker is validated for a specific use case.
        
        Args:
            use_case: Use case ("prognostic", "predictive", "therapeutic")
        
        Returns:
            True if validated, False otherwise
        """
        return self.get_evidence_level(use_case) == "validated"
