#!/usr/bin/env python3
"""
Migration Utility for Linking Existing Data to Authenticated Users
Links anonymous analysis_history and sessions to authenticated users.
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from typing import List, Dict, Any
import asyncio

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from api.services.supabase_service import supabase

load_dotenv()

async def link_analysis_history_to_user(user_id: str, analysis_keys: List[str] = None):
    """
    Link existing analysis_history entries to authenticated user.
    
    Args:
        user_id: Authenticated user ID
        analysis_keys: List of analysis keys to link (if None, links all with null user_id)
    """
    if not supabase.enabled:
        print("⚠️  Supabase not enabled, skipping migration")
        return
    
    try:
        # Find analyses to link
        if analysis_keys:
            # Link specific analyses
            for key in analysis_keys:
                await supabase.update(
                    "analysis_history",
                    {"user_id": user_id},
                    {"key": key}
                )
            print(f"✅ Linked {len(analysis_keys)} analyses to user {user_id[:8]}...")
        else:
            # Link all anonymous analyses (use with caution!)
            print("⚠️  Linking ALL anonymous analyses to user (use with caution)")
            # This would require a custom SQL query in Supabase
            print("   Run this SQL in Supabase SQL Editor:")
            print(f"   UPDATE analysis_history SET user_id = '{user_id}' WHERE user_id IS NULL;")
    
    except Exception as e:
        print(f"❌ Failed to link analyses: {e}")

async def link_sessions_to_user(user_id: str, session_ids: List[str] = None):
    """
    Link existing user_sessions to authenticated user.
    
    Args:
        user_id: Authenticated user ID
        session_ids: List of session IDs to link (if None, links all with null user_id)
    """
    if not supabase.enabled:
        print("⚠️  Supabase not enabled, skipping migration")
        return
    
    try:
        if session_ids:
            # Link specific sessions
            for session_id in session_ids:
                await supabase.update(
                    "user_sessions",
                    {"user_id": user_id},
                    {"id": session_id}
                )
            print(f"✅ Linked {len(session_ids)} sessions to user {user_id[:8]}...")
        else:
            print("⚠️  Linking ALL anonymous sessions to user (use with caution)")
            print("   Run this SQL in Supabase SQL Editor:")
            print(f"   UPDATE user_sessions SET user_id = '{user_id}' WHERE user_id IS NULL;")
    
    except Exception as e:
        print(f"❌ Failed to link sessions: {e}")

async def create_user_profile_from_signup(user_id: str, email: str, metadata: Dict[str, Any] = None):
    """
    Create user profile when user signs up.
    Called automatically by Supabase trigger, but can be used manually.
    """
    if not supabase.enabled:
        print("⚠️  Supabase not enabled, skipping profile creation")
        return
    
    try:
        profile_data = {
            "id": user_id,
            "email": email,
            "tier": "free",
            "role": metadata.get("role", "researcher") if metadata else "researcher",
            "institution": metadata.get("institution") if metadata else None,
            "full_name": metadata.get("full_name") if metadata else None,
        }
        
        await supabase.insert("user_profiles", [profile_data])
        
        # Create default quotas
        quota_data = {
            "user_id": user_id,
            "tier": "free",
            "variant_analyses_limit": 10,
            "drug_queries_limit": 5,
            "food_queries_limit": 3,
            "clinical_trials_limit": 0,
        }
        
        await supabase.insert("user_quotas", [quota_data])
        
        print(f"✅ Created profile and quotas for user {user_id[:8]}...")
    
    except Exception as e:
        print(f"❌ Failed to create profile: {e}")

async def main():
    """CLI for migration utilities."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Migrate existing data to authenticated users")
    parser.add_argument("--user-id", required=True, help="Authenticated user ID")
    parser.add_argument("--link-analyses", action="store_true", help="Link analysis_history to user")
    parser.add_argument("--analysis-keys", nargs="+", help="Specific analysis keys to link")
    parser.add_argument("--link-sessions", action="store_true", help="Link user_sessions to user")
    parser.add_argument("--session-ids", nargs="+", help="Specific session IDs to link")
    
    args = parser.parse_args()
    
    print("🔄 MIGRATING EXISTING DATA TO USER")
    print("=" * 60)
    
    if args.link_analyses:
        await link_analysis_history_to_user(args.user_id, args.analysis_keys)
    
    if args.link_sessions:
        await link_sessions_to_user(args.user_id, args.session_ids)
    
    print("\n✅ Migration complete")

if __name__ == "__main__":
    asyncio.run(main())

