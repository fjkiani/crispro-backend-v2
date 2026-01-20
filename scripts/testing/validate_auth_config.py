#!/usr/bin/env python3
"""
Validate Auth Configuration
Checks that all required environment variables and dependencies are set up correctly.
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

load_dotenv()

def check_environment_variables():
    """Check required environment variables."""
    print("🔍 Checking Environment Variables...")
    print("=" * 60)
    
    required_vars = {
        "SUPABASE_URL": "Supabase project URL",
        "SUPABASE_ANON_KEY": "Supabase anon key",
        "SUPABASE_JWT_SECRET": "Supabase JWT secret (required for auth)"
    }
    
    optional_vars = {
        "SUPABASE_KEY": "Supabase service role key (optional)"
    }
    
    all_ok = True
    
    for var, description in required_vars.items():
        value = os.getenv(var)
        if value:
            print(f"✅ {var}: {value[:30]}... ({description})")
        else:
            print(f"❌ {var}: NOT SET ({description})")
            all_ok = False
    
    for var, description in optional_vars.items():
        value = os.getenv(var)
        if value:
            print(f"✅ {var}: {value[:30]}... ({description})")
        else:
            print(f"⚠️  {var}: NOT SET ({description}) - Optional")
    
    print()
    return all_ok

def check_dependencies():
    """Check Python dependencies."""
    print("🔍 Checking Python Dependencies...")
    print("=" * 60)
    
    dependencies = {
        "supabase": "Supabase Python client",
        "jwt": "PyJWT for token verification",
        "fastapi": "FastAPI framework"
    }
    
    all_ok = True
    
    for module, description in dependencies.items():
        try:
            if module == "jwt":
                import jwt
            else:
                __import__(module)
            print(f"✅ {module}: Installed ({description})")
        except ImportError:
            print(f"❌ {module}: NOT INSTALLED ({description})")
            all_ok = False
    
    print()
    return all_ok

def check_code_files():
    """Check that auth code files exist."""
    print("🔍 Checking Auth Code Files...")
    print("=" * 60)
    
    files = {
        "api/middleware/auth_middleware.py": "Auth middleware",
        "api/services/auth_service.py": "Auth service",
        "api/routers/auth.py": "Auth router"
    }
    
    all_ok = True
    
    for file_path, description in files.items():
        full_path = project_root / file_path
        if full_path.exists():
            print(f"✅ {file_path}: Exists ({description})")
        else:
            print(f"❌ {file_path}: NOT FOUND ({description})")
            all_ok = False
    
    print()
    return all_ok

def main():
    print("🔍 VALIDATING AUTH CONFIGURATION")
    print("=" * 60)
    print()
    
    env_ok = check_environment_variables()
    deps_ok = check_dependencies()
    files_ok = check_code_files()
    
    print("=" * 60)
    
    if env_ok and deps_ok and files_ok:
        print("✅ All checks passed! Auth is ready to use.")
        print()
        print("📋 Next steps:")
        print("1. Run database schema in Supabase SQL Editor")
        print("2. Test: bash scripts/test_auth_endpoints.sh")
        return 0
    else:
        print("❌ Some checks failed. Please fix the issues above.")
        print()
        if not env_ok:
            print("📋 Fix environment variables:")
            print("   - Add SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_JWT_SECRET to .env")
        if not deps_ok:
            print("📋 Install dependencies:")
            print("   pip install supabase PyJWT python-multipart")
        return 1

if __name__ == "__main__":
    sys.exit(main())








