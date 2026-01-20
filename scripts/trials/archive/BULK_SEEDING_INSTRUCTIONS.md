# Bulk Trial Seeding Instructions

## Status: ✅ Script Working

The bulk seeding script is now functional and successfully fetching trials from ClinicalTrials.gov API.

## Quick Start

### Run in Background (Recommended for 5,000-10,000 trials)

```bash
cd oncology-coPilot/oncology-backend-minimal

# Run in background with nohup
nohup python3 scripts/bulk_seed_trials.py --target 10000 > logs/bulk_seeding_$(date +%Y%m%d_%H%M%S).log 2>&1 &

# Check progress
tail -f logs/bulk_seeding_*.log
```

### Run in Foreground (for testing)

```bash
cd oncology-coPilot/oncology-backend-minimal
python3 scripts/bulk_seed_trials.py --target 5000 --max-strategies 5
```

## Current Status

- **Current trials in database**: ~1,200
- **Target**: 5,000-10,000 trials
- **Needed**: 3,800-8,800 more trials

## Query Strategies

The script uses 15 different query strategies to get diverse trials:

1. Ovarian Cancer - Recruiting (2,000 target)
2. Ovarian Cancer - All Status (1,500 target)
3. Breast Cancer - Recruiting (2,000 target)
4. Lung Cancer - Recruiting (2,000 target)
5. Colorectal Cancer - Recruiting (1,000 target)
6. Pancreatic Cancer - Recruiting (800 target)
7. DNA Repair - PARP Inhibitors (1,000 target)
8. DNA Repair - ATR Inhibitors (500 target)
9. Immunotherapy - Checkpoint Inhibitors (1,500 target)
10. Basket Trials - Tumor Agnostic (500 target)
11. Precision Medicine - Biomarker Driven (800 target)
12. Rare Mutations - MBD4 (200 target)
13. Rare Mutations - TP53 (500 target)
14. High TMB / MSI-H (400 target)
15. Phase 2/3 - All Cancers (2,000 target)

**Total potential**: ~17,200 trials (will deduplicate)

## Performance

- **Rate**: ~100 trials/minute (with rate limiting)
- **Estimated time for 5,000 trials**: ~50 minutes
- **Estimated time for 10,000 trials**: ~100 minutes

## Features

✅ **Deduplication**: Automatically skips trials already in database  
✅ **Rate Limiting**: Respects API limits (2 req/sec)  
✅ **Progress Tracking**: Real-time progress updates  
✅ **Error Handling**: Continues on errors, logs failures  
✅ **Post-Processing Filtering**: Filters by status, phase, study type after fetch  

## Monitoring

### Check Current Count

```bash
cd oncology-coPilot/oncology-backend-minimal
python3 -c "import sqlite3; conn = sqlite3.connect('data/clinical_trials.db'); cursor = conn.cursor(); cursor.execute('SELECT COUNT(*) FROM trials'); print(f'Current trials: {cursor.fetchone()[0]}'); conn.close()"
```

### Check Recruiting Trials

```bash
python3 -c "import sqlite3; conn = sqlite3.connect('data/clinical_trials.db'); cursor = conn.cursor(); cursor.execute(\"SELECT COUNT(*) FROM trials WHERE status LIKE '%RECRUITING%'\"); print(f'Recruiting trials: {cursor.fetchone()[0]}'); conn.close()"
```

## Troubleshooting

### If script stops early:
- Check log file for errors
- API may have rate limited - wait 5 minutes and restart
- Network issues - check internet connection

### If not reaching target:
- Run with more strategies: `--max-strategies 15` (all strategies)
- Increase individual strategy limits in the script
- Run multiple times (deduplication will prevent duplicates)

## Next Steps After Seeding

1. **Verify count**: Check database has 5,000-10,000 trials
2. **Check quality**: Verify trials have required fields (title, status, eligibility)
3. **Update embeddings**: If using vector search, re-embed new trials
4. **Test queries**: Verify advanced query endpoint works with new data

## Notes

- The script uses simplified API queries (no complex filters) and filters in post-processing for reliability
- Trials are inserted with `INSERT OR REPLACE` to handle duplicates gracefully
- The script tracks progress and will stop early if target is reached











