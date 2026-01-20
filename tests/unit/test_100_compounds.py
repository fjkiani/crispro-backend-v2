"""
100-Compound Test Battery for Alias Resolver

Tests compound alias resolution with 100 diverse compounds
to validate <5% failure rate acceptance criteria.

Author: CrisPRO Platform
Date: November 5, 2025
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.services.compound_alias_resolver import CompoundAliasResolver


# 100 diverse compounds spanning multiple categories
TEST_COMPOUNDS = [
    # Vitamins & Minerals (10)
    "Vitamin A", "Vitamin B12", "Vitamin C", "Vitamin D", "Vitamin E",
    "Vitamin K", "Folic Acid", "Niacin", "Riboflavin", "Thiamine",
    
    # Polyphenols & Antioxidants (20)
    "Curcumin", "Resveratrol", "Quercetin", "Catechin", "Epicatechin",
    "Epigallocatechin gallate", "Genistein", "Daidzein", "Lycopene",
    "Beta-carotene", "Lutein", "Zeaxanthin", "Anthocyanins", "Ellagic acid",
    "Ferulic acid", "Caffeic acid", "Chlorogenic acid", "Rutin",
    "Hesperidin", "Naringenin",
    
    # Omega Fatty Acids (5)
    "Omega-3 fatty acids", "EPA", "DHA", "Alpha-linolenic acid", "Omega-6 fatty acids",
    
    # Herbs & Extracts (20)
    "Green Tea Extract", "Turmeric", "Ginger", "Garlic", "Ginseng",
    "Milk Thistle", "St. John's Wort", "Echinacea", "Ginkgo Biloba",
    "Saw Palmetto", "Valerian", "Ashwagandha", "Rhodiola", "Holy Basil",
    "Astragalus", "Schisandra", "Cordyceps", "Reishi Mushroom",
    "Lion's Mane", "Chaga Mushroom",
    
    # Amino Acids & Derivatives (10)
    "L-Glutamine", "L-Arginine", "L-Carnitine", "Creatine", "Taurine",
    "N-Acetyl Cysteine", "Alpha-lipoic acid", "Coenzyme Q10", "L-Theanine",
    "5-HTP",
    
    # Probiotics & Enzymes (5)
    "Lactobacillus acidophilus", "Bifidobacterium", "Saccharomyces boulardii",
    "Digestive Enzymes", "Bromelain",
    
    # Minerals & Trace Elements (10)
    "Calcium", "Magnesium", "Zinc", "Iron", "Selenium",
    "Copper", "Manganese", "Chromium", "Iodine", "Potassium",
    
    # Specialty Compounds (10)
    "Melatonin", "Glucosamine", "Chondroitin", "MSM", "Collagen",
    "Hyaluronic acid", "Biotin", "Inositol", "PABA", "Rutin",
    
    # Marine & Specialty (5)
    "Fish Oil", "Krill Oil", "Astaxanthin", "Spirulina", "Chlorella",
    
    # Phytonutrients (5)
    "Indole-3-carbinol", "Sulforaphane", "Diindolylmethane", "Berberine", "Piperine"
]


def run_100_compound_test():
    """Run comprehensive 100-compound test battery."""
    
    print("\n" + "="*80)
    print("🎯 100-COMPOUND TEST BATTERY - ALIAS RESOLVER")
    print("="*80 + "\n")
    
    resolver = CompoundAliasResolver()
    
    results = {
        "total": len(TEST_COMPOUNDS),
        "successes": 0,
        "failures": 0,
        "failed_compounds": [],
        "resolutions": {}
    }
    
    print(f"Testing {results['total']} compounds...\n")
    
    # Test each compound
    for idx, compound in enumerate(TEST_COMPOUNDS, 1):
        try:
            canonical = resolver.resolve_compound_alias(compound)
            
            # Success if we got a non-empty result
            if canonical and len(canonical) > 0:
                results["successes"] += 1
                results["resolutions"][compound] = canonical
                
                # Only print if resolution changed the name
                if canonical.lower() != compound.lower():
                    print(f"  {idx:3d}. ✅ {compound:40s} → {canonical}")
                else:
                    print(f"  {idx:3d}. ⚪ {compound:40s} (no change)")
            else:
                results["failures"] += 1
                results["failed_compounds"].append(compound)
                print(f"  {idx:3d}. ❌ {compound:40s} FAILED (empty result)")
                
        except Exception as e:
            results["failures"] += 1
            results["failed_compounds"].append(compound)
            print(f"  {idx:3d}. ❌ {compound:40s} FAILED ({e})")
    
    # Print summary
    print("\n" + "="*80)
    print("📊 TEST SUMMARY")
    print("="*80)
    
    failure_rate = (results["failures"] / results["total"]) * 100
    
    print(f"\nTotal Compounds:    {results['total']}")
    print(f"Successful:         {results['successes']} ({(results['successes']/results['total'])*100:.1f}%)")
    print(f"Failed:             {results['failures']} ({failure_rate:.1f}%)")
    
    # Cache statistics
    cache_stats = resolver.get_cache_stats()
    print(f"\n Cache Performance:")
    print(f"   - Cache size:    {cache_stats['cache_size']} entries")
    print(f"   - Cache hits:    {cache_stats['cache_hits']}")
    print(f"   - Cache misses:  {cache_stats['cache_misses']}")
    print(f"   - Hit rate:      {cache_stats['hit_rate']*100:.1f}%")
    print(f"   - Failures:      {cache_stats['resolution_failures']}")
    
    # Acceptance criteria check
    print(f"\n🎯 ACCEPTANCE CRITERIA:")
    print(f"   - Target: <5% failure rate")
    print(f"   - Actual: {failure_rate:.1f}%")
    
    if failure_rate < 5.0:
        print(f"   ✅ PASS - Below 5% threshold")
    else:
        print(f"   ❌ FAIL - Above 5% threshold")
        print(f"\n   Failed compounds:")
        for compound in results["failed_compounds"]:
            print(f"     - {compound}")
    
    # Cache hit rate check
    if cache_stats['hit_rate'] > 0.8:
        print(f"   ✅ PASS - Cache hit rate >80%")
    else:
        print(f"   ⚠️  WARNING - Cache hit rate {cache_stats['hit_rate']*100:.1f}% (target: >80%)")
    
    print("\n" + "="*80 + "\n")
    
    return results, cache_stats


if __name__ == "__main__":
    results, stats = run_100_compound_test()
    
    # Exit with appropriate code
    failure_rate = (results["failures"] / results["total"]) * 100
    if failure_rate >= 5.0:
        sys.exit(1)  # Fail if > 5% failure rate
    else:
        sys.exit(0)  # Pass





