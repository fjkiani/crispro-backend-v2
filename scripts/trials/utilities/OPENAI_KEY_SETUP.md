# OpenAI API Key Setup for Trial Sync

## Current Issue
The `OPENAI_API_KEY` in `.env` is currently set to a **Google API key** (starts with `AIza...`), but OpenAI keys start with `sk-`.

## Fix Required
Update `.env` file with a valid OpenAI API key:

1. **Get OpenAI API Key**: https://platform.openai.com/account/api-keys
2. **Update `.env` file**:
   ```bash
   OPENAI_API_KEY=sk-your-actual-openai-key-here
   ```
3. **Format**: OpenAI keys start with `sk-` and are ~50 characters long

## Once Fixed, Run Sync

With OpenAI (faster, no rate limits on paid keys):
```bash
cd oncology-coPilot/oncology-backend-minimal
env COHERE_API_KEY= GEMINI_API_KEY= GOOGLE_API_KEY= \
PYTHONPATH=$(pwd):$PYTHONPATH \
python3 scripts/trials/utilities/seed_astradb_from_sqlite.py \
  --batch-size 10 \
  --limit 0
```

## Alternative: Use Cohere with Better Rate Limiting

If you prefer to use Cohere (which is already working):
- The rate limiting fixes are already applied
- Use smaller batch size (e.g., `--batch-size 4`)
- Or wait for Cohere production key (higher rate limits)

## Provider Priority

The system checks providers in this order:
1. **COHERE** (if `COHERE_API_KEY` set) ← Currently selected
2. **GEMINI** (if `GEMINI_API_KEY` or `GOOGLE_API_KEY` set)
3. **OPENAI** (if `OPENAI_API_KEY` set) ← What we want
4. **ANTHROPIC** (not implemented yet)

To force OpenAI, we unset COHERE, GEMINI, and GOOGLE keys in the command above.
