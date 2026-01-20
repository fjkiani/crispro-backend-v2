#!/bin/bash
# Test script that will work after backend restart

echo "🧪 Testing Graph-Optimized Trial Search Endpoints"
echo "================================================"
echo ""
echo "⚠️  NOTE: Backend must be restarted first for code changes to take effect!"
echo ""

API_ROOT="${API_ROOT:-http://localhost:8000}"

# Test 1: Hybrid Search
echo "📊 TEST 1: Hybrid Graph-Optimized Search"
echo "----------------------------------------"
RESPONSE1=$(curl -s -X POST "$API_ROOT/api/trials/search-optimized" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "ovarian cancer BRCA1",
    "patient_context": {
      "condition": "ovarian cancer",
      "location_state": "NY",
      "disease_category": "ovarian_cancer"
    },
    "top_k": 10
  }' \
  -w "\nHTTP_STATUS:%{http_code}")

HTTP_STATUS1=$(echo "$RESPONSE1" | grep "HTTP_STATUS" | cut -d: -f2)
BODY1=$(echo "$RESPONSE1" | sed '/HTTP_STATUS/d')

if [ "$HTTP_STATUS1" = "200" ]; then
  echo "✅ PASSED (HTTP $HTTP_STATUS1)"
  echo "$BODY1" | python3 -m json.tool 2>/dev/null | head -30
  echo ""
  TRIAL_COUNT=$(echo "$BODY1" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('data', {}).get('count', 0))" 2>/dev/null || echo "0")
  echo "Found $TRIAL_COUNT trials"
else
  echo "❌ FAILED (HTTP $HTTP_STATUS1)"
  echo "$BODY1"
fi

echo ""
echo ""

# Test 2: Autonomous Agent
echo "🤖 TEST 2: Autonomous Trial Agent"
echo "----------------------------------"
RESPONSE2=$(curl -s -X POST "$API_ROOT/api/trials/agent/search" \
  -H "Content-Type: application/json" \
  -d '{
    "mutations": [{"gene": "BRCA1", "hgvs_p": "V600E"}],
    "disease": "ovarian cancer",
    "state": "CA",
    "biomarkers": ["BRCA1"]
  }' \
  -w "\nHTTP_STATUS:%{http_code}")

HTTP_STATUS2=$(echo "$RESPONSE2" | grep "HTTP_STATUS" | cut -d: -f2)
BODY2=$(echo "$RESPONSE2" | sed '/HTTP_STATUS/d')

if [ "$HTTP_STATUS2" = "200" ]; then
  echo "✅ PASSED (HTTP $HTTP_STATUS2)"
  echo "$BODY2" | python3 -m json.tool 2>/dev/null | head -40
  echo ""
  TOTAL=$(echo "$BODY2" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('data', {}).get('total_found', 0))" 2>/dev/null || echo "0")
  QUERIES=$(echo "$BODY2" | python3 -c "import sys, json; d=json.load(sys.stdin); q=d.get('data', {}).get('queries_used', []); print(len(q))" 2>/dev/null || echo "0")
  echo "Agent found $TOTAL trials using $QUERIES queries"
else
  echo "❌ FAILED (HTTP $HTTP_STATUS2)"
  echo "$BODY2"
fi

echo ""
echo "================================================"
if [ "$HTTP_STATUS1" = "200" ] && [ "$HTTP_STATUS2" = "200" ]; then
  echo "🎉 ALL TESTS PASSED!"
  exit 0
else
  echo "⚠️  Some tests failed. Check backend logs and ensure server was restarted."
  exit 1
fi
