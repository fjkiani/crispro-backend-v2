#!/usr/bin/env python3
"""
Small-scale benchmark test with checkpoint/resume and incremental expansion.

Usage:
  python3 benchmark_small_test.py                    # Run 50-patient test
  python3 benchmark_small_test.py --patients 100     # Run 100-patient test
  python3 benchmark_small_test.py --resume           # Resume from specific checkpoint
  python3 benchmark_small_test.py --patients 409 --continue  # Continue from largest checkpoint (50→409)
  
Checkpoint Features:
  - Automatic checkpoint saving after each run
  - Resume from specific checkpoint with --resume
  - Incremental expansion with --continue (finds largest checkpoint, continues from there)
  - No duplicate API calls when expanding (50 → 100 → 200 → 409)
"""

import sys
import json
import asyncio
import argparse
from pathlib import Path
from datetime import datetime

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent
BENCHMARK_DIR = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT / "oncology-coPilot" / "oncology-backend-minimal"))
sys.path.insert(0, str(BENCHMARK_DIR))

# Import what we need
import httpx
import numpy as np
from scipy import stats
from sklearn.metrics import roc_auc_score

# Import modular functions
from benchmark_common.metrics.drug_ranking import compute_drug_ranking_accuracy

# Define OUTPUT_DIR
OUTPUT_DIR = PROJECT_ROOT / "data" / "benchmarks"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def load_cbioportal_dataset(dataset_file: str = None) -> list:
    """Load cBioPortal dataset."""
    if dataset_file is None:
        dataset_file = OUTPUT_DIR / "cbioportal_trial_datasets_latest.json"
    
    with open(dataset_file, 'r') as f:
        data = json.load(f)
    
    # Data is a list of study objects
    patients = []
    if isinstance(data, list):
        # List of studies
        for study in data:
            for patient in study.get("patients", []):
                # Must have mutations (non-empty list), PFS, and OS
                mutations = patient.get("mutations", [])
                outcomes = patient.get("clinical_outcomes") or patient.get("outcomes", {})
                if (mutations and len(mutations) > 0 and  # Must have at least 1 mutation
                    outcomes.get("PFS_MONTHS") is not None and
                    outcomes.get("OS_MONTHS") is not None):
                    patients.append(patient)
    elif isinstance(data, dict):
        # Dict of studies
        for study_data in data.values():
            for patient in study_data.get("patients", []):
                mutations = patient.get("mutations", [])
                outcomes = patient.get("clinical_outcomes") or patient.get("outcomes", {})
                if (mutations and len(mutations) > 0 and  # Must have at least 1 mutation
                    outcomes.get("PFS_MONTHS") is not None and
                    outcomes.get("OS_MONTHS") is not None):
                    patients.append(patient)
    
    return patients


