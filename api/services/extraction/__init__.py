"""
Data Extraction Service - Module 01

Extracts structured patient data from various file formats:
- VCF (Variant Call Format)
- MAF (Mutation Annotation Format)
- PDF (NGS reports - LLM-based extraction)
- JSON (Structured mutation data)
- TXT/CSV (Clinical notes)
"""

from .extraction_agent import DataExtractionAgent
from .models import PatientProfile, Mutation, GermlinePanel, ClinicalData, Demographics

__all__ = [
    'DataExtractionAgent',
    'PatientProfile',
    'Mutation',
    'GermlinePanel',
    'ClinicalData',
    'Demographics'
]


