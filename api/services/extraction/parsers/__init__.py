"""
File parsers for data extraction.
"""
from .vcf_parser import VCFParser
from .maf_parser import MAFParser
from .pdf_parser import PDFParser
from .json_parser import JSONParser
from .text_parser import TextParser

__all__ = [
    'VCFParser',
    'MAFParser',
    'PDFParser',
    'JSONParser',
    'TextParser'
]


