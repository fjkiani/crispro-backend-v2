"""
Survival Analysis Module

Compute survival analysis (Kaplan-Meier, Cox regression) for PFS and OS.
"""

from typing import List, Dict, Any
import pandas as pd

# Optional: lifelines for survival analysis
try:
    from lifelines import KaplanMeierFitter, CoxPHFitter
    from lifelines.statistics import logrank_test
    HAS_LIFELINES = True
except ImportError:
    HAS_LIFELINES = False


def compute_survival_analysis(
    predictions: List[Dict[str, Any]],
    patients: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Compute survival analysis (Kaplan-Meier, Cox regression).
    
    Args:
        predictions: List of prediction results (may include errors)
        patients: List of patient dicts with clinical_outcomes
    
    Returns:
        Dict with pfs_survival and os_survival metrics
    """
    if not HAS_LIFELINES:
        error_msg = {"error": "lifelines not available - install with: pip install lifelines"}
        print(f"   ⚠️  Survival Analysis: {error_msg['error']}")
        return error_msg
    
    print(f"\n📊 Computing survival analysis...")
    
    # Create patient lookup
    patient_lookup = {p.get("patient_id"): p for p in patients}
    
    # Prepare data for survival analysis
    survival_data = []
    
    for pred in predictions:
        if "error" in pred:
            continue
        
        patient_id = pred.get("patient_id")
        patient = patient_lookup.get(patient_id)
        
        if not patient:
            continue
        
        outcomes = patient.get("clinical_outcomes") or patient.get("outcomes", {})
        # Handle both top_drug dict and direct efficacy_score
        if isinstance(pred.get("top_drug"), dict):
            efficacy_score = pred.get("top_drug", {}).get("efficacy_score", 0.0)
        else:
            efficacy_score = pred.get("efficacy_score", 0.0)
        
        # PFS data
        pfs_months = outcomes.get("PFS_MONTHS")
        pfs_status = outcomes.get("PFS_STATUS", "")
        # Use parser to handle all formats
        from benchmark_common.utils.pfs_status_parser import parse_pfs_status
        event, status = parse_pfs_status(pfs_status)
        pfs_event = event if event is not None else 0
        
        # OS data
        os_months = outcomes.get("OS_MONTHS")
        os_status = outcomes.get("OS_STATUS", "")
        os_event = 1 if ("1:DECEASED" in os_status or "1:" in os_status) else 0
        
        if pfs_months is not None and os_months is not None:
            try:
                survival_data.append({
                    "patient_id": patient_id,
                    "efficacy_score": float(efficacy_score),
                    "pfs_months": float(pfs_months),
                    "pfs_event": int(pfs_event),
                    "os_months": float(os_months),
                    "os_event": int(os_event),
                })
            except (ValueError, TypeError):
                pass
    
    if len(survival_data) < 50:
        error_msg = {"error": f"Insufficient data for survival analysis (n={len(survival_data)})"}
        print(f"   ⚠️  Survival Analysis: {error_msg['error']}")
        return error_msg
    
    df = pd.DataFrame(survival_data)
    
    # Create efficacy score quartiles
    try:
        df["efficacy_quartile"] = pd.qcut(df["efficacy_score"], q=4, labels=["Q1", "Q2", "Q3", "Q4"])
    except ValueError:
        # If not enough unique values for quartiles, skip quartile analysis
        df["efficacy_quartile"] = "Q1"
    
    metrics = {}
    
    # PFS Survival Analysis
    try:
        # Kaplan-Meier by quartile
        kmf_q1 = KaplanMeierFitter()
        kmf_q4 = KaplanMeierFitter()
        
        q1_data = df[df["efficacy_quartile"] == "Q1"]
        q4_data = df[df["efficacy_quartile"] == "Q4"]
        
        if len(q1_data) > 0 and len(q4_data) > 0:
            kmf_q1.fit(q1_data["pfs_months"], q1_data["pfs_event"], label="Q1 (Low Efficacy)")
            kmf_q4.fit(q4_data["pfs_months"], q4_data["pfs_event"], label="Q4 (High Efficacy)")
            
            # Log-rank test
            results = logrank_test(
                q1_data["pfs_months"], q4_data["pfs_months"],
                q1_data["pfs_event"], q4_data["pfs_event"]
            )
            
            # Cox regression
            cph = CoxPHFitter()
            cph.fit(df[["pfs_months", "pfs_event", "efficacy_score"]], duration_col="pfs_months", event_col="pfs_event")
            hr = cph.hazard_ratios_["efficacy_score"]
            hr_p_value = cph.summary.loc["efficacy_score", "p"]
            
            metrics["pfs_survival"] = {
                "logrank_p_value": float(results.p_value),
                "hazard_ratio": float(hr),
                "hazard_ratio_p_value": float(hr_p_value),
                "q1_median_pfs": float(kmf_q1.median_survival_time_) if hasattr(kmf_q1, 'median_survival_time_') and kmf_q1.median_survival_time_ is not None else None,
                "q4_median_pfs": float(kmf_q4.median_survival_time_) if hasattr(kmf_q4, 'median_survival_time_') and kmf_q4.median_survival_time_ is not None else None,
                "n_patients": len(df)
            }
            print(f"   ✅ PFS Survival: HR={hr:.3f}, p={hr_p_value:.4f} (n={len(df)})")
        else:
            metrics["pfs_survival"] = {"error": "Insufficient data for quartile comparison", "n_patients": len(df)}
            print(f"   ⚠️  PFS Survival: Insufficient data for quartile comparison")
    except Exception as e:
        metrics["pfs_survival"] = {"error": str(e), "n_patients": len(df)}
        print(f"   ⚠️  PFS Survival: Error - {e}")
    
    # OS Survival Analysis
    try:
        # Kaplan-Meier by quartile
        kmf_q1_os = KaplanMeierFitter()
        kmf_q4_os = KaplanMeierFitter()
        
        if len(q1_data) > 0 and len(q4_data) > 0:
            kmf_q1_os.fit(q1_data["os_months"], q1_data["os_event"], label="Q1 (Low Efficacy)")
            kmf_q4_os.fit(q4_data["os_months"], q4_data["os_event"], label="Q4 (High Efficacy)")
            
            # Log-rank test
            results_os = logrank_test(
                q1_data["os_months"], q4_data["os_months"],
                q1_data["os_event"], q4_data["os_event"]
            )
            
            # Cox regression
            cph_os = CoxPHFitter()
            cph_os.fit(df[["os_months", "os_event", "efficacy_score"]], duration_col="os_months", event_col="os_event")
            hr_os = cph_os.hazard_ratios_["efficacy_score"]
            hr_os_p_value = cph_os.summary.loc["efficacy_score", "p"]
            
            metrics["os_survival"] = {
                "logrank_p_value": float(results_os.p_value),
                "hazard_ratio": float(hr_os),
                "hazard_ratio_p_value": float(hr_os_p_value),
                "q1_median_os": float(kmf_q1_os.median_survival_time_) if hasattr(kmf_q1_os, 'median_survival_time_') and kmf_q1_os.median_survival_time_ is not None else None,
                "q4_median_os": float(kmf_q4_os.median_survival_time_) if hasattr(kmf_q4_os, 'median_survival_time_') and kmf_q4_os.median_survival_time_ is not None else None,
                "n_patients": len(df)
            }
            print(f"   ✅ OS Survival: HR={hr_os:.3f}, p={hr_os_p_value:.4f} (n={len(df)})")
        else:
            metrics["os_survival"] = {"error": "Insufficient data for quartile comparison", "n_patients": len(df)}
            print(f"   ⚠️  OS Survival: Insufficient data for quartile comparison")
    except Exception as e:
        metrics["os_survival"] = {"error": str(e), "n_patients": len(df)}
        print(f"   ⚠️  OS Survival: Error - {e}")
    
    return metrics


