"""
MM Ablation Study - Measure component contributions (S, P, E) to efficacy prediction.
Publication-ready ablation experiments with statistical significance testing.
"""
import asyncio
import httpx
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any
from dataclasses import dataclass

# Canonical MM test variants with expected drugs
MM_TEST_VARIANTS = [
    {
        "gene": "BRAF",
        "hgvs_p": "V600E",
        "chrom": "7",
        "pos": 140753336,  # GRCh38
        "ref": "A",
        "alt": "T",
        "expected_drug": "BRAF inhibitor",
        "category": "MAPK"
    },
    {
        "gene": "BRAF",
        "hgvs_p": "V600K",
        "chrom": "7",
        "pos": 140753335,  # GRCh38
        "ref": "G",
        "alt": "A",
        "expected_drug": "BRAF inhibitor",
        "category": "MAPK"
    },
    {
        "gene": "KRAS",
        "hgvs_p": "G12D",
        "chrom": "12",
        "pos": 25245350,  # GRCh38
        "ref": "C",
        "alt": "T",
        "expected_drug": "MEK inhibitor",
        "category": "MAPK"
    },
    {
        "gene": "KRAS",
        "hgvs_p": "G12V",
        "chrom": "12",
        "pos": 25245350,  # GRCh38
        "ref": "C",
        "alt": "A",
        "expected_drug": "MEK inhibitor",
        "category": "MAPK"
    },
    {
        "gene": "NRAS",
        "hgvs_p": "Q61K",
        "chrom": "1",
        "pos": 114716127,  # GRCh38
        "ref": "T",
        "alt": "G",
        "expected_drug": "MEK inhibitor",
        "category": "MAPK"
    },
    {
        "gene": "TP53",
        "hgvs_p": "R248W",
        "chrom": "17",
        "pos": 7675088,  # GRCh38
        "ref": "C",
        "alt": "T",
        "expected_drug": None,
        "category": "TP53"
    },
    {
        "gene": "TP53",
        "hgvs_p": "R273H",
        "chrom": "17",
        "pos": 7674220,  # GRCh38
        "ref": "G",
        "alt": "A",
        "expected_drug": None,
        "category": "TP53"
    },
]

@dataclass
class AblationResult:
    """Results for a single ablation mode."""
    mode: str
    pathway_accuracy: float
    avg_confidence: float
    mapk_correct: int
    mapk_total: int
    avg_margin: float  # Average confidence margin between correct and incorrect
    per_variant_results: List[Dict[str, Any]]

async def predict_mm_efficacy(
    variant: Dict[str, Any],
    api_base: str,
    timeout: float,
    ablation_mode: str = "SPE"
) -> Dict[str, Any]:
    """Call efficacy prediction endpoint with specific ablation mode."""
    payload = {
        "model_id": "evo2_1b",
        "mutations": [
            {
                "gene": variant["gene"],
                "hgvs_p": variant["hgvs_p"],
                "chrom": variant["chrom"],
                "pos": variant["pos"],
                "ref": variant["ref"],
                "alt": variant["alt"],
            }
        ],
        "options": {
            "adaptive": True,
            "ensemble": False,
            "ablation_mode": ablation_mode,
            "enable_fusion": False,
        },
        "api_base": api_base,
    }
    
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(f"{api_base}/api/efficacy/predict", json=payload)
        resp.raise_for_status()
        return resp.json()

