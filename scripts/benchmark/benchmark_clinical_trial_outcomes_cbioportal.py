#!/usr/bin/env python3
"""
cBioPortal Clinical Trial Outcome Benchmark Script

Benchmarks our system's ability to predict clinical trial outcomes (PFS, OS, response)
using extracted cBioPortal patient data.

Input: Extracted cBioPortal dataset (mutations + clinical outcomes + treatments)
Output: Correlation metrics, classification metrics, survival analysis
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

import httpx
import numpy as np
from scipy import stats
from sklearn.metrics import roc_auc_score, average_precision_score, roc_curve, precision_recall_curve
import pandas as pd

# Optional: lifelines for survival analysis
try:
    from lifelines import KaplanMeierFitter, CoxPHFitter
    from lifelines.statistics import logrank_test
    HAS_LIFELINES = True
except ImportError:
    HAS_LIFELINES = False
    print("⚠️  lifelines not available - survival analysis will be skipped")

API_ROOT = "http://127.0.0.1:8000"

# Output directory - find project root
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent
OUTPUT_DIR = PROJECT_ROOT / "data" / "benchmarks"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def load_cbioportal_dataset(dataset_file: Optional[str] = None) -> List[Dict[str, Any]]:
    """Load extracted cBioPortal dataset."""
    if dataset_file is None:
        dataset_file = OUTPUT_DIR / "cbioportal_trial_datasets_latest.json"
    
    if not Path(dataset_file).exists():
        raise FileNotFoundError(f"Dataset file not found: {dataset_file}")
    
    with open(dataset_file, "r") as f:
        datasets = json.load(f)
    
    # Focus on ov_tcga_pan_can_atlas_2018 (best dataset with PFS + OS)
    primary_dataset = next(
        (d for d in datasets if d.get("study_id") == "ov_tcga_pan_can_atlas_2018"),
        None
    )
    
    if not primary_dataset:
        raise ValueError("Primary dataset (ov_tcga_pan_can_atlas_2018) not found")
    
    patients = primary_dataset.get("patients", [])
    
    # Filter to patients with mutations + PFS + OS
    eligible_patients = [
        p for p in patients
        if len(p.get("mutations", [])) > 0 and
        isinstance(p.get("clinical_outcomes"), dict) and
        p.get("clinical_outcomes", {}).get("PFS_MONTHS") is not None and
        p.get("clinical_outcomes", {}).get("OS_MONTHS") is not None
    ]
    
    print(f"✅ Loaded {len(eligible_patients)} eligible patients from {dataset_file.name}")
    print(f"   Total patients in dataset: {len(patients)}")
    print(f"   Eligible (mutations + PFS + OS): {len(eligible_patients)}")
    
    return eligible_patients


def convert_mutation_to_request_format(mutation: Dict[str, Any]) -> Dict[str, Any]:
    """Convert cBioPortal mutation format to our API request format."""
    # cBioPortal uses chromosome, position, ref, alt
    # Our API expects chrom, pos, ref, alt, hgvs_p, gene
    
    # Handle chromosome format (may be "17" or "chr17")
    chrom = str(mutation.get("chromosome", "")).replace("chr", "").replace("Chr", "")
    
    return {
        "gene": mutation.get("gene", ""),
        "hgvs_p": mutation.get("protein_change") or "",
        "chrom": chrom,
        "pos": mutation.get("position"),
        "ref": mutation.get("ref", ""),
        "alt": mutation.get("alt", ""),
        "build": "GRCh37"  # TCGA data is on GRCh37
    }


async def predict_patient_efficacy(
    client: httpx.AsyncClient,
    patient: Dict[str, Any],
    api_base: str = API_ROOT
) -> Dict[str, Any]:
    """Predict drug efficacy for a patient using our system."""
    try:
        # Convert mutations to request format
        mutations = [
            convert_mutation_to_request_format(m)
            for m in patient.get("mutations", [])
            if m.get("gene") and m.get("position")  # Require gene and position
        ]
        
        if not mutations:
            return {"error": "No valid mutations", "patient_id": patient.get("patient_id")}
        
        # Build request payload
        payload = {
            "model_id": "evo2_1b",
            "mutations": mutations,
            "disease": "ovarian_cancer",
            "options": {
                "adaptive": True,
                "ensemble": False,
            },
            "tumor_context": {
                "disease": "ovarian_cancer"
            }
        }
        
        # Call API
        resp = await client.post(
            f"{api_base}/api/efficacy/predict",
            json=payload,
            timeout=120.0,  # Longer timeout for multiple mutations
        )
        
        if resp.status_code >= 400:
            return {
                "error": f"HTTP {resp.status_code}",
                "patient_id": patient.get("patient_id"),
                "response_text": resp.text[:200]
            }
        
        data = resp.json()
        drugs = data.get("drugs", [])
        provenance = data.get("provenance", {})
        
        # Extract key metrics
        top_drug = drugs[0] if drugs else {}
        
        # Extract pathway scores from provenance
        pathway_disruption = provenance.get("confidence_breakdown", {}).get("pathway_disruption", {})
        
        return {
            "patient_id": patient.get("patient_id"),
            "top_drug": {
                "name": top_drug.get("name", ""),
                "efficacy_score": top_drug.get("efficacy_score", 0.0),
                "confidence": top_drug.get("confidence", 0.0),
                "evidence_tier": top_drug.get("evidence_tier", ""),
            },
            "drug_rankings": [
                {
                    "name": drug.get("name", ""),
                    "efficacy_score": drug.get("efficacy_score", 0.0),
                    "confidence": drug.get("confidence", 0.0),
                }
                for drug in drugs[:10]  # Top 10 drugs
            ],
            "pathway_disruption": pathway_disruption,
            "provenance": {
                "S_contribution": provenance.get("confidence_breakdown", {}).get("S_contribution", 0.0),
                "P_contribution": provenance.get("confidence_breakdown", {}).get("P_contribution", 0.0),
                "E_contribution": provenance.get("confidence_breakdown", {}).get("E_contribution", 0.0),
            }
        }
        
    except Exception as e:
        return {
            "error": str(e)[:200],
            "patient_id": patient.get("patient_id")
        }


async def run_benchmark(
    patients: List[Dict[str, Any]],
    api_base: str = API_ROOT,
    max_concurrent: int = 5
) -> List[Dict[str, Any]]:
    """Run predictions for all patients."""
    print(f"\n🔬 Running predictions for {len(patients)} patients...")
    print(f"   API Base: {api_base}")
    print(f"   Max Concurrent: {max_concurrent}")
    
    results = []
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def predict_with_semaphore(client, patient):
        async with semaphore:
            return await predict_patient_efficacy(client, patient, api_base)
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        tasks = [predict_with_semaphore(client, patient) for patient in patients]
        results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Handle exceptions
    valid_results = []
    errors = 0
    
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            errors += 1
            print(f"   ⚠️  Error for patient {patients[i].get('patient_id', 'unknown')}: {result}")
        elif result.get("error"):
            errors += 1
            print(f"   ⚠️  Error for patient {result.get('patient_id', 'unknown')}: {result.get('error')}")
        else:
            valid_results.append(result)
    
    print(f"   ✅ Completed: {len(valid_results)} successful, {errors} errors")
    return valid_results


def compute_correlation_metrics(
    predictions: List[Dict[str, Any]],
    patients: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Compute correlation metrics between predictions and outcomes."""
    print(f"\n📊 Computing correlation metrics...")
    
    # Create patient lookup
    patient_lookup = {p.get("patient_id"): p for p in patients}
    
    # Extract data for correlation
    pfs_scores = []
    pfs_months = []
    os_scores = []
    os_months = []
    response_scores = []
    response_labels = []
    
    for pred in predictions:
        patient_id = pred.get("patient_id")
        patient = patient_lookup.get(patient_id)
        
        if not patient:
            continue
        
        outcomes = patient.get("clinical_outcomes", {})
        efficacy_score = pred.get("top_drug", {}).get("efficacy_score", 0.0)
        
        # PFS data
        pfs_months_val = outcomes.get("PFS_MONTHS")
        if pfs_months_val is not None:
            try:
                pfs_months.append(float(pfs_months_val))
                pfs_scores.append(efficacy_score)
            except (ValueError, TypeError):
                pass
        
        # OS data
        os_months_val = outcomes.get("OS_MONTHS")
        if os_months_val is not None:
            try:
                os_months.append(float(os_months_val))
                os_scores.append(efficacy_score)
            except (ValueError, TypeError):
                pass
        
        # Response data (PFS_STATUS: 0:CENSORED = good, 1:PROGRESSION = poor)
        pfs_status = outcomes.get("PFS_STATUS", "")
        if pfs_status:
            if "0:CENSORED" in pfs_status or "0:" in pfs_status:
                response_labels.append(1)  # Good response (no progression)
                response_scores.append(efficacy_score)
            elif "1:PROGRESSION" in pfs_status or "1:" in pfs_status:
                response_labels.append(0)  # Poor response (progression)
                response_scores.append(efficacy_score)
    
    metrics = {}
    
    # PFS Correlation (filter NaN/Inf)
    if len(pfs_scores) >= 10:
        pfs_valid_mask = ~(np.isnan(pfs_scores) | np.isinf(pfs_scores) | np.isnan(pfs_months) | np.isinf(pfs_months))
        pfs_scores_clean = np.array(pfs_scores)[pfs_valid_mask]
        pfs_months_clean = np.array(pfs_months)[pfs_valid_mask]
        print(f"   Filtered: {len(pfs_scores_clean)}/{len(pfs_scores)} valid PFS pairs")
        
        if len(pfs_scores_clean) >= 10:
            pfs_pearson = stats.pearsonr(pfs_scores_clean, pfs_months_clean)
            pfs_spearman = stats.spearmanr(pfs_scores_clean, pfs_months_clean)
            metrics["pfs_correlation"] = {
                "pearson_r": float(pfs_pearson[0]),
                "pearson_p_value": float(pfs_pearson[1]),
                "spearman_rho": float(pfs_spearman[0]),
                "spearman_p_value": float(pfs_spearman[1]),
                "n_patients": len(pfs_scores_clean),
                "filtered_out": len(pfs_scores) - len(pfs_scores_clean)
            }
            print(f"   ✅ PFS Correlation: r={pfs_pearson[0]:.3f}, p={pfs_pearson[1]:.4f} (n={len(pfs_scores_clean)})")
        else:
            metrics["pfs_correlation"] = {"error": "Insufficient valid data after filtering", "n_patients": len(pfs_scores_clean)}
            print(f"   ⚠️  PFS Correlation: Insufficient data after filtering (n={len(pfs_scores_clean)})")
    else:
        metrics["pfs_correlation"] = {"error": "Insufficient data", "n_patients": len(pfs_scores)}
        print(f"   ⚠️  PFS Correlation: Insufficient data (n={len(pfs_scores)})")
    
    # OS Correlation (filter NaN/Inf)
    if len(os_scores) >= 10:
        os_valid_mask = ~(np.isnan(os_scores) | np.isinf(os_scores) | np.isnan(os_months) | np.isinf(os_months))
        os_scores_clean = np.array(os_scores)[os_valid_mask]
        os_months_clean = np.array(os_months)[os_valid_mask]
        print(f"   Filtered: {len(os_scores_clean)}/{len(os_scores)} valid OS pairs")
        
        if len(os_scores_clean) >= 10:
            os_pearson = stats.pearsonr(os_scores_clean, os_months_clean)
            os_spearman = stats.spearmanr(os_scores_clean, os_months_clean)
            metrics["os_correlation"] = {
                "pearson_r": float(os_pearson[0]),
                "pearson_p_value": float(os_pearson[1]),
                "spearman_rho": float(os_spearman[0]),
                "spearman_p_value": float(os_spearman[1]),
                "n_patients": len(os_scores_clean),
                "filtered_out": len(os_scores) - len(os_scores_clean)
            }
            print(f"   ✅ OS Correlation: r={os_pearson[0]:.3f}, p={os_pearson[1]:.4f} (n={len(os_scores_clean)})")
        else:
            metrics["os_correlation"] = {"error": "Insufficient valid data after filtering", "n_patients": len(os_scores_clean)}
            print(f"   ⚠️  OS Correlation: Insufficient data after filtering (n={len(os_scores_clean)})")
    else:
        metrics["os_correlation"] = {"error": "Insufficient data", "n_patients": len(os_scores)}
        print(f"   ⚠️  OS Correlation: Insufficient data (n={len(os_scores)})")
    
    # Response Classification
    if len(response_scores) >= 20 and len(set(response_labels)) >= 2:
        try:
            roc_auc = roc_auc_score(response_labels, response_scores)
            pr_auc = average_precision_score(response_labels, response_scores)
            
            # Compute optimal threshold
            fpr, tpr, thresholds = roc_curve(response_labels, response_scores)
            optimal_idx = np.argmax(tpr - fpr)
            optimal_threshold = thresholds[optimal_idx]
            
            # Compute sensitivity and specificity at optimal threshold
            predictions_binary = (np.array(response_scores) >= optimal_threshold).astype(int)
            tp = np.sum((predictions_binary == 1) & (np.array(response_labels) == 1))
            tn = np.sum((predictions_binary == 0) & (np.array(response_labels) == 0))
            fp = np.sum((predictions_binary == 1) & (np.array(response_labels) == 0))
            fn = np.sum((predictions_binary == 0) & (np.array(response_labels) == 1))
            
            sensitivity = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            specificity = tn / (tn + fp) if (tn + fp) > 0 else 0.0
            
            metrics["response_classification"] = {
                "roc_auc": float(roc_auc),
                "pr_auc": float(pr_auc),
                "sensitivity": float(sensitivity),
                "specificity": float(specificity),
                "optimal_threshold": float(optimal_threshold),
                "n_patients": len(response_scores),
                "n_events": sum(1 for l in response_labels if l == 0),  # Progressions
                "n_censored": sum(1 for l in response_labels if l == 1)  # Censored (good)
            }
            print(f"   ✅ Response Classification: AUC={roc_auc:.3f}, Sens={sensitivity:.3f}, Spec={specificity:.3f} (n={len(response_scores)})")
        except Exception as e:
            metrics["response_classification"] = {"error": str(e), "n_patients": len(response_scores)}
            print(f"   ⚠️  Response Classification: Error - {e}")
    else:
        metrics["response_classification"] = {"error": "Insufficient data", "n_patients": len(response_scores)}
        print(f"   ⚠️  Response Classification: Insufficient data (n={len(response_scores)})")
    
    return metrics


