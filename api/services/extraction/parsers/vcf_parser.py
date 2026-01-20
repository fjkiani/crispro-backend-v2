"""
VCF (Variant Call Format) Parser

Supports:
- VCF 4.1, 4.2, 4.3
- Multi-sample VCFs (uses first sample)
- Gzipped VCF files
"""
from typing import BinaryIO, Union, List, Dict, Optional
import io
import gzip
import logging

logger = logging.getLogger(__name__)


class VCFParser:
    """Parse VCF files and extract mutations."""
    
    def __init__(self):
        self.required_fields = ['#CHROM', 'POS', 'ID', 'REF', 'ALT', 'QUAL', 'FILTER', 'INFO']
    
    async def parse(
        self,
        file: Union[BinaryIO, bytes, str],
        metadata: Optional[Dict] = None
    ) -> Dict:
        """
        Parse VCF file and extract mutations.
        
        Args:
            file: VCF file content (binary, bytes, or path)
            metadata: Optional metadata
            
        Returns:
            Dict with mutations and header info
        """
        # Handle different input types
        if isinstance(file, bytes):
            file = io.BytesIO(file)
        elif isinstance(file, str):
            # Check if gzipped
            try:
                with gzip.open(file, 'rt') as f:
                    content = f.read()
                file = io.StringIO(content)
            except (gzip.BadGzipFile, OSError):
                with open(file, 'r') as f:
                    file = io.StringIO(f.read())
        
        mutations = []
        header_info = {}
        columns = []
        
        # Read file line by line
        if hasattr(file, 'read'):
            lines = file.readlines() if hasattr(file, 'readlines') else [file.read()]
        else:
            lines = file if isinstance(file, list) else [file]
        
        for line in lines:
            if isinstance(line, bytes):
                line = line.decode('utf-8')
            line = line.strip()
            
            if not line:
                continue
            
            # Parse header lines
            if line.startswith('##'):
                self._parse_header_line(line, header_info)
                continue
            
            # Parse column header
            if line.startswith('#CHROM'):
                columns = line[1:].split('\t')  # Remove # from #CHROM
                continue
            
            # Parse variant line
            if line and not line.startswith('#'):
                mutation = self._parse_variant_line(line, columns)
                if mutation:
                    mutations.append(mutation)
        
        return {
            'mutations': mutations,
            'vcf_header': header_info,
            'mutation_count': len(mutations)
        }
    
    def _parse_header_line(self, line: str, header_info: Dict):
        """Parse a header line (##INFO, ##FORMAT, etc.)."""
        if line.startswith('##INFO='):
            # Extract INFO field definition
            # Format: ##INFO=<ID=GENE,Number=1,Type=String,Description="Gene name">
            try:
                if '<' in line and '>' in line:
                    info_def = line[line.index('<')+1:line.index('>')]
                    parts = info_def.split(',')
                    for part in parts:
                        if '=' in part:
                            key, value = part.split('=', 1)
                            if key == 'ID':
                                header_info[f"INFO_{value}"] = info_def
            except Exception as e:
                logger.debug(f"Failed to parse header line: {e}")
        elif line.startswith('##fileformat='):
            header_info['fileformat'] = line.split('=', 1)[1]
        elif line.startswith('##'):
            # Store other header lines
            if '=' in line:
                key, value = line[2:].split('=', 1)
                header_info[key] = value
    
    def _parse_variant_line(self, line: str, columns: List[str]) -> Optional[Dict]:
        """Parse a single variant line."""
        fields = line.split('\t')
        
        if len(fields) < 8:
            logger.warning(f"VCF line has insufficient fields: {len(fields)}")
            return None
        
        mutation = {
            'chrom': fields[0].replace('chr', ''),
            'pos': int(fields[1]) if fields[1] != '.' else None,
            'id': fields[2] if fields[2] != '.' else None,
            'ref': fields[3],
            'alt': fields[4].split(',')[0] if fields[4] != '.' else None,  # Take first ALT
            'qual': float(fields[5]) if fields[5] != '.' else None,
            'filter': fields[6],
            'info': self._parse_info(fields[7]) if len(fields) > 7 else {}
        }
        
        # Extract gene and variant from INFO field
        info = mutation['info']
        mutation['gene'] = info.get('GENE') or info.get('Gene') or info.get('SYMBOL') or ''
        
        # Extract HGVS notation
        mutation['hgvs_c'] = info.get('HGVSc') or info.get('HGVS_c') or info.get('HGVSc') or ''
        mutation['hgvs_p'] = info.get('HGVSp') or info.get('HGVS_p') or info.get('HGVSp') or ''
        
        # Generate variant string
        if mutation['hgvs_p']:
            mutation['variant'] = mutation['hgvs_p']
        elif mutation['hgvs_c']:
            mutation['variant'] = mutation['hgvs_c']
        else:
            mutation['variant'] = f"{mutation['ref']}>{mutation['alt']}" if mutation['alt'] else ''
        
        # Extract VAF if available in sample data
        if len(fields) > 9:  # Has sample data
            format_fields = fields[8].split(':')
            sample_data = fields[9].split(':')
            format_dict = dict(zip(format_fields, sample_data))
            
            # Try different VAF field names
            if 'AF' in format_dict:
                try:
                    af_value = format_dict['AF']
                    if ',' in af_value:
                        af_value = af_value.split(',')[0]  # Take first allele frequency
                    mutation['vaf'] = float(af_value)
                except (ValueError, TypeError):
                    pass
            elif 'AD' in format_dict and 'DP' in format_dict:
                # Calculate from allele depth
                try:
                    ad = [int(x) for x in format_dict['AD'].split(',')]
                    dp = int(format_dict['DP'])
                    if dp > 0 and len(ad) > 1:
                        mutation['vaf'] = ad[1] / dp
                except (ValueError, TypeError, IndexError):
                    pass
        
        # Extract coverage if available
        if 'DP' in mutation.get('info', {}):
            try:
                mutation['coverage'] = int(mutation['info']['DP'])
            except (ValueError, TypeError):
                pass
        
        # Infer zygosity from GT field
        if len(fields) > 9:
            format_fields = fields[8].split(':')
            sample_data = fields[9].split(':')
            format_dict = dict(zip(format_fields, sample_data))
            
            if 'GT' in format_dict:
                gt = format_dict['GT']
                if gt in ['0/1', '0|1', '1/0', '1|0']:
                    mutation['zygosity'] = 'heterozygous'
                elif gt in ['1/1', '1|1']:
                    mutation['zygosity'] = 'homozygous'
                elif gt in ['1']:
                    mutation['zygosity'] = 'hemizygous'
        
        return mutation
    
    def _parse_info(self, info_str: str) -> Dict:
        """Parse INFO field into dictionary."""
        info = {}
        if not info_str or info_str == '.':
            return info
        
        for item in info_str.split(';'):
            if '=' in item:
                key, value = item.split('=', 1)
                # Try to convert to appropriate type
                if value.lower() in ['true', 'yes']:
                    info[key] = True
                elif value.lower() in ['false', 'no']:
                    info[key] = False
                else:
                    # Try numeric conversion
                    try:
                        if '.' in value:
                            info[key] = float(value)
                        else:
                            info[key] = int(value)
                    except ValueError:
                        info[key] = value
            else:
                info[item] = True
        
        return info


