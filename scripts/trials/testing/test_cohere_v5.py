"""Test Cohere v5 API with generate method."""
import cohere

api_key = 's7cLuA3QHm20mSx4w5T6DZTvjQ0kscQuETumSKoG'
client = cohere.Client(api_key=api_key)

print('🧪 Testing Cohere v5 API...')
print(f'   API key: {api_key[:10]}...{api_key[-4:]}')

# Try generate method (more universal than chat)
try:
    print('\n   Testing generate() method...')
    response = client.generate(
        model='command-r-plus',
        prompt='Say hello in one word.',
        max_tokens=5
    )
    print(f'   ✅ SUCCESS with generate(): {response.generations[0].text.strip()}')
    print('   → Using generate() method for trial tagging')
    working_method = 'generate'
    working_model = 'command-r-plus'
except Exception as e:
    error_str = str(e)
    print(f'   ❌ generate() failed: {type(e).__name__}')
    print(f'      Error: {error_str[:300]}')
    
    # Try command-r instead
    try:
        print('\n   Testing generate() with command-r...')
        response = client.generate(
            model='command-r',
            prompt='Say hello in one word.',
            max_tokens=5
        )
        print(f'   ✅ SUCCESS with command-r: {response.generations[0].text.strip()}')
        working_method = 'generate'
        working_model = 'command-r'
    except Exception as e2:
        print(f'   ❌ command-r also failed: {type(e2).__name__}')
        
        # Try chat_stream (async chat API)
        try:
            print('\n   Testing chat_stream() method...')
            # Note: chat_stream is async, but let's try the sync version
            messages = [{"role": "user", "content": "Say hello in one word."}]
            response = client.chat_stream(
                model='command-r-plus',
                message="Say hello in one word.",
                max_tokens=5
            )
            # chat_stream returns a generator, so we need to iterate
            for chunk in response:
                if chunk.event_type == 'text-generation':
                    print(f'   ✅ SUCCESS with chat_stream(): {chunk.text}')
                    working_method = 'chat_stream'
                    working_model = 'command-r-plus'
                    break
        except Exception as e3:
            print(f'   ❌ chat_stream() failed: {type(e3).__name__}')
            print(f'      Error: {str(e3)[:300]}')
            working_method = None
            working_model = None

if working_method:
    print(f'\n✅ Working: {working_method}() with model: {working_model}')
    print('   → Ready to proceed with trial tagging')
    print('   → Rate limit: 20 requests/min = 3 seconds between calls')
else:
    print('\n❌ No working method/model found')
    print('   → Need to check Cohere v5 documentation')

