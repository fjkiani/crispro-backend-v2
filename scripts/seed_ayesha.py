#!/usr/bin/env python3
"""
Seed script for Ayesha patient data.

Purpose: Create Ayesha user account and patient profile with complete clinical data
Usage: python3 scripts/seed_ayesha.py

Requirements:
- Supabase configured (SUPABASE_URL, SUPABASE_SERVICE_KEY in .env)
- User must be created in Supabase Auth first (via dashboard or signup endpoint)
- Then run this script to populate patient profile data
"""

import asyncio
import os
import sys
from datetime import datetime
from typing import Dict, Any

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.services.patient_service import get_patient_service
from api.services.auth_service import get_auth_service
from api.config import get_config

logger = get_config().logger


# Ayesha's clinical profile (from AYESHA_SESSION_CONTEXT_PLAN.md)
AYESHA_PROFILE = {
    "patient_id": "AYESHA-001",
    "disease": "ovarian_cancer_hgs",
    "stage": "IVB",
    "treatment_line": 0,  # Treatment-naive
    "ca125_value": 2842.0,
    "ca125_baseline": 2842.0,
    "ca125_last_updated": datetime.utcnow().isoformat(),
    "germline_status": "negative",  # Ambry 38-gene panel negative
    "has_ascites": True,
    "has_peritoneal_disease": True,
    "location_state": "NY",
    "ecog_status": 1,
    "tumor_context": {
        "level": "L0",  # Pre-NGS (no tumor NGS yet)
        "completeness": 0.2,  # Only germline + CA-125 available
        "germline_status": "negative",
        "somatic_mutations": [],  # Pending NGS
        "tmb_score": None,
        "msi_status": None,
        "hrd_score": None
    },
    "treatment_history": []
}


async def seed_ayesha(user_email: str = "ak@ak.com", user_id: str = None):
    """
    Seed Ayesha patient data.
    
    Args:
        user_email: Email of user to seed (must exist in Supabase Auth)
        user_id: Optional user ID (if not provided, will look up by email)
    """
    logger.info("🌱 Starting Ayesha seed script...")
    
    # Get services
    auth_service = get_auth_service()
    patient_service = get_patient_service()
    
    # Step 1: Get or verify user exists
    if not user_id:
        logger.info(f"🔍 Looking up user by email: {user_email}")
        user_profile = await auth_service.get_user_profile_by_email(user_email)
        if not user_profile:
            logger.error(f"❌ User {user_email} not found in Supabase. Please create user first via:")
            logger.error("   1. Supabase Dashboard → Authentication → Users → Add user")
            logger.error("   2. Or use /api/auth/signup endpoint")
            return False
        
        user_id = user_profile["id"]
        logger.info(f"✅ Found user: {user_id[:8]}... ({user_email})")
    else:
        logger.info(f"✅ Using provided user_id: {user_id[:8]}...")
    
    # Step 2:  profile already exists
    existing_profile = await patient_service.get_patient_profile_by_user_id(user_id)
    if existing_profile:
        logger.warning(f"⚠️  Patient profile already exists for user {user_id[:8]}...")
        response = input("Do you want to update it? (y/n): ")
        if response.lower() != 'y':
            logger.info("❌ Aborted. Exiting.")
            return False
        
        # Update existing profile
        logger.info("🔄 Updating existing patient profile...")
        updated = await patient_service.update_patient_profile_by_user_id(
            user_id,
            AYESHA_PROFILE
        )
        if updated:
            logger.info("✅ Patient profile updated successfully!")
            return True
        else:
            logger.error("❌ Failed to update patient profile")
            return False
    
    # Step 3: Create patient profile
    logger.info("📝 Creating patient profile...")
    profile = await patient_service.create_patient_profile(user_id, AYES  
    if profile:
        logger.info("✅ Patient profile created successfully!")
        logger.info(f"   Patient ID: {profile.get('patient_id', 'N/A')}")
        logger.info(f"   Disease: {profile.get('disease', 'N/A')}")
        logger.info(f"   Stage: {profile.get('stage', 'N/A')}")
        logger.info(f"   CA-125: {profile.get('ca125_value', 'N/A')} U/mL")
        logger.info(f"   Germline Status: {profile.get('germline_status', 'N/A')}")
        return True
    else:
        logger.error("❌ Failed to create patient profile")
        return False


async def main():
    """CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Seed Ayesha patient data")
    parser.add_argument(
        "--email",
        type=str,
        default="ak@ak.com",
        help="Email of user to seed (default: ak@ak.com)"
    )
    parser.add_argument(
        "--user-id",
        type=str,
        default=None,
        help="Optional user ID (if provided, skips email lookup)"
      
    args = parser.parse_args()
    
    success = await seed_ayesha(args.email, args.user_id)
    
    if success:
        logger.info("\n✅ Seed script completed successfully!")
        logger.info("\n📋 Next steps:")
        logger.info("   1. Verify patient profile in Supabase Dashboard")
        logger.info("   2. Test login with: ak@ak.com / <password>")
        logger.info("   3. Navigate to /ayesha-trials or /ayesha-complete-care")
        sys.exit(0)
    else:
        logger.error("\n❌ Seed script failed!")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
