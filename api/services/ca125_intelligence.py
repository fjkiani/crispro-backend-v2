"""
CA-125 Intelligence Service

For AK - Stage IVB Ovarian Cancer
CA-125: 2,842 U/mL (baseline, November 2025)

This service provides:
1. Burden classification (MINIMAL/MODERATE/SIGNIFICANT/EXTENSIVE)
2. Expected response forecast (cycle 3, cycle 6 targets)
3. Resistance signal rules (when to escalate)
4. Monitoring strategy

Based on GOG-218, ICON7, and NCCN guidelines for HGSOC.

Author: Zo
Date: January 13, 2025
Purpose: Help Ayesha's oncologist track response and detect resistance EARLY
"""

from typing import Dict, Any, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class CA125IntelligenceService:
    """
    CA-125 Intelligence Service
    
    Provides burden assessment, response forecasts, and resistance detection
    based on established clinical patterns from ovarian cancer trials.
    """
    
    # Thresholds from manager's specification (AYESHA_END_TO_END_AGENT_PLAN.mdc lines 391-395)
    BURDEN_THRESHOLDS = {
        "MINIMAL": (0, 100),
        "MODERATE": (100, 500),
        "SIGNIFICANT": (500, 1000),
        "EXTENSIVE": (1000, float('inf'))
    }
    
    # Clinical response expectations from GOG-218 / ICON7
    # For chemo-sensitive HGSOC, expect:
    # - ≥70% drop by cycle 3 (week 9)
    # - ≥90% drop by cycle 6 (week 18)
    # - Complete response target: <35 U/mL
    RESPONSE_EXPECTATIONS = {
        "cycle3_drop_percent": 70,  # Minimum expected drop by cycle 3
        "cycle6_drop_percent": 90,  # Minimum expected drop by cycle 6
        "complete_response_threshold": 35,  # CR target in U/mL
        "resistance_threshold_percent": 50  # <50% drop by cycle 3 → resistance signal
    }
    
    def __init__(self):
        """Initialize CA-125 Intelligence Service"""
        logger.info("CA-125 Intelligence Service initialized")
    
    def analyze_ca125(
        self,
        current_value: float,
        baseline_value: Optional[float] = None,
        cycle: Optional[int] = None,
        treatment_ongoing: bool = False
    ) -> Dict[str, Any]:
        """
        Analyze CA-125 value and provide clinical intelligence.
        
        Args:
            current_value: Current CA-125 value in U/mL
            baseline_value: Baseline CA-125 before treatment (if available)
            cycle: Treatment cycle number (if treatment started)
            treatment_ongoing: Whether patient is currently on treatment
        
        Returns:
            Dict containing:
            - burden_class: MINIMAL/MODERATE/SIGNIFICANT/EXTENSIVE
            - burden_score: Numeric score (0-1)
            - forecast: Expected response milestones
            - resistance_signals: List of warning flags
            - monitoring_strategy: Recommended monitoring frequency
            - clinical_notes: Interpretation for oncologist
            - provenance: Data sources and calculation method
        """
        logger.info(f"Analyzing CA-125: current={current_value}, baseline={baseline_value}, cycle={cycle}")
        
        # 1. Burden Classification
        burden_class = self._classify_burden(current_value)
        burden_score = self._calculate_burden_score(current_value)
        
        # 2. Response Forecast (if baseline provided)
        forecast = self._generate_forecast(current_value, baseline_value, cycle)
        
        # 3. Resistance Signals (if treatment ongoing)
        resistance_signals = []
        if treatment_ongoing and baseline_value:
            resistance_signals = self._detect_resistance_signals(
                current_value, baseline_value, cycle
            )
        
        # 4. Monitoring Strategy
        monitoring_strategy = self._recommend_monitoring(burden_class, treatment_ongoing)
        
        # 5. Clinical Notes
        clinical_notes = self._generate_clinical_notes(
            current_value, burden_class, baseline_value, cycle, resistance_signals
        )
        
        # 6. Provenance
        provenance = {
            "method": "ca125_intelligence_v1",
            "data_sources": ["GOG-218", "ICON7", "NCCN Guidelines v2024"],
            "thresholds": self.BURDEN_THRESHOLDS,
            "expectations": self.RESPONSE_EXPECTATIONS,
            "analyzed_at": datetime.utcnow().isoformat(),
            "run_id": f"ca125_{int(datetime.utcnow().timestamp())}"
        }
        
        return {
            "burden_class": burden_class,
            "burden_score": burden_score,
            "forecast": forecast,
            "resistance_signals": resistance_signals,
            "monitoring_strategy": monitoring_strategy,
            "clinical_notes": clinical_notes,
            "provenance": provenance
        }
    
    def _classify_burden(self, ca125_value: float) -> str:
        """
        Classify CA-125 burden into MINIMAL/MODERATE/SIGNIFICANT/EXTENSIVE.
        
        Args:
            ca125_value: CA-125 value in U/mL
        
        Returns:
            Burden class string
        """
        for burden_class, (low, high) in self.BURDEN_THRESHOLDS.items():
            if low <= ca125_value < high:
                return burden_class
        return "EXTENSIVE"  # Default for very high values
    
    def _calculate_burden_score(self, ca125_value: float) -> float:
        """
        Calculate numeric burden score (0-1).
        
        Higher CA-125 → higher burden score.
        Logarithmic scale to handle wide range (35 - 10,000+).
        
        Args:
            ca125_value: CA-125 value in U/mL
        
        Returns:
            Burden score (0-1)
        """
        import math
        
        # Log scale: 35 (normal) → 0.0, 2000 (high) → ~0.75, 10000 (very high) → ~0.95
        if ca125_value <= 35:
            return 0.0
        
        # Log10 scale with normalization
        log_value = math.log10(ca125_value)
        log_normal = math.log10(35)  # Normal upper limit
        log_max = math.log10(10000)  # Very high (cap)
        
        score = (log_value - log_normal) / (log_max - log_normal)
        return min(max(score, 0.0), 1.0)  # Clamp to [0, 1]
    
    def _generate_forecast(
        self,
        current_value: float,
        baseline_value: Optional[float],
        cycle: Optional[int]
    ) -> Dict[str, Any]:
        """
        Generate response forecast milestones.
        
        Args:
            current_value: Current CA-125 value
            baseline_value: Baseline CA-125 before treatment
            cycle: Current treatment cycle
        
        Returns:
            Forecast dict with cycle 3, 6 targets and CR threshold
        """
        forecast = {
            "complete_response_target": self.RESPONSE_EXPECTATIONS["complete_response_threshold"],
            "complete_response_target_unit": "U/mL"
        }
        
        if baseline_value:
            # Calculate expected values based on baseline
            cycle3_expected = baseline_value * (1 - self.RESPONSE_EXPECTATIONS["cycle3_drop_percent"] / 100)
            cycle6_expected = baseline_value * (1 - self.RESPONSE_EXPECTATIONS["cycle6_drop_percent"] / 100)
            
            forecast["cycle3_expected_value"] = round(cycle3_expected, 1)
            forecast["cycle3_expected_drop_percent"] = self.RESPONSE_EXPECTATIONS["cycle3_drop_percent"]
            forecast["cycle6_expected_value"] = round(cycle6_expected, 1)
            forecast["cycle6_expected_drop_percent"] = self.RESPONSE_EXPECTATIONS["cycle6_drop_percent"]
            
            # If current cycle provided, show progress
            if cycle:
                if baseline_value > 0:
                    actual_drop_percent = ((baseline_value - current_value) / baseline_value) * 100
                    forecast["actual_drop_percent"] = round(actual_drop_percent, 1)
                    forecast["current_cycle"] = cycle
                    
                    # Compare to expectations
                    if cycle >= 3:
                        expected_drop = self.RESPONSE_EXPECTATIONS["cycle3_drop_percent"]
                        if actual_drop_percent >= expected_drop:
                            forecast["cycle3_status"] = "ON_TRACK"
                        else:
                            forecast["cycle3_status"] = "BELOW_EXPECTED"
                    
                    if cycle >= 6:
                        expected_drop = self.RESPONSE_EXPECTATIONS["cycle6_drop_percent"]
                        if actual_drop_percent >= expected_drop:
                            forecast["cycle6_status"] = "ON_TRACK"
                        else:
                            forecast["cycle6_status"] = "BELOW_EXPECTED"
        else:
            # No baseline - provide general expectations
            forecast["note"] = "Baseline CA-125 not available. General expectations: ≥70% drop by cycle 3, ≥90% by cycle 6 for chemo-sensitive disease."
        
        return forecast
    
    def _detect_resistance_signals(
        self,
        current_value: float,
        baseline_value: float,
        cycle: Optional[int]
    ) -> list:
        """
        Detect resistance signals based on CA-125 kinetics.
        
        Resistance signals:
        1. On-therapy rise (CA-125 increases while on treatment)
        2. <50% drop by cycle 3 (inadequate response)
        3. Velocity worsening (rate of decline slowing or reversing)
        
        Args:
            current_value: Current CA-125 value
            baseline_value: Baseline CA-125 before treatment
            cycle: Current treatment cycle
        
        Returns:
            List of resistance signal dicts
        """
        signals = []
        
        if baseline_value <= 0:
            return signals
        
        # Calculate drop percentage
        drop_percent = ((baseline_value - current_value) / baseline_value) * 100
        
        # Signal 1: On-therapy rise
        if current_value > baseline_value:
            signals.append({
                "type": "ON_THERAPY_RISE",
                "severity": "HIGH",
                "message": f"CA-125 rising on therapy (baseline: {baseline_value:.1f} → current: {current_value:.1f})",
                "recommendation": "Consider alternative therapy. Rising CA-125 on treatment indicates resistance."
            })
        
        # Signal 2: <50% drop by cycle 3
        if cycle and cycle >= 3:
            if drop_percent < self.RESPONSE_EXPECTATIONS["resistance_threshold_percent"]:
                signals.append({
                    "type": "INADEQUATE_RESPONSE_CYCLE3",
                    "severity": "HIGH",
                    "message": f"<50% drop by cycle 3 (actual: {drop_percent:.1f}%)",
                    "recommendation": "Inadequate response. Consider imaging correlation and treatment intensification or switch."
                })
        
        # Signal 3: Minimal drop (<30%) by any cycle post-cycle 2
        if cycle and cycle >= 2:
            if 0 < drop_percent < 30:
                signals.append({
                    "type": "MINIMAL_RESPONSE",
                    "severity": "MODERATE",
                    "message": f"Minimal CA-125 decline ({drop_percent:.1f}% drop)",
                    "recommendation": "Monitor closely. Consider imaging to assess anatomic response."
                })
        
        return signals
    
    def _recommend_monitoring(
        self,
        burden_class: str,
        treatment_ongoing: bool
    ) -> Dict[str, Any]:
        """
        Recommend CA-125 monitoring frequency and strategy.
        
        Args:
            burden_class: Burden classification
            treatment_ongoing: Whether patient is on treatment
        
        Returns:
            Monitoring strategy dict
        """
        if treatment_ongoing:
            # On treatment: monitor every cycle (every 3 weeks for standard chemo)
            frequency = "every_3_weeks"
            timing = "Just before each chemotherapy cycle"
            rationale = "Track response kinetics and detect resistance early"
        else:
            # Pre-treatment or maintenance: frequency based on burden
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
            "method": "Serum CA-125 (U/mL)"
        }
    
    def _generate_clinical_notes(
        self,
        current_value: float,
        burden_class: str,
        baseline_value: Optional[float],
        cycle: Optional[int],
        resistance_signals: list
    ) -> str:
        """
        Generate clinical interpretation notes for oncologist.
        
        Args:
            current_value: Current CA-125 value
            burden_class: Burden classification
            baseline_value: Baseline value (if available)
            cycle: Current cycle (if on treatment)
            resistance_signals: List of resistance signals
        
        Returns:
            Clinical notes string
        """
        notes = []
        
        # Burden interpretation
        if burden_class == "EXTENSIVE":
            notes.append(f"CA-125 of {current_value:.1f} U/mL indicates EXTENSIVE disease burden (>1,000).")
        elif burden_class == "SIGNIFICANT":
            notes.append(f"CA-125 of {current_value:.1f} U/mL indicates SIGNIFICANT disease burden (500-1,000).")
        elif burden_class == "MODERATE":
            notes.append(f"CA-125 of {current_value:.1f} U/mL indicates MODERATE disease burden (100-500).")
        else:
            notes.append(f"CA-125 of {current_value:.1f} U/mL is within normal to minimal range (<100).")
        
        # Trackability
        if current_value > 100:
            notes.append("CA-125 is highly trackable and suitable for response monitoring.")
        
        # Response assessment (if on treatment)
        if baseline_value and cycle:
            drop_percent = ((baseline_value - current_value) / baseline_value) * 100
            if drop_percent > 0:
                notes.append(f"On-treatment response: {drop_percent:.1f}% reduction from baseline (cycle {cycle}).")
                
                if cycle >= 3:
                    if drop_percent >= 70:
                        notes.append("✓ Response ON TRACK for cycle 3 (≥70% drop expected).")
                    else:
                        notes.append("⚠ Response BELOW EXPECTED for cycle 3 (<70% drop). Consider imaging correlation.")
                
                if cycle >= 6:
                    if drop_percent >= 90:
                        notes.append("✓ Excellent response (≥90% drop by cycle 6).")
                    else:
                        notes.append("⚠ Sub-optimal response for cycle 6 (<90% drop). Consider alternative strategies.")
        
        # Resistance signals
        if resistance_signals:
            notes.append(f"⚠️ {len(resistance_signals)} resistance signal(s) detected:")
            for signal in resistance_signals:
                notes.append(f"  - {signal['type']}: {signal['message']}")
        
        # Complete response target
        if current_value > self.RESPONSE_EXPECTATIONS["complete_response_threshold"]:
            cr_target = self.RESPONSE_EXPECTATIONS["complete_response_threshold"]
            notes.append(f"Complete response target: <{cr_target} U/mL. Additional therapy cycles likely needed.")
        else:
            notes.append("✓ CA-125 within complete response range (<35 U/mL).")
        
        return " ".join(notes)


    def analyze(self, ca125_value: float) -> Dict[str, Any]:
        """
        Simplified analyze method for trial matching (wrapper around analyze_ca125).
        
        Args:
            ca125_value: Current CA-125 level (U/mL)
            
        Returns:
            Simplified intelligence dict for trial matching
        """
        full_result = self.analyze_ca125(ca125_value)
        
        # Extract burden class
        burden_class = full_result['burden_class']
        
        # Build simplified forecast
        forecast = full_result.get('forecast', {})
        expected_response = {
            "chemo_sensitivity": "LIKELY_SENSITIVE",  # 70-80% respond to platinum
            "cycle3_expected_drop": "≥70%",
            "cycle6_expected_drop": "≥90%",
            "target": "<35 U/mL",
            "cycle3_expected_value": f"{int(ca125_value * 0.2)}-{int(ca125_value * 0.3)} (70-80% drop expected)",
            "cycle6_expected_value": f"<{int(ca125_value * 0.1)} (90%+ drop expected)",
            "resistance_signal": "⚠️ Alert if: On-therapy rise OR <50% drop by cycle 3"
        }
        
        # Trial preferences based on CA-125
        trial_preferences = []
        boost_keywords = []
        
        if ca125_value > 1000:  # Extensive disease
            trial_preferences.extend([
                "trials_measuring_ca125_response",
                "trials_targeting_bulk_disease",
                "trials_with_cytoreductive_intent",
                "trials_with_IP_chemotherapy",
            ])
            boost_keywords.extend([
                "CA-125 response",
                "bulk disease",
                "cytoreduction",
                "intraperitoneal",
                "neoadjuvant"
            ])
        
        # CA-125 kinetics trials
        trial_preferences.append("trials_with_ca125_kinetics")
        boost_keywords.extend(["CA-125", "tumor marker"])
        
        return {
            "ca125_value": ca125_value,
            "disease_burden": burden_class,
            "marker_utility": "HIGHLY_TRACKABLE",
            "expected_response": expected_response,
            "trial_preferences": trial_preferences,
            "boost_keywords": boost_keywords,
            "monitoring_strategy": "Primary tumor marker - track every 3 weeks during chemo"
        }


# Singleton instance
_ca125_service = None


def get_ca125_service() -> CA125IntelligenceService:
    """Get singleton CA-125 Intelligence Service instance."""
    global _ca125_service
    if _ca125_service is None:
        _ca125_service = CA125IntelligenceService()
    return _ca125_service
