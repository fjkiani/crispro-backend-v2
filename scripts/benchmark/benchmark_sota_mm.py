#!/usr/bin/env python3
"""
SOTA Benchmark Script for Multiple Myeloma
Reuses run_mm_baseline.py logic with standardized output format.
"""
import asyncio
import json
import sys
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

import httpx
from sklearn.metrics import roc_auc_score, average_precision_score

API_ROOT = "http://127.0.0.1:8000"

# MM test variants: known pathogenic mutations in MAPK pathway
MM_TEST_VARIANTS = [
    {"gene": "BRAF", "hgvs_p": "V600E", "chrom": "7", "pos": 140453136, "ref": "T", "alt": "A", "expected_drug": "BRAF inhibitor", "category": "MAPK"},
    {"gene": "BRAF", "hgvs_p": "V600K", "chrom": "7", "pos": 140453136, "ref": "T", "alt": "G", "expected_drug": "BRAF inhibitor", "category": "MAPK"},
    {"gene": "KRAS", "hgvs_p": "G12D", "chrom": "12", "pos": 25245350, "ref": "C", "alt": "T", "expected_drug": "MEK inhibitor", "category": "MAPK"},
    {"gene": "KRAS", "hgvs_p": "G12V", "chrom": "12", "pos": 25245350, "ref": "C", "alt": "A", "expected_drug": "MEK inhibitor", "category": "MAPK"},
    {"gene": "NRAS", "hgvs_p": "Q61K", "chrom": "1", "pos": 114713909, "ref": "G", "alt": "T", "expected_drug": "MEK inhibitor", "category": "MAPK"},
    {"gene": "TP53", "hgvs_p": "R248W", "chrom": "17", "pos": 7577538, "ref": "C", "alt": "T", "expected_drug": None, "category": "TP53"},
    {"gene": "TP53", "hgvs_p": "R273H", "chrom": "17", "pos": 7577120, "ref": "G", "alt": "A", "expected_drug": None, "category": "TP53"},
]

async def predict_mm_efficacy(client: httpx.AsyncClient, variant: Dict[str, Any]) -> Dict[str, Any]:
    """Predict drug efficacy for MM variant."""
    try:
        payload = {
            "model_id": "evo2_1b",
            "mutations": [{
                "gene": variant["gene"],
                "hgvs_p": variant["hgvs_p"],
                "chrom": str(variant["chrom"]),
                "pos": variant["pos"],
                "ref": variant["ref"],
                "alt": variant["alt"],
            }],
            "options": {
                "adaptive": True,
                "ensemble": False,
                "ablation_mode": "SPE",
            },
            "disease": "multiple_myeloma",
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
        
        # Find expected drug in results
        expected_drug = variant.get("expected_drug")
        expected_rank = None
        expected_confidence = None
        
        if expected_drug:
            for i, drug in enumerate(drugs):
                if drug["name"] == expected_drug:
                    expected_rank = i + 1
                    expected_confidence = drug.get("confidence", 0.0)
                    break
        
        return {
            "variant": f"{variant['gene']} {variant['hgvs_p']}",
            "expected_drug": expected_drug,
            "expected_rank": expected_rank,
            "expected_confidence": expected_confidence,
            "top_drug": drugs[0]["name"] if drugs else None,
            "top_confidence": drugs[0].get("confidence", 0.0) if drugs else 0.0,
            "drugs": [
                {
                    "name": drug["name"],
                    "confidence": drug.get("confidence", 0.0),
                    "efficacy_score": drug.get("efficacy_score", 0.0),
                    "evidence_tier": drug.get("evidence_tier"),
                }
                for drug in drugs[:5]
            ],
        }
    except Exception as e:
        return {"error": str(e)[:100]}

async def run_mm_benchmark():
    """Run MM benchmark and compute metrics."""
    print("🧬 Running MM SOTA Benchmark...")
    
    results = []
    correct_predictions = 0
    total_predictions = 0
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        for variant in MM_TEST_VARIANTS:
            expected_drug = variant.get("expected_drug")
            if not expected_drug:  # Skip TP53 variants (no expected drug)
                continue
            
            print(f"  Testing {variant['gene']} {variant['hgvs_p']}...")
            result = await predict_mm_efficacy(client, variant)
            
            if "error" in result:
                print(f"    ✗ Error: {result['error']}")
                continue
            
            # Check if expected drug is ranked #1
            is_correct = (result.get("expected_rank") == 1)
            if is_correct:
                correct_predictions += 1
            total_predictions += 1
            
            result["correct"] = is_correct
            results.append(result)
            
            status = "✅" if is_correct else "❌"
            print(f"    {status} Expected: {expected_drug}, Got: {result.get('top_drug')}, Rank: {result.get('expected_rank', 'N/A')}")
    
    # Compute metrics
    accuracy = correct_predictions / total_predictions if total_predictions > 0 else 0.0
    avg_confidence = sum(r.get("expected_confidence", 0.0) for r in results if r.get("expected_confidence")) / len([r for r in results if r.get("expected_confidence")]) if results else 0.0
    
    benchmark_result = {
        "timestamp": datetime.now().isoformat(),
        "disease": "multiple_myeloma",
        "metrics": {
            "pathway_alignment_accuracy": accuracy,
            "correct_predictions": correct_predictions,
            "total_predictions": total_predictions,
            "average_confidence": avg_confidence,
        },
        "target": {
            "pathway_alignment_accuracy": 1.0,  # 100% target
        },
        "results": results,
        "provenance": {
            "script": "benchmark_sota_mm.py",
            "api_base": API_ROOT,
            "model_id": "evo2_1b",
            "ablation_mode": "SPE",
        }
    }
    
    # Save results
    output_dir = Path(__file__).parent.parent / "results" / "sota"
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"mm_benchmark_{timestamp}.json"
    
    with open(output_file, "w") as f:
        json.dump(benchmark_result, f, indent=2)
    
    print(f"\n✅ Benchmark complete!")
    print(f"   Accuracy: {accuracy:.1%} ({correct_predictions}/{total_predictions})")
    print(f"   Average Confidence: {avg_confidence:.3f}")
    print(f"   Results saved to: {output_file}")
    
    return benchmark_result

if __name__ == "__main__":
    asyncio.run(run_mm_benchmark())

