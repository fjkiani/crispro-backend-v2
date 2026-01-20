"""
Trial Data Enricher Service

Extracts detailed information from ClinicalTrials.gov API responses:
- Principal Investigator contact info
- Enrollment criteria and genetic requirements
- Therapy types and mechanism vectors
- Location details

Manager P3 Compliance: MoA tagging should be OFFLINE ONLY (never runtime) when possible.
Runtime keyword fallback is allowed only when explicitly enabled by the caller.
"""
import logging
import json
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
from api.services.client_dossier.dossier_generator import DRUG_MECHANISM_DB, get_drug_mechanism

logger = logging.getLogger(__name__)

# --- MoA Vector Store (offline tags) ---
_MOA_VECTOR_CACHE: Optional[Dict[str, Any]] = None


def _get_backend_root() -> Path:
    # From: api/services/trial_data_enricher.py -> api/services -> api -> oncology-backend-minimal
    current = Path(__file__).resolve()
    return current.parent.parent.parent


def _load_moa_vector_store() -> Dict[str, Any]:
    """
    Load offline-tagged MoA vectors from api/resources/trial_moa_vectors.json.
    Cached in-process for repeated calls.
    """
    global _MOA_VECTOR_CACHE
    if _MOA_VECTOR_CACHE is not None:
        return _MOA_VECTOR_CACHE

    store_path = _get_backend_root() / "api" / "resources" / "trial_moa_vectors.json"
    if not store_path.exists():
        _MOA_VECTOR_CACHE = {}
        return _MOA_VECTOR_CACHE

    try:
        with open(store_path, "r") as f:
            _MOA_VECTOR_CACHE = json.load(f) or {}
    except Exception as e:
        logger.warning(f"Failed to load MoA vector store: {e}")
        _MOA_VECTOR_CACHE = {}

    return _MOA_VECTOR_CACHE


def _normalize_nct_id(trial_data: Dict[str, Any]) -> Optional[str]:
    """
    Normalize NCT ID from various trial payload shapes.
    """
    for key in ("nct_id", "nctId", "id", "NCTId", "nct"):
        val = trial_data.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()

    # ClinicalTrials.gov v2 shape
    protocol = trial_data.get("protocolSection", {}) if isinstance(trial_data.get("protocolSection", {}), dict) else {}
    ident = protocol.get("identificationModule", {}) if isinstance(protocol.get("identificationModule", {}), dict) else {}
    nct = ident.get("nctId")
    if isinstance(nct, str) and nct.strip():
        return nct.strip()

    return None


def extract_moa_vector_for_trial(
    trial_data: Dict[str, Any],
    *,
    allow_runtime_keyword_fallback: bool = False
) -> Tuple[Optional[Dict[str, float]], Dict[str, Any]]:
    """
    Return MoA vector dict for a trial, preferring OFFLINE-tagged vectors.

    Order:
    1) Offline MoA vector store (api/resources/trial_moa_vectors.json)
    2) Optional runtime keyword fallback (interventions -> DRUG_MECHANISM_DB) if allow_runtime_keyword_fallback=True

    Returns:
        (moa_vector_dict or None, metadata dict)
    """
    nct_id = _normalize_nct_id(trial_data)
    if not nct_id:
        return None, {"source": "no_nct_id"}

    store = _load_moa_vector_store()
    stored = store.get(nct_id)
    if isinstance(stored, dict):
        moa = stored.get("moa_vector")
        prov = stored.get("provenance", {})
        if isinstance(moa, dict) and moa:
            return moa, {
                "source": stored.get("source", "offline_tag"),
                "provider": prov.get("provider"),
                "model": prov.get("model"),
                "confidence": stored.get("confidence"),
                "tagged_at": stored.get("tagged_at"),
                "provenance": prov,
            }

    if not allow_runtime_keyword_fallback:
        return None, {"source": "no_offline_tag"}

    # --- Runtime keyword fallback (explicitly enabled only) ---
    interventions = trial_data.get("interventions") or trial_data.get("interventions_text") or ""
    if isinstance(interventions, list):
        interventions_text = ", ".join([str(x) for x in interventions])
    else:
        interventions_text = str(interventions)

    moa_dict: Dict[str, float] = {
        "ddr": 0.0, "mapk": 0.0, "pi3k": 0.0, "vegf": 0.0, "her2": 0.0, "io": 0.0, "efflux": 0.0
    }

    # naive mapping: if any known drug mechanism tags map to our 7D categories
    # (kept intentionally conservative; offline tags preferred)
    for token in [t.strip() for t in interventions_text.replace(";", ",").split(",") if t.strip()]:
        mech = get_drug_mechanism(token)
        if not mech:
            continue
        mech_lower = str(mech).lower()
        if "parp" in mech_lower or "atr" in mech_lower or "chk" in mech_lower or "wee1" in mech_lower:
            moa_dict["ddr"] = max(moa_dict["ddr"], 0.7)
        if "mek" in mech_lower or "braf" in mech_lower or "kras" in mech_lower or "mapk" in mech_lower:
            moa_dict["mapk"] = max(moa_dict["mapk"], 0.7)
        if "pi3k" in mech_lower or "akt" in mech_lower or "mtor" in mech_lower:
            moa_dict["pi3k"] = max(moa_dict["pi3k"], 0.7)
        if "vegf" in mech_lower or "angiogenesis" in mech_lower:
            moa_dict["vegf"] = max(moa_dict["vegf"], 0.7)
        if "her2" in mech_lower or "trastuzumab" in mech_lower or "pertuzumab" in mech_lower:
            moa_dict["her2"] = max(moa_dict["her2"], 0.7)
        if "pd-1" in mech_lower or "pd-l1" in mech_lower or "ctla-4" in mech_lower or "immuno" in mech_lower:
            moa_dict["io"] = max(moa_dict["io"], 0.7)
        if "abcb1" in mech_lower or "p-gp" in mech_lower or "mdr" in mech_lower:
            moa_dict["efflux"] = max(moa_dict["efflux"], 0.7)

    if all(v == 0.0 for v in moa_dict.values()):
        return None, {"source": "runtime_keyword_no_match"}

    return moa_dict, {"source": "runtime_keyword_matching", "interventions": interventions_text[:200]}


