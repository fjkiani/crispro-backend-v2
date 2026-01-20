#!/usr/bin/env python3
"""Quick test of direct PostgreSQL connection."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from api.services.research_intelligence.db_helper import get_postgres_connection
import os

print('🔍 Testing Direct PostgreSQL Connection...')
print(f'SUPABASE_URL: {os.getenv("SUPABASE_URL")}')
print(f'SUPABASE_DB_PASSWORD: {"SET" if os.getenv("SUPABASE_DB_PASSWORD") else "NOT SET"}')
print()

conn = get_postgres_connection()
if conn:
    print('✅ Direct PostgreSQL connection successful!')
    try:
        cur = conn.cursor()
        # Test table existence
        cur.execute("""
            SELECT COUNT(*) 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = 'research_intelligence_queries';
        """)
        exists = cur.fetchone()[0] > 0
        print(f'✅ Table exists: {exists}')
        
        if exists:
            cur.execute("SELECT COUNT(*) FROM research_intelligence_queries;")
            count = cur.fetchone()[0]
            print(f'✅ Can query research_intelligence_queries table: {count} records found')
        
        cur.close()
        conn.close()
        print('✅ Connection closed successfully')
    except Exception as e:
        print(f'❌ Query failed: {e}')
        import traceback
        traceback.print_exc()
        if conn:
            conn.close()
else:
    print('❌ Direct PostgreSQL connection failed')
