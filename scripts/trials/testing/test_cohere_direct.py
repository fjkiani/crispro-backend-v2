"""Test Cohere API directly via HTTP to understand the correct model names."""
import requests
import json

api_key = 's7cLuA3QHm20mSx4w5T6DZTvjQ0kscQuETumSKoG'
base_url = 'https://api.cohere.com/v1'

headers = {
    'Authorization': f'Bearer {api_key}',
    'Content-Type': 'application/json',
    'Accept': 'application/json'
}

print('🧪 Testing Cohere API directly via HTTP...')
print(f'   API key: {api_key[:10]}...{api_key[-4:]}')

# Try to list available models (if endpoint exists)
try:
    print('\n   Checking for models endpoint...')
    response = requests.get(f'{base_url}/models', headers=headers, timeout=10)
    print(f'   Status: {response.status_code}')
    if response.status_code == 200:
        models = response.json()
        print(f'   ✅ Available models: {json.dumps(models, indent=2)[:500]}')
    else:
        print(f'   ❌ Models endpoint not available: {response.text[:200]}')
except Exception as e:
    print(f'   ⚠️ Models endpoint check failed: {e}')

# Try chat endpoint with command-r-plus
print('\n   Testing chat endpoint with command-r-plus...')
chat_payload = {
    'model': 'command-r-plus',
    'message': 'Say hello in one word.',
    'max_tokens': 5
}
try:
    response = requests.post(
        f'{base_url}/chat',
        headers=headers,
        json=chat_payload,
        timeout=30
    )
    print(f'   Status: {response.status_code}')
    if response.status_code == 200:
        result = response.json()
        print(f'   ✅ SUCCESS: {result.get("text", result)[:200]}')
        print('   → Using command-r-plus with chat endpoint')
    else:
        print(f'   ❌ Error: {response.text[:500]}')
        # Try to parse error to see what models are available
        try:
            error_json = response.json()
            if 'message' in error_json:
                print(f'   Error message: {error_json["message"]}')
        except:
            pass
except Exception as e:
    print(f'   ❌ Request failed: {e}')

# Try generate endpoint instead
print('\n   Testing generate endpoint with command-r-plus...')
generate_payload = {
    'model': 'command-r-plus',
    'prompt': 'Say hello in one word.',
    'max_tokens': 5
}
try:
    response = requests.post(
        f'{base_url}/generate',
        headers=headers,
        json=generate_payload,
        timeout=30
    )
    print(f'   Status: {response.status_code}')
    if response.status_code == 200:
        result = response.json()
        print(f'   ✅ SUCCESS: {result.get("generations", [{}])[0].get("text", result)[:200]}')
        print('   → Using command-r-plus with generate endpoint')
    else:
        print(f'   ❌ Error: {response.text[:500]}')
except Exception as e:
    print(f'   ❌ Request failed: {e}')

