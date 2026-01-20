"""
Universal Biomarker Intelligence Service

Provides biomarker monitoring for any cancer type.
Supports multiple biomarkers: CA-125 (ovarian), PSA (prostate), CEA (colorectal), etc.

Cloned from ca125_intelligence.py with universalization.

Author: Zo
Date: January 2025
"""

from typing import Dict, Any, Optional
from datetime import datetime
import logging
import math

from .config import get_biomarker_config, get_primary_biomarker

logger = logging.getLogger(__name__)


class BiomarkerIntelligenceService:
    """
    Universal Biomarker Intelligence Service
    
    Provides burden assessment, response forecasts, and resistance detection
    for any biomarker type based on disease-specific configurations.
    """
    
    def __init__(self):
        """Initialize Universal Biomarker Intelligence Service"""
        logger.info("Universal Biomarker Intelligence Service initialized")
    
    def analyze_biomarker(
        self,
        disease_type: str,
        biomarker_type: Optional[str] = None,
        current_value: float = None,
        baseline_value: Optional[float] = None,
        cycle: Optional[int] = None,
        treatment_ongoing: bool = False
    ) -> Dict[str, Any]:
        """
        Analyze biomarker value and provide clinical intelligence.
        
        Args:
            disease_type: Disease type (e.g., "ovarian_cancer_hgs", "prostate_cancer")
            biomarker_type: Biomarker type (e.g., "ca125", "psa", "cea"). If None, uses primary biomarker for disease.
            current_value: Current biomarker value
            baseline_value: Baseline biomarker before treatment (if available)
            cycle: Treatment cycle number (if treatment started)
            treatment_ongoing: Whether patient is currently on treatment
        
        Returns:
            Dict containing:
            - biomarker_type: Type of biomarker analyzed
            - burden_class: MINIMAL/MODERATE/SIGNIFICANT/EXTENSIVE
            - burden_score: Numeric score (0-1)
            - forecast: Expected response milestones
            - resistance_signals: List of warning flags
            - monitoring_strategy: Recommended monitoring frequency
            - clinical_notes: Interpretation for oncologist
            - provenance: Data sources and calculation method
        """
        # Get biomarker config
        if not biomarker_type:
            biomarker_type = get_primary_biomarker(disease_type)
        
        if not biomarker_type:
            return {
                "error": "biomarker_not_configured",
                "message": f"Biomarker monitoring not configured for {disease_type}",
                "disease_type": disease_type
            }
        
        config = get_biomarker_config(disease_type, biomarker_type)
        if not config:
            return {
                "error": "biomarker_not_configured",
                "message": f"Biomarker {biomarker_type} not configured for {disease_type}",
                "disease_type": disease_type,
                "biomarker_type": biomarker_type
            }
        
        if current_value is None:
            return {
                "error": "value_required",
                "message": f"Biomarker value required for {biomarker_type}",
                "biomarker_type": biomarker_type
            }
        
        logger.info(f"Analyzing {biomarker_type}: current={current_value}, baseline={baseline_value}, cycle={cycle}, disease={disease_type}")
        
        # Extract thresholds and expectations from config
        burden_thresholds = config.get("burden_thresholds", {})
        response_expectations = config.get("response_expectations", {})
        normal_upper_limit = config.get("normal_upper_limit", 0.0)
        
        # 1. Burden Classification
        burden_class = self._classify_burden(current_value, burden_thresholds)
        burden_score = self._calculate_burden_score(current_value, normal_upper_limit, burden_thresholds)
        
        # 2. Response Forecast (if baseline provided)
        forecast = self._generate_forecast(
            current_value, baseline_value, cycle, response_expectations, biomarker_type
        )
        
        # 3. Resistance Signals (if treatment ongoing)
        resistance_signals = []
        if treatment_ongoing and baseline_value:
            resistance_signals = self._detect_resistance_signals(
                current_value, baseline_value, cycle, response_expectations, biomarker_type
            )
        
        # 4. Monitoring Strategy
        monitoring_strategy = self._recommend_monitoring(
            burden_class, treatment_ongoing, biomarker_type
        )
        
        # 5. Clinical Notes
        clinical_notes = self._generate_clinical_notes(
            current_value, burden_class, baseline_value, cycle, resistance_signals,
            response_expectations, biomarker_type
        )
        
        # 6. Provenance
        provenance = {
            "method": "biomarker_intelligence_universal_v1",
            "biomarker_type": biomarker_type,
            "disease_type": disease_type,
            "data_sources": config.get("clinical_trials", []),
            "guidelines": config.get("guidelines", "NCCN Guidelines"),
            "thresholds": burden_thresholds,
            "expectations": response_expectations,
            "analyzed_at": datetime.utcnow().isoformat(),
            "run_id": f"biomarker_{biomarker_type}_{int(datetime.utcnow().timestamp())}"
        }
        
        return {
            "biomarker_type": biomarker_type,
            "disease_type": disease_type,
            "burden_class": burden_class,
            "burden_score": burden_score,
            "forecast": forecast,
            "resistance_signals": resistance_signals,
            "monitoring_strategy": monitoring_strategy,
            "clinical_notes": clinical_notes,
            "provenance": provenance
        }
    
    def _classify_burden(self, value: float, burden_thresholds: Dict[str, tuple]) -> str:
        """Classify biomarker burden."""
        for burden_class, (low, high) in burden_thresholds.items():
            if low <= value < high:
                return burden_class
        return "EXTENSIVE"  # Default for very high values
    
    def _calculate_burden_score(self, value: float, normal_upper_limit: float, burden_thresholds: Dict[str, tuple]) -> float:
        """Calculate numeric burden score (0-1)."""
        if value <= normal_upper_limit:
            return 0.0
        
        # Find max threshold for scaling
        max_threshold = 0
        for (low, high) in burden_thresholds.values():
            if high != float('inf'):
                max_threshold = max(max_threshold, high)
            else:
                # For EXTENSIVE, use a reasonable cap (10x the SIGNIFICANT threshold)
                for (sl, sh) in burden_thresholds.values():
                    if sh != float('inf'):
                        max_threshold = max(max_threshold, sh * 10)
        
        if max_threshold == 0:
            max_threshold = normal_upper_limit * 100  # Fallback
        
        # Log scale normalization
        log_value = math.log10(value)
        log_normal = math.log10(normal_upper_limit) if normal_upper_limit > 0 else 0
        log_max = math.log10(max_threshold)
        
        if log_max <= log_normal:
            return 1.0
        
        score = (log_value - log_normal) / (log_max - log_normal)
        return min(max(score, 0.0), 1.0)
    
    def _generate_forecast(
        self,
        current_value: float,
        baseline_value: Optional[float],
        cycle: Optional[int],
        response_expectations: Dict[str, Any],
        biomarker_type: str
    ) -> Dict[str, Any]:
        """Generate response forecast milestones."""
        forecast = {
            "complete_response_target": response_expectations.get("complete_response_threshold", 0),
            "complete_response_target_unit": self._get_unit(biomarker_type)
        }
        
        if baseline_value:
            cycle3_drop = response_expectations.get("cycle3_drop_percent", 70)
            cycle6_drop = response_expectations.get("cycle6_drop_percent", 90)
            
            cycle3_expected = baseline_value * (1 - cycle3_drop / 100)
            cycle6_expected = baseline_value * (1 - cycle6_drop / 100)
            
            forecast["cycle3_expected_value"] = round(cycle3_expected, 2)
            forecast["cycle3_expected_drop_percent"] = cycle3_drop
            forecast["cycle6_expected_value"] = round(cycle6_expected, 2)
            forecast["cycle6_expected_drop_percent"] = cycle6_drop
            
            if cycle and baseline_value > 0:
                actual_drop_percent = ((baseline_value - current_value) / baseline_value) * 100
                forecast["actual_drop_percent"] = round(actual_drop_percent, 1)
                forecast["current_cycle"] = cycle
                
                if cycle >= 3:
                    expected_drop = cycle3_drop
                    forecast["cycle3_status"] = "ON_TRACK" if actual_drop_percent >= expected_drop else "BELOW_EXPECTED"
                
                if cycle >= 6:
                    expected_drop = cycle6_drop
                    forecast["cycle6_status"] = "ON_TRACK" if actual_drop_percent >= expected_drop else "BELOW_EXPECTED"
        else:
            forecast["note"] = f"Baseline {biomarker_type.upper()} not available. Response expectations depend on biomarker type and disease."
        
        return forecast
    
    def _detect_resistance_signals(
        self,
        current_value: float,
        baseline_value: float,
        cycle: Optional[int],
        response_expectations: Dict[str, Any],
        biomarker_type: str
    ) -> list:
        """Detect resistance signals based on biomarker kinetics."""
        signals = []
        
        if baseline_value <= 0:
            return signals
        
        drop_percent = ((baseline_value - current_value) / baseline_value) * 100
        resistance_threshold = response_expectations.get("resistance_threshold_percent", 50)
        
        # Signal 1: On-therapy rise
        if current_value > baseline_value:
            signals.append({
                "type": "ON_THERAPY_RISE",
                "severity": "HIGH",
                "message": f"{biomarker_type.upper()} rising on therapy (baseline: {baseline_value:.2f} → current: {current_value:.2f})",
                "recommendation": "Consider alternative therapy. Rising biomarker on treatment indicates resistance."
            })
        
        # Signal 2: Inadequate response by cycle 3
        if cycle and cycle >= 3:
            if drop_percent < resistance_threshold:
                signals.append({
                    "type": "INADEQUATE_RESPONSE_CYCLE3",
                    "severity": "HIGH",
                    "message": f"<{resistance_threshold}% drop by cycle 3 (actual: {drop_percent:.1f}%)",
                    "recommendation": "Inadequate response. Consider imaging correlation and treatment intensification or switch."
                })
        
        # Signal 3: Minimal response
        if cycle and cycle >= 2:
            if 0 < drop_percent < 30:
                signals.append({
                    "type": "MINIMAL_RESPONSE",
                    "severity": "MODERATE",
                    "message": f"Minimal {biomarker_type.upper()} decline ({drop_percent:.1f}% drop)",
                    "recommendation": "Monitor closely. Consider imaging to assess anatomic response."
                })
        
        return signals
    
    def _recommend_monitoring(
        self,
        burden_class: str,
        treatment_ongoing: bool,
        biomarker_type: str
    ) -> Dict[str, Any]:
        """Recommend biomarker monitoring frequency and strategy."""
        if treatment_ongoing:
            frequency = "every_3_weeks"
            timing = "Just before each chemotherapy cycle"
            rationale = "Track response kinetics and detect resistance early"
        else:
            if burden_class == "EXTENSIVE":
                frequency = "every_2_weeks"
                timing = "Until treatment initiation"
                rationale = "High baseline; track any changes before treatment"
            elif burden_class == "SIGNIFICANT":
                frequency = "every_4_weeks"
                timing = "Until treatment initiation or during surveillance"
                rationale = "Moderate baseline; routine monitoring"
            else:
                frequency = "every_3_months"
                timing = "During routine surveillance"
                rationale = "Low/normal baseline; surveillance monitoring"
        
        return {
            "frequency": frequency,
            "timing": timing,
            "rationale": rationale,
            "method": f"Serum {biomarker_type.upper()} ({self._get_unit(biomarker_type)})"
        }
    
    def _generate_clinical_notes(
        self,
        current_value: float,
        burden_class: str,
        baseline_value: Optional[float],
        cycle: Optional[int],
        resistance_signals: list,
        response_expectations: Dict[str, Any],
        biomarker_type: str
    ) -> str:
        """Generate clinical interpretation notes."""
        notes = []
        unit = self._get_unit(biomarker_type)
        
        # Burden interpretation
        if burden_class == "EXTENSIVE":
            notes.append(f"{biomarker_type.upper()} of {current_value:.2f} {unit} indicates EXTENSIVE disease burden.")
        elif burden_class == "SIGNIFICANT":
            notes.append(f"{biomarker_type.upper()} of {current_value:.2f} {unit} indicates SIGNIFICANT disease burden.")
        elif burden_class == "MODERATE":
            notes.append(f"{biomarker_type.upper()} of {current_value:.2f} {unit} indicates MODERATE disease burden.")
        else:
            notes.append(f"{biomarker_type.upper()} of {current_value:.2f} {unit} is within normal to minimal range.")
        
        # Response assessment
        if baseline_value and cycle:
            drop_percent = ((baseline_value - current_value) / baseline_value) * 100
            if drop_percent > 0:
                notes.append(f"On-treatment response: {drop_percent:.1f}% reduction from baseline (cycle {cycle}).")
                
                cycle3_drop = response_expectations.get("cycle3_drop_percent", 70)
                cycle6_drop = response_expectations.get("cycle6_drop_percent", 90)
                
                if cycle >= 3:
                    if drop_percent >= cycle3_drop:
                        notes.append(f"✓ Response ON TRACK for cycle 3 (≥{cycle3_drop}% drop expected).")
                    else:
                        notes.append(f"⚠ Response BELOW EXPECTED for cycle 3 (<{cycle3_drop}% drop). Consider imaging correlation.")
                
                if cycle >= 6:
                    if drop_percent >= cycle6_drop:
                        notes.append(f"✓ Excellent response (≥{cycle6_drop}% drop by cycle 6).")
                    else:
                        notes.append(f"⚠ Sub-optimal response for cycle 6 (<{cycle6_drop}% drop). Consider alternative strategies.")
        
        # Resistance signals
        if resistance_signals:
            notes.append(f"⚠️ {len(resistance_signals)} resistance signal(s) detected:")
            for signal in resistance_signals:
                notes.append(f"  - {signal['type']}: {signal['message']}")
        
        # Complete response target
        cr_threshold = response_expectations.get("complete_response_threshold", 0)
        if current_value > cr_threshold:
            notes.append(f"Complete response target: <{cr_threshold} {unit}. Additional therapy cycles likely needed.")
        else:
            notes.append(f"✓ {biomarker_type.upper()} within complete response range (<{cr_threshold} {unit}).")
        
        return " ".join(notes)
    
    def _get_unit(self, biomarker_type: str) -> str:
        """Get unit for biomarker type."""
        units = {
            "ca125": "U/mL",
            "psa": "ng/mL",
            "cea": "ng/mL"
        }
        return units.get(biomarker_type.lower(), "units")


# Singleton instance
_biomarker_service = None


def get_biomarker_intelligence_service() -> BiomarkerIntelligenceService:
    """Get singleton Universal Biomarker Intelligence Service instance."""
    global _biomarker_service
    if _biomarker_service is None:
        _biomarker_service = BiomarkerIntelligenceService()
    return _biomarker_service