async def predict_patient_efficacy(patient: dict, client: httpx.AsyncClient, api_root: str) -> dict:
    """Predict efficacy for one patient."""
    try:
        # GRCh37 chromosome lengths (cBioPortal TCGA data uses GRCh37)
        CHROM_LENGTHS = {
            "1": 249250621, "2": 243199373, "3": 198022430, "4": 191154276,
            "5": 180915260, "6": 171115067, "7": 159138663, "8": 146364022,
            "9": 141213431, "10": 135534747, "11": 135006516, "12": 133851895,
            "13": 115169878, "14": 107349540, "15": 102531392, "16": 90354753,
            "17": 81195210, "18": 78077248, "19": 59128983, "20": 63025520,
            "21": 48129895, "22": 51304566, "X": 155270560, "Y": 59373566, "MT": 16569
        }
        
        # Convert mutations to API format
        mutations = []
        for mut in patient.get("mutations", []):
            # Handle both cBioPortal format (chromosome, position) and standard format (chrom, pos)
            chrom = mut.get("chrom") or mut.get("chromosome", "")
            pos = mut.get("pos") or mut.get("position", 0)
            hgvs_p = mut.get("hgvs_p") or mut.get("protein_change", "")
            
            # Skip if missing critical fields
            if not chrom or not pos or not mut.get("gene"):
                continue
            
            # Normalize chromosome
            chrom = str(chrom).replace("chr", "").replace("CHR", "").strip()
            
            # Map chromosome 23 → X (cBioPortal uses 23 for X chromosome)
            if chrom == "23":
                chrom = "X"
            
            # Validate chromosome
            valid_chroms = set([str(i) for i in range(1, 23)] + ["X", "Y", "MT", "M"])
            if chrom not in valid_chroms:
                continue  # Skip invalid chromosomes
            
            # Validate coordinates are within chromosome bounds
            if chrom in CHROM_LENGTHS:
                max_pos = CHROM_LENGTHS[chrom]
                if int(pos) > max_pos:
                    continue  # Skip out-of-bounds coordinates
            
            mutations.append({
                "gene": mut.get("gene"),
                "hgvs_p": hgvs_p,
                "chrom": chrom,
                "pos": int(pos),
                "ref": mut.get("ref", ""),
                "alt": mut.get("alt", ""),
                "build": "GRCh37"
            })
        
        # Skip if no valid mutations after filtering
        if not mutations:
            return {
                "patient_id": patient.get("patient_id"),
                "error": "No valid mutations after filtering (chromosome/coordinate validation)"
            }
        
        # Build tumor_context from patient data
        from benchmark_common.utils.biomarker_extractor import build_tumor_context
        tumor_context = build_tumor_context(patient)
        
        # API request
        response = await client.post(
            f"{api_root}/api/efficacy/predict",
            json={
                "model_id": "evo2_1b",
                "mutations": mutations,
                "disease": "ovarian_cancer",
                "tumor_context": tumor_context,  # NEW: Pass tumor context for sporadic gates
                "options": {"adaptive": True}
            },
            timeout=300.0  # Increased to 5 minutes (was 120s)
        )
        
        if response.status_code != 200:
            return {"patient_id": patient.get("patient_id"), "error": f"API error {response.status_code}"}
        
        data = response.json()
        top_drug = data.get("drugs", [{}])[0] if data.get("drugs") else {}
        
        return {
            "patient_id": patient.get("patient_id"),
            "efficacy_score": top_drug.get("efficacy_score", 0.0),
            "top_drug": top_drug.get("name", ""),
            "confidence": top_drug.get("confidence", 0.0),
            "all_drugs": [d.get("name") for d in data.get("drugs", [])[:5]],
            "api_response": data  # NEW: Store full response for pathway analysis
        }
    
    except Exception as e:
        import traceback
        error_msg = str(e) if str(e) else f"Unknown error: {type(e).__name__}"
        return {"patient_id": patient.get("patient_id"), "error": error_msg}


async def run_benchmark(patients: list, max_concurrent: int = 5) -> list:
    """Run benchmark for all patients."""
    api_root = "http://127.0.0.1:8000"
    
    async with httpx.AsyncClient(timeout=300.0) as client:  # Increased to 5 minutes (was 120s)
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def bounded_predict(patient):
            async with semaphore:
                return await predict_patient_efficacy(patient, client, api_root)
        
        tasks = [bounded_predict(p) for p in patients]
        predictions = await asyncio.gather(*tasks)
    
    return predictions


