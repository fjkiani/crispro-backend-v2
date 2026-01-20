#!/bin/bash
# End-to-End Test Script for Graph-Optimized Trial Search
# Tests hybrid search and autonomous agent endpoints

API_ROOT="${API_ROOT:-http://localhost:8000}"
echo "🚀 Testing Clinical Trials Graph System"
echo "API Root: $API_ROOT"
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test 1: Hybrid Graph-Optimized Search
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 TEST 1: Hybrid Graph-Optimized Search"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

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
RESPONSE_BODY1=$(echo "$RESPONSE1" | sed '/HTTP_STATUS/d')

if [ "$HTTP_STATUS1" = "200" ]; then
  echo -e "${GREEN}✅ Test 1 PASSED${NC} (HTTP $HTTP_STATUS1)"
  echo ""
  echo "Response:"
  echo "$RESPONSE_BODY1" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE_BODY1"
  
  # Extract count
  TRIAL_COUNT=$(echo "$RESPONSE_BODY1" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('data', {}).get('count', 0))" 2>/dev/null || echo "0")
  echo ""
  echo -e "${GREEN}Found $TRIAL_COUNT trials${NC}"
else
  echo -e "${RED}❌ Test 1 FAILED${NC} (HTTP $HTTP_STATUS1)"
  echo "Response:"
  echo "$RESPONSE_BODY1"
fi

echo ""
echo ""

# Test 2: Autonomous Trial Agent
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🤖 TEST 2: Autonomous Trial Agent"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

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
RESPONSE_BODY2=$(echo "$RESPONSE2" | sed '/HTTP_STATUS/d')

if [ "$HTTP_STATUS2" = "200" ]; then
  echo -e "${GREEN}✅ Test 2 PASSED${NC} (HTTP $HTTP_STATUS2)"
  echo ""
  echo "Response:"
  echo "$RESPONSE_BODY2" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE_BODY2"
  
  # Extract counts
  TOTAL_FOUND=$(echo "$RESPONSE_BODY2" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('data', {}).get('total_found', 0))" 2>/dev/null || echo "0")
  QUERIES_USED=$(echo "$RESPONSE_BODY2" | python3 -c "import sys, json; data=json.load(sys.stdin); queries=data.get('data', {}).get('queries_used', []); print(len(queries))" 2>/dev/null || echo "0")
  echo ""
  echo -e "${GREEN}Agent found $TOTAL_FOUND trials using $QUERIES_USED queries${NC}"
else
  echo -e "${RED}❌ Test 2 FAILED${NC} (HTTP $HTTP_STATUS2)"
  echo "Response:"
  echo "$RESPONSE_BODY2"
fi

echo ""
echo ""

# Test 3: Basic Health Check
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🏥 TEST 3: API Health Check"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

HEALTH_CHECK=$(curl -s "$API_ROOT/docs" -w "\nHTTP_STATUS:%{http_code}")
HTTP_STATUS_HEALTH=$(echo "$HEALTH_CHECK" | grep "HTTP_STATUS" | cut -d: -f2)

if [ "$HTTP_STATUS_HEALTH" = "200" ]; then
  echo -e "${GREEN}✅ API is running${NC} (FastAPI docs available at $API_ROOT/docs)"
else
  echo -e "${YELLOW}⚠️  API docs not accessible (HTTP $HTTP_STATUS_HEALTH)${NC}"
  echo "But endpoints may still work - check individual tests above"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📋 TEST SUMMARY"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if [ "$HTTP_STATUS1" = "200" ] && [ "$HTTP_STATUS2" = "200" ]; then
  echo -e "${GREEN}🎉 ALL TESTS PASSED!${NC}"
  echo ""
  echo "✅ Hybrid search endpoint operational"
  echo "✅ Autonomous agent endpoint operational"
  echo ""
  echo "Next steps:"
  echo "  1. Check frontend at ResearchPortal page"
  echo "  2. Test Graph-Optimized tab"
  echo "  3. Test Autonomous Agent tab"
  exit 0
else
  echo -e "${RED}⚠️  SOME TESTS FAILED${NC}"
  echo ""
  [ "$HTTP_STATUS1" != "200" ] && echo "❌ Hybrid search endpoint failed"
  [ "$HTTP_STATUS2" != "200" ] && echo "❌ Autonomous agent endpoint failed"
  echo ""
  echo "Troubleshooting:"
  echo "  1. Ensure backend is running: python -m api.main"
  echo "  2. Check .env file has correct credentials"
  echo "  3. Verify Neo4j and AstraDB connections"
  exit 1
fi










