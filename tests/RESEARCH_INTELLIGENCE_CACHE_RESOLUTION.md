# Research Intelligence - PostgREST Cache Resolution

## Current Status

✅ **Schema Applied**: Tables `research_intelligence_queries` and `research_intelligence_dossiers` exist in PostgreSQL  
❌ **PostgREST Cache**: Supabase API layer hasn't refreshed schema cache yet  
❌ **Direct PostgreSQL**: DNS resolution failing (network/firewall issue)

## The Problem

After running `.cursor/SUPABASE_RESEARCH_INTELLIGENCE_SCHEMA.sql`, the tables exist in PostgreSQL, but Supabase's PostgREST API layer maintains a schema cache that hasn't refreshed yet.

**Error**: `PGRST205: Could not find the table 'public.research_intelligence_queries' in the schema cache`

## Solutions

### Option 1: Manual PostgREST Cache Refresh (Recommended)

1. **Go to Supabase Dashboard**: https://supabase.com/dashboard/project/xfhiwodulrbbtfcqneqt
2. **Navigate to**: Settings → API → PostgREST
3. **Click**: "Refresh Schema Cache" or "Reload Schema"
4. **Wait**: 10-30 seconds for cache to refresh
5. **Test**: Run `python3 tests/test_fallback_persistence.py` again

### Option 2: Trigger Cache Refresh via SQL

Run this in Supabase SQL Editor:

```sql
-- Force PostgREST to refresh by querying the table
SELECT COUNT(*) FROM public.research_intelligence_queries;
SELECT COUNT(*) FROM public.research_intelligence_dossiers;

-- Sometimes a simple ALTER helps trigger refresh
ALTER TABLE public.research_intelligence_queries SET SCHEMA public;
ALTER TABLE public.research_intelligence_dossiers SET SCHEMA public;
```

### Option 3: Wait for Auto-Refresh

PostgREST typically refreshes its cache automatically within 1-5 minutes after schema changes. If it's been longer, use Option 1 or 2.

### Option 4: Verify Table Exists (Diagnostic)

Run this in Supabase SQL Editor to confirm tables exist:

```sql
SELECT 
    table_name, 
    table_schema 
FROM information_schema.tables 
WHERE table_schema = 'public' 
AND table_name IN ('research_intelligence_queries', 'research_intelligence_dossiers');
```

Expected output:
```
research_intelligence_queries | public
research_intelligence_dossiers | public
```

## Direct PostgreSQL Connection Issue

The direct PostgreSQL connection (`psycopg2`) is failing due to DNS resolution:
- **Error**: `could not translate host name "db.xfhiwodulrbbtfcqneqt.supabase.co" to address`
- **Cause**: Network/firewall blocking direct PostgreSQL connections
- **Impact**: We must rely on Supabase client (PostgREST API) for now

**Note**: Some Supabase projects restrict direct PostgreSQL connections for security. This is normal and expected. The Supabase client (PostgREST) is the recommended approach.

## Next Steps

1. **Refresh PostgREST cache** using Option 1 or 2 above
2. **Re-run test**: `python3 tests/test_fallback_persistence.py`
3. **Expected**: Query should save successfully via Supabase client
4. **Then test API**: `python3 tests/test_research_intelligence_api.py`

## Verification

After cache refresh, verify with:

```bash
python3 tests/test_fallback_persistence.py
```

Expected output:
```
✅ Query saved successfully via fallback! Query ID: [uuid]
```
