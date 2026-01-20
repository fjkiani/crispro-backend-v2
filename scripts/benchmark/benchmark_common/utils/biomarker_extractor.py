"""
Biomarker Extractor: Extract TMB, HRD, and MSI from patient data.

Handles TCGA dataset format with fallback estimation strategies.
Enhanced extraction expands gene lists for HRD (full HRR pathway) and MSI (extended MMR panel).
"""

from typing import Optional, Literal, Dict, Any, Tuple

# Core HRR pathway genes (High confidence for HRD estimation)
HRR_GENES_CORE = {
    "BRCA1", "BRCA2",           # Current: 4.7%
    "PALB2",                     # BRCA2 binding partner
    "RAD51C", "RAD51D",          # RAD51 paralogs (HR restoration)
    "BRIP1",                     # BRCA1 binding partner
    "BARD1",                     # BRCA1 binding partner
}

# Extended HRR pathway (Medium confidence)
HRR_GENES_EXTENDED = {
    "ATM",                       # DNA damage sensor
    "CHEK2",                     # DNA damage checkpoint
    "FANCA", "FANCC", "FANCD2",  # Fanconi anemia pathway (core)
    "FANCM", "FANCI", "FANCL", "FANCE", "FAN1",  # Fanconi anemia pathway (extended)
    "RAD50", "MRE11", "NBN",     # MRN complex
    "RAD54L", "RAD54L2", "RAD54B",  # RAD54 paralogs (HR restoration)
    "RAD51AP2",                  # RAD51 associated protein
    "XRCC1", "XRCC2", "XRCC4", "XRCC6",  # XRCC family (DNA repair)
    "RAD21",                     # Cohesin complex (DNA repair)
}

# Core MMR genes (High confidence for MSI-H)
MMR_GENES_CORE = {
    "MLH1", "MSH2", "MSH6", "PMS2"  # Current: 1.3%
}

# Extended MMR genes (Medium confidence)
MMR_GENES_EXTENDED = {
    "PMS1",                     # MMR pathway
    "MLH3",                     # MLH1 paralog
    "MSH3",                     # MSH2 binding partner
    "EXO1",                     # MMR exonuclease
    "POLD1", "POLE",            # DNA polymerase (proofreading)
}

# Mutation types to include for HRD/MSI estimation
# Handles both short form ("Missense") and cBioPortal form ("Missense_Mutation")
PATHOGENIC_MUTATION_TYPES = {
    # Short forms
    "missense", "nonsense", "frameshift", "splice", "indel", 
    "insertion", "deletion", "stop_gained", "stop_lost",
    # cBioPortal forms
    "missense_mutation", "nonsense_mutation", "frameshift_del", "frameshift_ins",
    "splice_site", "in_frame_del", "in_frame_ins", "nonstop_mutation",
    "frame_shift_del", "frame_shift_ins", "splice_region",
}

# Mutation types to exclude
BENIGN_MUTATION_TYPES = {
    "silent", "intron", "synonymous", "3'utr", "5'utr", 
    "3'flank", "5'flank", "ign", "rna", "translation_start_site"
}


def is_pathogenic_mutation(mutation: dict) -> bool:
    """
    Check if a mutation is likely pathogenic based on mutation_type or variant_type.
    Handles various naming conventions from different data sources.
    """
    # Try mutation_type first (cBioPortal format)
    mutation_type = mutation.get("mutation_type", "").strip().lower()
    if mutation_type:
        if mutation_type in BENIGN_MUTATION_TYPES:
            return False
        if mutation_type in PATHOGENIC_MUTATION_TYPES:
            return True
        # Check for partial matches (e.g., "frameshift" in "Frame_Shift_Del")
        for pathogenic in PATHOGENIC_MUTATION_TYPES:
            if pathogenic in mutation_type or mutation_type in pathogenic:
                return True
    
    # Try variant_type as fallback
    variant_type = mutation.get("variant_type", "").strip().lower()
    if variant_type:
        if variant_type in BENIGN_MUTATION_TYPES:
            return False
        if variant_type in PATHOGENIC_MUTATION_TYPES:
            return True
    
    # If we have a protein change, likely pathogenic
    if mutation.get("protein_change") or mutation.get("proteinChange"):
        protein_change = str(mutation.get("protein_change") or mutation.get("proteinChange", ""))
        # Exclude synonymous (p.X123=) and unknown (p.?)
        if protein_change and "=" not in protein_change and "?" not in protein_change:
            return True
    
    return False


