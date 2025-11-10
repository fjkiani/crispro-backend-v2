#!/usr/bin/env python3
"""
Run HRD baseline experiments and ablations.
Extracts TCGA-OV cohort, runs S/P/E ablations, computes AUROC/AUPRC.
"""
import asyncio
import json
import sys
from pathlib import Path
from typing import List, Dict, Any

import httpx

API_ROOT = "http://127.0.0.1:8000"

async def extract_hrd_cohort(limit=500):
    """Extract HRD cohort from TCGA-OV with real clinical outcomes."""
    print(f"Extracting HRD cohort (limit={limit})...")
    async with httpx.AsyncClient(timeout=300.0) as client:
        resp = await client.post(
            f"{API_ROOT}/api/datasets/extract_hrd_cohort",
            json={
                "study_id": "ov_tcga",
                "genes": ["BRCA1", "BRCA2", "TP53", "PTEN", "ATM"],  # Focus on known HRD genes
                "limit": limit,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        rows = data.get("rows", [])
        positives = sum(1 for r in rows if r.get("outcome_platinum") == 1)
        print(f"✓ Extracted {len(rows)} variant-level rows")
        print(f"  Variant-level positives: {positives} ({positives/len(rows)*100:.1f}%)")
        return rows

async def predict_variant_efficacy(client, variant, ablation_mode="baseline", enable_fusion=False):
    """Call /api/efficacy/predict for a single variant."""
    try:
        # Map ablation mode to options
        options = {
            "adaptive": ablation_mode in ["richer_s", "SPE"],
            "ensemble": ablation_mode == "SPE",
            "enable_fusion": enable_fusion,
        }
        
        payload = {
            "model_id": "evo2_1b",
            "mutations": [{
                "gene": variant.get("gene"),
                "hgvs_p": variant.get("hgvs_p"),
                "chrom": str(variant.get("chrom", "")),
                "pos": variant.get("pos", 0),
                "ref": variant.get("ref", ""),
                "alt": variant.get("alt", ""),
            }],
            "options": options,
            "api_base": API_ROOT,
        }
        
        resp = await client.post(
            f"{API_ROOT}/api/efficacy/predict",
            json=payload,
            timeout=60.0,  # Increased timeout
        )
        
        if resp.status_code >= 400:
            error_text = resp.text[:100] if resp.text else f"HTTP {resp.status_code}"
            print(f"    ✗ {variant.get('gene')} {variant.get('hgvs_p')}: HTTP {resp.status_code}")
            return None
        
        data = resp.json()
        drugs = data.get("drugs", [])
        
        # Use average confidence across drugs as the prediction score
        # Accept even low confidence (> 0) for now to get predictions
        if drugs:
            avg_confidence = sum(d.get("confidence", 0) for d in drugs) / len(drugs)
            return avg_confidence if avg_confidence > 0 else None
        return None
        
    except httpx.TimeoutException as e:
        print(f"    ✗ {variant.get('gene')} {variant.get('hgvs_p')}: TIMEOUT")
        return None
    except Exception as e:
        error_msg = str(e) if str(e) else type(e).__name__
        print(f"    ✗ {variant.get('gene')} {variant.get('hgvs_p')}: {error_msg[:80]}")
        return None

def aggregate_patient_variants(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Aggregate variants by patient_id for patient-level prediction."""
    from collections import defaultdict
    
    patient_data = defaultdict(lambda: {"variants": [], "outcome": None, "patient_id": None})
    
    for row in rows:
        pid = row.get("patient_id")
        if not pid:
            continue
        
        patient_data[pid]["variants"].append(row)
        patient_data[pid]["outcome"] = row.get("outcome_platinum", 0)
        patient_data[pid]["patient_id"] = pid
    
    # Convert to list of patient-level records
    patient_rows = []
    for pid, data in patient_data.items():
        patient_rows.append({
            "patient_id": pid,
            "variants": data["variants"],
            "outcome_platinum": data["outcome"],
            "n_variants": len(data["variants"])
        })
    
    return patient_rows

async def run_ablation(rows: List[Dict[str, Any]], ablation_mode: str, profile="baseline", enable_fusion=False):
    """Run efficacy prediction with specific ablation mode and compute AUROC/AUPRC at PATIENT level."""
    fusion_label = "+Fusion" if enable_fusion else ""
    print(f"\nRunning ablation: {ablation_mode} (profile={profile}{fusion_label})...")
    
    # Aggregate variants by patient
    patient_rows = aggregate_patient_variants(rows)
    print(f"  Aggregated {len(rows)} variants → {len(patient_rows)} patients")
    
    # Collect predictions and ground truth labels at PATIENT level
    y_true = []
    y_pred = []
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        # Process patients in batches
        batch_size = 5
        for i in range(0, len(patient_rows), batch_size):
            batch = patient_rows[i:i+batch_size]
            print(f"  Patient batch {i//batch_size + 1}/{(len(patient_rows) + batch_size - 1)//batch_size}...", end=" ", flush=True)
            
            # For each patient, predict all variants and aggregate scores
            for patient in batch:
                patient_variants = patient["variants"]
                patient_outcome = patient["outcome_platinum"]
                
                # Predict for all patient variants
                tasks = [predict_variant_efficacy(client, var, ablation_mode, enable_fusion=enable_fusion) for var in patient_variants]
                predictions = await asyncio.gather(*tasks)
                
                # Aggregate: use MAX confidence across all variants as patient-level score
                valid_preds = [p for p in predictions if p is not None]
                if valid_preds:
                    patient_score = max(valid_preds)  # Max disruption across all variants
                    y_true.append(patient_outcome)
                    y_pred.append(patient_score)
            
            succeeded = sum(1 for p in batch if p.get("patient_id") in [pt["patient_id"] for pt in patient_rows[:i+len(batch)] if pt["patient_id"]])
            print(f"✓ {len(batch)} patients processed")
    
    print(f"  Total patient predictions: {len(y_pred)}/{len(patient_rows)}")
    
    # Compute metrics using sklearn
    if len(y_pred) >= 10:
        try:
            from sklearn.metrics import roc_auc_score, average_precision_score
            
            auroc = roc_auc_score(y_true, y_pred)
            auprc = average_precision_score(y_true, y_pred)
            
            print(f"  ✓ AUROC: {auroc:.3f}")
            print(f"  ✓ AUPRC: {auprc:.3f}")
            
            return {
            "ablation_mode": ablation_mode,
            "profile": profile,
            "enable_fusion": enable_fusion,
            "n_variants": len(rows),
            "n_predictions": len(y_pred),
            "auroc": auroc,
            "auprc": auprc,
            "positives": sum(y_true),
            "prevalence": sum(y_true) / len(y_true) if y_true else 0,
        }
        except Exception as e:
            print(f"  ✗ Metrics computation failed: {e}")
            return {
                "ablation_mode": ablation_mode,
                "profile": profile,
                "enable_fusion": enable_fusion,
                "n_variants": len(rows),
                "n_predictions": len(y_pred),
                "auroc": None,
                "auprc": None,
                "error": str(e),
            }
    else:
        print(f"  ✗ Insufficient predictions ({len(y_pred)}) or classes ({len(set(y_true))}) to compute metrics")
        return {
            "ablation_mode": ablation_mode,
            "profile": profile,
            "enable_fusion": enable_fusion,
            "n_variants": len(rows),
            "n_predictions": len(y_pred),
            "auroc": None,
            "auprc": None,
            "note": "Insufficient predictions or classes",
        }

async def main():
    """Run full HRD baseline experiment with real efficacy predictions."""
    print("=" * 60)
    print("HRD BASELINE EXPERIMENT (REAL PREDICTIONS)")
    print("=" * 60)
    
    # Step 1: Extract cohort with clinical outcomes
    rows = await extract_hrd_cohort(limit=100)  # Increased to 100 now that we have working pipeline
    
    if not rows:
        print("ERROR: No rows extracted")
        sys.exit(1)
    
    # Step 2: Run baseline ablation only (can expand to others later)
    print("\n" + "=" * 60)
    print("RUNNING ABLATIONS")
    print("=" * 60)
    
    results = {}
    
    # 1. Baseline (minimal features)
    print("\n[1/3] Baseline (delta-only, no adaptive)")
    baseline_metrics = await run_ablation(rows, "baseline", profile="baseline")
    results["baseline"] = baseline_metrics
    
    # 2. Richer S (adaptive + multi-window)
    print("\n[2/3] Richer S (adaptive scoring)")
    richer_s_metrics = await run_ablation(rows, "richer_s", profile="richer_s")
    results["richer_s"] = richer_s_metrics
    
    # 3. Full S+P+E (ensemble mode)
    print("\n[3/3] Full SPE (ensemble, all features)")
    spe_metrics = await run_ablation(rows, "SPE", profile="full")
    results["spe_full"] = spe_metrics
    
    # Step 3: Save results
    output_dir = Path(__file__).parent.parent / "results" / "hrd_baseline"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    output_file = output_dir / "baseline_results_real.json"
    
    # Compute cohort stats
    positives = sum(1 for r in rows if r.get("outcome_platinum") == 1)
    
    with open(output_file, "w") as f:
        json.dump({
            "cohort": {
                "study": "ov_tcga",
                "n_samples": len(rows),
                "positives": positives,
                "prevalence": positives / len(rows) if rows else 0,
            },
            "ablations": results,
        }, f, indent=2)
    
    print(f"\n✓ Results saved to: {output_file}")
    
    # Step 4: Print summary
    print("\n" + "=" * 60)
    print("SUMMARY - ABLATION COMPARISON (PATIENT-LEVEL)")
    print("=" * 60)
    n_patients = len(set(r.get("patient_id") for r in rows if r.get("patient_id")))
    patient_positives = len(set(r.get("patient_id") for r in rows if r.get("patient_id") and r.get("outcome_platinum") == 1))
    print(f"Cohort: {len(rows)} variants from {n_patients} patients")
    print(f"  Patients with poor outcome: {patient_positives}/{n_patients} ({patient_positives/n_patients*100:.1f}%)")
    print()
    print(f"{'Mode':<20} {'AUROC':<10} {'AUPRC':<10} {'Predictions':<12} {'Lift vs Baseline'}")
    print("-" * 80)
    
    baseline_auroc = results.get('baseline', {}).get('auroc')
    baseline_auprc = results.get('baseline', {}).get('auprc')
    
    for mode, metrics in results.items():
        auroc = metrics.get('auroc')
        auprc = metrics.get('auprc')
        n_pred = metrics.get('n_predictions', 0)
        
        auroc_str = f"{auroc:.3f}" if auroc is not None else "N/A"
        auprc_str = f"{auprc:.3f}" if auprc is not None else "N/A"
        
        # Calculate lift
        if auroc is not None and baseline_auroc is not None and mode != 'baseline':
            auroc_lift = auroc - baseline_auroc
            auprc_lift = auprc - baseline_auprc if auprc and baseline_auprc else 0
            lift_str = f"AUROC +{auroc_lift:.3f}, AUPRC +{auprc_lift:.3f}"
        else:
            lift_str = "-"
        
        print(f"{mode:<20} {auroc_str:<10} {auprc_str:<10} {n_pred:<12} {lift_str}")
    
    print("\n" + "=" * 60)
    print("ANALYSIS")
    print("=" * 60)
    
    if baseline_metrics.get('auroc') is not None:
        baseline_auroc = baseline_metrics['auroc']
        baseline_auprc = baseline_metrics['auprc']
        
        print(f"\n📊 Baseline Performance:")
        print(f"   AUROC: {baseline_auroc:.3f} ({'random' if baseline_auroc < 0.52 else 'above random'})")
        print(f"   AUPRC: {baseline_auprc:.3f} (prevalence={positives/len(rows):.3f})")
        
        # Check if we got improvements
        best_auroc = max(m.get('auroc', 0) for m in results.values() if m.get('auroc'))
        best_mode = [k for k, v in results.items() if v.get('auroc') == best_auroc][0]
        
        if best_auroc > baseline_auroc:
            lift = best_auroc - baseline_auroc
            print(f"\n🚀 Best Performance: {best_mode}")
            print(f"   AUROC: {best_auroc:.3f} (+{lift:.3f} improvement)")
            print(f"   Status: {'✅ Publishable' if best_auroc > 0.70 else '⚠️  Needs further tuning'}")
        else:
            print(f"\n⚠️  No improvement over baseline detected")
            print(f"   This suggests:")
            print(f"   - Features may need tuning")
            print(f"   - Evo service may need warmup")
            print(f"   - More samples needed for statistical power")
    else:
        print("\n⚠️  Metrics computation failed. Check logs above for errors.")
    
    print("\n📊 Next Steps:")
    print("  1. ✅ Ablations complete (baseline, richer_s, SPE)")
    print("  2. Scale to 200-500 samples for robust CIs")
    print("  3. Add Fusion Engine ablation (+AlphaMissense)")
    print("  4. Generate figures (ROC/PR curves)")
    print("  5. Bootstrap confidence intervals")

if __name__ == "__main__":
    asyncio.run(main())




Run HRD baseline experiments and ablations.
Extracts TCGA-OV cohort, runs S/P/E ablations, computes AUROC/AUPRC.
"""
import asyncio
import json
import sys
from pathlib import Path
from typing import List, Dict, Any

import httpx

API_ROOT = "http://127.0.0.1:8000"

async def extract_hrd_cohort(limit=500):
    """Extract HRD cohort from TCGA-OV with real clinical outcomes."""
    print(f"Extracting HRD cohort (limit={limit})...")
    async with httpx.AsyncClient(timeout=300.0) as client:
        resp = await client.post(
            f"{API_ROOT}/api/datasets/extract_hrd_cohort",
            json={
                "study_id": "ov_tcga",
                "genes": ["BRCA1", "BRCA2", "TP53", "PTEN", "ATM"],  # Focus on known HRD genes
                "limit": limit,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        rows = data.get("rows", [])
        positives = sum(1 for r in rows if r.get("outcome_platinum") == 1)
        print(f"✓ Extracted {len(rows)} variant-level rows")
        print(f"  Variant-level positives: {positives} ({positives/len(rows)*100:.1f}%)")
        return rows

async def predict_variant_efficacy(client, variant, ablation_mode="baseline", enable_fusion=False):
    """Call /api/efficacy/predict for a single variant."""
    try:
        # Map ablation mode to options
        options = {
            "adaptive": ablation_mode in ["richer_s", "SPE"],
            "ensemble": ablation_mode == "SPE",
            "enable_fusion": enable_fusion,
        }
        
        payload = {
            "model_id": "evo2_1b",
            "mutations": [{
                "gene": variant.get("gene"),
                "hgvs_p": variant.get("hgvs_p"),
                "chrom": str(variant.get("chrom", "")),
                "pos": variant.get("pos", 0),
                "ref": variant.get("ref", ""),
                "alt": variant.get("alt", ""),
            }],
            "options": options,
            "api_base": API_ROOT,
        }
        
        resp = await client.post(
            f"{API_ROOT}/api/efficacy/predict",
            json=payload,
            timeout=60.0,  # Increased timeout
        )
        
        if resp.status_code >= 400:
            error_text = resp.text[:100] if resp.text else f"HTTP {resp.status_code}"
            print(f"    ✗ {variant.get('gene')} {variant.get('hgvs_p')}: HTTP {resp.status_code}")
            return None
        
        data = resp.json()
        drugs = data.get("drugs", [])
        
        # Use average confidence across drugs as the prediction score
        # Accept even low confidence (> 0) for now to get predictions
        if drugs:
            avg_confidence = sum(d.get("confidence", 0) for d in drugs) / len(drugs)
            return avg_confidence if avg_confidence > 0 else None
        return None
        
    except httpx.TimeoutException as e:
        print(f"    ✗ {variant.get('gene')} {variant.get('hgvs_p')}: TIMEOUT")
        return None
    except Exception as e:
        error_msg = str(e) if str(e) else type(e).__name__
        print(f"    ✗ {variant.get('gene')} {variant.get('hgvs_p')}: {error_msg[:80]}")
        return None

def aggregate_patient_variants(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Aggregate variants by patient_id for patient-level prediction."""
    from collections import defaultdict
    
    patient_data = defaultdict(lambda: {"variants": [], "outcome": None, "patient_id": None})
    
    for row in rows:
        pid = row.get("patient_id")
        if not pid:
            continue
        
        patient_data[pid]["variants"].append(row)
        patient_data[pid]["outcome"] = row.get("outcome_platinum", 0)
        patient_data[pid]["patient_id"] = pid
    
    # Convert to list of patient-level records
    patient_rows = []
    for pid, data in patient_data.items():
        patient_rows.append({
            "patient_id": pid,
            "variants": data["variants"],
            "outcome_platinum": data["outcome"],
            "n_variants": len(data["variants"])
        })
    
    return patient_rows

async def run_ablation(rows: List[Dict[str, Any]], ablation_mode: str, profile="baseline", enable_fusion=False):
    """Run efficacy prediction with specific ablation mode and compute AUROC/AUPRC at PATIENT level."""
    fusion_label = "+Fusion" if enable_fusion else ""
    print(f"\nRunning ablation: {ablation_mode} (profile={profile}{fusion_label})...")
    
    # Aggregate variants by patient
    patient_rows = aggregate_patient_variants(rows)
    print(f"  Aggregated {len(rows)} variants → {len(patient_rows)} patients")
    
    # Collect predictions and ground truth labels at PATIENT level
    y_true = []
    y_pred = []
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        # Process patients in batches
        batch_size = 5
        for i in range(0, len(patient_rows), batch_size):
            batch = patient_rows[i:i+batch_size]
            print(f"  Patient batch {i//batch_size + 1}/{(len(patient_rows) + batch_size - 1)//batch_size}...", end=" ", flush=True)
            
            # For each patient, predict all variants and aggregate scores
            for patient in batch:
                patient_variants = patient["variants"]
                patient_outcome = patient["outcome_platinum"]
                
                # Predict for all patient variants
                tasks = [predict_variant_efficacy(client, var, ablation_mode, enable_fusion=enable_fusion) for var in patient_variants]
                predictions = await asyncio.gather(*tasks)
                
                # Aggregate: use MAX confidence across all variants as patient-level score
                valid_preds = [p for p in predictions if p is not None]
                if valid_preds:
                    patient_score = max(valid_preds)  # Max disruption across all variants
                    y_true.append(patient_outcome)
                    y_pred.append(patient_score)
            
            succeeded = sum(1 for p in batch if p.get("patient_id") in [pt["patient_id"] for pt in patient_rows[:i+len(batch)] if pt["patient_id"]])
            print(f"✓ {len(batch)} patients processed")
    
    print(f"  Total patient predictions: {len(y_pred)}/{len(patient_rows)}")
    
    # Compute metrics using sklearn
    if len(y_pred) >= 10:
        try:
            from sklearn.metrics import roc_auc_score, average_precision_score
            
            auroc = roc_auc_score(y_true, y_pred)
            auprc = average_precision_score(y_true, y_pred)
            
            print(f"  ✓ AUROC: {auroc:.3f}")
            print(f"  ✓ AUPRC: {auprc:.3f}")
            
            return {
            "ablation_mode": ablation_mode,
            "profile": profile,
            "enable_fusion": enable_fusion,
            "n_variants": len(rows),
            "n_predictions": len(y_pred),
            "auroc": auroc,
            "auprc": auprc,
            "positives": sum(y_true),
            "prevalence": sum(y_true) / len(y_true) if y_true else 0,
        }
        except Exception as e:
            print(f"  ✗ Metrics computation failed: {e}")
            return {
                "ablation_mode": ablation_mode,
                "profile": profile,
                "enable_fusion": enable_fusion,
                "n_variants": len(rows),
                "n_predictions": len(y_pred),
                "auroc": None,
                "auprc": None,
                "error": str(e),
            }
    else:
        print(f"  ✗ Insufficient predictions ({len(y_pred)}) or classes ({len(set(y_true))}) to compute metrics")
        return {
            "ablation_mode": ablation_mode,
            "profile": profile,
            "enable_fusion": enable_fusion,
            "n_variants": len(rows),
            "n_predictions": len(y_pred),
            "auroc": None,
            "auprc": None,
            "note": "Insufficient predictions or classes",
        }

async def main():
    """Run full HRD baseline experiment with real efficacy predictions."""
    print("=" * 60)
    print("HRD BASELINE EXPERIMENT (REAL PREDICTIONS)")
    print("=" * 60)
    
    # Step 1: Extract cohort with clinical outcomes
    rows = await extract_hrd_cohort(limit=100)  # Increased to 100 now that we have working pipeline
    
    if not rows:
        print("ERROR: No rows extracted")
        sys.exit(1)
    
    # Step 2: Run baseline ablation only (can expand to others later)
    print("\n" + "=" * 60)
    print("RUNNING ABLATIONS")
    print("=" * 60)
    
    results = {}
    
    # 1. Baseline (minimal features)
    print("\n[1/3] Baseline (delta-only, no adaptive)")
    baseline_metrics = await run_ablation(rows, "baseline", profile="baseline")
    results["baseline"] = baseline_metrics
    
    # 2. Richer S (adaptive + multi-window)
    print("\n[2/3] Richer S (adaptive scoring)")
    richer_s_metrics = await run_ablation(rows, "richer_s", profile="richer_s")
    results["richer_s"] = richer_s_metrics
    
    # 3. Full S+P+E (ensemble mode)
    print("\n[3/3] Full SPE (ensemble, all features)")
    spe_metrics = await run_ablation(rows, "SPE", profile="full")
    results["spe_full"] = spe_metrics
    
    # Step 3: Save results
    output_dir = Path(__file__).parent.parent / "results" / "hrd_baseline"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    output_file = output_dir / "baseline_results_real.json"
    
    # Compute cohort stats
    positives = sum(1 for r in rows if r.get("outcome_platinum") == 1)
    
    with open(output_file, "w") as f:
        json.dump({
            "cohort": {
                "study": "ov_tcga",
                "n_samples": len(rows),
                "positives": positives,
                "prevalence": positives / len(rows) if rows else 0,
            },
            "ablations": results,
        }, f, indent=2)
    
    print(f"\n✓ Results saved to: {output_file}")
    
    # Step 4: Print summary
    print("\n" + "=" * 60)
    print("SUMMARY - ABLATION COMPARISON (PATIENT-LEVEL)")
    print("=" * 60)
    n_patients = len(set(r.get("patient_id") for r in rows if r.get("patient_id")))
    patient_positives = len(set(r.get("patient_id") for r in rows if r.get("patient_id") and r.get("outcome_platinum") == 1))
    print(f"Cohort: {len(rows)} variants from {n_patients} patients")
    print(f"  Patients with poor outcome: {patient_positives}/{n_patients} ({patient_positives/n_patients*100:.1f}%)")
    print()
    print(f"{'Mode':<20} {'AUROC':<10} {'AUPRC':<10} {'Predictions':<12} {'Lift vs Baseline'}")
    print("-" * 80)
    
    baseline_auroc = results.get('baseline', {}).get('auroc')
    baseline_auprc = results.get('baseline', {}).get('auprc')
    
    for mode, metrics in results.items():
        auroc = metrics.get('auroc')
        auprc = metrics.get('auprc')
        n_pred = metrics.get('n_predictions', 0)
        
        auroc_str = f"{auroc:.3f}" if auroc is not None else "N/A"
        auprc_str = f"{auprc:.3f}" if auprc is not None else "N/A"
        
        # Calculate lift
        if auroc is not None and baseline_auroc is not None and mode != 'baseline':
            auroc_lift = auroc - baseline_auroc
            auprc_lift = auprc - baseline_auprc if auprc and baseline_auprc else 0
            lift_str = f"AUROC +{auroc_lift:.3f}, AUPRC +{auprc_lift:.3f}"
        else:
            lift_str = "-"
        
        print(f"{mode:<20} {auroc_str:<10} {auprc_str:<10} {n_pred:<12} {lift_str}")
    
    print("\n" + "=" * 60)
    print("ANALYSIS")
    print("=" * 60)
    
    if baseline_metrics.get('auroc') is not None:
        baseline_auroc = baseline_metrics['auroc']
        baseline_auprc = baseline_metrics['auprc']
        
        print(f"\n📊 Baseline Performance:")
        print(f"   AUROC: {baseline_auroc:.3f} ({'random' if baseline_auroc < 0.52 else 'above random'})")
        print(f"   AUPRC: {baseline_auprc:.3f} (prevalence={positives/len(rows):.3f})")
        
        # Check if we got improvements
        best_auroc = max(m.get('auroc', 0) for m in results.values() if m.get('auroc'))
        best_mode = [k for k, v in results.items() if v.get('auroc') == best_auroc][0]
        
        if best_auroc > baseline_auroc:
            lift = best_auroc - baseline_auroc
            print(f"\n🚀 Best Performance: {best_mode}")
            print(f"   AUROC: {best_auroc:.3f} (+{lift:.3f} improvement)")
            print(f"   Status: {'✅ Publishable' if best_auroc > 0.70 else '⚠️  Needs further tuning'}")
        else:
            print(f"\n⚠️  No improvement over baseline detected")
            print(f"   This suggests:")
            print(f"   - Features may need tuning")
            print(f"   - Evo service may need warmup")
            print(f"   - More samples needed for statistical power")
    else:
        print("\n⚠️  Metrics computation failed. Check logs above for errors.")
    
    print("\n📊 Next Steps:")
    print("  1. ✅ Ablations complete (baseline, richer_s, SPE)")
    print("  2. Scale to 200-500 samples for robust CIs")
    print("  3. Add Fusion Engine ablation (+AlphaMissense)")
    print("  4. Generate figures (ROC/PR curves)")
    print("  5. Bootstrap confidence intervals")

if __name__ == "__main__":
    asyncio.run(main())