def extract_pi_information(trial_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Extract Principal Investigator information from trial data.
    
    Priority: Overall PI > Study Director > Study Chair
    
    Args:
        trial_data: ClinicalTrials.gov API response or parsed trial data
        
    Returns:
        Dict with PI name, email, institution, phone, or None if not found
    """
    try:
        protocol_section = trial_data.get('protocolSection', {})
        contacts_locations = protocol_section.get('contactsLocationsModule', {})
        
        # Try overall PI first
        # API v2 uses 'overallOfficials' (plural), but also check 'overallOfficial' (singular) for compatibility
        overall_officials = contacts_locations.get('overallOfficials', [])
        if not overall_officials:
            overall_officials = contacts_locations.get('overallOfficial', [])

        def _extract_field(official: Dict[str, Any], field: str) -> str:
            """Extract field handling both flat (API v2) and nested structures."""
            value = official.get(field, '')
            if isinstance(value, dict):
                return value.get('value', '')
            return value if isinstance(value, str) else ''

        def _extract_contact_info(official: Dict[str, Any]) -> tuple[str, str]:
            """Extract email and phone from contact object or direct fields."""
            contact = official.get('contact', {})
            if isinstance(contact, dict):
                email = contact.get('email', '') or official.get('email', '')
                phone = contact.get('phone', '') or official.get('phone', '')
            else:
                email = official.get('email', '')
                phone = official.get('phone', '')
            return (email if isinstance(email, str) else '', phone if isinstance(phone, str) else '')

        # Try overall PI first
        for official in overall_officials:
            role = _extract_field(official, 'role')
            if role == 'PRINCIPAL_INVESTIGATOR':
                email, phone = _extract_contact_info(official)
                return {
                    'name': _extract_field(official, 'name'),
                    'email': email,
                    'institution': _extract_field(official, 'affiliation'),
                    'phone': phone,
                    'role': role
                }

        # Try Study Director
        for official in overall_officials:
            role = _extract_field(official, 'role')
            if role == 'STUDY_DIRECTOR':
                email, phone = _extract_contact_info(official)
                return {
                    'name': _extract_field(official, 'name'),
                    'email': email,
                    'institution': _extract_field(official, 'affiliation'),
                    'phone': phone,
                    'role': role
                }

        # Try Study Chair
        for official in overall_officials:
            role = _extract_field(official, 'role')
            if role == 'STUDY_CHAIR':
                email, phone = _extract_contact_info(official)
                return {
                    'name': _extract_field(official, 'name'),
                    'email': email,
                    'institution': _extract_field(official, 'affiliation'),
                    'phone': phone,
                    'role': role
                }

        # Fallback: First overall official
        if overall_officials:
            official = overall_officials[0]
            email, phone = _extract_contact_info(official)
            return {
                'name': _extract_field(official, 'name'),
                'email': email,
                'institution': _extract_field(official, 'affiliation'),
                'phone': phone,
                'role': _extract_field(official, 'role')
            }
        
    except Exception as e:
        logger.warning(f"Failed to extract PI information: {e}")
    
    return None