def compute_correlation_metrics(predictions: list, patients: list) -> dict:
    """Compute correlation between predicted scores and actual outcomes."""
    patient_lookup = {p.get("patient_id"): p for p in patients}
    
    pfs_scores, pfs_months = [], []
    os_scores, os_months = [], []
    
    for pred in predictions:
        if "error" in pred:
            continue
        
        patient_id = pred.get("patient_id")
        patient = patient_lookup.get(patient_id)
        if not patient:
            continue
        
        efficacy_score = pred.get("efficacy_score", 0.0)
        outcomes = patient.get("clinical_outcomes") or patient.get("outcomes", {})
        
        # PFS data
        pfs = outcomes.get("PFS_MONTHS")
        if pfs is not None:
            pfs_scores.append(efficacy_score)
            pfs_months.append(float(pfs))
        
        # OS data
        os = outcomes.get("OS_MONTHS")
        if os is not None:
            os_scores.append(efficacy_score)
            os_months.append(float(os))
    
    metrics = {}
    
    # PFS Correlation (with NaN/Inf filtering)
    if len(pfs_scores) >= 10:
        pfs_valid_mask = ~(np.isnan(pfs_scores) | np.isinf(pfs_scores) | np.isnan(pfs_months) | np.isinf(pfs_months))
        pfs_scores_clean = np.array(pfs_scores)[pfs_valid_mask]
        pfs_months_clean = np.array(pfs_months)[pfs_valid_mask]
        
        if len(pfs_scores_clean) >= 10:
            pfs_pearson = stats.pearsonr(pfs_scores_clean, pfs_months_clean)
            pfs_spearman = stats.spearmanr(pfs_scores_clean, pfs_months_clean)
            metrics["pfs_correlation"] = {
                "pearson_r": float(pfs_pearson[0]),
                "pearson_p_value": float(pfs_pearson[1]),
                "spearman_rho": float(pfs_spearman[0]),
                "spearman_p_value": float(pfs_spearman[1]),
                "n_patients": len(pfs_scores_clean)
            }
        else:
            metrics["pfs_correlation"] = {"error": "Insufficient valid data after filtering"}
    else:
        metrics["pfs_correlation"] = {"error": "Insufficient data"}
    
    # OS Correlation (with NaN/Inf filtering)
    if len(os_scores) >= 10:
        os_valid_mask = ~(np.isnan(os_scores) | np.isinf(os_scores) | np.isnan(os_months) | np.isinf(os_months))
        os_scores_clean = np.array(os_scores)[os_valid_mask]
        os_months_clean = np.array(os_months)[os_valid_mask]
        
        if len(os_scores_clean) >= 10:
            os_pearson = stats.pearsonr(os_scores_clean, os_months_clean)
            os_spearman = stats.spearmanr(os_scores_clean, os_months_clean)
            metrics["os_correlation"] = {
                "pearson_r": float(os_pearson[0]),
                "pearson_p_value": float(os_pearson[1]),
                "spearman_rho": float(os_spearman[0]),
                "spearman_p_value": float(os_spearman[1]),
                "n_patients": len(os_scores_clean)
            }
        else:
            metrics["os_correlation"] = {"error": "Insufficient valid data after filtering"}
    else:
        metrics["os_correlation"] = {"error": "Insufficient data"}
    
    return metrics


def compute_classification_metrics(predictions: list, patients: list) -> dict:
    """Compute classification metrics (AUC for progression prediction)."""
    patient_lookup = {p.get("patient_id"): p for p in patients}
    
    response_labels, response_scores = [], []
    
    for pred in predictions:
        if "error" in pred:
            continue
        
        patient_id = pred.get("patient_id")
        patient = patient_lookup.get(patient_id)
        if not patient:
            continue
        
        efficacy_score = pred.get("efficacy_score", 0.0)
        outcomes = patient.get("clinical_outcomes") or patient.get("outcomes", {})
        pfs_status = outcomes.get("PFS_STATUS", "")
        
        # Use parser to handle all formats
        from benchmark_common.utils.pfs_status_parser import parse_pfs_status
        event, status = parse_pfs_status(pfs_status)
        
        if event is not None:
            # event=0 means censored (good, no progression)
            # event=1 means progressed (poor, progression occurred)
            # For classification: 1 = good (no progression), 0 = poor (progression)
            response_labels.append(1 - event)  # Invert: 0→1 (good), 1→0 (poor)
            response_scores.append(efficacy_score)
    
    if len(response_labels) >= 10:
        try:
            auc = roc_auc_score(response_labels, response_scores)
            return {"auc": float(auc), "n_patients": len(response_labels)}
        except:
            return {"error": "AUC computation failed"}
    else:
        return {"error": "Insufficient data"}


