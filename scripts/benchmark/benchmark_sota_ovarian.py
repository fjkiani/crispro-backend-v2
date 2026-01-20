#!/usr/bin/env python3
"""
SOTA Benchmark Script for Ovarian Cancer
Uses TCGA-OV dataset to validate platinum response prediction.
"""
import asyncio
import json
import sys
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

import httpx
from sklearn.metrics import roc_auc_score, average_precision_score, roc_curve, precision_recall_curve
import numpy as np

API_ROOT = "http://127.0.0.1:8000"

def load_tcga_ov_data(data_file: str = None) -> List[Dict[str, Any]]:
    """Load TCGA-OV validation dataset."""
    if data_file is None:
        # Try to find existing benchmark results (prefer 1k dataset, fallback to sample)
        benchmark_dir = Path(__file__).parent.parent.parent / "tools" / "benchmarks"
        
        # Priority 1: Use 1k dataset if available (more robust for benchmarking)
        data_file_1k = benchmark_dir / "hrd_tcga_ov_labeled_1k_results.json"
        if data_file_1k.exists():
            data_file = data_file_1k
            print(f"✅ Using 1k dataset: {data_file_1k}")
        else:
            # Priority 2: Use sample dataset
            data_file = benchmark_dir / "hrd_tcga_ov_labeled_sample_results.json"
    
    if not Path(data_file).exists():
        print(f"⚠️  Data file not found: {data_file}")
        print("   Using sample data from existing results...")
        # Fallback: create sample from known results
        return [
            {
                "input": {
                    "disease": "ovarian cancer",
                    "gene": "BRCA2",
                    "hgvs_p": "C711*",
                    "chrom": "13",
                    "pos": 32910625,
                    "ref": "C",
                    "alt": "A",
                    "outcome_platinum": "1"
                },
                "expected_score": 0.8,  # Should score high for PARP inhibitors
            },
            {
                "input": {
                    "disease": "ovarian cancer",
                    "gene": "BRCA1",
                    "hgvs_p": "I1108*",
                    "chrom": "17",
                    "pos": 43070943,
                    "ref": "A",
                    "alt": "T",
                    "outcome_platinum": "1"
                },
                "expected_score": 0.8,
            },
        ]
    
    with open(data_file, "r") as f:
        data = json.load(f)
    
    # Extract results from benchmark file
    results = data.get("results", [])
    print(f"✅ Loaded {len(results)} variants from {data_file.name}")
    return results

async def predict_ovarian_efficacy(client: httpx.AsyncClient, variant_input: Dict[str, Any]) -> Dict[str, Any]:
    """Predict drug efficacy for ovarian cancer variant."""
    try:
        # Convert input format to efficacy request format
        mutation = {
            "gene": variant_input.get("gene", ""),
            "hgvs_p": variant_input.get("hgvs_p", ""),
            "chrom": str(variant_input.get("chrom", "")),
            "pos": variant_input.get("pos", ""),
            "ref": variant_input.get("ref", ""),
            "alt": variant_input.get("alt", ""),
        }
        
        payload = {
            "model_id": "evo2_1b",
            "mutations": [mutation],
            "options": {
                "adaptive": True,
                "ensemble": False,
                "ablation_mode": "SPE",
            },
            "disease": "ovarian_cancer",
            "api_base": API_ROOT,
        }
        
        resp = await client.post(
            f"{API_ROOT}/api/efficacy/predict",
            json=payload,
            timeout=60.0,
        )
        
        if resp.status_code >= 400:
            return {"error": f"HTTP {resp.status_code}"}
        
        data = resp.json()
        drugs = data.get("drugs", [])
        
        # Find PARP inhibitors and platinum in results
        parp_drugs = [d for d in drugs if "PARP" in d.get("moa", "").upper() or "olaparib" in d.get("name", "").lower() or "niraparib" in d.get("name", "").lower()]
        platinum_drugs = [d for d in drugs if "platinum" in d.get("moa", "").lower() or "carboplatin" in d.get("name", "").lower()]
        
        # Get top PARP or platinum score
        top_parp = parp_drugs[0] if parp_drugs else None
        top_platinum = platinum_drugs[0] if platinum_drugs else None
        
        # Use PARP if available, else platinum, else top drug
        relevant_drug = top_parp or top_platinum or (drugs[0] if drugs else None)
        
        return {
            "variant": f"{variant_input.get('gene')} {variant_input.get('hgvs_p')}",
            "score": relevant_drug.get("efficacy_score", 0.0) if relevant_drug else 0.0,
            "confidence": relevant_drug.get("confidence", 0.0) if relevant_drug else 0.0,
            "drug_name": relevant_drug.get("name", "") if relevant_drug else "",
            "evidence_tier": relevant_drug.get("evidence_tier", "") if relevant_drug else "",
            "top_5_drugs": [
                {
                    "name": drug["name"],
                    "efficacy_score": drug.get("efficacy_score", 0.0),
                    "confidence": drug.get("confidence", 0.0),
                }
                for drug in drugs[:5]
            ],
        }
    except Exception as e:
        return {"error": str(e)[:100], "score": 0.5}  # Default to baseline score

