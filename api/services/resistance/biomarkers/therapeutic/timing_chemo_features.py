"""
Timing & Chemosensitivity Engine - Pan-Cancer Treatment History Standardizer.

Computes PFI, PTPI, TFI, PFS, OS, and optional KELIM/CA-125 features for each regimen.
Outputs a per-regimen feature table that captures "how the tumor behaved under prior therapies".
"""

from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
import logging

from ...config.timing_config import (
    TIMING_CONFIG,
    get_timing_config,
    is_platinum_regimen,
    is_ddr_targeted_regimen,
    get_regimen_biomarker_class,
)
from ...config.kinetic_biomarker_config import (
    get_kinetic_biomarker_config,
    is_kinetic_biomarker_available,
    get_marker_for_disease,
)
from .ca125_kelim_ovarian import CA125KELIMOvarian

logger = logging.getLogger(__name__)


def build_timing_chemo_features(
    regimen_table: List[Dict[str, Any]],
    survival_table: List[Dict[str, Any]],
    clinical_table: List[Dict[str, Any]],
    ca125_features_table: Optional[List[Dict[str, Any]]] = None,
    ca125_measurements_table: Optional[List[Dict[str, Any]]] = None,
    config: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """
    Build timing and chemosensitivity features for each regimen.
    
    Computes:
    - TFI (Treatment-Free Interval) between regimens
    - PFS/OS from regimen start
    - PFI (Platinum-Free Interval) for platinum regimens
    - PTPI (Platinum-to-PARPi Interval) for DDR-targeted regimens
    - KELIM/CA-125 features when available (if configured)
    
    Args:
        regimen_table: List of regimen records, one per regimen_id.
            Each record must have: patient_id, regimen_id, regimen_start_date, regimen_end_date,
            regimen_type, line_of_therapy, setting, last_platinum_dose_date (optional),
            progression_date (optional)
        survival_table: List of survival records, one per patient_id.
            Each record must have: patient_id, vital_status, death_date (optional),
            last_followup_date
        clinical_table: List of clinical records, one per patient_id.
            Each record must have: patient_id, disease_site, tumor_subtype (optional)
        ca125_features_table: Optional list of pre-computed CA-125 features, one per (patient_id, regimen_id).
            Each record must have: patient_id, regimen_id, kelim_k_value (optional),
            kelim_category (optional), ca125_percent_change_day21 (optional), etc.
        ca125_measurements_table: Optional list of raw CA-125 measurements for on-the-fly KELIM computation.
            Each record must have: patient_id, regimen_id, date (datetime/str), value (float).
            If provided and ca125_features_table is not, KELIM will be computed from raw measurements.
        config: Optional custom timing configuration dict. If not provided, uses
            disease_site from clinical_table to get config.
    
    Returns:
        List of timing feature records, one per (patient_id, regimen_id), with columns:
        - patient_id, regimen_id, disease_site, tumor_subtype, regimen_type, line_of_therapy, setting
        - TFI_days, PFS_from_regimen_days, PFS_event, OS_from_regimen_days, OS_event
        - PFI_days, PFI_category (for platinum regimens)
        - PTPI_days (for DDR-targeted regimens)
        - kelim_k_value, kelim_category, ca125_percent_change_day21, etc. (when available)
        - Data quality flags (has_prior_platinum, has_progression_date, etc.)
    """
    logger.info("Starting timing and chemosensitivity feature computation...")
    
    # Group inputs by patient_id for efficient processing
    regimens_by_patient = _group_by_patient(regimen_table, "patient_id")
    survival_by_patient = {r["patient_id"]: r for r in survival_table}
    clinical_by_patient = {r["patient_id"]: r for r in clinical_table}
    ca125_by_regimen = {}
    if ca125_features_table:
        # Use pre-computed CA-125 features if provided
        ca125_by_regimen = {
            (r["patient_id"], r["regimen_id"]): r
            for r in ca125_features_table
        }
    
    # Group raw CA-125 measurements by (patient_id, regimen_id) for on-the-fly computation
    ca125_measurements_by_regimen = {}
    if ca125_measurements_table:
        for m in ca125_measurements_table:
            key = (m["patient_id"], m["regimen_id"])
            if key not in ca125_measurements_by_regimen:
                ca125_measurements_by_regimen[key] = []
            ca125_measurements_by_regimen[key].append(m)
    
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
            patient_config = get_timing_config(disease_site)
        
        # Get patient's data
        patient_regimens = regimens_by_patient.get(patient_id, [])
        patient_survival = survival_by_patient.get(patient_id, {})
        
        # Sort regimens by start date
        sorted_regimens = sorted(
            patient_regimens,
            key=lambda r: _parse_date(r.get("regimen_start_date")) or datetime.min
        )
        
        # Compute features for each regimen
        for i, regimen in enumerate(sorted_regimens):
            regimen_id = regimen["regimen_id"]
            
            # Get prior regimen (for TFI)
            prior_regimen = sorted_regimens[i - 1] if i > 0 else None
            
            # Get prior platinum regimen (for PFI/PTPI)
            prior_platinum_regimen = _find_most_recent_prior_platinum(
                regimen, sorted_regimens[:i], patient_config
            )
            
            # Compute timing features for this regimen
            timing_features = _compute_regimen_timing_features(
                patient_id=patient_id,
                disease_site=disease_site,
                tumor_subtype=tumor_subtype,
                regimen=regimen,
                prior_regimen=prior_regimen,
                prior_platinum_regimen=prior_platinum_regimen,
                sorted_regimens=sorted_regimens,
                survival=patient_survival,
                config=patient_config
            )
            
            # Integrate CA-125/KELIM features if configured and available
            if patient_config.get("use_ca125_for_chemosensitivity", False):
                # Try pre-computed features first
                ca125_features = ca125_by_regimen.get((patient_id, regimen_id))
                
                if ca125_features:
                    # Use pre-computed CA-125 features
                    timing_features.update(_extract_ca125_features(ca125_features))
                elif ca125_measurements_table:
                    # Compute KELIM on-the-fly from raw measurements
                    raw_measurements = ca125_measurements_by_regimen.get((patient_id, regimen_id))
                    if raw_measurements:
                        # Get regimen start date
                        regimen_start_date = _parse_date(regimen.get("regimen_start_date"))
                        if regimen_start_date:
                            kelim_features = _compute_kelim_from_measurements(
                                raw_measurements=raw_measurements,
                                treatment_start_date=regimen_start_date,
                                disease_site=disease_site
                            )
                            if kelim_features:
                                timing_features.update(kelim_features)
            
            results.append(timing_features)
    
    logger.info(f"Completed timing feature computation for {len(results)} regimens")
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


def _parse_date(date_value: Any) -> Optional[datetime]:
    """Parse date value to datetime object."""
    if date_value is None:
        return None
    
    if isinstance(date_value, datetime):
        return date_value
    
    if isinstance(date_value, str):
        try:
            # Try ISO format first
            return datetime.fromisoformat(date_value.replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            try:
                # Try common date formats
                for fmt in ['%Y-%m-%d', '%Y/%m/%d', '%m/%d/%Y', '%d/%m/%Y']:
                    try:
                        return datetime.strptime(date_value, fmt)
                    except ValueError:
                        continue
            except Exception:
                pass
    
    return None


def _compute_regimen_timing_features(
    patient_id: str,
    disease_site: str,
    tumor_subtype: Optional[str],
    regimen: Dict[str, Any],
    prior_regimen: Optional[Dict[str, Any]],
    prior_platinum_regimen: Optional[Dict[str, Any]],
    sorted_regimens: List[Dict[str, Any]],
    survival: Dict[str, Any],
    config: Dict[str, Any]
) -> Dict[str, Any]:
    """Compute timing features for a single regimen."""
    regimen_id = regimen["regimen_id"]
    regimen_type = regimen.get("regimen_type", "")
    regimen_start_date = _parse_date(regimen.get("regimen_start_date"))
    regimen_end_date = _parse_date(regimen.get("regimen_end_date"))
    
    # Initialize result
    result = {
        "patient_id": patient_id,
        "regimen_id": regimen_id,
        "disease_site": disease_site,
        "tumor_subtype": tumor_subtype,
        "regimen_type": regimen_type,
        "line_of_therapy": regimen.get("line_of_therapy"),
        "setting": regimen.get("setting"),
    }
    
    # 1. Compute TFI (Treatment-Free Interval)
    tfi_days = _compute_tfi(regimen, prior_regimen)
    result["TFI_days"] = tfi_days
    
    # 2. Compute PFS and OS from regimen start
    pfs_features = _compute_pfs(regimen, survival, regimen_start_date)
    result.update(pfs_features)
    
    os_features = _compute_os(regimen, survival, regimen_start_date)
    result.update(os_features)
    
    # 3. Compute PFI (Platinum-Free Interval) if platinum regimen
    if is_platinum_regimen(regimen_type) and config.get("require_platinum_for_pfi", True):
        pfi_features = _compute_pfi(
            regimen, sorted_regimens, config
        )
        result.update(pfi_features)
    else:
        result["PFI_days"] = None
        result["PFI_category"] = None
    
    # 4. Compute PTPI (Platinum-to-PARPi Interval) if DDR-targeted regimen
    if is_ddr_targeted_regimen(regimen_type):
        ptpi_days = _compute_ptpi(regimen, prior_platinum_regimen, regimen_start_date)
        result["PTPI_days"] = ptpi_days
    else:
        result["PTPI_days"] = None
    
    # 5. Data quality flags
    result["has_prior_platinum"] = prior_platinum_regimen is not None
    result["has_progression_date"] = regimen.get("progression_date") is not None
    result["has_death_or_followup"] = (
        survival.get("death_date") is not None or
        survival.get("last_followup_date") is not None
    )
    result["has_ca125_data"] = False  # Will be set if CA-125 features added
    
    return result


def _compute_tfi(
    regimen: Dict[str, Any],
    prior_regimen: Optional[Dict[str, Any]]
) -> Optional[int]:
    """Compute Treatment-Free Interval (TFI)."""
    if prior_regimen is None:
        return None  # First regimen, no prior regimen
    
    regimen_start = _parse_date(regimen.get("regimen_start_date"))
    prior_end = _parse_date(prior_regimen.get("regimen_end_date"))
    
    if regimen_start is None or prior_end is None:
        return None
    
    tfi_days = (regimen_start - prior_end).days
    
    # Handle overlapping regimens (TFI <= 0)
    if tfi_days < 0:
        logger.warning(
            f"Regimens overlap: regimen {regimen.get('regimen_id')} starts before "
            f"prior regimen {prior_regimen.get('regimen_id')} ends. TFI set to 0."
        )
        return 0
    
    return tfi_days


def _compute_pfs(
    regimen: Dict[str, Any],
    survival: Dict[str, Any],
    regimen_start_date: Optional[datetime]
) -> Dict[str, Any]:
    """Compute PFS (Progression-Free Survival) from regimen start."""
    if regimen_start_date is None:
        return {
            "PFS_from_regimen_days": None,
            "PFS_event": 0
        }
    
    progression_date = _parse_date(regimen.get("progression_date"))
    death_date = _parse_date(survival.get("death_date"))
    last_followup = _parse_date(survival.get("last_followup_date"))
    
    # Determine PFS event date (first of progression, death, or follow-up)
    event_dates = []
    if progression_date:
        event_dates.append(progression_date)
    if death_date:
        event_dates.append(death_date)
    if last_followup:
        event_dates.append(last_followup)
    
    if not event_dates:
        return {
            "PFS_from_regimen_days": None,
            "PFS_event": 0
        }
    
    pfs_event_date = min(event_dates)
    pfs_days = (pfs_event_date - regimen_start_date).days
    
    # PFS event = 1 if progression or death occurred (before follow-up)
    pfs_event = 0
    if progression_date or death_date:
        if pfs_event_date <= (last_followup or datetime.max):
            pfs_event = 1
    
    return {
        "PFS_from_regimen_days": max(0, pfs_days),  # Ensure non-negative
        "PFS_event": pfs_event
    }


def _compute_os(
    regimen: Dict[str, Any],
    survival: Dict[str, Any],
    regimen_start_date: Optional[datetime]
) -> Dict[str, Any]:
    """Compute OS (Overall Survival) from regimen start."""
    if regimen_start_date is None:
        return {
            "OS_from_regimen_days": None,
            "OS_event": 0
        }
    
    vital_status = survival.get("vital_status", "").lower()
    death_date = _parse_date(survival.get("death_date"))
    last_followup = _parse_date(survival.get("last_followup_date"))
    
    if vital_status == "dead" and death_date:
        os_days = (death_date - regimen_start_date).days
        os_event = 1
    elif last_followup:
        os_days = (last_followup - regimen_start_date).days
        os_event = 0
    else:
        return {
            "OS_from_regimen_days": None,
            "OS_event": 0
        }
    
    return {
        "OS_from_regimen_days": max(0, os_days),  # Ensure non-negative
        "OS_event": os_event
    }


def _find_most_recent_prior_platinum(
    current_regimen: Dict[str, Any],
    prior_regimens: List[Dict[str, Any]],
    config: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """Find most recent prior platinum regimen that ended before current regimen starts."""
    current_start = _parse_date(current_regimen.get("regimen_start_date"))
    if current_start is None:
        return None
    
    # Iterate backwards through prior regimens
    for prior_regimen in reversed(prior_regimens):
        prior_type = prior_regimen.get("regimen_type", "")
        if is_platinum_regimen(prior_type):
            prior_end = (
                _parse_date(prior_regimen.get("last_platinum_dose_date")) or
                _parse_date(prior_regimen.get("regimen_end_date"))
            )
            if prior_end and prior_end <= current_start:
                return prior_regimen
    
    return None


def _compute_pfi(
    regimen: Dict[str, Any],
    sorted_regimens: List[Dict[str, Any]],
    config: Dict[str, Any]
) -> Dict[str, Any]:
    """Compute PFI (Platinum-Free Interval) for platinum regimen."""
    # For PFI, we need to find the most recent prior platinum regimen
    # and compute interval from that to current regimen start (or progression)
    regimen_index = next(
        (i for i, r in enumerate(sorted_regimens) if r["regimen_id"] == regimen["regimen_id"]),
        -1
    )
    if regimen_index < 0:
        return {
            "PFI_days": None,
            "PFI_category": None
        }
    
    # Find most recent prior platinum regimen
    prior_platinum_regimen = _find_most_recent_prior_platinum(
        regimen, sorted_regimens[:regimen_index], config
    )
    
    if prior_platinum_regimen is None:
        # This is the first platinum regimen - PFI is computed from its last dose to next event
        last_platinum_dose = (
            _parse_date(regimen.get("last_platinum_dose_date")) or
            _parse_date(regimen.get("regimen_end_date"))
        )
        
        if last_platinum_dose is None:
            return {
                "PFI_days": None,
                "PFI_category": None
            }
        
        # Find next platinum regimen or progression
        subsequent_regimens = sorted_regimens[regimen_index + 1:]
        progression_date = _parse_date(regimen.get("progression_date"))
        
        # Find next platinum regimen
        next_platinum_regimen = None
        for subsequent_regimen in subsequent_regimens:
            if is_platinum_regimen(subsequent_regimen.get("regimen_type", "")):
                next_platinum_regimen = subsequent_regimen
                break
        
        # Determine PFI event based on config
        pfi_event_definition = config.get("pfi_event_definition", "next_platinum_or_progression")
        
        pfi_event_date = None
        if pfi_event_definition == "next_platinum_or_progression":
            # Use next platinum OR progression (whichever comes first)
            next_platinum_start = None
            if next_platinum_regimen:
                next_platinum_start = _parse_date(next_platinum_regimen.get("regimen_start_date"))
            
            event_dates = []
            if next_platinum_start:
                event_dates.append(next_platinum_start)
            if progression_date:
                event_dates.append(progression_date)
            
            if event_dates:
                pfi_event_date = min(event_dates)
        elif pfi_event_definition == "progression_only":
            # Use progression only
            if progression_date:
                pfi_event_date = progression_date
        elif pfi_event_definition == "next_platinum_only":
            # Use next platinum only
            if next_platinum_regimen:
                pfi_event_date = _parse_date(next_platinum_regimen.get("regimen_start_date"))
        
        if pfi_event_date is None:
            return {
                "PFI_days": None,
                "PFI_category": None
            }
        
        # Compute PFI days
        pfi_days = (pfi_event_date - last_platinum_dose).days
    else:
        # This is a subsequent platinum regimen - PFI is from prior platinum to current start
        prior_platinum_end = (
            _parse_date(prior_platinum_regimen.get("last_platinum_dose_date")) or
            _parse_date(prior_platinum_regimen.get("regimen_end_date"))
        )
        
        if prior_platinum_end is None:
            return {
                "PFI_days": None,
                "PFI_category": None
            }
        
        current_regimen_start = _parse_date(regimen.get("regimen_start_date"))
        
        if current_regimen_start is None:
            return {
                "PFI_days": None,
                "PFI_category": None
            }
        
        # PFI is from prior platinum end to current platinum start
        pfi_days = (current_regimen_start - prior_platinum_end).days
    
    if pfi_days < 0:
        logger.warning(
            f"PFI negative: prior platinum ends after current regimen starts. "
            f"PFI set to None."
        )
        return {
            "PFI_days": None,
            "PFI_category": None
        }
    
    # Categorize PFI
    pfi_category = _categorize_pfi(pfi_days, config)
    
    return {
        "PFI_days": pfi_days,
        "PFI_category": pfi_category
    }


def _categorize_pfi(pfi_days: int, config: Dict[str, Any]) -> str:
    """Categorize PFI into resistant/partially_sensitive/sensitive."""
    pfi_cutpoints = config.get("pfi_cutpoints_days", [180, 365])
    pfi_categories = config.get("pfi_categories", {})
    
    if len(pfi_cutpoints) < 2:
        # Fallback if cutpoints not properly configured
        if pfi_days < 180:
            return "<6m"
        elif pfi_days < 365:
            return "6-12m"
        else:
            return ">12m"
    
    cutpoint_1 = pfi_cutpoints[0]  # 180 days
    cutpoint_2 = pfi_cutpoints[1]  # 365 days
    
    if pfi_days < cutpoint_1:
        # Resistant (<6m)
        return pfi_categories.get("resistant", {}).get("label", "<6m")
    elif pfi_days < cutpoint_2:
        # Partially sensitive (6-12m)
        return pfi_categories.get("partially_sensitive", {}).get("label", "6-12m")
    else:
        # Sensitive (>12m)
        return pfi_categories.get("sensitive", {}).get("label", ">12m")


def _compute_ptpi(
    regimen: Dict[str, Any],
    prior_platinum_regimen: Optional[Dict[str, Any]],
    regimen_start_date: Optional[datetime]
) -> Optional[int]:
    """Compute PTPI (Platinum-to-PARPi Interval)."""
    if prior_platinum_regimen is None or regimen_start_date is None:
        return None
    
    prior_platinum_end = (
        _parse_date(prior_platinum_regimen.get("last_platinum_dose_date")) or
        _parse_date(prior_platinum_regimen.get("regimen_end_date"))
    )
    
    if prior_platinum_end is None:
        return None
    
    ptpi_days = (regimen_start_date - prior_platinum_end).days
    
    if ptpi_days < 0:
        logger.warning(
            f"PTPI negative: regimen {regimen.get('regimen_id')} starts before "
            f"prior platinum ends. PTPI set to None."
        )
        return None
    
    return ptpi_days


def _extract_ca125_features(ca125_record: Dict[str, Any]) -> Dict[str, Any]:
    """Extract CA-125/KELIM features from CA-125 record."""
    return {
        "kelim_k_value": ca125_record.get("kelim_k_value"),
        "kelim_category": ca125_record.get("kelim_category"),
        "ca125_percent_change_day21": ca125_record.get("ca125_percent_change_day21"),
        "ca125_percent_change_day42": ca125_record.get("ca125_percent_change_day42"),
        "ca125_time_to_50pct_reduction_days": ca125_record.get("ca125_time_to_50pct_reduction_days"),
        "ca125_normalized_by_cycle3": ca125_record.get("ca125_normalized_by_cycle3"),
        "has_ca125_data": True
    }


def _compute_kelim_from_measurements(
    raw_measurements: List[Dict[str, Any]],
    treatment_start_date: Optional[datetime],
    disease_site: str
) -> Optional[Dict[str, Any]]:
    """
    Compute KELIM from raw CA-125 measurements using kinetic biomarker framework.
    
    Args:
        raw_measurements: List of raw CA-125 measurements with date and value
        treatment_start_date: Treatment start date for the regimen
        disease_site: Disease site (e.g., "ovarian", "ovary")
    
    Returns:
        Dictionary with KELIM features or None if computation fails
    """
    if not treatment_start_date:
        return None
    
    if not raw_measurements:
        return None
    
    # Check if kinetic biomarker is available for this disease
    # Normalize disease site (ovary -> ovarian)
    disease_normalized = disease_site.lower()
    if disease_normalized == "ovary":
        disease_normalized = "ovarian"
    
    if not is_kinetic_biomarker_available(disease_normalized, "ca125"):
        logger.debug(f"CA-125 KELIM not configured for disease site: {disease_site}")
        return None
    
    try:
        # Initialize CA-125 KELIM computer for ovarian cancer
        kelim_computer = CA125KELIMOvarian()
        
        # Prepare measurements for computation
        measurements = [
            {
                "date": m.get("date"),
                "value": m.get("value")
            }
            for m in raw_measurements
            if m.get("value") is not None
        ]
        
        if not measurements:
            return None
        
        # Compute KELIM
        kelim_result = kelim_computer.compute_k_value(measurements, treatment_start_date)
        
        if kelim_result.get("k_value") is None:
            logger.debug(
                f"Failed to compute KELIM: {kelim_result.get('error', 'Unknown error')}"
            )
            return None
        
        # Extract KELIM features
        return {
            "kelim_k_value": kelim_result.get("k_value"),
            "kelim_category": kelim_result.get("category"),
            "has_ca125_data": True,
            # Additional metadata can be included if needed
            "kelim_confidence": kelim_result.get("confidence"),
            "kelim_measurements_used": kelim_result.get("measurements_used"),
            "kelim_modeling_approach": kelim_result.get("modeling_approach"),
        }
    
    except Exception as e:
        logger.error(f"Error computing KELIM from raw measurements: {e}")
        return None