# compute_drug_ranking_accuracy is now imported from benchmark_common.metrics.drug_ranking
# This ensures consistent handling of treatment data (list vs dict formats)


def compute_survival_analysis(predictions: list, patients: list) -> dict:
    """Placeholder for survival analysis (requires lifelines)."""
    return {"error": "lifelines not available"}

def find_largest_checkpoint(output_dir: Path):
    """Find the largest checkpoint file and load it."""
    checkpoints = list(output_dir.glob("checkpoint_*patients.json"))
    if not checkpoints:
        return None, None, 0
    
    # Extract patient count from filename and find largest
    largest_checkpoint = None
    largest_n = 0
    
    for cp in checkpoints:
        try:
            # Extract number from "checkpoint_Npatients.json"
            n_str = cp.stem.replace("checkpoint_", "").replace("patients", "")
            n = int(n_str)
            if n > largest_n:
                largest_n = n
                largest_checkpoint = cp
        except:
            continue
    
    if largest_checkpoint and largest_checkpoint.exists():
        try:
            with open(largest_checkpoint, 'r') as f:
                checkpoint_data = json.load(f)
                return largest_checkpoint, checkpoint_data, largest_n
        except Exception as e:
            print(f"   ⚠️  Failed to load checkpoint {largest_checkpoint.name}: {e}")
    
    return None, None, 0