def compute_survival_analysis(
    predictions: List[Dict[str, Any]],
    patients: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Compute survival analysis (Kaplan-Meier, Cox regression)."""
    if not HAS_LIFELINES:
        return {"error": "lifelines not available - install with: pip install lifelines"}
    
    print(f"\n📊 Computing survival analysis...")
    
    # Create patient lookup
    patient_lookup = {p.get("patient_id"): p for p in patients}
    
    # Prepare data for survival analysis
    survival_data = []
    
    for pred in predictions:
        patient_id = pred.get("patient_id")
        patient = patient_lookup.get(patient_id)
        
        if not patient:
            continue
        
        outcomes = patient.get("clinical_outcomes", {})
        efficacy_score = pred.get("top_drug", {}).get("efficacy_score", 0.0)
        
        # PFS data
        pfs_months = outcomes.get("PFS_MONTHS")
        pfs_status = outcomes.get("PFS_STATUS", "")
        pfs_event = 1 if ("1:PROGRESSION" in pfs_status or "1:" in pfs_status) else 0
        
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
        return {"error": f"Insufficient data for survival analysis (n={len(survival_data)})"}
    
    df = pd.DataFrame(survival_data)
    
    # Create efficacy score quartiles
    df["efficacy_quartile"] = pd.qcut(df["efficacy_score"], q=4, labels=["Q1", "Q2", "Q3", "Q4"])
    
    metrics = {}
    
    # PFS Survival Analysis
    try:
        # Kaplan-Meier by quartile
        kmf_q1 = KaplanMeierFitter()
        kmf_q4 = KaplanMeierFitter()
        
        q1_data = df[df["efficacy_quartile"] == "Q1"]
        q4_data = df[df["efficacy_quartile"] == "Q4"]
        
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
            "q1_median_pfs": float(kmf_q1.median_survival_time_) if hasattr(kmf_q1, 'median_survival_time_') else None,
            "q4_median_pfs": float(kmf_q4.median_survival_time_) if hasattr(kmf_q4, 'median_survival_time_') else None,
            "n_patients": len(df)
        }
        print(f"   ✅ PFS Survival: HR={hr:.3f}, p={hr_p_value:.4f} (n={len(df)})")
    except Exception as e:
        metrics["pfs_survival"] = {"error": str(e), "n_patients": len(df)}
        print(f"   ⚠️  PFS Survival: Error - {e}")
    
    # OS Survival Analysis
    try:
        # Kaplan-Meier by quartile
        kmf_q1_os = KaplanMeierFitter()
        kmf_q4_os = KaplanMeierFitter()
        
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
            "q1_median_os": float(kmf_q1_os.median_survival_time_) if hasattr(kmf_q1_os, 'median_survival_time_') else None,
            "q4_median_os": float(kmf_q4_os.median_survival_time_) if hasattr(kmf_q4_os, 'median_survival_time_') else None,
            "n_patients": len(df)
        }
        print(f"   ✅ OS Survival: HR={hr_os:.3f}, p={hr_os_p_value:.4f} (n={len(df)})")
    except Exception as e:
        metrics["os_survival"] = {"error": str(e), "n_patients": len(df)}
        print(f"   ⚠️  OS Survival: Error - {e}")
    
    return metrics


def compute_drug_ranking_accuracy(
    predictions: List[Dict[str, Any]],
    patients: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Compute drug ranking accuracy (did we rank received drugs in top 3?)."""
    print(f"\n📊 Computing drug ranking accuracy...")
    
    # Create patient lookup
    patient_lookup = {p.get("patient_id"): p for p in patients}
    
    # Extract received treatments
    patients_with_treatments = []
    
    for pred in predictions:
        patient_id = pred.get("patient_id")
        patient = patient_lookup.get(patient_id)
        
        if not patient:
            continue
        
        treatments = patient.get("treatments", [])
        if not treatments:
            continue
        
        # Get treatment names
        received_drugs = set()
        for treatment in treatments:
            drug_name = treatment.get("treatment", "")
            if drug_name:
                # Normalize drug names (lowercase, remove common variations)
                drug_name_normalized = drug_name.lower().strip()
                received_drugs.add(drug_name_normalized)
        
        if received_drugs:
            # Get our drug rankings
            drug_rankings = pred.get("drug_rankings", [])
            our_drugs = [d.get("name", "").lower().strip() for d in drug_rankings]
            
            patients_with_treatments.append({
                "patient_id": patient_id,
                "received_drugs": received_drugs,
                "our_drugs": our_drugs,
            })
    
    if len(patients_with_treatments) < 10:
        return {"error": f"Insufficient data (n={len(patients_with_treatments)})"}
    
    # Compute accuracy metrics
    top_1_matches = 0
    top_3_matches = 0
    top_5_matches = 0
    
    for patient_data in patients_with_treatments:
        received = patient_data["received_drugs"]
        our_drugs = patient_data["our_drugs"]
        
        # Check if any received drug is in our top N
        if our_drugs and any(drug in received for drug in our_drugs[:1]):
            top_1_matches += 1
        if our_drugs and any(drug in received for drug in our_drugs[:3]):
            top_3_matches += 1
        if our_drugs and any(drug in received for drug in our_drugs[:5]):
            top_5_matches += 1
    
    n = len(patients_with_treatments)
    
    metrics = {
        "top_1_accuracy": top_1_matches / n if n > 0 else 0.0,
        "top_3_accuracy": top_3_matches / n if n > 0 else 0.0,
        "top_5_accuracy": top_5_matches / n if n > 0 else 0.0,
        "n_patients": n
    }
    
    print(f"   ✅ Drug Ranking: Top-1={metrics['top_1_accuracy']:.3f}, Top-3={metrics['top_3_accuracy']:.3f}, Top-5={metrics['top_5_accuracy']:.3f} (n={n})")
    
    return metrics


async def main():
    """Main benchmark function."""
    print("="*80)
    print("cBioPortal Clinical Trial Outcome Benchmark")
    print("="*80)
    
    # Load dataset
    patients = load_cbioportal_dataset()
    
    if len(patients) < 50:
        print(f"⚠️  Insufficient patients for benchmarking (n={len(patients)}, need ≥50)")
        return
    
    # Run predictions
    predictions = await run_benchmark(patients, max_concurrent=5)
    
    if len(predictions) < 50:
        print(f"⚠️  Insufficient successful predictions (n={len(predictions)}, need ≥50)")
        return
    
    # Compute metrics
    correlation_metrics = compute_correlation_metrics(predictions, patients)
    survival_metrics = compute_survival_analysis(predictions, patients)
    ranking_metrics = compute_drug_ranking_accuracy(predictions, patients)
    
    # Combine results
    timestamp = datetime.now().isoformat()
    output = {
        "timestamp": timestamp,
        "benchmark_type": "clinical_trial_outcomes_cbioportal",
        "study_id": "ov_tcga_pan_can_atlas_2018",
        "metrics": {
            **correlation_metrics,
            **survival_metrics,
            "drug_ranking_accuracy": ranking_metrics
        },
        "targets": {
            "pfs_correlation": {"min_pearson_r": 0.50},
            "os_correlation": {"min_pearson_r": 0.45},
            "response_classification": {"min_roc_auc": 0.65},
            "pfs_survival": {"min_hr": 1.3},
            "os_survival": {"min_hr": 1.3},
            "drug_ranking_accuracy": {"min_top_3": 0.70}
        },
        "results": [
            {
                "patient_id": pred.get("patient_id"),
                "top_drug": pred.get("top_drug", {}),
                "actual_outcomes": next(
                    (p.get("clinical_outcomes", {}) for p in patients if p.get("patient_id") == pred.get("patient_id")),
                    {}
                )
            }
            for pred in predictions[:20]  # Sample of 20 results
        ],
        "provenance": {
            "script": "benchmark_clinical_trial_outcomes_cbioportal.py",
            "dataset_source": "cbioportal",
            "study_id": "ov_tcga_pan_can_atlas_2018",
            "api_base": API_ROOT,
            "model_id": "evo2_1b",
            "n_patients": len(predictions),
            "n_eligible": len(patients)
        }
    }
    
    # Save results
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = OUTPUT_DIR / f"cbioportal_benchmark_results_{timestamp_str}.json"
    
    print(f"\n💾 Saving results to {output_file}...")
    with open(output_file, "w") as f:
        json.dump(output, f, indent=2, default=str)
    
    print(f"✅ Benchmark complete!")
    print(f"\n📊 Summary:")
    print(f"   Patients processed: {len(predictions)}")
    print(f"   PFS correlation: {correlation_metrics.get('pfs_correlation', {}).get('pearson_r', 'N/A')}")
    print(f"   OS correlation: {correlation_metrics.get('os_correlation', {}).get('pearson_r', 'N/A')}")
    print(f"   Response AUC: {correlation_metrics.get('response_classification', {}).get('roc_auc', 'N/A')}")
    
    # Also save latest
    latest_file = OUTPUT_DIR / "cbioportal_benchmark_results_latest.json"
    with open(latest_file, "w") as f:
        json.dump(output, f, indent=2, default=str)
    print(f"   Also saved as: {latest_file}")


if __name__ == "__main__":
    asyncio.run(main())

