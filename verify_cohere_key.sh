#!/bin/bash
# Quick script to verify COHERE_API_KEY is set

cd "$(dirname "$0")"

echo "Checking .env file for COHERE_API_KEY..."
echo ""

if grep -q "COHERE_API_KEY=" .env; then
    KEY_LINE=$(grep "COHERE_API_KEY=" .env | head -1)
    KEY_VALUE=$(echo "$KEY_LINE" | cut -d'=' -f2)
    
    if [ -z "$KEY_VALUE" ]; then
        echo "❌ COHERE_API_KEY is empty"
        echo ""
        echo "Current line in .env:"
        echo "  $KEY_LINE"
        echo ""
        echo "📝 To fix:"
        echo "  1. Open: $(pwd)/.env"
        echo "  2. Find: COHERE_API_KEY="
        echo "  3. Add your key: COHERE_API_KEY=your-actual-key-here"
        echo "  4. Save the file"
        exit 1
    else
        echo "✅ COHERE_API_KEY is set"
        echo "   Length: ${#KEY_VALUE} characters"
        echo "   First 10 chars: ${KEY_VALUE:0:10}..."
        echo ""
        echo "Running Python test..."
        python3 tests/test_cohere_with_key.py
    fi
else
    echo "❌ COHERE_API_KEY line not found in .env"
    exit 1
fi

