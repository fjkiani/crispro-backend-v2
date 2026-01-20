"""
Risk stratification and confidence configuration constants.

Manager Q9, Q15, Q16 thresholds and rules.
"""

# Manager Q9: Risk stratification thresholds
RISK_STRATIFICATION_THRESHOLDS = {
    "high_risk_probability": 0.70,      # HIGH: >=0.70 probability + >=2 signals
    "medium_risk_probability": 0.50,    # MEDIUM: 0.50-0.69 or exactly 1 signal
    "min_signals_for_high": 2,          # Minimum signals required for HIGH risk
}

# Manager Q15: Confidence cap when CA-125 missing
# Manager Q16: Baseline penalty configuration
CONFIDENCE_CONFIG = {
    "baseline_penalty": 0.80,           # 20% penalty if baseline missing (Manager Q16)
    "ca125_missing_cap": 0.60,          # Cap at 0.60 if no CA-125 and <2 signals (Manager Q15)
    "patient_baseline_confidence": 0.90, # Confidence when patient baseline available
    "population_baseline_confidence": 0.60,  # Confidence when using population average
}
