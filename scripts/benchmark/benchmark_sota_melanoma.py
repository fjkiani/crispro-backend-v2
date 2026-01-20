#!/usr/bin/env python3
"""
SOTA Benchmark Script for Melanoma
Tests known BRAF/NRAS driver mutations for drug ranking accuracy.
"""
import asyncio
import json
import sys
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

import httpx

API_ROOT = "http://127.0.0.1:8000"

# Known driver mutations for melanoma
MELANOMA_TEST_VARIANTS = [
    {
        "gene": "BRAF",
        "hgvs_p": "V600E",
        "chrom": "7",
        "pos": 140453136,
        "ref": "T",
        "alt": "A",
        "expected_drug": "BRAF inhibitor",
        "expected_rank": 1,  # Should be ranked #1
    },
    {
        "gene": "BRAF",
        "hgvs_p": "V600K",
        "chrom": "7",
        "pos": 140453136,
        "ref": "T",
        "alt": "G",
        "expected_drug": "BRAF inhibitor",
        "expected_rank": 1,
    },
    {
        "gene": "NRAS",
        "hgvs_p": "Q61R",
        "chrom": "1",
        "pos": 114713909,
        "ref": "G",
        "alt": "A",
        "expected_drug": "MEK inhibitor",
        "expected_rank": 1,
    },
    {
        "gene": "NRAS",
        "hgvs_p": "Q61K",
        "chrom": "1",
        "pos": 114713909,
        "ref": "G",
        "alt": "T",
        "expected_drug": "MEK inhibitor",
        "expected_rank": 1,
    },
]

async def predict_melanoma_efficacy(client: httpx.AsyncClient, variant: Dict[str, Any], full_mode: bool = True) -> Dict[str, Any]:
    """Predict drug efficacy for melanoma variant."""
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
                "ablation_mode": "SPE" if full_mode else "SP",
            },
            "disease": "melanoma",
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
            "evidence_tier": drugs[0].get("evidence_tier", "") if drugs else "",
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

async def run_melanoma_benchmark():
    """Run melanoma benchmark and compute drug ranking accuracy."""
    print("🧬 Running Melanoma SOTA Benchmark...")
    
    results = []
    correct_predictions = 0
    total_predictions = 0
    confidence_scores = []
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        for variant in MELANOMA_TEST_VARIANTS:
            expected_drug = variant.get("expected_drug")
            expected_rank = variant.get("expected_rank", 1)
            
            print(f"  Testing {variant['gene']} {variant['hgvs_p']} (expected: {expected_drug} at rank {expected_rank})...")
            
            # Test with full-mode (SPE)
            result = await predict_melanoma_efficacy(client, variant, full_mode=True)
            
            if "error" in result:
                print(f"    ✗ Error: {result['error']}")
                continue
            
            # Check if expected drug is at expected rank
            actual_rank = result.get("expected_rank")
            is_correct = (actual_rank == expected_rank) if actual_rank else False
            
            if is_correct:
                correct_predictions += 1
            total_predictions += 1
            
            if result.get("expected_confidence"):
                confidence_scores.append(result["expected_confidence"])
            
            result["correct"] = is_correct
            result["mode"] = "full"  # Full-mode SPE
            results.append(result)
            
            status = "✅" if is_correct else "❌"
            print(f"    {status} Expected: {expected_drug} at rank {expected_rank}, Got: rank {actual_rank}, Confidence: {result.get('expected_confidence', 0.0):.3f}")
    
    # Compute metrics
    accuracy = correct_predictions / total_predictions if total_predictions > 0 else 0.0
    avg_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.0
    
    benchmark_result = {
        "timestamp": datetime.now().isoformat(),
        "disease": "melanoma",
        "metrics": {
            "drug_ranking_accuracy": accuracy,
            "correct_predictions": correct_predictions,
            "total_predictions": total_predictions,
            "average_confidence": avg_confidence,
        },
        "target": {
            "drug_ranking_accuracy": 0.90,  # 90%+ target
            "average_confidence": 0.50,  # >0.50 target
        },
        "results": results,
        "provenance": {
            "script": "benchmark_sota_melanoma.py",
            "api_base": API_ROOT,
            "model_id": "evo2_1b",
            "ablation_mode": "SPE",
            "mode": "full",
        }
    }
    
    # Save results
    output_dir = Path(__file__).parent.parent / "results" / "sota"
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"melanoma_benchmark_{timestamp}.json"
    
    with open(output_file, "w") as f:
        json.dump(benchmark_result, f, indent=2)
    
    print(f"\n✅ Benchmark complete!")
    print(f"   Accuracy: {accuracy:.1%} ({correct_predictions}/{total_predictions})")
    print(f"   Average Confidence: {avg_confidence:.3f} (target: >0.50)")
    print(f"   Results saved to: {output_file}")
    
    # Status
    accuracy_status = "✅ PASS" if accuracy >= 0.90 else "⚠️  BELOW TARGET"
    confidence_status = "✅ PASS" if avg_confidence >= 0.50 else "⚠️  BELOW TARGET"
    print(f"   Accuracy Status: {accuracy_status}")
    print(f"   Confidence Status: {confidence_status}")
    
    return benchmark_result

if __name__ == "__main__":
    asyncio.run(run_melanoma_benchmark())

