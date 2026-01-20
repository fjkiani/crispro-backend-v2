"""
Text Parser - For clinical notes and unstructured text
"""
from typing import BinaryIO, Union, Dict, Optional
import io
import re
import logging

logger = logging.getLogger(__name__)


class TextParser:
    """Parse text files and extract basic mutation mentions."""
    
    async def parse(
        self,
        file: Union[BinaryIO, bytes, str],
        metadata: Optional[Dict] = None
    ) -> Dict:
        """
        Parse text file and extract mutation mentions.
        
        Uses simple pattern matching to find gene mutations.
        """
        # Read text content
        if isinstance(file, bytes):
            text = file.decode('utf-8', errors='ignore')
        elif isinstance(file, str):
            with open(file, 'r', encoding='utf-8', errors='ignore') as f:
                text = f.read()
        else:
            # BinaryIO
            content = file.read()
            if isinstance(content, bytes):
                text = content.decode('utf-8', errors='ignore')
            else:
                text = content
        
        # Extract mutations using pattern matching
        mutations = []
        
        # Pattern: "BRAF V600E" or "BRAF p.V600E" or "BRAF mutation"
        mutation_pattern = r'\b([A-Z0-9]+)\s+(?:p\.)?([A-Z]\d+[A-Z*]|del|ins|fs|mutation)\b'
        matches = re.finditer(mutation_pattern, text, re.IGNORECASE)
        
        seen = set()
        for match in matches:
            gene = match.group(1).upper()
            variant = match.group(2)
            
            # Skip common false positives
            if gene in ['TMB', 'MSI', 'PD', 'HRD', 'VAF', 'NGS', 'DNA', 'RNA', 'PCR']:
                continue
            
            # Skip if already seen
            key = f"{gene}_{variant}"
            if key in seen:
                continue
            seen.add(key)
            
            mutations.append({
                'gene': gene,
                'variant': variant if variant != 'mutation' else '',
                'hgvs_p': f"p.{variant}" if variant and not variant.startswith('p.') and variant != 'mutation' else None,
                'hgvs_c': None,
                'vaf': None,
                'classification': None
            })
        
        return {
            'mutations': mutations,
            'mutation_count': len(mutations),
            'extraction_method': 'pattern_matching',
            'note': 'Text extraction uses simple pattern matching. For accurate results, use structured formats (VCF, MAF, JSON) or PDF with LLM extraction.'
        }


