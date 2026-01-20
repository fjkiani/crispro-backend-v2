#!/usr/bin/env python3
"""
Therapy Fit Demo Script

Showcases Therapy Fit capabilities using verified test cases.
Designed for demo presentations with clear, readable output.

IMPORTANT: This script makes REAL API calls to /api/efficacy/predict.
All displayed data comes from actual API responses - NO hard-coded values.

Usage:
    python scripts/demo_therapy_fit.py --test-case AYESHA-001
    python scripts/demo_therapy_fit.py --all --interactive
    python scripts/demo_therapy_fit.py --all --debug  # Show response structure
"""

import argparse
import asyncio
import httpx
import json
import sys
from typing import Dict, List, Any, Optional
from datetime import datetime
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

API_BASE_URL = "http://127.0.0.1:8000"
TIMEOUT = 300.0  # 5 minutes for Evo2 scoring

# Import test cases from the generator script
try:
    from generate_therapy_fit_results import TEST_CASES
except ImportError:
    # Fallback: define test cases directly
    TEST_CASES = [
        {
            "name": "Ayesha (MBD4+TP53 HGSOC)",
            "patient_id": "AYESHA-001",
            "disease": "ovarian_cancer",
            "mutations": [
                {"gene": "MBD4", "hgvs_p": "p.Q346*", "chrom": "3", "pos": 129149435, "ref": "C", "alt": "T", "consequence": "stop_gained"},
                {"gene": "TP53", "hgvs_p": "p.R273H", "chrom": "17", "pos": 7673802, "ref": "G", "alt": "A", "consequence": "missense_variant"}
            ]
        },
        {
            "name": "Multiple Myeloma Patient (KRAS G12D)",
            "patient_id": "MM-001",
            "disease": "multiple_myeloma",
            "mutations": [
                {"gene": "KRAS", "hgvs_p": "p.G12D", "chrom": "12", "pos": 25398284, "ref": "G", "alt": "A", "consequence": "missense_variant"}
            ]
        },
        {
            "name": "Melanoma Patient (BRAF V600E)",
            "patient_id": "MEL-001",
            "disease": "melanoma",
            "mutations": [
                {"gene": "BRAF", "hgvs_p": "p.V600E", "chrom": "7", "pos": 140753336, "ref": "T", "alt": "A", "consequence": "missense_variant"}
            ]
        }
    ]


def print_header(title: str, width: int = 80):
    """Print a formatted header."""
    print("\n" + "=" * width)
    print(f"  {title}")
    print("=" * width)


def print_section(title: str, width: int = 80):
    """Print a formatted section header."""
    print("\n" + "-" * width)
    print(f"  {title}")
    print("-" * width)


def print_mutation_summary(mutations: List[Dict[str, Any]]):
    """Print a formatted mutation summary."""
    print(f"\n📋 Patient Mutations ({len(mutations)}):")
    for i, mut in enumerate(mutations, 1):
        gene = mut.get("gene", "N/A")
        hgvs_p = mut.get("hgvs_p", "N/A")
        consequence = mut.get("consequence", "N/A")
        print(f"   {i}. {gene} {hgvs_p} ({consequence})")


def print_drug_ranking(drugs: List[Dict[str, Any]], top_n: int = 5):
    """Print formatted drug ranking."""
    print(f"\n💊 Top {min(top_n, len(drugs))} Drug Recommendations:")
    print()
    
    if not drugs:
        print("   ⚠️  No drugs in response")
        return
    
    for i, drug in enumerate(drugs[:top_n], 1):
        # Extract all fields from actual API response (no hard-coded values)
        name = drug.get("name") or drug.get("drug_name") or "N/A"
        efficacy = drug.get("efficacy_score") or drug.get("efficacy") or 0.0
        confidence = drug.get("confidence") or drug.get("confidence_score") or 0.0
        tier = drug.get("evidence_tier") or drug.get("tier") or "N/A"
        badges = drug.get("badges") or drug.get("badge") or []
        
        # Ensure badges is a list
        if not isinstance(badges, list):
            badges = [badges] if badges else []
        
        # Format badges
        badge_str = ", ".join(badges) if badges else "None"
        
        # Print drug info (all from actual API response)
        print(f"   {i}. {name}")
        print(f"      Efficacy Score: {efficacy:.3f}")
        print(f"      Confidence: {confidence:.3f} ({confidence*100:.1f}%)")
        print(f"      Evidence Tier: {str(tier).upper()}")
        print(f"      Badges: {badge_str}")
        
        # Print S/P/E breakdown if available (from actual response)
        if "spe_breakdown" in drug:
            spe = drug["spe_breakdown"]
            print(f"      S/P/E: S={spe.get('sequence', 0):.3f}, P={spe.get('pathway', 0):.3f}, E={spe.get('evidence', 0):.3f}")
        elif "sequence" in drug or "pathway" in drug or "evidence" in drug:
            # Alternative S/P/E structure
            seq = drug.get("sequence", 0)
            path = drug.get("pathway", 0)
            evd = drug.get("evidence", 0)
            print(f"      S/P/E: S={seq:.3f}, P={path:.3f}, E={evd:.3f}")
        
        # Print insights if available (from actual response)
        insights = drug.get("insights", {})
        if insights and isinstance(insights, dict):
            print(f"      Insights:")
            if "functionality" in insights:
                print(f"         Functionality: {insights['functionality']:.3f}")
            if "essentiality" in insights:
                print(f"         Essentiality: {insights['essentiality']:.3f}")
            if "chromatin" in insights:
                print(f"         Chromatin: {insights['chromatin']:.3f}")
            if "regulatory" in insights:
                print(f"         Regulatory: {insights['regulatory']:.3f}")
        
        # Show raw drug data structure if debug mode (first drug only)
        if i == 1 and hasattr(print_drug_ranking, '_debug'):
            print(f"      [DEBUG] Drug keys: {list(drug.keys())}")
        
        print()


