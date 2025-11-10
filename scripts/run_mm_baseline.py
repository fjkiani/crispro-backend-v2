#!/usr/bin/env python3
"""
Run MM (Multiple Myeloma) baseline experiments with drug efficacy prediction.
Uses BRAF/KRAS/NRAS/TP53 variants to predict BRAF/MEK inhibitor efficacy.
"""
import asyncio
import json
import sys
from pathlib import Path
from typing import List, Dict, Any

import httpx
from sklearn.metrics import roc_auc_score, average_precision_score

API_ROOT = "http://127.0.0.1:8000"

# MM test variants: known pathogenic mutations in MAPK pathway
MM_TEST_VARIANTS = [
    # BRAF V600E (GRCh38) chr7:140453136 T>A
    {"gene": "BRAF", "hgvs_p": "V600E", "chrom": "7", "pos": 140453136, "ref": "T", "alt": "A", "expected_high": True, "drug": "BRAF inhibitor"},
    # BRAF V600K (GRCh38) chr7:140453136 T>G (approx; acceptable for smoke)
    {"gene": "BRAF", "hgvs_p": "V600K", "chrom": "7", "pos": 140453136, "ref": "T", "alt": "G", "expected_high": True, "drug": "BRAF inhibitor"},
    # KRAS G12D - canonical RAS variant, should predict MEK inhibitor > BRAF inhibitor
    {"gene": "KRAS", "hgvs_p": "G12D", "chrom": "12", "pos": 25245350, "ref": "C", "alt": "T", "expected_high": True, "drug": "MEK inhibitor"},
    # KRAS G12V - another G12 variant
    {"gene": "KRAS", "hgvs_p": "G12V", "chrom": "12", "pos": 25245350, "ref": "C", "alt": "A", "expected_high": True, "drug": "MEK inhibitor"},
    # NRAS Q61K - RAS family, should predict MEK inhibitor
    {"gene": "NRAS", "hgvs_p": "Q61K", "chrom": "1", "pos": 114713909, "ref": "G", "alt": "T", "expected_high": True, "drug": "MEK inhibitor"},
    # TP53 R248W - hotspot, should NOT predict MAPK inhibitors highly (different pathway)
    {"gene": "TP53", "hgvs_p": "R248W", "chrom": "17", "pos": 7577538, "ref": "C", "alt": "T", "expected_high": False, "drug": "None"},
    # TP53 R273H - another hotspot
    {"gene": "TP53", "hgvs_p": "R273H", "chrom": "17", "pos": 7577120, "ref": "G", "alt": "A", "expected_high": False, "drug": "None"},
]

async def predict_mm_efficacy(client: httpx.AsyncClient, variant: Dict[str, Any], 
                              profile: str = "baseline") -> Dict[str, Any]:
    """Predict drug efficacy for MM variant."""
    try:
        # Full S+P+E with Fusion enabled
        options = {
            "adaptive": True,
            "ensemble": False,
            "ablation_mode": "SPE",  # Enable evidence
            "enable_fusion": True,   # Enable AlphaMissense
        }
        
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
            "options": options,
            "disease": "multiple myeloma",
            "api_base": API_ROOT,
        }
        
        resp = await client.post(
            f"{API_ROOT}/api/efficacy/predict",
            json=payload,
            timeout=60.0,
        )
        
        if resp.status_code >= 400:
            print(f"    ✗ {variant['gene']} {variant['hgvs_p']}: HTTP {resp.status_code}")
            return None
        
        data = resp.json()
        drugs = data.get("drugs", [])
        
        # Return drug-specific scores
        result = {
            "variant": f"{variant['gene']} {variant['hgvs_p']}",
            "expected_drug": variant.get("drug"),
            "expected_high": variant.get("expected_high"),
            "drugs": {}
        }
        
        for drug in drugs:
            result["drugs"][drug["name"]] = {
                "confidence": drug.get("confidence", 0.0),
                "efficacy_score": drug.get("efficacy_score", 0.0),
                "evidence_tier": drug.get("evidence_tier"),
                "badges": drug.get("badges", []),
            }
        
        return result
        
    except httpx.TimeoutException:
        print(f"    ✗ {variant['gene']} {variant['hgvs_p']}: TIMEOUT")
        return None
    except Exception as e:
        print(f"    ✗ {variant['gene']} {variant['hgvs_p']}: {str(e)[:80]}")
        return None

async def run_mm_test(profile: str = "baseline"):
    """Run MM drug efficacy test."""
    print(f"\n{'='*60}")
    print(f"MM DRUG EFFICACY TEST (profile={profile})")
    print(f"{'='*60}")
    print(f"Testing {len(MM_TEST_VARIANTS)} canonical variants...")
    
    results = []
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        for i, variant in enumerate(MM_TEST_VARIANTS):
            print(f"\n[{i+1}/{len(MM_TEST_VARIANTS)}] {variant['gene']} {variant['hgvs_p']} (expect: {variant['drug']})")
            
            result = await predict_mm_efficacy(client, variant, profile)
            if result:
                results.append(result)
                
                # Print top drugs
                sorted_drugs = sorted(
                    result["drugs"].items(), 
                    key=lambda x: x[1]["confidence"], 
                    reverse=True
                )[:3]
                
                for drug_name, drug_data in sorted_drugs:
                    conf = drug_data["confidence"]
                    tier = drug_data["evidence_tier"]
                    print(f"  {drug_name:25s} confidence={conf:.3f} tier={tier}")
    
    return results

