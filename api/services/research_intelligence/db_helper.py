"""
Direct PostgreSQL Helper for Research Intelligence

Bypasses PostgREST schema cache by using direct PostgreSQL connection.
Falls back to Supabase client if direct connection unavailable.
"""

import os
import logging
from typing import Dict, Any, Optional
from datetime import datetime
import uuid
import json

logger = logging.getLogger(__name__)

# Try to import psycopg2
try:
    import psycopg2
    from psycopg2.extras import RealDictCursor, Json
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False
    logger.warning("⚠️ psycopg2 not installed. Run: pip install psycopg2-binary")

from api.config import SUPABASE_URL
from api.services.agent_manager import get_supabase_client

def get_postgres_connection():
    """Get direct PostgreSQL connection from Supabase."""
    if not PSYCOPG2_AVAILABLE:
        return None
    
    # Try DATABASE_URL first
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        try:
            conn = psycopg2.connect(database_url)
            logger.info("✅ Direct PostgreSQL connection via DATABASE_URL")
            return conn
        except Exception as e:
            logger.warning(f"⚠️ DATABASE_URL connection failed: {e}")
    
    # Fallback: Construct from SUPABASE_URL + password
    if not SUPABASE_URL:
        return None
    
    db_password = os.getenv("SUPABASE_DB_PASSWORD")
    if not db_password:
        logger.warning("⚠️ SUPABASE_DB_PASSWORD not set. Cannot use direct PostgreSQL connection.")
        return None
    
    # Extract project ref from URL
    # Format: https://project-ref.supabase.co
    project_ref = SUPABASE_URL.replace("https://", "").replace(".supabase.co", "")
    
    # Try direct connection first (port 5432)
    conn_string_direct = f"postgresql://postgres:{db_password}@db.{project_ref}.supabase.co:5432/postgres"
    try:
        conn = psycopg2.connect(conn_string_direct, connect_timeout=10)
        logger.info("✅ Direct PostgreSQL connection via SUPABASE_URL (port 5432)")
        return conn
    except Exception as e:
        logger.warning(f"⚠️ Direct connection (port 5432) failed: {e}")
        # Try connection pooler (port 6543) as fallback
        conn_string_pooler = f"postgresql://postgres:{db_password}@db.{project_ref}.supabase.co:6543/postgres"
        try:
            conn = psycopg2.connect(conn_string_pooler, connect_timeout=10)
            logger.info("✅ PostgreSQL connection via connection pooler (port 6543)")
            return conn
        except Exception as e2:
            logger.warning(f"⚠️ Connection pooler (port 6543) also failed: {e2}")
            logger.warning(f"   Attempted host: db.{project_ref}.supabase.co")
            return None


def save_query_direct(query_data: Dict[str, Any]) -> Optional[str]:
    """
    Save query to database using direct PostgreSQL connection.
    Returns query_id if successful, None otherwise.
    """
    conn = get_postgres_connection()
    if not conn:
        return None
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            query_id = str(uuid.uuid4())
            
            # Insert query
            cur.execute("""
                INSERT INTO public.research_intelligence_queries (
                    id, user_id, session_id, question, context, options,
                    result, provenance, persona, created_at, updated_at, last_accessed_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                ) RETURNING id
            """, (
                query_id,
                query_data.get("user_id"),
                query_data.get("session_id"),
                query_data.get("question"),
                Json(query_data.get("context", {})),
                Json(query_data.get("options", {})),
                Json(query_data.get("result", {})),
                Json(query_data.get("provenance", {})),
                query_data.get("persona", "patient"),
                datetime.utcnow(),
                datetime.utcnow(),
                datetime.utcnow()
            ))
            
            result = cur.fetchone()
            conn.commit()
            
            if result:
                logger.info(f"✅ Saved query {query_id} via direct PostgreSQL")
                return query_id
            return None
            
    except Exception as e:
        conn.rollback()
        logger.error(f"❌ Failed to save query via direct PostgreSQL: {e}")
        return None
    finally:
        conn.close()


