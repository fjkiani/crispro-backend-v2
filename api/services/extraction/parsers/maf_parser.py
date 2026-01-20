"""
MAF (Mutation Annotation Format) Parser

MAF is a tab-delimited format with specific columns for mutation data.
"""
from typing import BinaryIO, Union, Dict, Optional, List
import io
import csv
import logging

logger = logging.getLogger(__name__)


class MAFParser:
    """Parse MAF files and extract mutations."""
    
    # Standard MAF column names
    GENE_COLUMNS = ['Hugo_Symbol', 'Gene', 'Gene_Symbol']
    VARIANT_COLUMNS = ['HGVSp_Short', 'Protein_Change', 'Variant', 'AAChange']
    HGVS_C_COLUMNS = ['HGVSc', 'cDNA_Change']
    CHROM_COLUMNS = ['Chromosome', 'Chrom']
    POS_COLUMNS = ['Start_Position', 'Start', 'Position']
    REF_COLUMNS = ['Reference_Allele', 'Ref']
    ALT_COLUMNS = ['Tumor_Seq_Allele2', 'Tumor_Seq_Allele1', 'Alt']
    VAF_COLUMNS = ['t_alt_count', 't_vaf', 'VAF']
    COVERAGE_COLUMNS = ['t_depth', 't_ref_count', 'Coverage']
    
    async def parse(
        self,
        file: Union[BinaryIO, bytes, str],
        metadata: Optional[Dict] = None
    ) -> Dict:
        """
        Parse MAF file and extract mutations.
        
        Args:
            file: MAF file content (binary, bytes, or path)
            metadata: Optional metadata
            
        Returns:
            Dict with mutations
        """
        # Handle different input types
        if isinstance(file, bytes):
            file = io.BytesIO(file)
        elif isinstance(file, str):
            file = open(file, 'r', encoding='utf-8')
        
        mutations = []
        
        try:
            # Read as TSV
            reader = csv.DictReader(file, delimiter='\t')
            
            for row in reader:
                mutation = self._parse_maf_row(row)
                if mutation:
                    mutations.append(mutation)
        
        except Exception as e:
            logger.error(f"Failed to parse MAF file: {e}")
        finally:
            if isinstance(file, io.TextIOWrapper):
                file.close()
        
        return {
            'mutations': mutations,
            'mutation_count': len(mutations)
        }
    
    def _parse_maf_row(self, row: Dict[str, str]) -> Optional[Dict]:
        """Parse a single MAF row."""
        # Find gene column
        gene = None
        for col in self.GENE_COLUMNS:
            if col in row and row[col]:
                gene = row[col].strip()
                break
        
        if not gene:
            return None
        
        # Find variant/HGVS_p column
        variant = None
        hgvs_p = None
        for col in self.VARIANT_COLUMNS:
            if col in row and row[col]:
                value = row[col].strip()
                if value.startswith('p.'):
                    hgvs_p = value
                    variant = value.replace('p.', '')
                else:
                    variant = value
                    hgvs_p = f"p.{value}" if value else None
                break
        
        # Find HGVS_c
        hgvs_c = None
        for col in self.HGVS_C_COLUMNS:
            if col in row and row[col]:
                hgvs_c = row[col].strip()
                break
        
        # Find chromosome
        chrom = None
        for col in self.CHROM_COLUMNS:
            if col in row and row[col]:
                chrom = str(row[col]).replace('chr', '').replace('Chr', '')
                break
        
        # Find position
        pos = None
        for col in self.POS_COLUMNS:
            if col in row and row[col]:
                try:
                    pos = int(row[col])
                except (ValueError, TypeError):
                    pass
                break
        
        # Find ref/alt
        ref = None
        for col in self.REF_COLUMNS:
            if col in row and row[col]:
                ref = row[col].strip()
                break
        
        alt = None
        for col in self.ALT_COLUMNS:
            if col in row and row[col]:
                alt = row[col].strip()
                break
        
        # Find VAF
        vaf = None
        for col in self.VAF_COLUMNS:
            if col in row and row[col]:
                try:
                    vaf = float(row[col])
                except (ValueError, TypeError):
                    pass
                break
        
        # Find coverage
        coverage = None
        for col in self.COVERAGE_COLUMNS:
            if col in row and row[col]:
                try:
                    coverage = int(row[col])
                except (ValueError, TypeError):
                    pass
                break
        
        # Classification
        classification = row.get('Variant_Classification') or row.get('Classification') or None
        
        return {
            'gene': gene,
            'variant': variant or hgvs_p or f"{ref}>{alt}" if ref and alt else '',
            'hgvs_c': hgvs_c,
            'hgvs_p': hgvs_p,
            'chromosome': chrom,
            'position': pos,
            'ref': ref,
            'alt': alt,
            'vaf': vaf,
            'coverage': coverage,
            'classification': classification
        }


