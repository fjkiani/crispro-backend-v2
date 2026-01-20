#!/usr/bin/env python3
"""
Verify Supabase Auth Status
Checks if Supabase Auth is enabled and configured correctly.
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import httpx

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables
load_dotenv()

def check_supabase_auth():
    """Check if Supabase Auth is enabled and accessible."""
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_ANON_KEY")
    
    if not supabase_url:
        print("❌ SUPABASE_URL not found in environment variables")
        print("   Set SUPABASE_URL in .env file")
        return False
    
    if not supabase_key:
        print("❌ SUPABASE_KEY or SUPABASE_ANON_KEY not found in environment variables")
        print("   Set SUPABASE_KEY or SUPABASE_ANON_KEY in .env file")
        return False
    
    print(f"✅ Supabase URL: {supabase_url[:50]}...")
    print(f"✅ Supabase Key: {supabase_key[:20]}...")
    
    # Check if Auth API is accessible
    try:
        auth_url = f"{supabase_url.rstrip('/')}/auth/v1/health"
        response = httpx.get(auth_url, timeout=5.0)
        
        if response.status_code == 200:
            print("✅ Supabase Auth is accessible")
            return True
        else:
            print(f"⚠️  Supabase Auth returned status {response.status_code}")
            print("   Auth might not be enabled or URL is incorrect")
            return False
    except Exception as e:
        print(f"❌ Failed to connect to Supabase Auth: {e}")
        print("\n📋 SETUP INSTRUCTIONS:")
        print("1. Go to your Supabase project dashboard")
        print("2. Navigate to Authentication → Settings")
        print("3. Ensure 'Enable Email Auth' is turned ON")
        print("4. Copy your Project URL and anon key")
        print("5. Add to .env file:")
        print("   SUPABASE_URL=https://your-project.supabase.co")
        print("   SUPABASE_ANON_KEY=your-anon-key")
        return False

def check_jwt_secret():
    """Check if JWT secret is available."""
    # Note: JWT secret is typically in Supabase dashboard, not in .env
    # We'll check if we can get it from Supabase API or need manual setup
    print("\n📋 JWT SECRET SETUP:")
    print("1. Go to Supabase Dashboard → Settings → API")
    print("2. Find 'JWT Secret' (Service Role Secret)")
    print("3. Add to .env file:")
    print("   SUPABASE_JWT_SECRET=your-jwt-secret")
    print("\n⚠️  Note: JWT secret is needed for backend token verification")
    print("   Without it, backend cannot verify JWT tokens from frontend")

def main():
    print("🔍 VERIFYING SUPABASE AUTH STATUS")
    print("=" * 60)
    
    auth_enabled = check_supabase_auth()
    check_jwt_secret()
    
    print("\n" + "=" * 60)
    if auth_enabled:
        print("✅ Supabase Auth appears to be enabled and accessible")
        print("\n📋 NEXT STEPS:")
        print("1. Ensure JWT secret is in .env (SUPABASE_JWT_SECRET)")
        print("2. Run SaaS schema migration (see schemas/database_schema.sql)")
        print("3. Start Component 1 implementation")
    else:
        print("❌ Supabase Auth needs setup")
        print("\n📋 NEXT STEPS:")
        print("1. Follow setup instructions above")
        print("2. Verify Auth is accessible")
        print("3. Add JWT secret to .env")
        print("4. Then proceed with Component 1")

if __name__ == "__main__":
    main()