def save_dossier_direct(dossier_data: Dict[str, Any]) -> Optional[str]:
    """
    Save dossier to database using direct PostgreSQL connection.
    Returns dossier_id if successful, None otherwise.
    """
    conn = get_postgres_connection()
    if not conn:
        return None
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            dossier_id = str(uuid.uuid4())
            
            # Insert dossier
            cur.execute("""
                INSERT INTO public.research_intelligence_dossiers (
                    id, query_id, user_id, persona, markdown, pdf_path,
                    shareable_link, shareable_expires_at, is_public,
                    created_at, updated_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                ) RETURNING id
            """, (
                dossier_id,
                dossier_data.get("query_id"),
                dossier_data.get("user_id"),
                dossier_data.get("persona", "patient"),
                dossier_data.get("markdown"),
                dossier_data.get("pdf_path"),
                dossier_data.get("shareable_link"),
                dossier_data.get("shareable_expires_at"),
                dossier_data.get("is_public", False),
                datetime.utcnow(),
                datetime.utcnow()
            ))
            
            result = cur.fetchone()
            conn.commit()
            
            if result:
                logger.info(f"✅ Saved dossier {dossier_id} via direct PostgreSQL")
                return dossier_id
            return None
            
    except Exception as e:
        conn.rollback()
        logger.error(f"❌ Failed to save dossier via direct PostgreSQL: {e}")
        return None
    finally:
        conn.close()


def update_query_dossier_id(query_id: str, dossier_id: str) -> bool:
    """
    Update query with dossier_id using direct PostgreSQL connection.
    Returns True if successful, False otherwise.
    """
    conn = get_postgres_connection()
    if not conn:
        return False
    
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE public.research_intelligence_queries
                SET dossier_id = %s, updated_at = %s
                WHERE id = %s
            """, (dossier_id, datetime.utcnow(), query_id))
            
            conn.commit()
            logger.info(f"✅ Updated query {query_id} with dossier_id {dossier_id}")
            return True
            
    except Exception as e:
        conn.rollback()
        logger.error(f"❌ Failed to update query dossier_id: {e}")
        return False
    finally:
        conn.close()


def save_query_with_fallback(query_data: Dict[str, Any]) -> Optional[str]:
    """
    Save query using direct PostgreSQL connection first,
    fall back to Supabase client if direct connection unavailable.
    """
    # Try direct PostgreSQL first
    query_id = save_query_direct(query_data)
    if query_id:
        return query_id
    
    # Fallback to Supabase client
    logger.info("⚠️ Direct PostgreSQL unavailable, trying Supabase client...")
    supabase = get_supabase_client()
    if not supabase:
        logger.warning("⚠️ Both direct PostgreSQL and Supabase client unavailable")
        return None
    
    try:
        response = supabase.table("research_intelligence_queries").insert(query_data).execute()
        if response.data:
            query_id = response.data[0]["id"]
            logger.info(f"✅ Saved query {query_id} via Supabase client")
            return query_id
    except Exception as e:
        logger.warning(f"⚠️ Supabase client save failed: {e}")
    
    return None


def save_dossier_with_fallback(dossier_data: Dict[str, Any]) -> Optional[str]:
    """
    Save dossier using direct PostgreSQL connection first,
    fall back to Supabase client if direct connection unavailable.
    """
    # Try direct PostgreSQL first
    dossier_id = save_dossier_direct(dossier_data)
    if dossier_id:
        return dossier_id
    
    # Fallback to Supabase client
    logger.info("⚠️ Direct PostgreSQL unavailable, trying Supabase client...")
    supabase = get_supabase_client()
    if not supabase:
        logger.warning("⚠️ Both direct PostgreSQL and Supabase client unavailable")
        return None
    
    try:
        response = supabase.table("research_intelligence_dossiers").insert(dossier_data).execute()
        if response.data:
            dossier_id = response.data[0]["id"]
            logger.info(f"✅ Saved dossier {dossier_id} via Supabase client")
            return dossier_id
    except Exception as e:
        logger.warning(f"⚠️ Supabase client save failed: {e}")
    
    return None