def extract_tmb_from_patient(
    patient: dict,
    use_pathogenic_only: bool = True,
    min_maf: float = 0.01,
    cap_hypermutators: bool = True,
    max_tmb: float = 50.0
) -> Tuple[Optional[float], Optional[str], Optional[str]]:
    """
    Extract TMB from patient data with improved filtering.
    
    Tries multiple sources in order:
    1. TMB_NONSYNONYMOUS (direct TCGA field) → high confidence
    2. TMB_SCORE (alternative field name) → high confidence
    3. MUTATION_COUNT / 30.0 (estimate from mutation count) → medium confidence
    4. Filtered mutations / 30.0 (fallback estimate with filtering) → medium/low confidence
    
    Args:
        patient: Patient dict with clinical_outcomes and mutations
        use_pathogenic_only: If True, filter to pathogenic variants only
        min_maf: Exclude variants with MAF > min_maf (common variants)
        
    Returns:
        Tuple of (TMB value (mutations/Mb) or None, source string, confidence string)
        Source is one of: "direct", "estimated_from_mutation_count", "estimated_from_mutations_filtered", "none"
        Confidence is one of: "high", "medium", "low", or None
    """
    outcomes = patient.get("clinical_outcomes") or patient.get("outcomes", {})
    
    # Try direct TMB field (high confidence)
    tmb = outcomes.get("TMB_NONSYNONYMOUS")
    if tmb is not None:
        try:
            return float(tmb), "direct", "high"
        except (ValueError, TypeError):
            pass
    
    # Try TMB_SCORE (high confidence)
    tmb_score = outcomes.get("TMB_SCORE")
    if tmb_score is not None:
        try:
            return float(tmb_score), "direct", "high"
        except (ValueError, TypeError):
            pass
    
    # Estimate from mutation count (medium confidence)
    mutation_count = outcomes.get("MUTATION_COUNT")
    if mutation_count is not None:
        try:
            # Assume ~30Mb panel size (typical for Foundation Medicine)
            return float(mutation_count) / 30.0, "estimated_from_mutation_count", "medium"
        except (ValueError, TypeError):
            pass
    
    # Fallback: estimate from mutations list with filtering
    mutations = patient.get("mutations", [])
    if mutations:
        filtered_mutations = _filter_mutations_for_tmb(
            mutations, 
            use_pathogenic_only=use_pathogenic_only,
            min_maf=min_maf
        )
        if filtered_mutations:
            tmb_value = len(filtered_mutations) / 30.0
            
            # Cap hypermutators to prevent skewing (e.g., MSI-H patients)
            if cap_hypermutators and tmb_value > max_tmb:
                tmb_value = max_tmb
                confidence = "medium"  # Capped value has lower confidence
                source = "estimated_from_mutations_filtered_capped"
            else:
                source = "estimated_from_mutations_filtered"
                # Confidence depends on filtering quality
                confidence = "medium" if use_pathogenic_only and min_maf < 0.05 else "low"
            
            return tmb_value, source, confidence
    
    return None, "none", None


def _filter_mutations_for_tmb(
    mutations: list,
    use_pathogenic_only: bool = True,
    min_maf: float = 0.01
) -> list:
    """
    Filter mutations for TMB calculation.
    
    Args:
        mutations: List of mutation dicts
        use_pathogenic_only: If True, filter to pathogenic variants
        min_maf: Exclude variants with MAF > min_maf
        
    Returns:
        Filtered list of mutations
    """
    filtered = []
    
    for mut in mutations:
        # Use improved pathogenicity detection
        if use_pathogenic_only:
            if not is_pathogenic_mutation(mut):
                continue
            
            # Also check ClinVar if available for extra confidence
            clinvar = mut.get("clinvar_classification", "").upper()
            if clinvar in ["BENIGN", "LIKELY_BENIGN"]:
                continue  # Exclude known benign
        
        # Check MAF if provided (exclude common variants)
        maf = mut.get("maf") or mut.get("gnomad_maf")
        if maf is not None:
            try:
                maf_float = float(maf)
                if maf_float > min_maf:
                    continue  # Exclude common variants
            except (ValueError, TypeError):
                pass  # Include if MAF not parseable
        
        filtered.append(mut)
    
    return filtered


