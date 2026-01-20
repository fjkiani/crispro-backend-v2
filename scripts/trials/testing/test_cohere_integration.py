"""Test Cohere integration for trial tagging."""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load .env from root
root_env = Path("/Users/fahadkiani/Desktop/development/crispr-assistant-main/.env")
if root_env.exists():
    load_dotenv(root_env, override=True)
    print(f"✅ Loaded .env from: {root_env}")

# Get API key
api_key = os.getenv("COHERE_API_KEY")
print(f"\n🔑 API Key: {api_key[:10] if api_key else 'None'}...{api_key[-4:] if api_key else ''}")

# Test Cohere
try:
    import cohere
    client = cohere.Client(api_key=api_key)
    
    print("\n🧪 Testing Cohere Chat API with command-r7b-12-2024...")
    response = client.chat(
        model="command-r7b-12-2024",
        message="Say hello in one word.",
        max_tokens=5
    )
    print(f"✅ SUCCESS: {response.text.strip()}")
    print("\n🎉 Cohere integration working!")
    
except Exception as e:
    error_msg = str(e)
    print(f"\n❌ ERROR: {type(e).__name__}")
    print(f"   Message: {error_msg[:300]}")

