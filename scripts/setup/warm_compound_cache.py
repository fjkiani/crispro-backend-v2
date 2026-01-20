"""
Warm Compound Alias Resolver Cache

Pre-resolves common compounds to populate cache before production use.
This improves first-query performance by eliminating cold-start latency.

Usage:
    python scripts/warm_compound_cache.py

Author: CrisPRO Platform
Date: November 5, 2025
"""

import sys
import json
import time
from pathlib import Path

# Add parent directory to path
backend_root = Path(__file__).parent.parent
sys.path.insert(0, str(backend_root))

# Change working directory to backend root
import os
os.chdir(backend_root)

from api.services.compound_alias_resolver import get_resolver

# Read compounds list directly from config file (avoid Pydantic import issues)
def get_common_compounds():
    """Extract common_compounds list from config file."""
    config_path = backend_root / "api" / "config" / "compound_resolution.py"
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    
    # Read file and extract common_compounds list
    with open(config_path, 'r') as f:
        content = f.read()
    
    # Find the common_compounds list
    import re
    # Match the list assignment
    match = re.search(r'common_compounds:\s*list\[str\]\s*=\s*\[(.*?)\]', content, re.DOTALL)
    if not match:
        # Fallback: try to find it another way
        # Look for the list content
        start_idx = content.find('common_compounds: list[str] = [')
        if start_idx == -1:
            # Default fallback list
            return [
                "Vitamin D", "Vitamin C", "Curcumin", "Resveratrol",
                "Omega-3 fatty acids", "Green Tea Extract", "Quercetin"
            ]
        
        # Extract the list content
        list_start = content.find('[', start_idx)
        bracket_count = 0
        list_end = list_start
        
        for i in range(list_start, len(content)):
            if content[i] == '[':
                bracket_count += 1
            elif content[i] == ']':
                bracket_count -= 1
                if bracket_count == 0:
                    list_end = i + 1
                    break
        
        list_content = content[list_start:list_end]
        
        # Extract string literals
        compounds = re.findall(r'"(.*?)"', list_content)
        return compounds
    
    # Extract compounds from the matched section
    list_content = match.group(1)
    compounds = re.findall(r'"(.*?)"', list_content)
    return compounds


def warm_cache():
    """Warm cache with common compounds."""
    print("=" * 80)
    print("🔥 COMPOUND ALIAS CACHE WARMING")
    print("=" * 80)
    
    resolver = get_resolver()
    
    # Get compounds list from config file
    common_compounds = get_common_compounds()
    total = len(common_compounds)
    
    print(f"\n📊 Configuration:")
    print(f"   Compounds to warm: {total}")
    print(f"   PubChem timeout: 5s (default)")
    print(f"   Max retries: 2 (default)")
    print(f"   Delay between requests: 0.2s (default)")
    print(f"\n🔄 Starting cache warming...")
    print(f"   (This may take a few minutes due to rate limiting)\n")
    
    start_time = time.time()
    
    # Resolve all compounds (batch processing with rate limiting)
    results = resolver.resolve_batch(
        common_compounds,
        delay_between_requests=0.2  # Default delay
    )
    
    elapsed_time = time.time() - start_time
    
    # Get cache statistics
    stats = resolver.get_cache_stats()
    
    # Calculate success rate
    successful = sum(1 for v in results.values() if v and v != "")
    failed = total - successful
    
    # Print results
    print("\n" + "=" * 80)
    print("✅ CACHE WARMING COMPLETE!")
    print("=" * 80)
    print(f"\n📊 Statistics:")
    print(f"   Total compounds: {total}")
    print(f"   Successfully resolved: {successful}")
    print(f"   Failed: {failed}")
    print(f"   Success rate: {(successful/total)*100:.1f}%")
    print(f"\n⏱️  Performance:")
    print(f"   Total time: {elapsed_time:.1f}s")
    print(f"   Average time per compound: {elapsed_time/total:.2f}s")
    print(f"   Compounds per second: {total/elapsed_time:.2f}")
    print(f"\n💾 Cache Statistics:")
    print(f"   Cache size: {stats['cache_size']}")
    print(f"   Cache hits: {stats['cache_hits']}")
    print(f"   Cache misses: {stats['cache_misses']}")
    print(f"   Resolution failures: {stats['resolution_failures']}")
    print(f"   Hit rate: {stats['hit_rate']*100:.1f}%")
    
    # Save results to file for inspection
    output_file = Path(__file__).parent / "cache_warm_results.json"
    output_data = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_compounds": total,
        "successful": successful,
        "failed": failed,
        "elapsed_time_seconds": elapsed_time,
        "cache_stats": stats,
        "results": results,
        "failed_compounds": [
            compound for compound, canonical in results.items()
            if not canonical or canonical == ""
        ]
    }
    
    with open(output_file, "w") as f:
        json.dump(output_data, f, indent=2)
    
    print(f"\n💾 Results saved to: {output_file}")
    
    # Print failed compounds if any
    failed_compounds = output_data["failed_compounds"]
    if failed_compounds:
        print(f"\n⚠️  Failed Compounds ({len(failed_compounds)}):")
        for compound in failed_compounds[:10]:  # Show first 10
            print(f"   - {compound}")
        if len(failed_compounds) > 10:
            print(f"   ... and {len(failed_compounds) - 10} more")
    
    # Performance recommendations
    print(f"\n💡 Recommendations:")
    if stats['hit_rate'] > 0.8:
        print(f"   ✅ Excellent cache hit rate ({stats['hit_rate']*100:.1f}%)")
    elif stats['hit_rate'] > 0.5:
        print(f"   ⚠️  Moderate cache hit rate ({stats['hit_rate']*100:.1f}%) - consider expanding common compounds")
    else:
        print(f"   ❌ Low cache hit rate ({stats['hit_rate']*100:.1f}%) - cache warming may not be effective")
    
    if elapsed_time < 60:
        print(f"   ✅ Fast warming (<1 minute)")
    elif elapsed_time < 300:
        print(f"   ⚠️  Moderate warming time ({elapsed_time/60:.1f} minutes)")
    else:
        print(f"   ❌ Slow warming ({elapsed_time/60:.1f} minutes) - consider reducing compounds or increasing delay")
    
    print("\n" + "=" * 80)
    
    return stats


if __name__ == "__main__":
    try:
        stats = warm_cache()
        print("\n✅ Cache warming script completed successfully!")
        sys.exit(0)
    except KeyboardInterrupt:
        print("\n\n⚠️  Cache warming interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Error during cache warming: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

