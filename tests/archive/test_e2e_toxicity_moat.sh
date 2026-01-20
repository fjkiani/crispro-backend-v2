#!/bin/bash
# End-to-End Test Script for Toxicity Moat Implementation
# Tests Phase 1 (Backend) + Phase 2 (Food Validation Integration)

echo "=========================================="
echo "TOXICITY MOAT - END-TO-END TEST"
echo "=========================================="
echo ""

# Check if API server is running
echo "[1] Checking API server..."
if curl -s http://127.0.0.1:8000/docs > /dev/null 2>&1; then
    echo "✅ API server is running"
else
    echo "❌ API server is NOT running"
    echo "   Please start it with: cd oncology-backend-minimal && uvicorn api.main:app --reload"
    exit 1
fi

echo ""
echo "[2] Running Phase 1 Tests (Backend MOAT)..."
echo "-------------------------------------------"
python3 test_moat_integration.py

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Phase 1 Tests PASSED"
else
    echo ""
    echo "❌ Phase 1 Tests FAILED"
    exit 1
fi

echo ""
echo "[3] Running Phase 2 Tests (Food Validation Integration)..."
echo "-------------------------------------------"
python3 test_toxicity_food_integration.py

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Phase 2 Tests COMPLETE"
else
    echo ""
    echo "⚠️  Phase 2 Tests - Check results above"
fi

echo ""
echo "=========================================="
echo "END-TO-END TEST COMPLETE"
echo "=========================================="
echo ""
echo "NOTE: If Phase 2 shows no toxicity_mitigation, the server may need"
echo "      to be restarted to pick up code changes:"
echo "      1. Stop the server (Ctrl+C)"
echo "      2. Restart: uvicorn api.main:app --reload"
echo "      3. Run this test again"