def extract_hrd_from_patient(
    patient: dict,
    estimate_hrd: bool = True,
    confidence_threshold: str = "medium"
) -> Tuple[Optional[float], Optional[str], Optional[str]]:
    """
    Extract HRD score from patient data with enhanced HRR pathway detection.
    
    Tries multiple sources in order:
    1. Direct HRD_SCORE field (highest confidence)
    2. Core HRR mutations (BRCA1/2/PALB2/RAD51C/RAD51D/BRIP1/BARD1) → HRD=55.0
    3. Extended HRR mutations (ATM/CHEK2/FANCA/etc.) → HRD=45.0 (if confidence_threshold="medium")
    4. Multiple HRR mutations (biallelic loss) → HRD=65.0
    
    Args:
        patient: Patient dict with clinical_outcomes and mutations
        estimate_hrd: If True, estimate HRD from HRR mutations when direct field unavailable
        confidence_threshold: "high" (core only) or "medium" (core + extended)
        
    Returns:
        Tuple of (HRD score 0-100 or None, source string, confidence string)
        Source is one of: "direct", "estimated_hrr_core", "estimated_hrr_extended", "estimated_hrr_biallelic", "none"
        Confidence is one of: "high", "medium", "low", or None
    """
    outcomes = patient.get("clinical_outcomes") or patient.get("outcomes", {})
    
    # Try direct HRD field first (highest confidence)
    hrd = outcomes.get("HRD_SCORE") or outcomes.get("HRD")
    if hrd is not None:
        try:
            hrd_float = float(hrd)
            # Validate range
            if 0 <= hrd_float <= 100:
                return hrd_float, "direct", "high"
        except (ValueError, TypeError):
            pass
    
    # If estimation disabled, return None
    if not estimate_hrd:
        return None, "none", None
    
    # Enhanced HRR pathway detection
    mutations = patient.get("mutations", [])
    if not mutations:
        return None, "none", None
    
    # Filter mutations to pathogenic variants only using improved detection
    pathogenic_mutations = [m for m in mutations if is_pathogenic_mutation(m)]
    
    if not pathogenic_mutations:
        return None, "none", None
    
    # Check for core HRR mutations (high confidence)
    core_hrr_mutations = [
        m for m in pathogenic_mutations
        if m.get("gene", "").strip().upper() in HRR_GENES_CORE
    ]
    
    # Check for extended HRR mutations (medium confidence)
    extended_hrr_mutations = []
    if confidence_threshold == "medium":
        extended_hrr_mutations = [
            m for m in pathogenic_mutations
            if m.get("gene", "").strip().upper() in HRR_GENES_EXTENDED
        ]
    
    # Check for multiple HRR mutations (biallelic loss - highest confidence estimation)
    all_hrr_mutations = core_hrr_mutations + extended_hrr_mutations
    if len(all_hrr_mutations) >= 2:
        # Multiple HRR mutations suggest biallelic loss
        return 65.0, "estimated_hrr_biallelic", "high"
    
    # Check core HRR first (high confidence)
    if core_hrr_mutations:
        return 55.0, "estimated_hrr_core", "high"
    
    # Check extended HRR if confidence threshold allows (medium confidence)
    if extended_hrr_mutations:
        return 45.0, "estimated_hrr_extended", "medium"
    
    # No HRR mutations found
    return None, "none", None


def extract_msi_from_patient(
    patient: dict,
    estimate_msi: bool = True,
    confidence_threshold: str = "medium"
) -> Tuple[Optional[Literal["MSI-H", "MSS"]], Optional[str], Optional[str]]:
    """
    Extract MSI status from patient data with enhanced MMR pathway detection.
    
    Tries multiple sources in order:
    1. Direct MSI_STATUS field (highest confidence)
    2. Core MMR mutations (MLH1/MSH2/MSH6/PMS2) → MSI-H
    3. Extended MMR mutations (PMS1/MLH3/MSH3/EXO1/POLD1/POLE) → MSI-H (if confidence_threshold="medium")
    
    Args:
        patient: Patient dict with clinical_outcomes and mutations
        estimate_msi: If True, estimate MSI from MMR mutations when direct field unavailable
        confidence_threshold: "high" (core only) or "medium" (core + extended)
        
    Returns:
        Tuple of (MSI status "MSI-H"/"MSS" or None, source string, confidence string)
        Source is one of: "direct", "estimated_mmr_core", "estimated_mmr_extended", "none"
        Confidence is one of: "high", "medium", "low", or None
    """
    outcomes = patient.get("clinical_outcomes") or patient.get("outcomes", {})
    
    # Try direct MSI field first (highest confidence)
    msi = outcomes.get("MSI_STATUS") or outcomes.get("MSI")
    if msi:
        msi_upper = str(msi).upper()
        if "MSI-H" in msi_upper or "HIGH" in msi_upper:
            return "MSI-H", "direct", "high"
        elif "MSS" in msi_upper or "STABLE" in msi_upper:
            return "MSS", "direct", "high"
    
    # If estimation disabled, return None
    if not estimate_msi:
        return None, "none", None
    
    # Enhanced MMR pathway detection
    mutations = patient.get("mutations", [])
    if not mutations:
        return None, "none", None
    
    # Filter mutations to pathogenic variants only using improved detection
    pathogenic_mutations = [m for m in mutations if is_pathogenic_mutation(m)]
    
    if not pathogenic_mutations:
        return None, "none", None
    
    # Check for core MMR mutations (high confidence)
    core_mmr_mutations = [
        m for m in pathogenic_mutations
        if m.get("gene", "").strip().upper() in MMR_GENES_CORE
    ]
    
    # Check for extended MMR mutations (medium confidence)
    extended_mmr_mutations = []
    if confidence_threshold == "medium":
        extended_mmr_mutations = [
            m for m in pathogenic_mutations
            if m.get("gene", "").strip().upper() in MMR_GENES_EXTENDED
        ]
    
    # Core MMR mutations → MSI-H (high confidence)
    if core_mmr_mutations:
        return "MSI-H", "estimated_mmr_core", "high"
    
    # Extended MMR mutations → MSI-H (medium confidence)
    if extended_mmr_mutations:
        return "MSI-H", "estimated_mmr_extended", "medium"
    
    # No MMR mutations found → return None (not MSS)
    # MSS should only be returned if we have direct evidence or explicit negative test
    return None, "none", None