async def small_test_benchmark(
    max_patients: int = 5,  # Changed default: 50 → 5 for validation
    use_checkpoint: bool = True,
    checkpoint_file: Path = None,
    continue_from_checkpoint: bool = False
):
    """Run small-scale benchmark with checkpoint/resume.
    
    Args:
        max_patients: Maximum number of patients to process
        use_checkpoint: Whether to save checkpoints
        checkpoint_file: Specific checkpoint file to use (if None, auto-detect)
        continue_from_checkpoint: If True, find largest checkpoint and continue from there
    """
    
    print("="*80)
    print(f"Small-Scale cBioPortal Benchmark (n={max_patients})")
    print("="*80)
    
    # Load dataset
    all_patients = load_cbioportal_dataset()
    
    # Checkpoint setup
    if checkpoint_file is None:
        checkpoint_file = OUTPUT_DIR / f"checkpoint_{max_patients}patients.json"
    
    # Try to find and load existing checkpoint
    existing_predictions = []
    existing_patient_ids = set()
    start_index = 0
    
    if use_checkpoint:
        if continue_from_checkpoint:
            # Find largest checkpoint and continue from there
            print(f"\n🔍 Looking for existing checkpoints...")
            cp_file, cp_data, cp_n = find_largest_checkpoint(OUTPUT_DIR)
            
            if cp_file and cp_data:
                existing_predictions = cp_data.get("predictions", [])
                existing_patient_ids = {p.get("patient_id") for p in existing_predictions if "error" not in p}
                start_index = cp_n
                
                print(f"   ✅ Found checkpoint: {cp_file.name}")
                print(f"   📊 Already processed: {len(existing_predictions)} patients")
                print(f"   🚀 Will continue from patient {start_index + 1}")
            else:
                print(f"   ℹ️  No existing checkpoint found, starting fresh")
        else:
            # Use specific checkpoint file
            if checkpoint_file.exists():
                print(f"\n♻️  Loading checkpoint: {checkpoint_file.name}")
                try:
                    with open(checkpoint_file, 'r') as f:
                        cp_data = json.load(f)
                        existing_predictions = cp_data.get("predictions", [])
                        existing_patient_ids = {p.get("patient_id") for p in existing_predictions if "error" not in p}
                        start_index = len(existing_predictions)
                        print(f"   ✅ Loaded {len(existing_predictions)} predictions")
                except Exception as e:
                    print(f"   ❌ Checkpoint load failed: {e}")
                    existing_predictions = []
    
    # Determine which patients to process
    # For validation: Use patients with LOWEST mutation counts (safest)
    # Extend validation mode to 10, 20, 50 patients for incremental testing
    validation_mode = (max_patients in [5, 10, 20, 50] and start_index == 0)
    
    if validation_mode:
        # Sort by mutation count, take lowest N
        patients_with_counts = [(p, len(p.get('mutations', []))) for p in all_patients]
        patients_with_counts = [(p, c) for p, c in patients_with_counts if c > 0]  # Exclude 0 mutations
        patients_with_counts.sort(key=lambda x: x[1])
        patients_to_process = [p for p, _ in patients_with_counts[:max_patients]]
        
        print(f"\n🎯 VALIDATION MODE: Using {max_patients} patients with LOWEST mutation counts")
        for i, p in enumerate(patients_to_process, 1):
            mut_count = len(p.get('mutations', []))
            print(f"   {i}. {p.get('patient_id')}: {mut_count} mutations")
    else:
        # If continuing, skip already processed patients
        if start_index > 0 and start_index < max_patients:
            patients_to_process = all_patients[start_index:max_patients]
            print(f"\n📋 Processing patients {start_index + 1} to {max_patients}")
        else:
            patients_to_process = all_patients[:max_patients]
            print(f"\n📋 Processing patients 1 to {max_patients}")
    
    print(f"   Total eligible: {len(all_patients)} patients")
    print(f"   This run: {len(patients_to_process)} patients")
    
    # Pre-flight validation: Calculate expected time
    total_mutations = sum(len(p.get('mutations', [])) for p in patients_to_process)
    avg_mutations = total_mutations / len(patients_to_process) if patients_to_process else 0
    expected_time_per_patient = avg_mutations + 25  # 1s per mutation + 25s overhead
    max_expected_time = max(len(p.get('mutations', [])) + 25 for p in patients_to_process) if patients_to_process else 0
    
    print(f"\n⏱️  PRE-FLIGHT TIME VALIDATION:")
    print(f"   Total mutations: {total_mutations}")
    print(f"   Avg mutations/patient: {avg_mutations:.1f}")
    print(f"   Expected time/patient: {expected_time_per_patient:.1f}s")
    print(f"   Max expected time: {max_expected_time:.1f}s")
    print(f"   Timeout: 300s")
    
    if max_expected_time > 300:
        print(f"   ⚠️  WARNING: Max expected time ({max_expected_time:.1f}s) exceeds timeout (300s)")
        print(f"   ⚠️  Some patients may timeout. Consider increasing timeout or reducing mutations.")
    else:
        print(f"   ✅ All patients should complete within timeout")
    
    # Run predictions for new patients
    new_predictions = []
    if len(patients_to_process) > 0:
        print(f"\n🔬 Running {len(patients_to_process)} API predictions...")
        
        new_predictions = await run_benchmark(patients_to_process, max_concurrent=2)  # Reduced concurrency
        
        successful = sum(1 for p in new_predictions if "error" not in p)
        errors = len(new_predictions) - successful
        
        print(f"   ✅ Completed: {successful} successful, {errors} errors")
    
    # Combine existing and new predictions
    all_predictions = existing_predictions + new_predictions
    
    # For metrics computation: use actual patients that were processed
    # Create lookup from patient_id to full patient data
    patient_lookup = {p.get("patient_id"): p for p in all_patients}
    # Get the actual patients that were processed (from predictions)
    processed_patient_ids = {p.get("patient_id") for p in all_predictions if "error" not in p}
    patients = [patient_lookup[pid] for pid in processed_patient_ids if pid in patient_lookup]
    
    print(f"\n📊 Total predictions: {len(all_predictions)}/{max_patients}")
    
    # SAVE CHECKPOINT IMMEDIATELY
    if use_checkpoint and len(new_predictions) > 0:
        print(f"\n💾 Saving checkpoint...")
        try:
            total_successful = sum(1 for p in all_predictions if "error" not in p)
            total_errors = len(all_predictions) - total_successful
            
            checkpoint_data = {
                "predictions": all_predictions,
                "n_patients": len(all_predictions),
                "timestamp": datetime.now().isoformat(),
                "successful": total_successful,
                "errors": total_errors,
                "continued_from": start_index if start_index > 0 else None
            }
            with open(checkpoint_file, 'w') as f:
                json.dump(checkpoint_data, f, indent=2)
            print(f"   ✅ Checkpoint saved: {checkpoint_file.name}")
            print(f"   📦 Size: {checkpoint_file.stat().st_size / 1024:.1f} KB")
        except Exception as e:
            print(f"   ❌ Checkpoint save failed: {e}")
    
    # Use all_predictions for metrics
    predictions = all_predictions
    
    # Compute metrics
    print(f"\n📊 Computing metrics...")
    
    try:
        correlation_metrics = compute_correlation_metrics(predictions, patients)
    except Exception as e:
        print(f"   ❌ Correlation metrics failed: {e}")
        correlation_metrics = {"error": str(e)}
    
    try:
        classification_metrics = compute_classification_metrics(predictions, patients)
    except Exception as e:
        print(f"   ❌ Classification metrics failed: {e}")
        classification_metrics = {"error": str(e)}
    
    try:
        drug_ranking_metrics = compute_drug_ranking_accuracy(predictions, patients)
    except Exception as e:
        print(f"   ❌ Drug ranking metrics failed: {e}")
        drug_ranking_metrics = {"error": str(e)}
    
    try:
        survival_metrics = compute_survival_analysis(predictions, patients)
    except Exception as e:
        print(f"   ⚠️  Survival metrics failed: {e}")
        survival_metrics = {"error": str(e)}
    
    # Compile results
    results = {
        "benchmark_info": {
            "test_name": f"small_test_{max_patients}patients",
            "n_patients": len(patients),
            "timestamp": datetime.now().isoformat(),
            "checkpoint_used": use_checkpoint,
            "checkpoint_file": str(checkpoint_file) if use_checkpoint else None
        },
        "metrics": {
            "correlation": correlation_metrics,
            "classification": classification_metrics,
            "drug_ranking": drug_ranking_metrics,
            "survival": survival_metrics
        },
        "predictions": predictions  # Save for analysis
    }
    
    # Save final results
    output_file = OUTPUT_DIR / f"benchmark_small_{max_patients}patients_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    print(f"\n💾 Saving final results...")
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"   ✅ Results saved: {output_file.name}")
    print(f"   📦 Size: {output_file.stat().st_size / 1024:.1f} KB")
    
    # Print summary
    print(f"\n" + "="*80)
    print(f"BENCHMARK COMPLETE")
    print(f"="*80)
    print(f"Patients: {len(patients)}")
    
    if "error" not in correlation_metrics:
        pfs_corr = correlation_metrics.get("pfs_correlation", {})
        if "error" not in pfs_corr:
            print(f"PFS Correlation: r={pfs_corr.get('pearson_r', 0):.3f} (p={pfs_corr.get('pearson_p_value', 1):.4f})")
    
    if "error" not in classification_metrics:
        print(f"PFS Classification: AUC={classification_metrics.get('auc', 0):.3f}")
    
    if "error" not in drug_ranking_metrics:
        print(f"Drug Ranking: Top-3={drug_ranking_metrics.get('top_3_accuracy', 0):.3f}")
    
    print(f"="*80)
    
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Small-scale benchmark with checkpoints")
    parser.add_argument("--patients", type=int, default=5, help="Number of patients (default: 5 for validation)")
    parser.add_argument("--resume", action="store_true", help="Resume from specific checkpoint file")
    parser.add_argument("--continue", action="store_true", dest="continue_from_checkpoint", help="Continue from largest existing checkpoint (for expanding 50→409)")
    parser.add_argument("--no-checkpoint", action="store_true", help="Disable checkpoints")
    
    args = parser.parse_args()
    
    # Run benchmark
    asyncio.run(small_test_benchmark(
        max_patients=args.patients,
        use_checkpoint=not args.no_checkpoint,
        continue_from_checkpoint=args.continue_from_checkpoint
    ))

