"""
Configuration for Trial MoA Tagging
===================================
Centralized configuration - easy to tune without touching code.
"""

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import List

# Paths (relative to backend root)
BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DB_PATH = BACKEND_ROOT / "data" / "clinical_trials.db"
OUTPUT_PATH = BACKEND_ROOT / "api" / "resources" / "trial_moa_vectors.json"


@dataclass
class TaggingConfig:
    """Configuration for trial tagging."""
    
    # Model settings
    model: str = "gemini-2.5-flash"  # Tier 1 compatible
    fallback_models: List[str] = field(default_factory=lambda: [
        "gemini-2.5-pro",
        "gemini-2.0-flash"
    ])
    
    # Batching - KEY OPTIMIZATION: Tag multiple trials per API call
    trials_per_prompt: int = 5  # How many trials to include in one prompt
    concurrent_batches: int = 2  # How many API calls to run in parallel
    
    # Rate limiting
    delay_between_calls: float = 3.0  # Seconds between API calls (tier 1)
    delay_on_rate_limit: float = 15.0  # Seconds to wait on 429 error
    max_retries: int = 3
    
    # Quality thresholds
    min_confidence: float = 0.5  # Minimum confidence to accept tagging
    
    # Processing limits
    max_trials: int = 200
    
    @classmethod
    def for_free_tier(cls) -> "TaggingConfig":
        """
        Config for free tier.
        
        FREE TIER LIMITS (as of 2025):
        - 5 requests/minute
        - 20 requests/day (!!!)
        - 1M tokens/month
        
        With 20 requests/day and 10 trials/request = 200 trials/day max
        """
        return cls(
            delay_between_calls=60.0,  # 1 request/minute to be very safe
            concurrent_batches=1,  # No parallel calls
            trials_per_prompt=10,  # More trials per call to maximize daily quota
            max_trials=200,  # Max possible with 20 requests/day
        )
    
    @classmethod
    def for_tier_1(cls) -> "TaggingConfig":
        """Config for tier 1 (higher limits)."""
        return cls(
            delay_between_calls=2.0,  # Fast
            concurrent_batches=3,  # Parallel calls
            trials_per_prompt=5,  # Smaller batches for better quality
        )
    
    @classmethod
    def from_env(cls) -> "TaggingConfig":
        """Load config from environment variables."""
        return cls(
            model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
            delay_between_calls=float(os.getenv("TAGGING_DELAY", "3.0")),
            concurrent_batches=int(os.getenv("TAGGING_CONCURRENCY", "2")),
            trials_per_prompt=int(os.getenv("TRIALS_PER_PROMPT", "5")),
            max_trials=int(os.getenv("MAX_TRIALS", "200")),
        )


# MoA Pathways (7D vector)
MOA_PATHWAYS = ["ddr", "mapk", "pi3k", "vegf", "her2", "io", "efflux"]

MOA_DESCRIPTIONS = {
    "ddr": "DNA Damage Repair (PARP, ATR, ATM, CHK1/2, WEE1 inhibitors)",
    "mapk": "RAS/MAPK pathway (BRAF, MEK, KRAS inhibitors)",
    "pi3k": "PI3K/AKT pathway (PI3K, AKT, mTOR inhibitors)",
    "vegf": "Angiogenesis (VEGF, VEGFR inhibitors, bevacizumab)",
    "her2": "HER2 pathway (trastuzumab, pertuzumab, HER2 inhibitors)",
    "io": "Immunotherapy (PD-1, PD-L1, CTLA-4 inhibitors)",
    "efflux": "Drug efflux (P-gp, ABCB1, MDR1 inhibitors)",
}

