"""
CA-125 KELIM for Ovarian Cancer.

Implementation of CA-125 KELIM (kinetic elimination rate constant) computation
using mixed-effects modeling for ovarian cancer chemosensitivity assessment.
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import numpy as np
from scipy import stats
import logging

from .kinetic_biomarker_base import KineticBiomarkerBase
from ...config.kinetic_biomarker_config import get_kinetic_biomarker_config

logger = logging.getLogger(__name__)


class CA125KELIMOvarian(KineticBiomarkerBase):
    """
    CA-125 KELIM for ovarian cancer.
    
    Evidence Level: SOC (Standard of Care / approaching standard)
    Validated: Prognostic, Predictive, Therapeutic
    
    References:
    - ICON7, CHIVA, GOG-0218 trials
    - GCIG meta-analysis (standardized cutpoints: K≥1.0 = favorable)
    - Real-world validation studies
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize CA-125 KELIM for ovarian cancer.
        
        Args:
            config: Optional custom configuration. If None, uses default from config.
        """
        if config is None:
            config = get_kinetic_biomarker_config("ovarian", "ca125")
        super().__init__("ovarian", "ca125", config)
    
    def compute_k_value(
        self,
        marker_values: List[Dict[str, Any]],
        treatment_start_date: datetime
    ) -> Dict[str, Any]:
        """
        Compute CA-125 KELIM using log-linear regression.
        
        Model: CA-125(t) = CA-125(0) * exp(-K * t/30)
        Where t is in days, standardized to 30-day periods (standard KELIM convention).
        
        Approach: Log-linear regression (simplified from mixed-effects model for initial implementation)
        - Future: Upgrade to full mixed-effects population PK model using statsmodels
        
        Args:
            marker_values: List of CA-125 measurements.
                Each dict must have: date (datetime/str), value (float) in U/mL
            treatment_start_date: Start date of treatment regimen
        
        Returns:
            Dictionary with K value, category, metadata, warnings
        """
        # Validate data requirements
        validation = self.validate_data_requirements(marker_values, treatment_start_date)
        if not validation["valid"]:
            return {
                "k_value": None,
                "category": None,
                "measurements_used": validation["measurements_in_window"],
                "time_window_days": validation["time_window_days"],
                "modeling_approach": "log_linear",  # Simplified from mixed_effects
                "confidence": 0.0,
                "warnings": validation["warnings"],
                "error": "Data requirements not met"
            }
        
        try:
            # Prepare measurements for computation
            measurements = self._prepare_measurements(marker_values, treatment_start_date)
            
            # Debug: Check if measurements were prepared correctly
            if len(measurements) < 3:
                return {
                    "k_value": None,
                    "category": None,
                    "measurements_used": len(measurements),
                    "time_window_days": validation["time_window_days"],
                    "modeling_approach": "log_linear",
                    "confidence": 0.0,
                    "warnings": validation["warnings"] + ["Insufficient measurements after filtering"],
                    "error": "Need at least 3 measurements after filtering"
                }
            
            # Compute K using log-linear regression
            k_value = self._compute_log_linear_k(measurements)
            
            if k_value is None:
                return {
                    "k_value": None,
                    "category": None,
                    "measurements_used": len(measurements),
                    "time_window_days": validation["time_window_days"],
                    "modeling_approach": "log_linear",
                    "confidence": 0.0,
                    "warnings": validation["warnings"] + ["Failed to compute K value"],
                    "error": "K computation failed"
                }
            
            # Categorize K value
            category = self.categorize_k_value(k_value)
            
            # Compute confidence
            confidence = self._compute_confidence(measurements, k_value)
            
            return {
                "k_value": round(k_value, 2),
                "category": category,
                "measurements_used": len(measurements),
                "time_window_days": validation["time_window_days"],
                "modeling_approach": "log_linear",
                "confidence": confidence,
                "warnings": validation["warnings"],
                "error": None
            }
        
        except Exception as e:
            logger.error(f"Error computing CA-125 KELIM: {e}")
            return {
                "k_value": None,
                "category": None,
                "measurements_used": 0,
                "time_window_days": validation["time_window_days"],
                "modeling_approach": "log_linear",
                "confidence": 0.0,
                "warnings": validation["warnings"] + [f"Computation error: {str(e)}"],
                "error": str(e)
            }
    
    def _prepare_measurements(
        self,
        marker_values: List[Dict[str, Any]],
        treatment_start_date: datetime
    ) -> List[Dict[str, Any]]:
        """
        Prepare measurements for K computation.
        
        Filters measurements within time window and converts to days since treatment start.
        
        Args:
            marker_values: List of CA-125 measurements
            treatment_start_date: Treatment start date
        
        Returns:
            List of prepared measurements with days_since_start and value
        """
        time_window_days = self.data_requirements.get("time_window_days", 100)
        window_end = treatment_start_date + timedelta(days=time_window_days)
        
        measurements = []
        
        for m in marker_values:
            m_date = self._parse_date(m.get("date"))
            m_value = m.get("value")
            
            if m_date is None or m_value is None:
                continue
            
            # Include baseline (before treatment start) and measurements during treatment
            if m_date <= window_end:
                days_since_start = (m_date - treatment_start_date).days
                measurements.append({
                    "date": m_date,
                    "days_since_start": days_since_start,
                    "value": float(m_value)
                })
        
        # Sort by days_since_start
        measurements.sort(key=lambda x: x["days_since_start"])
        
        return measurements
    
    def _compute_log_linear_k(self, measurements: List[Dict[str, Any]]) -> Optional[float]:
        """
        Compute K value using log-linear regression.
        
        Model: log(CA-125(t)) = log(CA-125(0)) - K * (t/30)
        Where t is in days, standardized to 30-day periods.
        
        KELIM standardizes time to 30-day periods, so:
        K = -30 * slope, where slope is from log(CA-125) ~ days
        
        Args:
            measurements: Prepared measurements with days_since_start and value
        
        Returns:
            K value (float) or None if computation fails
        """
        if len(measurements) < 2:
            return None
        
        # Extract time (in days) and values
        times = np.array([m["days_since_start"] for m in measurements])
        values = np.array([m["value"] for m in measurements])
        
        # Ensure positive values (CA-125 should be > 0)
        values = np.maximum(values, 1.0)
        
        # Log-linear regression: log(value) = log(baseline) - K * (t/30)
        log_values = np.log(values)
        
        # Standardize time to 30-day periods (KELIM convention)
        times_standardized = times / 30.0
        
        # Fit linear regression: log(value) ~ -K * (t/30)
        # Slope will be -K, so K = -slope
        try:
            slope, intercept, r_value, p_value, std_err = stats.linregress(
                times_standardized,
                log_values
            )
            
            # K is negative of slope (since we're modeling decay)
            k_value = -slope
            
            # Ensure non-negative (shouldn't be negative for elimination rate)
            k_value = max(0.0, k_value)
            
            return k_value
        
        except Exception as e:
            logger.error(f"Error in log-linear regression: {e}")
            return None
    
    def _compute_confidence(
        self,
        measurements: List[Dict[str, Any]],
        k_value: float
    ) -> float:
        """
        Compute confidence in K value based on data quality.
        
        Factors:
        - Number of measurements (more = higher confidence)
        - Time window coverage (longer = higher confidence)
        - Model fit quality (R-squared, if available)
        
        Args:
            measurements: Prepared measurements
            k_value: Computed K value
        
        Returns:
            Confidence value (0.0-1.0)
        """
        if k_value is None or len(measurements) < 2:
            return 0.0
        
        # Base confidence from number of measurements
        n_measurements = len(measurements)
        min_required = self.data_requirements.get("min_measurements", 3)
        
        if n_measurements >= 5:
            measurement_confidence = 1.0
        elif n_measurements >= min_required:
            measurement_confidence = 0.7 + 0.1 * (n_measurements - min_required)
        else:
            measurement_confidence = 0.5
        
        # Time window coverage
        if measurements:
            time_span = measurements[-1]["days_since_start"] - measurements[0]["days_since_start"]
            time_window = self.data_requirements.get("time_window_days", 100)
            
            if time_span >= time_window * 0.8:
                time_confidence = 1.0
            elif time_span >= time_window * 0.5:
                time_confidence = 0.8
            else:
                time_confidence = 0.6
        else:
            time_confidence = 0.5
        
        # Overall confidence (average of factors)
        confidence = (measurement_confidence + time_confidence) / 2.0
        
        # Cap at 1.0
        return min(1.0, confidence)


def compute_ca125_kelim(
    ca125_measurements: List[Dict[str, Any]],
    treatment_start_date: datetime,
    config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Convenience function to compute CA-125 KELIM.
    
    Args:
        ca125_measurements: List of CA-125 measurements with date and value
        treatment_start_date: Treatment start date
        config: Optional custom configuration
    
    Returns:
        Dictionary with K value, category, metadata (same as compute_k_value)
    """
    kelim = CA125KELIMOvarian(config=config)
    return kelim.compute_k_value(ca125_measurements, treatment_start_date)
