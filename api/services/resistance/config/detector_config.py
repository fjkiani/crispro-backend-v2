"""
Detector-specific configuration constants.

Thresholds and gene lists for individual signal detectors.
"""

# Manager Q9: DNA Repair Restoration threshold
# Restoration detected if capacity changes >15%
DNA_REPAIR_THRESHOLD = 0.15

# MM High-Risk Gene Markers (Proxy SAE - Gene-Level Validated)
# Source: MMRF CoMMpass GDC data, N=219 patients with mutations
MM_HIGH_RISK_GENES = {
    "DIS3": {
        "relative_risk": 2.08,
        "p_value": 0.0145,
        "confidence": 0.95,
        "validation_source": "MMRF_CoMMpass_GDC",
        "n_mutated": 38,
        "mechanism": "RNA surveillance deficiency",
        "drug_classes_affected": ["proteasome_inhibitor", "imid"],
        "rationale": "DIS3 loss-of-function impairs RNA quality control, associated with 2x mortality risk"
    },
    "TP53": {
        "relative_risk": 1.90,
        "p_value": 0.11,
        "confidence": 0.75,  # Trend, not significant
        "validation_source": "MMRF_CoMMpass_GDC",
        "n_mutated": 16,
        "mechanism": "Genomic instability, therapy resistance",
        "drug_classes_affected": ["proteasome_inhibitor", "imid", "anti_cd38"],
        "rationale": "TP53 mutations confer genomic instability and multi-drug resistance"
    },
    "KRAS": {
        "relative_risk": 0.93,
        "p_value": 0.87,
        "confidence": 0.0,  # No signal
        "validation_source": "MMRF_CoMMpass_GDC",
        "n_mutated": 73,
        "mechanism": "MAPK pathway activation",
        "drug_classes_affected": [],
        "rationale": "KRAS mutations do not predict mortality in MM (no validated signal)"
    },
    "NRAS": {
        "relative_risk": 0.93,
        "p_value": 0.87,
        "confidence": 0.0,  # No signal
        "validation_source": "MMRF_CoMMpass_GDC",
        "n_mutated": 52,
        "mechanism": "MAPK pathway activation",
        "drug_classes_affected": [],
        "rationale": "NRAS mutations do not predict mortality in MM (no validated signal)"
    },
}