async def analyze_results(results: List[Dict[str, Any]]):
    """Analyze if predictions match expected drug targets."""
    print(f"\n{'='*60}")
    print("ANALYSIS")
    print(f"{'='*60}")
    
    # Check pathway alignment: BRAF variants → BRAF inhibitor, KRAS/NRAS → MEK inhibitor
    mapk_variants = [r for r in results if r["variant"].startswith(("BRAF", "KRAS", "NRAS"))]
    tp53_variants = [r for r in results if r["variant"].startswith("TP53")]
    
    print(f"\n📊 MAPK Pathway Variants (n={len(mapk_variants)}):")
    for r in mapk_variants:
        braf_conf = r["drugs"].get("BRAF inhibitor", {}).get("confidence", 0.0)
        mek_conf = r["drugs"].get("MEK inhibitor", {}).get("confidence", 0.0)
        max_conf = max(braf_conf, mek_conf)
        
        expected_drug = r["expected_drug"]
        top_drug = "BRAF inhibitor" if braf_conf > mek_conf else "MEK inhibitor"
        match = "✅" if top_drug == expected_drug else "❌"
        
        print(f"  {match} {r['variant']:20s} → {top_drug:20s} (conf={max_conf:.3f})")
    
    print(f"\n📊 TP53 Variants (n={len(tp53_variants)}):")
    for r in tp53_variants:
        braf_conf = r["drugs"].get("BRAF inhibitor", {}).get("confidence", 0.0)
        mek_conf = r["drugs"].get("MEK inhibitor", {}).get("confidence", 0.0)
        max_mapk_conf = max(braf_conf, mek_conf)
        
        # TP53 should have LOW confidence for MAPK inhibitors
        low_conf = "✅" if max_mapk_conf < 0.5 else "❌"
        print(f"  {low_conf} {r['variant']:20s} → max MAPK conf={max_mapk_conf:.3f} (expect <0.5)")
    
    # Overall accuracy: check if top predicted drug matches expected
    correct = sum(1 for r in mapk_variants 
                  if ((r["drugs"].get("BRAF inhibitor", {}).get("confidence", 0) > 
                       r["drugs"].get("MEK inhibitor", {}).get("confidence", 0)) and 
                      r["expected_drug"] == "BRAF inhibitor") or
                     ((r["drugs"].get("MEK inhibitor", {}).get("confidence", 0) > 
                       r["drugs"].get("BRAF inhibitor", {}).get("confidence", 0)) and 
                      r["expected_drug"] == "MEK inhibitor"))
    
    accuracy = correct / len(mapk_variants) if mapk_variants else 0
    
    print(f"\n🎯 Pathway Alignment Accuracy: {correct}/{len(mapk_variants)} ({accuracy*100:.1f}%)")
    
    # Check if confidence > random
    all_confs = []
    for r in results:
        for drug_data in r["drugs"].values():
            all_confs.append(drug_data["confidence"])
    
    avg_conf = sum(all_confs) / len(all_confs) if all_confs else 0
    print(f"📈 Average Confidence: {avg_conf:.3f}")
    
    return {
        "accuracy": accuracy,
        "avg_confidence": avg_conf,
        "n_tested": len(results),
        "mapk_correct": correct,
        "mapk_total": len(mapk_variants),
    }

async def main():
    """Run MM baseline experiments."""
    print(f"{'='*60}")
    print("MM DRUG EFFICACY BASELINE")
    print(f"{'='*60}")
    
    # Run baseline test
    baseline_results = await run_mm_test(profile="baseline")
    baseline_metrics = await analyze_results(baseline_results)
    
    # Save results
    output_dir = Path(__file__).parent.parent / "results" / "mm_baseline"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    output_file = output_dir / "mm_efficacy_results.json"
    
    with open(output_file, "w") as f:
        json.dump({
            "test_variants": MM_TEST_VARIANTS,
            "results": baseline_results,
            "metrics": baseline_metrics,
        }, f, indent=2)
    
    print(f"\n✅ Results saved to: {output_file}")
    
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"Tested: {baseline_metrics['n_tested']} variants")
    print(f"Pathway Alignment: {baseline_metrics['mapk_correct']}/{baseline_metrics['mapk_total']} ({baseline_metrics['accuracy']*100:.1f}%)")
    print(f"Avg Confidence: {baseline_metrics['avg_confidence']:.3f}")
    
    if baseline_metrics['accuracy'] >= 0.7:
        print(f"\n✅ GOOD: Pathway alignment ≥70% - model understands MAPK biology")
    elif baseline_metrics['accuracy'] >= 0.5:
        print(f"\n⚠️  MODERATE: Pathway alignment 50-70% - some signal but needs tuning")
    else:
        print(f"\n❌ POOR: Pathway alignment <50% - model not capturing biology")

if __name__ == "__main__":
    asyncio.run(main())

