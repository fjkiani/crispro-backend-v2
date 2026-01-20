"""
DDR_bin Scoring Engine - Pan-Solid-Tumor DDR Deficiency Classifier.

Takes standard NGS outputs and optionally HRD assays as input, and returns
a simple, interpretable label per patient: DDR_bin_status ∈ {DDR_defective, DDR_proficient, unknown}.

This is a gene-based engine (variant classification + HRD assay), distinct from SAE-based DDR_bin.
"""

from typing import Dict, List, Optional, Any, Union
import logging
import json

from ...config.ddr_config import (
    DDR_CONFIG,
    DDR_SCORE_WEIGHTS,
    PATHOGENIC_VARIANT_CLASSIFICATIONS,
    HRD_POSITIVE_STATUS_VALUES,
    CNA_LOSS_STATES,
    get_ddr_config,
    get_core_brca_genes,
)

logger = logging.getLogger(__name__)


def assign_ddr_status(
    mutations_table: List[Dict[str, Any]],
    clinical_table: List[Dict[str, Any]],
    cna_table: Optional[List[Dict[str, Any]]] = None,
    hrd_assay_table: Optional[List[Dict[str, Any]]] = None,
    config: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """
    Assign DDR_bin_status to each patient based on genomic and HRD assay data.
    
    This is a pan-solid-tumor DDR deficiency classifier that takes standard NGS outputs
    and optionally HRD assays as input, and returns a simple, interpretable label per patient.
    
    Args:
        mutations_table: List of mutation records, one per (patient_id, gene).
            Each record must have: patient_id, gene_symbol, variant_classification, variant_type
        clinical_table: List of patient-level metadata.
            Each record must have: patient_id, disease_site, tumor_subtype (optional)
        cna_table: Optional list of copy-number alteration records, one per (patient_id, gene).
            Each record must have: patient_id, gene_symbol, copy_number_state, copy_number (optional)
        hrd_assay_table: Optional list of HRD assay results, one per patient.
            Each record must have: patient_id, hrd_score (optional), hrd_status (optional), assay_name (optional)
        config: Optional custom DDR configuration dict. If not provided, uses disease_site from clinical_table.
    
    Returns:
        List of DDR status records, one per patient_id, with columns:
        - patient_id, disease_site, tumor_subtype
        - DDR_bin_status ∈ {DDR_defective, DDR_proficient, unknown}
        - HRD_status_inferred ∈ {HRD_positive, HRD_negative, unknown}
        - HRD_score_raw (float or None)
        - BRCA_pathogenic (bool)
        - core_HRR_pathogenic (bool)
        - extended_DDR_pathogenic (bool)
        - DDR_score (float)
        - DDR_features_used (JSON string/list)
    """
    logger.info("Starting DDR_bin status assignment...")
    
    # Group inputs by patient_id for efficient processing
    mutations_by_patient = _group_by_patient(mutations_table, "patient_id")
    cna_by_patient = _group_by_patient(cna_table or [], "patient_id")
    hrd_by_patient = {r["patient_id"]: r for r in (hrd_assay_table or [])} if hrd_assay_table else {}
    clinical_by_patient = {r["patient_id"]: r for r in clinical_table}
    
    results = []
    
    # Process each patient
    for patient_record in clinical_table:
        patient_id = patient_record["patient_id"]
        disease_site = patient_record.get("disease_site", "default")
        tumor_subtype = patient_record.get("tumor_subtype")
        
        # Get disease-specific config
        if config:
            patient_config = config
        else:
            patient_config = get_ddr_config(disease_site)
        
        # Get patient's data
        patient_mutations = mutations_by_patient.get(patient_id, [])
        patient_cna = cna_by_patient.get(patient_id, [])
        patient_hrd = hrd_by_patient.get(patient_id, {})
        
        # Compute DDR status for this patient
        ddr_status = _compute_patient_ddr_status(
            patient_id=patient_id,
            disease_site=disease_site,
            tumor_subtype=tumor_subtype,
            mutations=patient_mutations,
            cna=patient_cna,
            hrd_assay=patient_hrd,
            config=patient_config
        )
        
        results.append(ddr_status)
    
    logger.info(f"Completed DDR_bin status assignment for {len(results)} patients")
    return results


def _group_by_patient(records: List[Dict[str, Any]], patient_id_key: str) -> Dict[str, List[Dict[str, Any]]]:
    """Group records by patient_id."""
    grouped = {}
    for record in records:
        patient_id = record.get(patient_id_key)
        if patient_id is None:
            continue
        if patient_id not in grouped:
            grouped[patient_id] = []
        grouped[patient_id].append(record)
    return grouped


def _compute_patient_ddr_status(
    patient_id: str,
    disease_site: str,
    tumor_subtype: Optional[str],
    mutations: List[Dict[str, Any]],
    cna: List[Dict[str, Any]],
    hrd_assay: Dict[str, Any],
    config: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Compute DDR_bin_status for a single patient.
    
    Implements priority-ordered rules:
    1. BRCA_pathogenic → DDR_defective
    2. HRD_positive_inferred → DDR_defective
    3. core_HRR_pathogenic → DDR_defective
    4. extended_DDR_pathogenic → DDR_defective
    5. no DDR/HRD data → unknown
    6. else → DDR_proficient
    """
    # Normalize gene symbols to uppercase
    mutations_normalized = [
        {**m, "gene_symbol": m.get("gene_symbol", "").upper()}
        for m in mutations
    ]
    cna_normalized = [
        {**c, "gene_symbol": c.get("gene_symbol", "").upper()}
        for c in cna
    ] if cna else []
    
    # Initialize flags
    flags = _compute_ddr_flags(
        mutations=mutations_normalized,
        cna=cna_normalized,
        hrd_assay=hrd_assay,
        config=config
    )
    
    # Assign DDR_bin_status using priority-ordered rules
    ddr_bin_status, ddr_features_used = _assign_ddr_bin_status(flags, config)
    
    # Compute DDR_score (weighted sum)
    ddr_score = _compute_ddr_score(flags)
    
    # Build result record
    result = {
        "patient_id": patient_id,
        "disease_site": disease_site,
        "tumor_subtype": tumor_subtype,
        "DDR_bin_status": ddr_bin_status,
        "HRD_status_inferred": flags["hrd_status_inferred"],
        "HRD_score_raw": flags.get("hrd_score_raw"),
        "BRCA_pathogenic": flags["BRCA_pathogenic"],
        "core_HRR_pathogenic": flags["core_HRR_pathogenic"],
        "extended_DDR_pathogenic": flags["extended_DDR_pathogenic"],
        "DDR_score": ddr_score,
        "DDR_features_used": json.dumps(ddr_features_used) if ddr_features_used else None,
    }
    
    return result


def _compute_ddr_flags(
    mutations: List[Dict[str, Any]],
    cna: List[Dict[str, Any]],
    hrd_assay: Dict[str, Any],
    config: Dict[str, Any]
) -> Dict[str, Any]:
    """Compute DDR flags (BRCA, HRD, core HRR, extended DDR)."""
    core_brca_genes = get_core_brca_genes()
    core_hrr_genes = {g.upper() for g in config.get("core_hrr_genes", [])}
    extended_ddr_genes = {g.upper() for g in config.get("extended_ddr_genes", [])}
    
    # Normalize pathogenic classifications
    pathogenic_classifications = {c.lower() for c in PATHOGENIC_VARIANT_CLASSIFICATIONS}
    
    # Check BRCA pathogenic variants
    brca_pathogenic_variants = [
        m for m in mutations
        if m.get("gene_symbol", "").upper() in {g.upper() for g in core_brca_genes}
        and m.get("variant_classification", "").lower() in pathogenic_classifications
    ]
    has_pathogenic_BRCA = len(brca_pathogenic_variants) > 0
    
    # Check biallelic loss (if CNA available and config requires it)
    brca_biallelic = False
    if has_pathogenic_BRCA and config.get("require_biallelic_if_cn_available", False) and cna:
        brca_genes_upper = {g.upper() for g in core_brca_genes}
        # Find which BRCA gene(s) have pathogenic variants
        pathogenic_brca_genes = {m.get("gene_symbol", "").upper() for m in brca_pathogenic_variants}
        # Check if any of those genes also have CNA loss
        brca_loss_in_cna = any(
            c.get("gene_symbol", "").upper() in pathogenic_brca_genes
            and c.get("copy_number_state", "").lower() in [s.lower() for s in CNA_LOSS_STATES]
            for c in cna
        )
        brca_biallelic = brca_loss_in_cna
    
    # Use biallelic confirmation if required, otherwise just pathogenic
    # If biallelic required but not available, still mark as pathogenic (pathogenic variant exists)
    BRCA_pathogenic = has_pathogenic_BRCA
    if config.get("require_biallelic_if_cn_available", False) and cna:
        # Only mark as strong (still pathogenic) if biallelic confirmed
        # But for now, we still consider it pathogenic even without biallelic
        # This can be refined later if needed
        pass
    
    # Check core HRR pathogenic variants (excluding BRCA if checking separately)
    core_hrr_pathogenic_variants = [
        m for m in mutations
        if m.get("gene_symbol", "").upper() in core_hrr_genes
        and m.get("gene_symbol", "").upper() not in {g.upper() for g in core_brca_genes}  # Exclude BRCA
        and m.get("variant_classification", "").lower() in pathogenic_classifications
    ]
    core_HRR_pathogenic = len(core_hrr_pathogenic_variants) > 0
    
    # Check extended DDR pathogenic variants
    extended_ddr_pathogenic_variants = [
        m for m in mutations
        if m.get("gene_symbol", "").upper() in extended_ddr_genes
        and m.get("variant_classification", "").lower() in pathogenic_classifications
    ]
    extended_DDR_pathogenic = len(extended_ddr_pathogenic_variants) > 0
    
    # Check HRD status
    hrd_score_raw = hrd_assay.get("hrd_score")
    hrd_status_raw = hrd_assay.get("hrd_status", "")
    hrd_score_cutoff = config.get("hrd_score_cutoff", 42)
    
    hrd_status_inferred = "unknown"
    hrd_positive_inferred = False
    
    if hrd_status_raw:
        # Check if HRD status indicates positive
        hrd_status_lower = str(hrd_status_raw).lower()
        if any(positive_value.lower() in hrd_status_lower for positive_value in HRD_POSITIVE_STATUS_VALUES):
            hrd_status_inferred = "HRD_positive"
            hrd_positive_inferred = True
        elif "negative" in hrd_status_lower or "hrd-" in hrd_status_lower:
            hrd_status_inferred = "HRD_negative"
    elif hrd_score_raw is not None:
        # Infer from score
        if hrd_score_raw >= hrd_score_cutoff:
            hrd_status_inferred = "HRD_positive"
            hrd_positive_inferred = True
        else:
            hrd_status_inferred = "HRD_negative"
    
    return {
        "BRCA_pathogenic": BRCA_pathogenic,
        "core_HRR_pathogenic": core_HRR_pathogenic,
        "extended_DDR_pathogenic": extended_DDR_pathogenic,
        "hrd_positive_inferred": hrd_positive_inferred,
        "hrd_status_inferred": hrd_status_inferred,
        "hrd_score_raw": hrd_score_raw,
    }


def _assign_ddr_bin_status(
    flags: Dict[str, Any],
    config: Dict[str, Any]
) -> tuple:
    """
    Assign DDR_bin_status using priority-ordered rules.
    
    Returns:
        Tuple of (ddr_bin_status, ddr_features_used)
    """
    ddr_features_used = []
    
    # Rule 1: BRCA pathogenic (highest priority)
    if flags["BRCA_pathogenic"]:
        ddr_bin_status = "DDR_defective"
        ddr_features_used.append("BRCA_pathogenic")
        return ddr_bin_status, ddr_features_used
    
    # Rule 2: HRD positive (genomic scar)
    if flags["hrd_positive_inferred"]:
        ddr_bin_status = "DDR_defective"
        if flags["hrd_score_raw"] is not None:
            ddr_features_used.append("HRD_score_high")
        else:
            ddr_features_used.append("HRD_status_positive")
        return ddr_bin_status, ddr_features_used
    
    # Rule 3: Core HRR pathogenic
    if flags["core_HRR_pathogenic"]:
        ddr_bin_status = "DDR_defective"
        ddr_features_used.append("core_hrr_pathogenic")
        return ddr_bin_status, ddr_features_used
    
    # Rule 4: Extended DDR pathogenic
    if flags["extended_DDR_pathogenic"]:
        ddr_bin_status = "DDR_defective"
        ddr_features_used.append("extended_ddr_pathogenic")
        return ddr_bin_status, ddr_features_used
    
    # Rule 5: No DDR/HRD information
    if not flags["BRCA_pathogenic"] and not flags["core_HRR_pathogenic"] and not flags["extended_DDR_pathogenic"] and flags["hrd_score_raw"] is None and flags["hrd_status_inferred"] == "unknown":
        ddr_bin_status = "unknown"
        return ddr_bin_status, ddr_features_used
    
    # Rule 6: DDR proficient (default)
    ddr_bin_status = "DDR_proficient"
    return ddr_bin_status, ddr_features_used


def _compute_ddr_score(flags: Dict[str, Any]) -> float:
    """
    Compute optional continuous DDR_score (weighted sum of hits).
    
    Weights:
    - BRCA_pathogenic: 3.0 (highest)
    - HRD_positive: 2.5
    - core_HRR_pathogenic: 2.0
    - extended_DDR_pathogenic: 1.0
    """
    score = 0.0
    
    if flags["BRCA_pathogenic"]:
        score += DDR_SCORE_WEIGHTS["BRCA_pathogenic"]
    
    if flags["hrd_positive_inferred"]:
        score += DDR_SCORE_WEIGHTS["HRD_positive"]
    
    if flags["core_HRR_pathogenic"]:
        score += DDR_SCORE_WEIGHTS["core_hrr_pathogenic"]
    
    if flags["extended_DDR_pathogenic"]:
        score += DDR_SCORE_WEIGHTS["extended_ddr_pathogenic"]
    
    return round(score, 2)


def get_ddr_status_for_patient(
    patient_id: str,
    mutations: List[Dict[str, Any]],
    clinical: Dict[str, Any],
    cna: Optional[List[Dict[str, Any]]] = None,
    hrd_assay: Optional[Dict[str, Any]] = None,
    config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Convenience function to get DDR status for a single patient.
    
    Args:
        patient_id: Patient identifier
        mutations: List of mutation records for this patient
        clinical: Patient clinical metadata (must have disease_site)
        cna: Optional copy-number alterations for this patient
        hrd_assay: Optional HRD assay result for this patient
        config: Optional custom DDR configuration
    
    Returns:
        DDR status record for this patient
    """
    results = assign_ddr_status(
        mutations_table=[{**m, "patient_id": patient_id} for m in mutations],
        clinical_table=[{**clinical, "patient_id": patient_id}],
        cna_table=[{**c, "patient_id": patient_id} for c in (cna or [])] if cna else None,
        hrd_assay_table=[{**hrd_assay, "patient_id": patient_id}] if hrd_assay else None,
        config=config
    )
    
    if results:
        return results[0]
    else:
        raise ValueError(f"No DDR status computed for patient {patient_id}")
