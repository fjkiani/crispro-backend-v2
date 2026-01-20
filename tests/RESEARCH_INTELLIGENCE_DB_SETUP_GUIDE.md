# 🔧 RESEARCH INTELLIGENCE - DATABASE SETUP GUIDE

**Date**: January 9, 2026  
**Status**: ⚠️ **DATABASE_URL NEEDS CORRECTION**

---

## 🎯 CURRENT STATUS

**✅ Implemented**: Direct PostgreSQL connection bypass (`db_helper.py`)  
**✅ Installed**: `psycopg2-binary` installed  
**⚠️ Issue**: `DATABASE_URL` in `.env` contains placeholder value

---

## 🔍 WHAT I FOUND

**Current `.env` Configuration**:
- ✅ `SUPABASE_URL`: `https://xfhiwodulrbbtfcqneqt.supabase.co` (valid)
- ❌ `DATABASE_URL`: Contains placeholder `db.abcdefghijklmnop.supabase.co` (invalid)
- ❌ `SUPABASE_DB_PASSWORD`: Not set

**Error When Testing**:
```
⚠️ DATABASE_URL connection failed: could not translate host name 
"db.abcdefghijklmnop.supabase.co" to address
```

---

## ✅ SOLUTION: Fix DATABASE_URL

### **Option 1: Use Correct DATABASE_URL (Recommended)**

**Get Connection String from Supabase Dashboard**:
1. Go to: https://supabase.com/dashboard/project/xfhiwodulrbbtfcqneqt/settings/database
2. Scroll to "Connection string" section
3. Select "URI" tab
4. Copy the connection string (format: `postgresql://postgres:[YOUR-PASSWORD]@db.xfhiwodulrbbtfcqneqt.supabase.co:5432/postgres`)
5. Replace `[YOUR-PASSWORD]` with your actual database password
6. Add to `.env`:
   ```bash
   DATABASE_URL=postgresql://postgres:YOUR_ACTUAL_PASSWORD@db.xfhiwodulrbbtfcqneqt.supabase.co:5432/postgres
   ```

### **Option 2: Use SUPABASE_DB_PASSWORD**

**Get Database Password**:
1. Go to: https://supabase.com/dashboard/project/xfhiwodulrbbtfcqneqt/settings/database
2. Find "Database password" section
3. Copy the password (or reset if needed)
4. Add to `.env`:
   ```bash
   SUPABASE_DB_PASSWORD=your_actual_password_here
   ```

**Note**: The code will automatically construct `DATABASE_URL` from `SUPABASE_URL` + `SUPABASE_DB_PASSWORD`

---

## 🧪 TEST AFTER FIXING

```bash
# Test direct PostgreSQL connection
python3 -c "
from dotenv import load_dotenv
load_dotenv()
from api.services.research_intelligence.db_helper import get_postgres_connection

conn = get_postgres_connection()
if conn:
    print('✅ Direct PostgreSQL connection working!')
    conn.close()
else:
    print('❌ Still failing - check DATABASE_URL or SUPABASE_DB_PASSWORD')
"

# Test full API endpoint
python3 tests/test_research_intelligence_api.py
```

**Expected Output**:
```
✅ Direct PostgreSQL connection working!
✅ Database persistence (query_id): PASS
✅ Dossier generation: PASS
✅ Value synthesis: PASS
```

---

## 📋 QUICK CHECKLIST

- [ ] `DATABASE_URL` set correctly (not placeholder) OR `SUPABASE_DB_PASSWORD` set
- [ ] `psycopg2-binary` installed (`pip install psycopg2-binary`)
- [ ] Test connection: `python3 tests/test_research_intelligence_db_direct.py`
- [ ] Test API: `python3 tests/test_research_intelligence_api.py`
- [ ] Verify `query_id` is not `None` in API response

---

## 💡 WHY THIS MATTERS

**Without Correct DATABASE_URL**:
- ❌ Direct PostgreSQL connection fails
- ❌ Falls back to Supabase client (which has PostgREST cache issue)
- ❌ Database saves fail → `query_id` is `None`
- ❌ Dossier and value synthesis skipped

**With Correct DATABASE_URL**:
- ✅ Direct PostgreSQL connection works
- ✅ Bypasses PostgREST cache entirely
- ✅ Database saves succeed → `query_id` is set
- ✅ Dossier and value synthesis generated

---

**Next Step**: Update `.env` with correct `DATABASE_URL` or `SUPABASE_DB_PASSWORD`, then re-test!
