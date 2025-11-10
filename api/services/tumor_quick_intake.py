"""
Tumor Quick Intake Service - Level 0/1 Support

Generates TumorContext from minimal clinical inputs using disease priors
for sporadic cancer patients without NGS reports.
"""

from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
import json
import os

from ..schemas.tumor_context import TumorContext, SomaticMutation


# Disease priors will be loaded from Agent Jr's file
# For now, we'll use conservative defaults until Agent Jr delivers
CONSERVATIVE_PRIORS = {
    "ovarian_hgs": {
        "name": "High-Grade Serous Ovarian Carcinoma",
        "prevalence": {
            "tp53_mutation": 0.96,
            "hrd_high": 0.50,
            "msi_high": 0.01
        },
        "distributions": {
            "tmb": {"median": 5.2, "q1": 3.1, "q3": 8.7, "high_cutoff": 10},
            "hrd": {"median": 42, "q1": 15, "q3": 60, "high_cutoff": 42}
        },
        "platinum_response": {
            "sensitive_hrd_correlation": 0.70
        }
    },
    "breast_tnbc": {
        "name": "Triple-Negative Breast Cancer",
        "prevalence": {
            "tp53_mutation": 0.80,
            "hrd_high": 0.30,
            "msi_high": 0.01
        },
        "distributions": {
            "tmb": {"median": 4.0, "q1": 2.5, "q3": 6.5, "high_cutoff": 10},
            "hrd": {"median": 28, "q1": 10, "q3": 45, "high_cutoff": 42}
        },
        "platinum_response": {
            "sensitive_hrd_correlation": 0.60
        }
    },
    "colorectal": {
        "name": "Colorectal Adenocarcinoma",
        "prevalence": {
            "tp53_mutation": 0.60,
            "hrd_high": 0.05,
            "msi_high": 0.15
        },
        "distributions": {
            "tmb": {"median": 8.5, "q1": 4.0, "q3": 15.0, "high_cutoff": 10},
            "hrd": {"median": 18, "q1": 8, "q3": 30, "high_cutoff": 42}
        },
        "platinum_response": {
            "sensitive_hrd_correlation": 0.40
        }
    }
}

PRIORS_VERSION = "v1.0_bootstrap"
PRIORS_REFRESH_DATE = datetime.utcnow().strftime("%Y-%m-%d")


def load_disease_priors() -> Dict[str, Any]:
    """
    Load disease priors from Agent Jr's JSON file.
    
    Falls back to conservative defaults if file not yet available.
    """
    priors_path = os.path.join(
        os.path.dirname(__file__),
        "..", "resources", "disease_priors.json"
    )
    
    try:
        if os.path.exists(priors_path):
            with open(priors_path, 'r') as f:
                priors_data = json.load(f)
                return priors_data.get("diseases", CONSERVATIVE_PRIORS)
    except Exception as e:
        print(f"Warning: Could not load disease_priors.json: {e}. Using conservative defaults.")
    
    return CONSERVATIVE_PRIORS


async def generate_level0_tumor_context(
    cancer_type: str,
    stage: Optional[str] = None,
    line: Optional[int] = None,
    platinum_response: Optional[str] = None,
    manual_tmb: Optional[float] = None,
    manual_msi: Optional[str] = None,
    manual_hrd: Optional[float] = None,
    manual_mutations: Optional[List[SomaticMutation]] = None
) -> Tuple[TumorContext, Dict[str, Any], float, List[str]]:
    """
    Generate TumorContext from minimal clinical inputs.
    
    Level 0: Disease priors only (no manual inputs)
    Level 1: Partial manual inputs (elevates confidence)
    
    Returns:
        (TumorContext, provenance_dict, confidence_cap, recommendations)
    """
    
    # Load disease priors
    disease_priors = load_disease_priors()
    
    if cancer_type not in disease_priors:
        raise ValueError(f"Unknown cancer type: {cancer_type}. Supported: {list(disease_priors.keys())}")
    
    priors = disease_priors[cancer_type]
    
    # Determine level based on manual inputs
    manual_fields_provided = sum([
        manual_tmb is not None,
        manual_msi is not None,
        manual_hrd is not None,
        bool(manual_mutations)
    ])
    
    if manual_fields_provided == 0:
        level = "L0"
        confidence_cap = 0.4
    else:
        level = "L1"
        confidence_cap = 0.6
    
    # Estimate TMB
    if manual_tmb is not None:
        tmb_value = manual_tmb
        tmb_source = "manual"
    else:
        # Use disease median (Agent Jr's structure has nested dicts)
        tmb_dist = priors["distributions"]["tmb"]
        tmb_value = tmb_dist.get("median", tmb_dist.get("value", 5.0))  # Backward compat
        tmb_source = "disease_prior"
    
    # Estimate MSI (CRITICAL: Do NOT infer - keep null if unknown)
    msi_status = manual_msi  # Will be None if not provided
    msi_source = "manual" if manual_msi else "unknown"
    
    # Estimate HRD
    if manual_hrd is not None:
        hrd_score = manual_hrd
        hrd_source = "manual"
    elif platinum_response == "sensitive":
        # Use platinum response as HRD proxy (conservative estimate)
        # Platinum-sensitive → possible HRD, use disease median
        hrd_dist = priors["distributions"]["hrd"]
        hrd_score = hrd_dist.get("median", hrd_dist.get("value", 30.0))  # Backward compat
        hrd_source = "platinum_proxy"
    else:
        # Use disease median (conservative)
        hrd_dist = priors["distributions"]["hrd"]
        hrd_score = hrd_dist.get("median", hrd_dist.get("value", 30.0))  # Backward compat
        hrd_source = "disease_prior"
    
    # Somatic mutations
    mutations = manual_mutations if manual_mutations else []
    
    # Calculate completeness score
    completeness_data = {
        "tmb": tmb_value,
        "msi_status": msi_status,
        "hrd_score": hrd_score,
        "somatic_mutations": mutations
    }
    completeness_score = TumorContext.calculate_completeness(completeness_data)
    
    # Build TumorContext
    tumor_context = TumorContext(
        somatic_mutations=mutations,
        tmb=tmb_value,
        msi_status=msi_status,
        hrd_score=hrd_score,
        level=level,
        priors_used=True,
        completeness_score=completeness_score,
        tumor_context_source="Quick Intake"
    )
    
    # Build provenance
    provenance = {
        "no_report_mode": True,
        "disease_priors_used": True,
        "disease_priors_version": PRIORS_VERSION,
        "priors_refresh_date": PRIORS_REFRESH_DATE,
        "platinum_proxy_used": platinum_response == "sensitive" and manual_hrd is None,
        "confidence_version": "v1.0",
        "estimates": {
            "tmb": {"value": tmb_value, "source": tmb_source},
            "msi_status": {"value": msi_status, "source": msi_source},
            "hrd_score": {"value": hrd_score, "source": hrd_source}
        }
    }
    
    # Build recommendations
    recommendations = []
    if level == "L0":
        recommendations.append("Level 0 analysis: Based on disease priors only. Tumor NGS recommended for refined analysis.")
    elif level == "L1":
        recommendations.append("Level 1 analysis: Partial data provided. Full tumor NGS recommended for complete assessment.")
    
    if msi_status is None:
        recommendations.append("MSI status unknown. MSI testing (IHC/PCR or NGS) recommended for immunotherapy eligibility.")
    
    if hrd_source == "platinum_proxy":
        recommendations.append("HRD estimated from platinum response. Genomic HRD testing recommended for PARP inhibitor eligibility.")
    
    return tumor_context, provenance, confidence_cap, recommendations

