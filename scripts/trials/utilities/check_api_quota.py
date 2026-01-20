#!/usr/bin/env python3
"""
Check Google Gemini API key quota and tier status.
"""
import os
import sys
import asyncio
from pathlib import Path
from dotenv import load_dotenv
import google.generativeai as genai
from google.api_core import exceptions

# Load .env from multiple possible locations
script_dir = Path(__file__).resolve().parent
backend_root = script_dir.parent.parent
root_env = backend_root.parent.parent / ".env"
backend_env = backend_root / ".env"

# Try to load .env files
if root_env.exists():
    load_dotenv(root_env, override=True)
    print(f"✅ Loaded .env from root: {root_env}")
if backend_env.exists():
    load_dotenv(backend_env, override=True)
    print(f"✅ Loaded .env from backend: {backend_env}")

# Get API key from env or command line
api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
if len(sys.argv) > 1:
    api_key = sys.argv[1]  # Allow override via command line

if not api_key:
    print("❌ No API key found. Set GOOGLE_API_KEY or GEMINI_API_KEY in .env, or pass as argument.")
    sys.exit(1)

print(f"\n🔑 Using API key: {api_key[:10]}...{api_key[-4:]}")
print("=" * 60)

# Configure Gemini
try:
    genai.configure(api_key=api_key)
    print("✅ Gemini configured successfully")
except Exception as e:
    print(f"❌ Failed to configure Gemini: {e}")
    sys.exit(1)

# Test with different models to check tier
models_to_test = [
    "gemini-1.5-flash",
    "gemini-1.5-pro",
    "gemini-2.0-flash-exp",
    "gemini-2.5-flash"
]

async def test_model(model_name: str):
    """Test a specific model to check availability and tier."""
    try:
        model = genai.GenerativeModel(model_name)
        
        # Simple test prompt
        test_prompt = "Say 'Hello' in one word."
        
        try:
            response = await asyncio.to_thread(
                model.generate_content,
                test_prompt,
                generation_config={"temperature": 0.1, "max_output_tokens": 10}
            )
            
            if response and response.text:
                print(f"✅ {model_name}: Available (Response: {response.text.strip()})")
                return True, None
            else:
                print(f"⚠️  {model_name}: Available but empty response")
                return True, "empty_response"
                
        except exceptions.ResourceExhausted as e:
            error_str = str(e).lower()
            if "quota" in error_str or "429" in error_str:
                print(f"⚠️  {model_name}: Rate limited (429) - Free tier or quota exceeded")
                return False, "rate_limited"
            else:
                print(f"❌ {model_name}: Resource exhausted - {e}")
                return False, "resource_exhausted"
                
        except exceptions.PermissionDenied as e:
            print(f"❌ {model_name}: Permission denied (403) - {e}")
            return False, "permission_denied"
            
        except exceptions.NotFound as e:
            print(f"⚠️  {model_name}: Not found (404) - Model may not exist or not available for this tier")
            return False, "not_found"
            
        except Exception as e:
            error_str = str(e).lower()
            if "403" in error_str or "permission" in error_str:
                print(f"❌ {model_name}: Permission denied - {e}")
                return False, "permission_denied"
            elif "429" in error_str or "quota" in error_str or "rate limit" in error_str:
                print(f"⚠️  {model_name}: Rate limited - {e}")
                return False, "rate_limited"
            else:
                print(f"❌ {model_name}: Error - {e}")
                return False, "unknown_error"
                
    except Exception as e:
        print(f"❌ {model_name}: Failed to initialize - {e}")
        return False, "init_error"

async def main():
    print("\n🧪 Testing models to determine API tier...\n")
    
    results = {}
    for model in models_to_test:
        available, error = await test_model(model)
        results[model] = {"available": available, "error": error}
        await asyncio.sleep(1)  # Small delay between tests
    
    print("\n" + "=" * 60)
    print("📊 SUMMARY:")
    print("=" * 60)
    
    available_models = [m for m, r in results.items() if r["available"]]
    unavailable_models = [m for m, r in results.items() if not r["available"]]
    
    if available_models:
        print(f"✅ Available models ({len(available_models)}):")
        for m in available_models:
            print(f"   - {m}")
    
    if unavailable_models:
        print(f"\n❌ Unavailable models ({len(unavailable_models)}):")
        for m in unavailable_models:
            error = results[m]["error"]
            print(f"   - {m}: {error}")
    
    # Tier inference
    print("\n🎯 TIER INFERENCE:")
    if "gemini-2.5-flash" in available_models or "gemini-2.0-flash-exp" in available_models:
        print("   → Likely TIER 1 (paid) - Advanced models available")
    elif "gemini-1.5-pro" in available_models:
        print("   → Likely TIER 1 (paid) - Pro model available")
    elif "gemini-1.5-flash" in available_models:
        print("   → Could be FREE TIER or TIER 1 - Flash model available")
    else:
        print("   → Unknown tier - No models available")
    
    # Rate limit check
    rate_limited = any(r["error"] == "rate_limited" for r in results.values())
    if rate_limited:
        print("\n⚠️  RATE LIMITING DETECTED:")
        print("   → If free tier: 5 requests/minute limit")
        print("   → If tier 1: Check quota dashboard for limits")
        print("   → Recommendation: Use 15s delay between calls for free tier")
    
    permission_denied = any(r["error"] == "permission_denied" for r in results.values())
    if permission_denied:
        print("\n❌ PERMISSION DENIED DETECTED:")
        print("   → API key may be invalid, leaked, or revoked")
        print("   → Check Google Cloud Console for key status")
        print("   → Generate a new API key if needed")

if __name__ == "__main__":
    asyncio.run(main())