def print_pathway_alignment(response: Dict[str, Any]):
    """Print pathway alignment scores."""
    pathway_scores = {}
    
    if "provenance" in response:
        provenance = response["provenance"]
        if "confidence_breakdown" in provenance:
            breakdown = provenance["confidence_breakdown"]
            pathway_disruption = breakdown.get("pathway_disruption", {})
            
            pathway_mapping = {
                "ddr": "DDR (DNA Damage Response)",
                "ras_mapk": "RAS/MAPK",
                "mapk": "RAS/MAPK",
                "pi3k": "PI3K/AKT",
                "vegf": "VEGF",
                "her2": "HER2"
            }
            
            for key, value in pathway_disruption.items():
                pathway_name = pathway_mapping.get(key.lower(), key)
                pathway_scores[pathway_name] = float(value) if value is not None else 0.0
    
    if pathway_scores:
        print_section("🛤️  Pathway Alignment Scores")
        print()
        for pathway, score in sorted(pathway_scores.items(), key=lambda x: x[1], reverse=True):
            bar_length = int(score * 40)
            bar = "█" * bar_length + "░" * (40 - bar_length)
            print(f"   {pathway:25s} {bar} {score:.3f} ({score*100:.1f}%)")


def print_mechanism_rationale(response: Dict[str, Any]):
    """Print mechanism rationale if available."""
    if "provenance" in response:
        provenance = response["provenance"]
        if "mechanism_rationale" in provenance:
            rationale = provenance["mechanism_rationale"]
            print_section("🧬 Mechanism Rationale")
            print()
            if isinstance(rationale, str):
                print(f"   {rationale}")
            elif isinstance(rationale, dict):
                for key, value in rationale.items():
                    print(f"   {key}: {value}")
            print()


async def call_efficacy_predict(
    client: httpx.AsyncClient,
    mutations: List[Dict[str, Any]],
    disease: str,
    model_id: str = "evo2_1b"
) -> Optional[Dict[str, Any]]:
    """Call /api/efficacy/predict endpoint."""
    url = f"{API_BASE_URL}/api/efficacy/predict"
    
    payload = {
        "model_id": model_id,
        "mutations": mutations,
        "disease": disease,
        "options": {
            "adaptive": True,
            "ensemble": False
        }
    }
    
    try:
        response = await client.post(url, json=payload, timeout=TIMEOUT)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        print(f"❌ HTTP Error: {e.response.status_code}")
        print(f"   Response: {e.response.text[:500]}")
        return None
    except Exception as e:
        print(f"❌ Error calling API: {e}")
        return None


async def demo_test_case(test_case: Dict[str, Any], client: httpx.AsyncClient, interactive: bool = False):
    """Run a demo for a single test case."""
    print_header(f"THERAPY FIT DEMO: {test_case['name']}")
    
    # Patient info
    print(f"\n👤 Patient ID: {test_case['patient_id']}")
    print(f"🏥 Disease: {test_case['disease'].replace('_', ' ').title()}")
    
    # Mutations
    print_mutation_summary(test_case["mutations"])
    
    if interactive:
        input("\n⏸️  Press Enter to call API...")
    
    # Call API
    print(f"\n📡 Calling Therapy Fit API...")
    print(f"   Endpoint: {API_BASE_URL}/api/efficacy/predict")
    start_time = datetime.now()
    
    response = await call_efficacy_predict(
        client,
        test_case["mutations"],
        test_case["disease"]
    )
    
    elapsed = (datetime.now() - start_time).total_seconds()
    
    if response is None:
        print("\n❌ API call failed. Please check:")
        print("   1. Backend server is running (uvicorn api.main:app)")
        print("   2. API is accessible at", API_BASE_URL)
        return None
    
    print(f"✅ Response received ({elapsed:.2f}s)")
    
    # Debug: Show response structure if requested
    if hasattr(main, '_debug_mode') and main._debug_mode:
        print(f"\n🔍 Response Structure (debug):")
        print(f"   Top-level keys: {list(response.keys())}")
        if "drugs" in response:
            print(f"   Drugs count: {len(response.get('drugs', []))}")
            if response.get("drugs"):
                print(f"   First drug keys: {list(response['drugs'][0].keys())}")
                print(f"   First drug sample: {json.dumps(response['drugs'][0], indent=6)[:500]}")
        if "provenance" in response:
            print(f"   Provenance keys: {list(response.get('provenance', {}).keys())}")
        print()
    
    # Drug rankings
    drugs = response.get("drugs", [])
    if drugs:
        print_section("💊 Drug Recommendations")
        print_drug_ranking(drugs, top_n=5)
    else:
        print("\n⚠️  No drugs returned in response")
        print(f"   Response keys: {list(response.keys())}")
        print(f"   Full response (first 500 chars): {str(response)[:500]}")
    
    # Pathway alignment
    print_pathway_alignment(response)
    
    # Mechanism rationale
    print_mechanism_rationale(response)
    
    # Summary
    if drugs:
        top_drug = drugs[0]
        print_section("📊 Summary")
        print(f"\n   Top Recommendation: {top_drug.get('name', 'N/A')}")
        print(f"   Efficacy Score: {top_drug.get('efficacy_score', 0):.3f}")
        print(f"   Confidence: {top_drug.get('confidence', 0):.3f} ({top_drug.get('confidence', 0)*100:.1f}%)")
        print(f"   Evidence Tier: {top_drug.get('evidence_tier', 'N/A').upper()}")
        print(f"   Response Time: {elapsed:.2f}s")
    
    return response


