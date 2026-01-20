"""
PDF Parser - LLM-based extraction from NGS reports

Supports:
- Foundation Medicine reports
- Tempus reports
- Guardant Health reports
- Generic lab reports
"""
from typing import BinaryIO, Union, Dict, Optional
import io
import json
import logging

logger = logging.getLogger(__name__)

# Try to import PDF and LLM libraries
try:
    import fitz  # PyMuPDF
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False
    logger.warning("PyMuPDF not available - PDF parsing will be limited")

try:
    from google import genai
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False
    logger.warning("google-genai not available - LLM extraction will be disabled")


class PDFParser:
    """
    Extract mutation and clinical data from PDF reports using LLM.
    """
    
    EXTRACTION_PROMPT = """You are a clinical genomics expert. Extract all mutations and clinical data from this NGS report.

Return JSON with this structure:
{{
    "patient_id": "string or null",
    "disease": "cancer type",
    "mutations": [
        {{
            "gene": "BRAF",
            "variant": "V600E",
            "hgvs_p": "p.Val600Glu",
            "hgvs_c": "c.1799T>A",
            "vaf": 0.45,
            "classification": "Pathogenic"
        }}
    ],
    "clinical_data": {{
        "stage": "IVB",
        "histology": "adenocarcinoma",
        "prior_treatments": ["carboplatin", "paclitaxel"],
        "biomarkers": {{
            "TMB": 10.2,
            "MSI": "Stable",
            "PD-L1": "50%"
        }}
    }},
    "germline_mutations": [],
    "lab_name": "Foundation Medicine",
    "report_date": "2025-01-15"
}}

IMPORTANT:
- Extract ALL mutations listed, including VUS
- Use standard HGVS notation
- Normalize gene symbols to HGNC
- If data is unclear, mark as null

Report text:
{report_text}"""
    
    def __init__(self, model_id: str = "gemini-2.0-flash"):
        """Initialize PDF parser."""
        self.model_id = model_id
        self.client = None
        
        if LLM_AVAILABLE:
            try:
                self.client = genai.Client()
            except Exception as e:
                logger.warning(f"Failed to initialize Gemini client: {e}")
    
    async def parse(
        self,
        file: Union[BinaryIO, bytes],
        metadata: Optional[Dict] = None
    ) -> Dict:
        """
        Parse PDF report and extract structured data.
        
        Args:
            file: PDF file content
            metadata: Optional metadata
            
        Returns:
            Dict with extracted data
        """
        # Step 1: Extract text from PDF
        text = self._extract_text(file)
        logger.info(f"Extracted {len(text)} characters from PDF")
        
        if not text:
            return {
                'mutations': [],
                'error': 'no_text_extracted',
                'extraction_method': 'pdf_text_extraction_failed'
            }
        
        # Step 2: Use LLM to extract structured data (if available)
        if self.client and LLM_AVAILABLE:
            try:
                prompt = self.EXTRACTION_PROMPT.format(report_text=text[:50000])  # Limit to 50k chars
                
                response = self.client.models.generate_content(
                    model=self.model_id,
                    contents=prompt,
                    config={
                        "response_mime_type": "application/json",
                        "temperature": 0.1  # Low temperature for accuracy
                    }
                )
                
                # Parse JSON response
                try:
                    extracted = json.loads(response.text)
                    extracted['extraction_method'] = 'llm_pdf_extraction'
                    extracted['source_text_length'] = len(text)
                    return extracted
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse LLM response as JSON: {e}")
                    logger.debug(f"Response text: {response.text[:500]}")
                    # Fall through to pattern-based extraction
            except Exception as e:
                logger.warning(f"LLM extraction failed: {e}, falling back to pattern matching")
        
        # Step 3: Fallback to pattern-based extraction
        extracted = self._pattern_based_extraction(text)
        extracted['extraction_method'] = 'pattern_based_extraction'
        extracted['source_text_length'] = len(text)
        
        return extracted
    
    def _extract_text(self, file: Union[BinaryIO, bytes]) -> str:
        """Extract text content from PDF."""
        if not PDF_AVAILABLE:
            logger.error("PyMuPDF not available - cannot extract PDF text")
            return ""
        
        try:
            if isinstance(file, bytes):
                file = io.BytesIO(file)
            
            doc = fitz.open(stream=file.read(), filetype="pdf")
            text = ""
            for page in doc:
                text += page.get_text()
            doc.close()
            
            return text
        except Exception as e:
            logger.error(f"Failed to extract PDF text: {e}")
            return ""
    
    def _pattern_based_extraction(self, text: str) -> Dict:
        """Fallback pattern-based extraction when LLM is unavailable."""
        import re
        
        mutations = []
        
        # Pattern for gene mutations: "BRAF V600E" or "BRAF p.V600E"
        mutation_pattern = r'([A-Z0-9]+)\s+(?:p\.)?([A-Z]\d+[A-Z*]|del|ins|fs)'
        matches = re.finditer(mutation_pattern, text, re.IGNORECASE)
        
        for match in matches:
            gene = match.group(1).upper()
            variant = match.group(2)
            
            # Skip common false positives
            if gene in ['TMB', 'MSI', 'PD', 'HRD', 'VAF', 'NGS']:
                continue
            
            mutations.append({
                'gene': gene,
                'variant': variant,
                'hgvs_p': f"p.{variant}" if not variant.startswith('p.') else variant,
                'hgvs_c': None,
                'vaf': None,
                'classification': None
            })
        
        # Extract TMB if mentioned
        tmb_match = re.search(r'TMB[:\s]+([\d.]+)', text, re.IGNORECASE)
        tmb = float(tmb_match.group(1)) if tmb_match else None
        
        # Extract MSI status
        msi_match = re.search(r'MSI[:\s]+(MSI-H|MSI-High|MSS|MSI-Stable)', text, re.IGNORECASE)
        msi_status = msi_match.group(1) if msi_match else None
        
        return {
            'mutations': mutations,
            'clinical_data': {
                'biomarkers': {
                    'TMB': tmb,
                    'MSI': msi_status
                }
            } if tmb or msi_status else {},
            'lab_name': None,
            'report_date': None
        }