async def run_ovarian_benchmark():
    """Run ovarian cancer benchmark and compute AUROC/AUPRC."""
    print("🧬 Running Ovarian Cancer SOTA Benchmark...")
    
    # Load TCGA-OV data
    tcga_data = load_tcga_ov_data()
    print(f"  Loaded {len(tcga_data)} variants from TCGA-OV dataset")
    
    results = []
    y_true = []
    y_scores = []
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        for i, item in enumerate(tcga_data):
            variant_input = item.get("input", {})
            expected_outcome = variant_input.get("outcome_platinum", "0")
            
            # Skip if no outcome label
            if expected_outcome not in ["0", "1"]:
                continue
            
            if i % 50 == 0:
                print(f"  Processing variant {i+1}/{len(tcga_data)}...")
            
            result = await predict_ovarian_efficacy(client, variant_input)
            
            if "error" in result:
                score = 0.5  # Default baseline
            else:
                score = result.get("score", 0.5)
            
            y_true.append(int(expected_outcome))
            y_scores.append(score)
            
            result["expected_outcome"] = int(expected_outcome)
            results.append(result)
    
    # Compute metrics
    if len(set(y_true)) > 1:  # Need both classes
        auroc = roc_auc_score(y_true, y_scores)
        auprc = average_precision_score(y_true, y_scores)
    else:
        auroc = 0.5  # Cannot compute if only one class
        auprc = 0.5
    
    benchmark_result = {
        "timestamp": datetime.now().isoformat(),
        "disease": "ovarian_cancer",
        "metrics": {
            "auroc": auroc,
            "auprc": auprc,
            "n_variants": len(results),
            "n_sensitive": sum(y_true),
            "n_resistant": len(y_true) - sum(y_true),
        },
        "target": {
            "auroc": 0.75,  # Target AUROC > 0.75 (match/exceed HRD performance)
            "auroc_minimum": 0.65,  # Minimum AUROC > 0.65 (better than random)
        },
        "results": results[:100],  # Limit to first 100 for file size
        "provenance": {
            "script": "benchmark_sota_ovarian.py",
            "api_base": API_ROOT,
            "model_id": "evo2_1b",
            "ablation_mode": "SPE",
            "data_source": str(Path(data_file).name) if data_file else "fallback",
        }
    }
    
    # Save results
    output_dir = Path(__file__).parent.parent / "results" / "sota"
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"ovarian_benchmark_{timestamp}.json"
    
    with open(output_file, "w") as f:
        json.dump(benchmark_result, f, indent=2)
    
    print(f"\n✅ Benchmark complete!")
    print(f"   AUROC: {auroc:.3f} (target: >0.75, minimum: >0.65)")
    print(f"   AUPRC: {auprc:.3f}")
    print(f"   Variants: {len(results)} (sensitive: {sum(y_true)}, resistant: {len(y_true) - sum(y_true)})")
    print(f"   Results saved to: {output_file}")
    
    # Status
    if auroc >= 0.75:
        status = "✅ PASS (Target Met)"
    elif auroc >= 0.65:
        status = "⚠️  MINIMUM MET (Below Target)"
    else:
        status = "❌ BELOW MINIMUM"
    print(f"   Status: {status}")
    
    return benchmark_result

if __name__ == "__main__":
    asyncio.run(run_ovarian_benchmark())