async def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Therapy Fit Demo Script",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run demo for Ayesha case
  python scripts/demo_therapy_fit.py --test-case AYESHA-001
  
  # Run all test cases
  python scripts/demo_therapy_fit.py --all
  
  # Interactive mode (pause between cases)
  python scripts/demo_therapy_fit.py --all --interactive
        """
    )
    parser.add_argument("--test-case", type=str, help="Run specific test case by patient ID (e.g., AYESHA-001)")
    parser.add_argument("--all", action="store_true", help="Run all test cases")
    parser.add_argument("--interactive", action="store_true", help="Pause between test cases (interactive mode)")
    parser.add_argument("--output", type=str, help="Save results to JSON file")
    parser.add_argument("--debug", action="store_true", help="Show debug information (response structure)")
    args = parser.parse_args()
    
    # Enable debug mode
    if args.debug:
        print_drug_ranking._debug = True
        main._debug_mode = True
    else:
        main._debug_mode = False
    
    # Print welcome banner
    print_header("THERAPY FIT DEMO", width=80)
    print("\n🎯 Showcasing Therapy Fit capabilities with real patient test cases")
    print(f"🌐 API Base URL: {API_BASE_URL}")
    print(f"📋 Test Cases Available: {len(TEST_CASES)}")
    
    # Filter test cases
    test_cases_to_run = TEST_CASES
    if args.test_case:
        test_cases_to_run = [tc for tc in TEST_CASES if tc["patient_id"] == args.test_case]
        if not test_cases_to_run:
            print(f"\n❌ Test case '{args.test_case}' not found")
            print(f"   Available IDs: {[tc['patient_id'] for tc in TEST_CASES]}")
            sys.exit(1)
    
    if not args.test_case and not args.all:
        print("\n⚠️  No test case specified. Use --test-case <ID> or --all")
        print(f"   Available IDs: {[tc['patient_id'] for tc in TEST_CASES]}")
        sys.exit(1)
    
    print(f"\n📋 Running {len(test_cases_to_run)} test case(s)...")
    if args.interactive:
        print("   Interactive mode: Will pause between test cases")
    
    # Run demos
    results = []
    
    async with httpx.AsyncClient() as client:
        for i, test_case in enumerate(test_cases_to_run, 1):
            if len(test_cases_to_run) > 1:
                print(f"\n\n{'='*80}")
                print(f"  Test Case {i}/{len(test_cases_to_run)}")
                print(f"{'='*80}")
            
            result = await demo_test_case(test_case, client, args.interactive)
            
            if result:
                results.append({
                    "test_case": test_case["name"],
                    "patient_id": test_case["patient_id"],
                    "response": result
                })
            
            if args.interactive and i < len(test_cases_to_run):
                input(f"\n⏸️  Press Enter to continue to next test case...")
    
    # Final summary
    print_header("DEMO COMPLETE", width=80)
    print(f"\n✅ Successfully ran {len(results)}/{len(test_cases_to_run)} test cases")
    
    if args.output:
        output_path = Path(__file__).parent / args.output
        with open(output_path, "w") as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "api_base_url": API_BASE_URL,
                "test_cases_run": len(results),
                "results": results
            }, f, indent=2)
        print(f"📄 Results saved to: {output_path}")
    
    print("\n💡 Key Features Demonstrated:")
    print("   ✅ Drug ranking with efficacy scores")
    print("   ✅ Confidence scoring")
    print("   ✅ Evidence tier classification")
    print("   ✅ Pathway alignment analysis")
    print("   ✅ S/P/E (Sequence/Pathway/Evidence) breakdown")
    print("   ✅ Insights chips (functionality, essentiality, chromatin, regulatory)")
    print("   ✅ Mechanism rationale")
    print("\n🎉 Demo complete!")


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