def build_tumor_context(
    patient: dict,
    estimate_hrd: bool = True,
    estimate_msi: bool = True,
    hrd_confidence: str = "medium",
    msi_confidence: str = "medium",
    tmb_pathogenic_only: bool = True,
    tmb_min_maf: float = 0.01,
    tmb_cap_hypermutators: bool = True,
    tmb_max_value: float = 50.0
) -> Dict[str, Any]:
    """
    Build tumor_context dict from patient data with enhanced biomarker extraction.
    
    Creates a Level 1 (L1) tumor context with TMB, HRD, and MSI.
    Completeness score reflects how many biomarkers were successfully extracted.
    Confidence tracking indicates data quality for each biomarker.
    
    Args:
        patient: Patient dict with clinical_outcomes and mutations
        estimate_hrd: If True, estimate HRD from HRR mutations when not available
        estimate_msi: If True, estimate MSI from MMR mutations when not available
        hrd_confidence: Confidence threshold for HRD estimation ("high", "medium", "low")
        msi_confidence: Confidence threshold for MSI estimation ("high", "medium", "low")
        tmb_pathogenic_only: If True, filter TMB mutations to pathogenic variants only
        tmb_min_maf: Exclude variants with MAF > min_maf from TMB calculation
        tmb_cap_hypermutators: If True, cap TMB at max_value to prevent hypermutator skewing
        tmb_max_value: Maximum TMB value (default 50.0 mut/Mb) when capping is enabled
        
    Returns:
        Tumor context dict compatible with TumorContext schema
        Includes biomarker_sources and biomarker_confidence for audit/debugging
    """
    # Extract biomarkers with enhanced logic (returns value, source, confidence)
    tmb, tmb_source, tmb_confidence = extract_tmb_from_patient(
        patient,
        use_pathogenic_only=tmb_pathogenic_only,
        min_maf=tmb_min_maf,
        cap_hypermutators=tmb_cap_hypermutators,
        max_tmb=tmb_max_value
    )
    hrd, hrd_source, hrd_confidence_val = extract_hrd_from_patient(
        patient,
        estimate_hrd=estimate_hrd,
        confidence_threshold=hrd_confidence
    )
    msi, msi_source, msi_confidence_val = extract_msi_from_patient(
        patient,
        estimate_msi=estimate_msi,
        confidence_threshold=msi_confidence
    )
    
    # Calculate completeness (fraction of biomarkers successfully extracted)
    biomarkers_extracted = sum([
        tmb is not None,
        hrd is not None,
        msi is not None
    ])
    completeness_score = biomarkers_extracted / 3.0
    
    # Use confidence values from extraction functions (already computed)
    biomarker_confidence = {}
    if tmb is not None and tmb_confidence:
        biomarker_confidence["tmb"] = tmb_confidence
    if hrd is not None and hrd_confidence_val:
        biomarker_confidence["hrd_score"] = hrd_confidence_val
    if msi is not None and msi_confidence_val:
        biomarker_confidence["msi_status"] = msi_confidence_val
    
    tumor_context = {
        "level": "L1",  # Level 1 (partial data)
        "completeness_score": completeness_score,
        "priors_used": False,
        # Source tracking for audit
        "biomarker_sources": {
            "tmb": tmb_source if tmb is not None else "none",
            "hrd": hrd_source if hrd is not None else "none",
            "msi": msi_source if msi is not None else "none",
        },
        # Confidence tracking for data quality assessment
        "biomarker_confidence": biomarker_confidence
    }
    
    # Add biomarkers if available
    if tmb is not None:
        tumor_context["tmb"] = tmb
    if hrd is not None:
        tumor_context["hrd_score"] = hrd
    if msi is not None:
        tumor_context["msi_status"] = msi
    
    return tumor_context

