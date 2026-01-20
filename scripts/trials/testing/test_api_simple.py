#!/usr/bin/env python3
"""
Simple test to verify API key works and check quota.
"""
import os
import sys
import asyncio
from pathlib import Path
from dotenv import load_dotenv
import google.generativeai as genai
from google.api_core import exceptions
import time

# Load .env
script_dir = Path(__file__).resolve().parent
backend_root = script_dir.parent.parent
root_env = backend_root.parent.parent / ".env"
backend_env = backend_root / ".env"

if root_env.exists():
    load_dotenv(root_env, override=True)
if backend_env.exists():
    load_dotenv(backend_env, override=True)

# Get API key
api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
if len(sys.argv) > 1:
    api_key = sys.argv[1]

if not api_key:
    print("❌ No API key found")
    sys.exit(1)

print(f"🔑 Testing API key: {api_key[:10]}...{api_key[-4:]}\n")

# Configure
genai.configure(api_key=api_key)

# Try to list available models first
print("📋 Attempting to list available models...")
try:
    models = genai.list_models()
    print("✅ Can list models:")
    for m in models:
        if 'generateContent' in m.supported_generation_methods:
            print(f"   - {m.name}")
except Exception as e:
    print(f"⚠️  Cannot list models: {e}")

print("\n🧪 Testing single API call with gemini-1.5-flash...")
print("   (Waiting 5 seconds to avoid immediate rate limit...)\n")
time.sleep(5)

try:
    model = genai.GenerativeModel("gemini-1.5-flash")
    response = model.generate_content("Say hello in one word.")
    
    if response and response.text:
        print(f"✅ SUCCESS: API key works!")
        print(f"   Response: {response.text.strip()}")
        print(f"   → This suggests TIER 1 (paid) or valid free tier")
    else:
        print("⚠️  Empty response")
        
except exceptions.ResourceExhausted as e:
    error_str = str(e)
    print(f"❌ Resource Exhausted (429):")
    print(f"   {error_str}")
    
    if "quota" in error_str.lower():
        print("\n   → QUOTA EXCEEDED")
        print("   → Check Google Cloud Console for quota limits")
    elif "rate limit" in error_str.lower() or "429" in error_str:
        print("\n   → RATE LIMIT HIT")
        print("   → Free tier: 5 requests/minute")
        print("   → Tier 1: Check quota dashboard")
    
except exceptions.PermissionDenied as e:
    print(f"❌ Permission Denied (403):")
    print(f"   {error_str}")
    print("\n   → API key may be invalid, leaked, or revoked")
    print("   → Generate new key in Google Cloud Console")
    
except exceptions.NotFound as e:
    print(f"⚠️  Model Not Found (404):")
    print(f"   {e}")
    print("\n   → Model name may be incorrect")
    print("   → Try: gemini-pro, gemini-1.5-flash, gemini-1.5-pro")
    
except Exception as e:
    print(f"❌ Error: {e}")
    print(f"   Type: {type(e).__name__}")

