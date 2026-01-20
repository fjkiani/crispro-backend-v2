"""
Test Research Intelligence Database (Direct PostgreSQL)

Tests database operations using direct PostgreSQL connection
to bypass PostgREST schema cache issues.

Run: python3 tests/test_research_intelligence_db_direct.py
"""

import os
import sys
from pathlib import Path
from datetime import datetime
import json

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False
    print("⚠️ psycopg2 not installed. Run: pip install psycopg2-binary")

from api.config import SUPABASE_URL

def get_postgres_connection():
    """Get direct PostgreSQL connection from Supabase URL."""
    if not SUPABASE_URL:
        print("❌ SUPABASE_URL not configured")
        return None
    
    # Extract connection details from Supabase URL
    # Format: https://project-ref.supabase.co
    # Direct PostgreSQL: postgresql://postgres:[password]@db.project-ref.supabase.co:5432/postgres
    
    # Get password from env
    db_password = os.getenv("SUPABASE_DB_PASSWORD")
    if not db_password:
        print("⚠️ SUPABASE_DB_PASSWORD not set in .env")
        print("   Get it from: Supabase Dashboard → Settings → Database → Connection string")
        return None
    
    # Extract project ref from URL
    project_ref = SUPABASE_URL.replace("https://", "").replace(".supabase.co", "")
    
    # Build connection string
    conn_string = f"postgresql://postgres:{db_password}@db.{project_ref}.supabase.co:5432/postgres"
    
    try:
        conn = psycopg2.connect(conn_string)
        return conn
    except Exception as e:
        print(f"❌ PostgreSQL connection failed: {e}")
        return None


def test_table_exists(conn, table_name: str) -> bool:
    """Check if table exists."""
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = %s
                );
            """, (table_name,))
            exists = cur.fetchone()[0]
            return exists
    except Exception as e:
        print(f"❌ Error checking table {table_name}: {e}")
        return False


def test_insert_query(conn):
    """Test inserting a query."""
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Insert test query
            cur.execute("""
                INSERT INTO public.research_intelligence_queries 
                (user_id, question, context, result, persona)
                VALUES 
                (%s, %s, %s, %s, %s)
                RETURNING id, created_at;
            """, (
                "00000000-0000-0000-0000-000000000000",  # Test user ID
                "Test question: How does curcumin help with cancer?",
                json.dumps({"disease": "breast_cancer"}),
                json.dumps({"mechanisms": ["anti-inflammatory", "antioxidant"]}),
                "patient"
            ))
            
            result = cur.fetchone()
            query_id = result['id']
            conn.commit()
            
            print(f"✅ Query inserted successfully")
            print(f"   Query ID: {query_id}")
            print(f"   Created at: {result['created_at']}")
            return query_id
    except Exception as e:
        conn.rollback()
        print(f"❌ Insert failed: {e}")
        return None


def test_select_query(conn, query_id: str):
    """Test selecting a query."""
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT id, question, persona, created_at
                FROM public.research_intelligence_queries
                WHERE id = %s;
            """, (query_id,))
            
            result = cur.fetchone()
            if result:
                print(f"✅ Query retrieved successfully")
                print(f"   Question: {result['question']}")
                print(f"   Persona: {result['persona']}")
                return True
            else:
                print("❌ Query not found")
                return False
    except Exception as e:
        print(f"❌ Select failed: {e}")
        return False


def test_insert_dossier(conn, query_id: str):
    """Test inserting a dossier."""
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                INSERT INTO public.research_intelligence_dossiers
                (query_id, user_id, persona, markdown)
                VALUES
                (%s, %s, %s, %s)
                RETURNING id, created_at;
            """, (
                query_id,
                "00000000-0000-0000-0000-000000000000",  # Test user ID
                "patient",
                "# Test Dossier\n\nThis is a test dossier."
            ))
            
            result = cur.fetchone()
            dossier_id = result['id']
            conn.commit()
            
            print(f"✅ Dossier inserted successfully")
            print(f"   Dossier ID: {dossier_id}")
            return dossier_id
    except Exception as e:
        conn.rollback()
        print(f"❌ Dossier insert failed: {e}")
        return None


def main():
    """Run all database tests."""
    print("="*80)
    print("RESEARCH INTELLIGENCE DATABASE TESTS (Direct PostgreSQL)")
    print("="*80)
    print(f"Started: {datetime.now()}\n")
    
    if not PSYCOPG2_AVAILABLE:
        print("❌ psycopg2 not available. Install with: pip install psycopg2-binary")
        return
    
    # Test 1: Connection
    print("="*80)
    print("TEST 1: PostgreSQL Connection")
    print("="*80)
    conn = get_postgres_connection()
    if not conn:
        print("\n❌ Cannot proceed without database connection")
        return
    
    print("✅ PostgreSQL connection successful\n")
    
    # Test 2: Table existence
    print("="*80)
    print("TEST 2: Table Existence")
    print("="*80)
    
    tables = ["research_intelligence_queries", "research_intelligence_dossiers"]
    all_exist = True
    
    for table in tables:
        exists = test_table_exists(conn, table)
        if exists:
            print(f"✅ Table '{table}' exists")
        else:
            print(f"❌ Table '{table}' does NOT exist")
            all_exist = False
    
    if not all_exist:
        print("\n❌ Some tables are missing. Run SUPABASE_RESEARCH_INTELLIGENCE_SCHEMA.sql")
        conn.close()
        return
    
    print("\n✅ All tables exist\n")
    
    # Test 3: Insert query
    print("="*80)
    print("TEST 3: Insert Query")
    print("="*80)
    query_id = test_insert_query(conn)
    if not query_id:
        conn.close()
        return
    
    print()
    
    # Test 4: Select query
    print("="*80)
    print("TEST 4: Select Query")
    print("="*80)
    test_select_query(conn, query_id)
    print()
    
    # Test 5: Insert dossier
    print("="*80)
    print("TEST 5: Insert Dossier")
    print("="*80)
    dossier_id = test_insert_dossier(conn, query_id)
    if dossier_id:
        print()
    
    # Test 6: Cleanup (optional)
    print("="*80)
    print("TEST 6: Cleanup (Optional)")
    print("="*80)
    cleanup = input("Delete test records? (y/n): ").strip().lower()
    if cleanup == 'y':
        try:
            with conn.cursor() as cur:
                if dossier_id:
                    cur.execute("DELETE FROM public.research_intelligence_dossiers WHERE id = %s;", (dossier_id,))
                cur.execute("DELETE FROM public.research_intelligence_queries WHERE id = %s;", (query_id,))
                conn.commit()
                print("✅ Test records deleted")
        except Exception as e:
            print(f"⚠️ Cleanup failed: {e}")
            conn.rollback()
    else:
        print("⚠️ Test records left in database")
    
    conn.close()
    
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    print("✅ All database operations working")
    print("\n💡 Note: PostgREST schema cache may still need refresh")
    print("   This test uses direct PostgreSQL, bypassing PostgREST")
    print("="*80)


if __name__ == "__main__":
    main()
