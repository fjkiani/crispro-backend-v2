# 🔄 Trial Sync In Progress

## Status
**Sync started**: Background process running to sync all 1,397 trials from SQLite to AstraDB

## Command
```bash
cd oncology-coPilot/oncology-backend-minimal
PYTHONPATH=/Users/fahadkiani/Desktop/development/crispr-assistant-main/oncology-coPilot/oncology-backend-minimal:$PYTHONPATH \
python3 scripts/trials/utilities/seed_astradb_from_sqlite.py --batch-size 10 --limit 0
```

## Monitoring

### Check Progress
```bash
# View logs
tail -f /tmp/trial_sync.log

# Check process
ps aux | grep seed_astradb_from_sqlite

# Check AstraDB count
cd oncology-coPilot/oncology-backend-minimal
python3 -c "
import sys; sys.path.insert(0, '.')
from api.services.database_connections import get_db_connections
db = get_db_connections()
vdb = db.get_vector_db_connection()
col = vdb.get_collection('clinical_trials_eligibility2')
all_docs = list(col.find({}, limit=2000))
print(f'Trials in AstraDB: {len(all_docs)}')
"
```

## Rate Limiting
- **Cohere API limit**: 40 calls/minute (trial key)
- **Batch size**: 10 trials per batch
- **Delay**: 2 seconds between batches
- **Effective rate**: ~30 batches/minute (stays under limit)

## Estimated Time
- **Total trials**: 1,397
- **Batches**: ~140 batches (1,397 / 10)
- **Time per batch**: ~2-3 seconds (embedding generation + delay)
- **Estimated total time**: ~7-10 minutes

## Expected Results
- All 1,397 trials from SQLite synced to AstraDB
- All trials will have vectors stored correctly
- Vector search will work for all trials
- Includes all 87 tagged ovarian trials

## If Sync Fails
If the sync stops due to rate limits or errors:
1. Check logs: `tail -100 /tmp/trial_sync.log`
2. Resume sync (it will skip already-synced trials if run again)
3. Or wait for rate limit to reset and continue

## Completion
Once sync completes:
- Check final count: Should show ~1,397 trials in AstraDB
- Test search: Vector search should return results
- Ayesha's trials: All 87 tagged ovarian trials will be searchable
