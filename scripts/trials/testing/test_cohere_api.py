"""Test Cohere API key and find the correct model name."""
import cohere

api_key = 's7cLuA3QHm20mSx4w5T6DZTvjQ0kscQuETumSKoG'
client = cohere.Client(api_key=api_key)

print('🧪 Testing Cohere API...')
print(f'   API key: {api_key[:10]}...{api_key[-4:]}')

# Try different model names based on Cohere's documentation
models_to_try = [
    'command-r-plus',
    'command-r',
    'command',
    'command-r7-plus',
    'command-r7b-plus',
]

working_model = None
for model_name in models_to_try:
    try:
        print(f'\n   Testing {model_name}...')
        response = client.chat(
            model=model_name,
            message='Say hello in one word.',
            max_tokens=5
        )
        print(f'   ✅ SUCCESS with {model_name}: {response.text.strip()}')
        working_model = model_name
        break
    except cohere.errors.NotFoundError:
        print(f'   ❌ {model_name}: Model not found')
    except cohere.errors.RateLimitError as e:
        print(f'   ⚠️ {model_name}: Rate limited (but model exists)')
        print(f'      Error: {str(e)[:200]}')
        working_model = model_name  # Model exists, just rate limited
        break
    except Exception as e:
        error_str = str(e)
        print(f'   ❌ {model_name}: {type(e).__name__}')
        print(f'      Error: {error_str[:200]}')

if working_model:
    print(f'\n✅ Working model: {working_model}')
    print('   → Ready to proceed with trial tagging')
    print('   → Rate limit: 20 requests/min = 3 seconds between calls')
else:
    print('\n❌ No working model found')
    print('   → Check API key or Cohere model names')

