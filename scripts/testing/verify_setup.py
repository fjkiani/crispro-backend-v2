#!/usr/bin/env python3
"""Quick verification script to check if environment is ready for testing."""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load .env
env_path = Path(__file__).parent / '.env'
if env_path.exists():
    load_dotenv(env_path)
else:
    load_dotenv()

print("🔍 Environment Verification")
print("=" * 60)

# Check API keys
gemini_key = os.getenv("GEMINI_API_KEY")
google_key = os.getenv("GOOGLE_API_KEY")
print(f"GEMINI_API_KEY: {'✅ SET' if gemini_key else '❌ NOT SET'}")
print(f"GOOGLE_API_KEY: {'✅ SET' if google_key else '❌ NOT SET'}")
print(f"Will use: {'GEMINI_API_KEY' if gemini_key else ('GOOGLE_API_KEY' if google_key else 'NONE')}")

# Check AstraDB
astra_token = os.getenv("ASTRA_DB_APPLICATION_TOKEN")
astra_endpoint = os.getenv("ASTRA_DB_API_ENDPOINT")
print(f"\nAstraDB:")
print(f"  Token: {'✅ SET' if astra_token else '❌ NOT SET'}")
print(f"  Endpoint: {'✅ SET' if astra_endpoint else '❌ NOT SET'}")

# Check Neo4j
neo4j_uri = os.getenv("NEO4J_URI")
neo4j_pass = os.getenv("NEO4J_PASSWORD")
print(f"\nNeo4j:")
print(f"  URI: {'✅ SET' if neo4j_uri else '❌ NOT SET'}")
print(f"  Password: {'✅ SET' if neo4j_pass else '❌ NOT SET'}")

# Test import
print(f"\n📦 Code Status:")
try:
    from api.services.clinical_trial_search_service import ClinicalTrialSearchService
    import inspect
    source = inspect.getsource(ClinicalTrialSearchService.__init__)
    if "GEMINI_API_KEY" in source and "GOOGLE_API_KEY" in source:
        print("  ✅ Service code supports both GEMINI_API_KEY and GOOGLE_API_KEY")
    else:
        print("  ⚠️  Service code may not support GEMINI_API_KEY")
except Exception as e:
    print(f"  ❌ Could not verify service code: {e}")

print("\n" + "=" * 60)
if gemini_key or google_key:
    print("✅ Environment ready - backend restart required to load fix")
else:
    print("❌ Missing API keys - check .env file")
    sys.exit(1)