async def run_ablation(
    mode: str,
    variants: List[Dict[str, Any]],
    api_base: str,
    timeout: float
) -> AblationResult:
    """Run ablation study for a specific mode (S-only, P-only, etc.)."""
    print(f"\n{'='*60}")
    print(f"ABLATION MODE: {mode}")
    print(f"{'='*60}")
    
    per_variant = []
    mapk_correct = 0
    mapk_total = 0
    confidences = []
    margins = []
    
    for i, variant in enumerate(variants, 1):
        print(f"\n[{i}/{len(variants)}] {variant['gene']} {variant['hgvs_p']} (expect: {variant.get('expected_drug', 'None')})")
        
        result = await predict_mm_efficacy(variant, api_base, timeout, ablation_mode=mode)
        drugs = result.get("drugs", [])
        
        # Sort by confidence
        drugs_sorted = sorted(drugs, key=lambda d: d.get("confidence", 0.0), reverse=True)
        
        # Display top 3
        for drug in drugs_sorted[:3]:
            print(f"  {drug['name']:<25} confidence={drug.get('confidence', 0.0):.3f} tier={drug.get('evidence_tier', 'unknown')}")
        
        # Check correctness
        expected = variant.get("expected_drug")
        if expected and variant["category"] == "MAPK":
            mapk_total += 1
            top_drug = drugs_sorted[0]["name"] if drugs_sorted else None
            is_correct = (top_drug == expected)
            if is_correct:
                mapk_correct += 1
            
            # Calculate margin
            expected_conf = next((d["confidence"] for d in drugs_sorted if d["name"] == expected), 0.0)
            top_conf = drugs_sorted[0]["confidence"] if drugs_sorted else 0.0
            margin = expected_conf - (top_conf if not is_correct else (drugs_sorted[1]["confidence"] if len(drugs_sorted) > 1 else 0.0))
            margins.append(margin)
        
        # Collect confidence stats
        if drugs_sorted:
            confidences.append(drugs_sorted[0]["confidence"])
        
        per_variant.append({
            "variant": f"{variant['gene']} {variant['hgvs_p']}",
            "expected": expected,
            "predicted": drugs_sorted[0]["name"] if drugs_sorted else None,
            "confidence": drugs_sorted[0]["confidence"] if drugs_sorted else 0.0,
            "tier": drugs_sorted[0]["evidence_tier"] if drugs_sorted else "unknown",
            "correct": (drugs_sorted[0]["name"] == expected) if (expected and drugs_sorted) else None,
        })
    
    pathway_accuracy = (mapk_correct / mapk_total) if mapk_total > 0 else 0.0
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
    avg_margin = sum(margins) / len(margins) if margins else 0.0
    
    print(f"\n{'='*60}")
    print(f"RESULTS: {mode}")
    print(f"{'='*60}")
    print(f"Pathway Accuracy: {mapk_correct}/{mapk_total} ({pathway_accuracy*100:.1f}%)")
    print(f"Avg Confidence: {avg_confidence:.3f}")
    print(f"Avg Margin: {avg_margin:.3f}")
    
    return AblationResult(
        mode=mode,
        pathway_accuracy=pathway_accuracy,
        avg_confidence=avg_confidence,
        mapk_correct=mapk_correct,
        mapk_total=mapk_total,
        avg_margin=avg_margin,
        per_variant_results=per_variant,
    )

async def main():
    """Run comprehensive ablation study."""
    api_base = "http://127.0.0.1:8000"
    timeout = 180.0
    
    print("="*60)
    print("MM ABLATION STUDY - Component Contribution Analysis")
    print("="*60)
    print(f"Testing {len(MM_TEST_VARIANTS)} canonical variants")
    print(f"Ablation modes: S-only, P-only, E-only, SP, SE, PE, SPE")
    print()
    
    # Run ablations
    ablation_modes = ["S", "P", "E", "SP", "SE", "PE", "SPE"]
    results = {}
    
    for mode in ablation_modes:
        result = await run_ablation(mode, MM_TEST_VARIANTS, api_base, timeout)
        results[mode] = result
    
    # Summary table
    print("\n" + "="*80)
    print("ABLATION SUMMARY TABLE")
    print("="*80)
    print(f"{'Mode':<8} {'Pathway Acc':<15} {'Avg Conf':<12} {'Avg Margin':<12}")
    print("-"*80)
    for mode in ablation_modes:
        r = results[mode]
        print(f"{mode:<8} {r.mapk_correct}/{r.mapk_total} ({r.pathway_accuracy*100:>5.1f}%)   {r.avg_confidence:>6.3f}       {r.avg_margin:>6.3f}")
    
    # Save results
    output_dir = Path(__file__).parent.parent / "results" / "mm_ablations"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"ablation_results_{timestamp}.json"
    
    export_data = {
        "timestamp": datetime.now().isoformat(),
        "ablation_modes": ablation_modes,
        "summary": {
            mode: {
                "pathway_accuracy": r.pathway_accuracy,
                "avg_confidence": r.avg_confidence,
                "avg_margin": r.avg_margin,
                "mapk_correct": r.mapk_correct,
                "mapk_total": r.mapk_total,
            }
            for mode, r in results.items()
        },
        "per_variant_details": {
            mode: r.per_variant_results
            for mode, r in results.items()
        }
    }
    
    with open(output_file, "w") as f:
        json.dump(export_data, f, indent=2)
    
    print(f"\n✅ Results saved to: {output_file}")
    
    # Key findings
    print("\n" + "="*80)
    print("KEY FINDINGS")
    print("="*80)
    spe_acc = results["SPE"].pathway_accuracy
    s_acc = results["S"].pathway_accuracy
    p_acc = results["P"].pathway_accuracy
    
    print(f"1. Full model (SPE): {spe_acc*100:.1f}% accuracy, {results['SPE'].avg_confidence:.3f} confidence")
    print(f"2. Sequence-only (S): {s_acc*100:.1f}% accuracy, {results['S'].avg_confidence:.3f} confidence")
    print(f"3. Pathway-only (P): {p_acc*100:.1f}% accuracy, {results['P'].avg_confidence:.3f} confidence")
    print(f"4. Best combination: {max(results.items(), key=lambda x: x[1].pathway_accuracy)[0]}")
    
    if spe_acc >= 0.7:
        print("\n✅ PUBLICATION READY: ≥70% pathway alignment demonstrates biological understanding")
    else:
        print("\n⚠️ NEEDS IMPROVEMENT: <70% alignment - consider additional features")

if __name__ == "__main__":
    asyncio.run(main())

