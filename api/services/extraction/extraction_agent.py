"""
Data Extraction Agent - Module 01

Intelligent agent for extracting structured patient data from various file formats.
"""
from typing import Union, BinaryIO, List, Dict, Optional, Any
import logging
import uuid
from datetime import datetime

from .models import (
    PatientProfile, Mutation, GermlinePanel, ClinicalData, Demographics,
    Zygosity, MutationSource
)
from .parsers import VCFParser, MAFParser, PDFParser, JSONParser, TextParser

logger = logging.getLogger(__name__)


class DataExtractionAgent:
    """
    Intelligent agent for extracting structured patient data from various file formats.
    
    Capabilities:
    - Multi-format parsing (VCF, MAF, PDF, JSON, TXT)
    - Mutation validation and normalization
    - Data quality assessment
    - Provenance tracking
    """
    
    def __init__(self):
        """Initialize data extraction agent."""
        # Initialize parsers
        self.parsers = {
            'vcf': VCFParser(),
            'maf': MAFParser(),
            'pdf': PDFParser(),
            'json': JSONParser(),
            'txt': TextParser(),
            'csv': TextParser(),
        }
        
        logger.info("DataExtractionAgent initialized")
    
    async def extract(
        self,
        file: Union[BinaryIO, bytes, str],
        file_type: str,
        metadata: Optional[Dict] = None
    ) -> PatientProfile:
        """
        Main extraction entry point.
        
        Args:
            file: File content (binary, bytes, or path)
            file_type: One of 'vcf', 'maf', 'pdf', 'json', 'txt', 'csv'
            metadata: Optional metadata (lab, date, patient_id)
        
        Returns:
            PatientProfile with extracted data
        """
        if metadata is None:
            metadata = {}
        
        logger.info(f"Starting extraction for file_type={file_type}")
        
        # Step 1: Parse file
        parser = self.parsers.get(file_type.lower())
        if not parser:
            raise ValueError(f"Unsupported file type: {file_type}. Supported: {list(self.parsers.keys())}")
        
        raw_data = await parser.parse(file, metadata)
        
        # Step 2: Extract mutations
        mutations = self._extract_mutations(raw_data)
        
        # Step 3: Validate and normalize mutations
        validated_mutations = []
        for mut_data in mutations:
            try:
                mutation = self._build_mutation(mut_data)
                if self._validate_mutation(mutation):
                    validated_mutations.append(mutation)
                else:
                    logger.warning(f"Invalid mutation skipped: {mutation.gene} {mutation.variant}")
            except Exception as e:
                logger.warning(f"Failed to build mutation from {mut_data}: {e}")
        
        # Step 4: Extract clinical data
        clinical_data = self._extract_clinical_data(raw_data)
        
        # Step 5: Extract demographics
        demographics = self._extract_demographics(raw_data)
        
        # Step 6: Extract germline panel (if available)
        germline_panel = self._extract_germline_panel(raw_data)
        
        # Step 7: Validate data quality and coverage
        quality_flags = self._check_data_quality(
            mutations=validated_mutations,
            clinical_data=clinical_data
        )
        
        # Step 7.5: Validate mutations meet quality thresholds
        validation_results = self._validate_mutation_quality(validated_mutations)
        quality_flags.extend(validation_results['warnings'])
        
        # Step 8: Build PatientProfile
        patient_id = metadata.get('patient_id') or self._generate_id()
        disease = self._extract_disease(raw_data, metadata)
        
        profile = PatientProfile(
            patient_id=patient_id,
            disease=disease,
            mutations=validated_mutations,
            germline_panel=germline_panel,
            clinical_data=clinical_data,
            demographics=demographics,
            data_quality_flags=quality_flags,
            extraction_provenance={
                'source': file_type,
                'lab': metadata.get('lab'),
                'extraction_method': parser.__class__.__name__,
                'confidence': self._calculate_confidence(raw_data, validated_mutations),
                'mutation_count': len(validated_mutations)
            }
        )
        
        logger.info(f"Extraction complete: {len(validated_mutations)} mutations, disease={disease}")
        return profile
    
    def _extract_mutations(self, raw_data: Dict) -> List[Dict]:
        """Extract mutation dicts from raw parsed data."""
        mutations = raw_data.get('mutations', [])
        
        # Ensure all mutations are dicts
        normalized = []
        for mut in mutations:
            if isinstance(mut, dict):
                normalized.append(mut)
            else:
                logger.warning(f"Skipping non-dict mutation: {type(mut)}")
        
        return normalized
    
    def _build_mutation(self, mut_data: Dict) -> Mutation:
        """Build Mutation object from dict."""
        # Parse zygosity
        zygosity_str = mut_data.get('zygosity', '').lower()
        if 'heterozygous' in zygosity_str or zygosity_str in ['het', '0/1', '1/0']:
            zygosity = Zygosity.HETEROZYGOUS
        elif 'homozygous' in zygosity_str or zygosity_str in ['hom', '1/1']:
            zygosity = Zygosity.HOMOZYGOUS
        elif 'hemizygous' in zygosity_str or zygosity_str == '1':
            zygosity = Zygosity.HEMIZYGOUS
        else:
            zygosity = Zygosity.UNKNOWN
        
        # Parse source
        source_str = mut_data.get('source', 'ngs').lower()
        if 'ihc' in source_str:
            source = MutationSource.IHC
        elif 'fish' in source_str:
            source = MutationSource.FISH
        elif 'pcr' in source_str:
            source = MutationSource.PCR
        elif 'inferred' in source_str:
            source = MutationSource.INFERRED
        else:
            source = MutationSource.NGS
        
        return Mutation(
            gene=mut_data.get('gene', '').upper(),
            variant=mut_data.get('variant', ''),
            hgvs_c=mut_data.get('hgvs_c'),
            hgvs_p=mut_data.get('hgvs_p'),
            chromosome=mut_data.get('chrom') or mut_data.get('chromosome'),
            position=mut_data.get('pos') or mut_data.get('position'),
            ref=mut_data.get('ref'),
            alt=mut_data.get('alt'),
            vaf=mut_data.get('vaf'),
            coverage=mut_data.get('coverage'),
            zygosity=zygosity,
            source=source,
            classification=mut_data.get('classification')
        )
    
    def _validate_mutation(self, mutation: Mutation) -> bool:
        """Validate mutation has minimum required fields."""
        if not mutation.gene or mutation.gene == 'UNKNOWN':
            return False
        
        if not mutation.variant and not mutation.hgvs_p and not mutation.hgvs_c:
            return False
        
        return True
    
    def _extract_clinical_data(self, raw_data: Dict) -> Optional[ClinicalData]:
        """Extract clinical data from raw data."""
        clinical_dict = raw_data.get('clinical_data', {})
        
        if not clinical_dict:
            return None
        
        return ClinicalData(
            stage=clinical_dict.get('stage'),
            histology=clinical_dict.get('histology'),
            grade=clinical_dict.get('grade'),
            ecog_ps=clinical_dict.get('ecog_ps'),
            biomarkers=clinical_dict.get('biomarkers', {}),
            prior_treatments=clinical_dict.get('prior_treatments', []),
            current_treatment=clinical_dict.get('current_treatment')
        )
    
    def _extract_demographics(self, raw_data: Dict) -> Optional[Demographics]:
        """Extract demographics from raw data."""
        demo_dict = raw_data.get('demographics', {})
        
        if not demo_dict:
            return None
        
        return Demographics(
            age=demo_dict.get('age'),
            sex=demo_dict.get('sex'),
            ethnicity=demo_dict.get('ethnicity')
        )
    
    def _extract_germline_panel(self, raw_data: Dict) -> Optional[GermlinePanel]:
        """Extract germline panel results."""
        germline_data = raw_data.get('germline_panel') or raw_data.get('germline_mutations', [])
        
        if not germline_data:
            return None
        
        # If it's a list of mutations, convert to panel format
        if isinstance(germline_data, list):
            pathogenic = {}
            vus = {}
            for mut in germline_data:
                gene = mut.get('gene', '')
                variant = mut.get('variant', '')
                classification = mut.get('classification', '').lower()
                
                if 'pathogenic' in classification:
                    pathogenic[gene] = variant
                elif 'vus' in classification or 'uncertain' in classification:
                    vus[gene] = variant
            
            return GermlinePanel(
                genes_tested=list(set([m.get('gene') for m in germline_data if m.get('gene')])),
                pathogenic=pathogenic,
                vus=vus
            )
        
        # If it's already a panel dict
        return GermlinePanel(
            genes_tested=germline_data.get('genes_tested', []),
            pathogenic=germline_data.get('pathogenic', {}),
            vus=germline_data.get('vus', {}),
            negative=germline_data.get('negative', []),
            panel_name=germline_data.get('panel_name'),
            test_date=datetime.fromisoformat(germline_data['test_date']) if germline_data.get('test_date') else None
        )
    
    def _extract_disease(self, raw_data: Dict, metadata: Dict) -> str:
        """Extract disease type from raw data or metadata."""
        disease = raw_data.get('disease') or metadata.get('disease')
        
        if disease:
            # Normalize disease name
            disease_lower = disease.lower()
            if 'ovarian' in disease_lower:
                return 'ovarian_cancer'
            elif 'myeloma' in disease_lower:
                return 'myeloma'
            elif 'breast' in disease_lower:
                return 'breast_cancer'
            elif 'lung' in disease_lower:
                return 'lung_cancer'
            elif 'colorectal' in disease_lower:
                return 'colorectal_cancer'
            else:
                return disease_lower.replace(' ', '_')
        
        return 'unknown'
    
    def _check_data_quality(self, mutations: List[Mutation], clinical_data: Optional[ClinicalData]) -> List[str]:
        """Check data quality and generate flags."""
        flags = []
        
        # Check mutation count
        if len(mutations) == 0:
            flags.append('no_mutations_extracted')
        
        # Check for missing VAF
        vaf_count = sum(1 for m in mutations if m.vaf is not None)
        if vaf_count < len(mutations) * 0.5:
            flags.append('low_vaf_coverage')
        
        # Check for missing HGVS notation
        hgvs_count = sum(1 for m in mutations if m.hgvs_p or m.hgvs_c)
        if hgvs_count < len(mutations) * 0.5:
            flags.append('low_hgvs_coverage')
        
        # Check clinical data
        if not clinical_data:
            flags.append('no_clinical_data')
        elif not clinical_data.stage:
            flags.append('stage_missing')
        
        return flags
    
    def _calculate_confidence(self, raw_data: Dict, mutations: List[Mutation]) -> float:
        """Calculate extraction confidence score."""
        if not mutations:
            return 0.0
        
        score = 0.5  # Base score
        
        # Bonus for having HGVS notation
        hgvs_count = sum(1 for m in mutations if m.hgvs_p or m.hgvs_c)
        score += 0.2 * (hgvs_count / len(mutations))
        
        # Bonus for having VAF
        vaf_count = sum(1 for m in mutations if m.vaf is not None)
        score += 0.2 * (vaf_count / len(mutations))
        
        # Bonus for having clinical data
        if raw_data.get('clinical_data'):
            score += 0.1
        
        return min(score, 1.0)
    
    def _generate_id(self) -> str:
        """Generate a unique patient ID."""
        return f"PT-{uuid.uuid4().hex[:8].upper()}"
    
    def _validate_mutation_quality(self, mutations: List[Mutation]) -> Dict[str, Any]:
        """Validate mutation quality and coverage thresholds."""
        warnings = []
        errors = []
        
        total_mutations = len(mutations)
        high_quality_count = 0
        
        for mut in mutations:
            # Check depth threshold (≥100x recommended)
            if mut.coverage:
                if mut.coverage < 100:
                    warnings.append(f"Low depth for {mut.gene}:{mut.position} ({mut.coverage}x, recommended: ≥100x)")
                else:
                    high_quality_count += 1
            else:
                warnings.append(f"Missing coverage data for {mut.gene}:{mut.position}")
            
            # Check VAF threshold (≥5% recommended)
            if mut.vaf:
                if mut.vaf < 0.05:
                    warnings.append(f"Low VAF for {mut.gene}:{mut.position} ({mut.vaf:.1%}, recommended: ≥5%)")
            else:
                warnings.append(f"Missing VAF data for {mut.gene}:{mut.position}")
            
            # Check required fields
            if not mut.gene or mut.gene == 'UNKNOWN':
                errors.append(f"Invalid gene name for mutation at {mut.position}")
            if not mut.variant and not mut.hgvs_p and not mut.hgvs_c:
                errors.append(f"Missing variant notation for {mut.gene}")
        
        # Calculate coverage ratio
        coverage_ratio = high_quality_count / total_mutations if total_mutations > 0 else 0
        
        # Overall quality assessment
        meets_threshold = coverage_ratio >= 0.8  # 80% high quality threshold
        
        if not meets_threshold and total_mutations > 0:
            warnings.append(f"Overall coverage quality below threshold: {coverage_ratio:.1%} high-quality (target: ≥80%)")
        
        return {
            'valid': len(errors) == 0,
            'warnings': warnings,
            'errors': errors,
            'total_mutations': total_mutations,
            'high_quality_count': high_quality_count,
            'coverage_ratio': coverage_ratio,
            'meets_threshold': meets_threshold
        }


