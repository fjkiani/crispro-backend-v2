"""
Unit Tests for Compound Alias Resolver

Tests for dynamic compound name resolution using PubChem API.

Author: CrisPRO Platform
Date: November 5, 2025
"""

import pytest
import time
import requests
from unittest.mock import Mock, patch
from api.services.compound_alias_resolver import CompoundAliasResolver, get_resolver


@pytest.fixture
def resolver():
    """Create a fresh resolver instance for each test."""
    return CompoundAliasResolver()


class TestCompoundAliasResolver:
    """Test suite for CompoundAliasResolver service."""
    
    def test_resolve_common_compound_vitamin_d(self, resolver):
        """Test resolution of Vitamin D (well-known compound)."""
        result = resolver.resolve_compound_alias("Vitamin D")
        
        # PubChem may return different vitamin D forms
        # Accept any of these as valid
        valid_forms = [
            "Cholecalciferol",
            "Ergocalciferol", 
            "Vitamin D",
            "Vitamin D3",
            "Vitamin D2"
        ]
        
        assert result in valid_forms, f"Expected Vitamin D form, got: {result}"
        print(f"✅ Vitamin D resolved to: {result}")
    
    def test_resolve_common_compound_curcumin(self, resolver):
        """Test resolution of Curcumin/Turmeric."""
        result = resolver.resolve_compound_alias("Turmeric")
        
        # Turmeric should resolve to Curcumin or related compound
        assert result is not None
        assert len(result) > 0
        print(f"✅ Turmeric resolved to: {result}")
    
    def test_resolve_with_cache(self, resolver):
        """Test that cache hit works correctly."""
        # First call - cache miss
        result1 = resolver.resolve_compound_alias("Curcumin")
        stats_after_first = resolver.get_cache_stats()
        
        assert stats_after_first["cache_misses"] == 1
        assert stats_after_first["cache_hits"] == 0
        
        # Second call - should hit cache
        result2 = resolver.resolve_compound_alias("Curcumin")
        stats_after_second = resolver.get_cache_stats()
        
        assert result1 == result2, "Cached result should match original"
        assert stats_after_second["cache_hits"] == 1
        assert stats_after_second["hit_rate"] == 0.5  # 1 hit, 1 miss
        
        print(f"✅ Cache working: {result1} (cached)")
    
    def test_resolve_unknown_compound(self, resolver):
        """Test fallback for unknown/non-existent compound."""
        unknown = "ThisDoesNotExist12345XYZ"
        result = resolver.resolve_compound_alias(unknown)
        
        # Should fallback to original name
        assert result == unknown
        
        # Should be cached to avoid repeated lookups
        assert unknown.lower() in resolver._cache
        
        print(f"✅ Unknown compound fallback: {result}")
    
    def test_batch_resolution(self, resolver):
        """Test batch resolution of multiple compounds."""
        compounds = ["Vitamin D", "Curcumin", "Resveratrol"]
        
        start_time = time.time()
        results = resolver.resolve_batch(compounds)
        elapsed = time.time() - start_time
        
        # Verify all compounds resolved
        assert len(results) == 3
        assert all(compound in results for compound in compounds)
        assert all(v is not None for v in results.values())
        assert all(len(v) > 0 for v in results.values())
        
        # Verify rate limiting (should take at least 0.4s for 3 compounds with 0.2s delay)
        # Allow some tolerance for timing variability
        assert elapsed >= 0.3, f"Batch processing too fast ({elapsed}s), rate limiting may not be working"
        
        print(f"✅ Batch resolution: {results}")
        print(f"   Elapsed: {elapsed:.2f}s")
    
    def test_cache_normalization(self, resolver):
        """Test that cache normalization works (case-insensitive, whitespace-trimmed)."""
        # These should all hit the same cache entry
        variants = [
            "Vitamin D",
            "vitamin d",
            "VITAMIN D",
            "  Vitamin D  ",
            " vitamin d "
        ]
        
        results = [resolver.resolve_compound_alias(v) for v in variants]
        
        # All should return the same result
        assert all(r == results[0] for r in results), "Cache normalization failed"
        
        # After first call, all subsequent should be cache hits
        stats = resolver.get_cache_stats()
        assert stats["cache_hits"] >= 4  # At least 4 out of 5 should be cache hits
        
        print(f"✅ Cache normalization working: {stats['cache_hits']} hits")
    
    def test_singleton_pattern(self):
        """Test that get_resolver() returns singleton instance."""
        resolver1 = get_resolver()
        resolver2 = get_resolver()
        
        assert resolver1 is resolver2, "get_resolver() should return same instance"
        
        print("✅ Singleton pattern working")
    
    def test_cache_stats(self, resolver):
        """Test that cache statistics are tracked correctly."""
        # Initial state
        stats = resolver.get_cache_stats()
        assert stats["cache_size"] == 0
        assert stats["cache_hits"] == 0
        assert stats["cache_misses"] == 0
        
        # Make some queries
        resolver.resolve_compound_alias("Vitamin D")  # Miss
        resolver.resolve_compound_alias("Vitamin D")  # Hit
        resolver.resolve_compound_alias("Curcumin")   # Miss
        
        stats = resolver.get_cache_stats()
        assert stats["cache_size"] == 2
        assert stats["cache_hits"] == 1
        assert stats["cache_misses"] == 2
        assert stats["hit_rate"] == 1/3
        
        print(f"✅ Cache stats: {stats}")
    
    def test_clear_cache(self, resolver):
        """Test that cache can be cleared."""
        # Populate cache
        resolver.resolve_compound_alias("Vitamin D")
        assert len(resolver._cache) > 0
        
        # Clear cache
        resolver.clear_cache()
        assert len(resolver._cache) == 0
        
        print("✅ Cache cleared successfully")
    
    @patch('requests.get')
    def test_retry_logic_on_timeout(self, mock_get, resolver):
        """Test that retry logic works on timeout errors."""
        # Mock timeout on first 2 attempts, success on 3rd
        mock_get.side_effect = [
            requests.exceptions.Timeout(),
            requests.exceptions.Timeout(),
            Mock(
                ok=True,
                json=lambda: {
                    'InformationList': {
                        'Information': [
                            {'Synonym': ['Cholecalciferol']}
                        ]
                    }
                }
            )
        ]
        
        result = resolver.resolve_compound_alias("Vitamin D", retries=2)
        
        # Should eventually succeed
        assert result == "Cholecalciferol"
        assert mock_get.call_count == 3  # 2 timeouts + 1 success
        
        print("✅ Retry logic working on timeout")
    
    @patch('requests.get')
    def test_rate_limit_backoff(self, mock_get, resolver):
        """Test exponential backoff on rate limit (429) errors."""
        # Mock rate limit on first attempt, success on second
        mock_get.side_effect = [
            Mock(ok=False, status_code=429),
            Mock(
                ok=True,
                json=lambda: {
                    'InformationList': {
                        'Information': [
                            {'Synonym': ['Curcumin']}
                        ]
                    }
                }
            )
        ]
        
        start_time = time.time()
        result = resolver.resolve_compound_alias("Curcumin", retries=1)
        elapsed = time.time() - start_time
        
        # Should succeed after retry
        assert result == "Curcumin"
        
        # Should have waited (exponential backoff: 2^0 = 1 second)
        # Allow some tolerance for timing
        assert elapsed >= 0.9, f"Backoff too short ({elapsed}s)"
        
        print(f"✅ Rate limit backoff working ({elapsed:.2f}s delay)")


# Integration test (requires network access)
@pytest.mark.integration
class TestCompoundAliasResolverIntegration:
    """Integration tests requiring real PubChem API access."""
    
    def test_real_pubchem_api_vitamin_d(self):
        """Test real PubChem API call for Vitamin D."""
        resolver = CompoundAliasResolver()
        result = resolver.resolve_compound_alias("Vitamin D")
        
        assert result is not None
        assert len(result) > 0
        
        print(f"✅ Real API call successful: Vitamin D → {result}")
    
    def test_real_pubchem_api_batch(self):
        """Test real PubChem API batch resolution."""
        resolver = CompoundAliasResolver()
        compounds = [
            "Vitamin D",
            "Curcumin",
            "Resveratrol",
            "Quercetin",
            "Genistein"
        ]
        
        results = resolver.resolve_batch(compounds)
        
        assert len(results) == len(compounds)
        assert all(results[c] is not None for c in compounds)
        
        # Print results
        print("✅ Real API batch resolution:")
        for original, canonical in results.items():
            print(f"   {original} → {canonical}")
        
        # Check cache performance
        stats = resolver.get_cache_stats()
        print(f"   Cache stats: {stats}")

