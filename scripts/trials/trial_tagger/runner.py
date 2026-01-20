"""
Trial Tagging Runner
=====================
Orchestrates the tagging process with progress tracking.
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from .config import TaggingConfig
from .db import Trial, get_untagged_trials, load_existing_vectors, save_vectors, get_tagged_nct_ids
from .llm import GeminiTagger

logger = logging.getLogger(__name__)


class TaggingRunner:
    """
    Orchestrates efficient batch tagging.
    
    Key features:
    - Batches multiple trials per API call
    - Concurrent batch processing
    - Progress saving after each batch
    - Detailed statistics
    """
    
    def __init__(self, config: Optional[TaggingConfig] = None):
        self.config = config or TaggingConfig.from_env()
        self.tagger: Optional[GeminiTagger] = None
        
        # Stats
        self.stats = {
            "started_at": None,
            "completed_at": None,
            "trials_processed": 0,
            "trials_tagged": 0,
            "trials_failed": 0,
            "api_calls": 0,
            "batches": 0,
        }
    
    async def run(self, limit: Optional[int] = None, nct_ids: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Run the tagging process.
        
        Args:
            limit: Max trials to process (default: config.max_trials)
            nct_ids: Specific NCT IDs to tag (optional)
        
        Returns:
            Dict of newly tagged trials
        """
        self.stats["started_at"] = datetime.utcnow()
        limit = limit or self.config.max_trials
        
        # Initialize tagger
        self.tagger = GeminiTagger(self.config)
        
        # Get trials to tag
        if nct_ids:
            # TODO: Fetch specific trials from DB
            trials = get_untagged_trials(limit=len(nct_ids))
            trials = [t for t in trials if t.nct_id in nct_ids]
        else:
            trials = get_untagged_trials(limit=limit)
        
        if not trials:
            logger.info("No trials to tag")
            return {}
        
        logger.info(f"🚀 Starting tagging of {len(trials)} trials")
        logger.info(f"   Config: {self.config.trials_per_prompt} trials/prompt, {self.config.concurrent_batches} concurrent")
        
        # Load existing vectors
        all_vectors = load_existing_vectors()
        new_vectors = {}
        
        # Split into batches
        batches = self._create_batches(trials)
        total_batches = len(batches)
        
        logger.info(f"   Created {total_batches} batches")
        
        # Process batches
        for batch_idx in range(0, total_batches, self.config.concurrent_batches):
            concurrent_batches = batches[batch_idx:batch_idx + self.config.concurrent_batches]
            batch_nums = range(batch_idx + 1, batch_idx + len(concurrent_batches) + 1)
            
            logger.info(f"\n📦 Processing batches {list(batch_nums)} of {total_batches}")
            
            # Run concurrent batches
            tasks = [self._process_batch(batch, i) for i, batch in zip(batch_nums, concurrent_batches)]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Collect results
            for result in results:
                if isinstance(result, dict):
                    new_vectors.update(result)
                elif isinstance(result, Exception):
                    logger.error(f"Batch failed: {result}")
            
            # Save progress
            if new_vectors:
                all_vectors.update(new_vectors)
                save_vectors(all_vectors)
                logger.info(f"   💾 Saved {len(all_vectors)} total vectors ({len(new_vectors)} new)")
            
            # Rate limiting between batch groups
            if batch_idx + self.config.concurrent_batches < total_batches:
                await asyncio.sleep(self.config.delay_between_calls)
        
        # Final stats
        self.stats["completed_at"] = datetime.utcnow()
        self.stats["trials_tagged"] = len(new_vectors)
        self.stats["api_calls"] = self.tagger.api_calls
        self.stats["batches"] = total_batches
        
        self._print_summary(new_vectors)
        
        return new_vectors
    
    def _create_batches(self, trials: List[Trial]) -> List[List[Trial]]:
        """Split trials into batches for API calls."""
        batch_size = self.config.trials_per_prompt
        return [trials[i:i + batch_size] for i in range(0, len(trials), batch_size)]
    
    async def _process_batch(self, batch: List[Trial], batch_num: int) -> Dict[str, Any]:
        """Process a single batch of trials."""
        nct_ids = [t.nct_id for t in batch]
        logger.info(f"   Batch {batch_num}: {len(batch)} trials ({nct_ids[0]}...{nct_ids[-1]})")
        
        results = await self.tagger.tag_batch(batch)
        
        tagged = len(results)
        failed = len(batch) - tagged
        
        self.stats["trials_processed"] += len(batch)
        self.stats["trials_failed"] += failed
        
        if tagged > 0:
            logger.info(f"   ✅ Batch {batch_num}: {tagged}/{len(batch)} tagged")
        if failed > 0:
            logger.warning(f"   ⚠️ Batch {batch_num}: {failed} failed/low-confidence")
        
        return results
    
    def _print_summary(self, new_vectors: Dict[str, Any]) -> None:
        """Print tagging summary."""
        elapsed = (self.stats["completed_at"] - self.stats["started_at"]).total_seconds()
        
        logger.info("\n" + "=" * 60)
        logger.info("📊 TAGGING SUMMARY")
        logger.info("=" * 60)
        logger.info(f"   ✅ Trials tagged: {self.stats['trials_tagged']}")
        logger.info(f"   ❌ Trials failed: {self.stats['trials_failed']}")
        logger.info(f"   🔄 API calls: {self.stats['api_calls']}")
        logger.info(f"   📦 Batches: {self.stats['batches']}")
        logger.info(f"   ⏱️  Time: {elapsed:.1f}s ({elapsed/60:.1f} min)")
        
        if self.stats['trials_tagged'] > 0:
            avg = elapsed / self.stats['trials_tagged']
            logger.info(f"   📈 Avg: {avg:.2f}s/trial")
            
            # Efficiency comparison
            old_time = self.stats['trials_tagged'] * 15  # Old: 15s per trial
            logger.info(f"   🚀 Speedup: {old_time/elapsed:.1f}x faster than sequential")
        
        logger.info("=" * 60)


async def run_tagging(
    limit: int = 200,
    tier: str = "auto",
    nct_ids: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Main entry point for trial tagging.
    
    Args:
        limit: Max trials to tag
        tier: "free", "tier1", or "auto" (detect from rate limits)
        nct_ids: Specific NCT IDs to tag
    
    Returns:
        Dict of newly tagged trials
    """
    # Select config based on tier
    if tier == "free":
        config = TaggingConfig.for_free_tier()
    elif tier == "tier1":
        config = TaggingConfig.for_tier_1()
    else:
        config = TaggingConfig.from_env()
    
    config.max_trials = limit
    
    runner = TaggingRunner(config)
    return await runner.run(limit=limit, nct_ids=nct_ids)

