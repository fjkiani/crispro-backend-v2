"""
Diagnostic biomarkers for resistance prediction.

Purpose: "What type of cancer do I have?"

Current detectors:
- DDR_bin Scoring Engine: Pan-solid-tumor DDR deficiency classifier

Future detectors:
- Subtype classification
- Molecular typing (MSI-H, etc.)
- Disease staging biomarkers
"""

from .ddr_bin_scoring import (
    assign_ddr_status,
    get_ddr_status_for_patient,
)

__all__ = [
    "assign_ddr_status",
    "get_ddr_status_for_patient",
]
