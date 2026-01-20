# Cohere Rate Limit Fix - Sync Script

## Problem
Cohere trial keys are limited to **40 API calls/minute**. The sync script was:
- Processing 10 trials per batch (10 API calls per batch)
- Only waiting 2 seconds between batches
- This allows ~30 batches/minute = 300 calls/minute (way over limit!)

## Solution Applied
1. **Dynamic delay calculation**: `batch_size × 1.5 seconds + 3 second buffer`
   - Example: batch_size=10 → 18 seconds between batches
   - This ensures we stay under 40 calls/minute

2. **Retry logic with exponential backoff**:
   - Catches rate limit errors (429, "rate limit", "quota")
   - Retries up to 3 times with exponential backoff: 5s, 10s, 20s
   - Gracefully handles failures

3. **Small delays between embedding calls**:
   - 0.25 seconds between individual calls within a batch
   - Helps smooth out the rate limiting

## Current Status
- ✅ Rate limiting fix applied
- ⏸️ Sync in progress (blocked by rate limits)
- 📊 **59/1,397 trials synced** (4.2% complete)

## Options to Complete Full Sync

### Option 1: Continue with Current Approach (Recommended)
- **Time estimate**: ~5-6 hours (with 18 second delays)
- **Pros**: No code changes needed, respects rate limits
- **Cons**: Slow but reliable

### Option 2: Reduce Batch Size
- **Change**: Reduce batch_size from 10 to 4
- **Result**: 4 calls/batch → 6 seconds + buffer = 10 seconds between batches
- **Time estimate**: ~4-5 hours
- **Command**: `python seed_astradb_from_sqlite.py --batch-size 4 --limit 0`

### Option 3: Use Production Cohere Key (If Available)
- **Change**: Set `COHERE_API_KEY` environment variable to production key
- **Rate limit**: 5,000 calls/minute (vs 40 for trial key)
- **Time estimate**: ~5-10 minutes
- **Command**: Same as current, just with production key

### Option 4: Resume from Last Successful Batch
- **Modification needed**: Add `--skip` parameter to resume from specific batch
- **Time estimate**: Remaining batches only
- **Status**: Requires code changes

## Recommendation
**Option 2 (reduce batch size to 4)** is the best balance:
- Faster than current approach
- No additional dependencies
- More conservative rate limiting (safer)
- Can resume if interrupted

## Next Steps
1. Stop current sync (Ctrl+C)
2. Run with smaller batch size: `python seed_astradb_from_sqlite.py --batch-size 4 --limit 0`
3. Let it run overnight or in background
4. Monitor progress in logs

Alternatively, if production Cohere key is available, use Option 3 for fastest sync.
