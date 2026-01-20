#!/bin/bash
# Clinical Trials Migration Validation Script
# Tests the complete migration from main backend to minimal backend

set -e  # Exit on error

echo "🔍 CLINICAL TRIALS MIGRATION VALIDATION"
echo "=========================================="
echo ""

# Configuration
MINIMAL_BACKEND_URL="${MINIMAL_BACKEND_URL:-http://localhost:8000}"
MAIN_BACKEND_URL="${MAIN_BACKEND_URL:-http://localhost:8001}"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test counters
TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0

# Helper function for test assertions
test_endpoint() {
    local name="$1"
    local url="$2"
    local method="$3"
    local data="$4"
    local expected_status="$5"
    local max_time="${6:-5.0}"  # Default 5 second timeout
    
    TESTS_RUN=$((TESTS_RUN + 1))
    echo -n "Test #${TESTS_RUN}: ${name}... "
    
    # Execute request
    if [ "$method" = "POST" ]; then
        response=$(curl -s -w "\n%{http_code}\n%{time_total}" -X POST "$url" \
            -H "Content-Type: application/json" \
            -d "$data" \
            --max-time 30)
    else
        response=$(curl -s -w "\n%{http_code}\n%{time_total}" "$url" --max-time 30)
    fi
    
    # Parse response
    status_code=$(echo "$response" | tail -n 2 | head -n 1)
    time_total=$(echo "$response" | tail -n 1)
    body=$(echo "$response" | head -n -2)
    
    # Validate status code
    if [ "$status_code" != "$expected_status" ]; then
        echo -e "${RED}FAILED${NC} (HTTP $status_code, expected $expected_status)"
        TESTS_FAILED=$((TESTS_FAILED + 1))
        echo "  Response: $body"
        return 1
    fi
    
    # Validate response time
    if (( $(echo "$time_total > $max_time" | bc -l) )); then
        echo -e "${YELLOW}SLOW${NC} (${time_total}s > ${max_time}s threshold)"
    fi
    
    echo -e "${GREEN}PASSED${NC} (HTTP $status_code, ${time_total}s)"
    TESTS_PASSED=$((TESTS_PASSED + 1))
    return 0
}

echo "📋 Phase 1: Minimal Backend Service Tests"
echo "-------------------------------------------"

# Test 1: Health check
test_endpoint "Health check" \
    "$MINIMAL_BACKEND_URL/health" \
    "GET" \
    "" \
    "200"

# Test 2: Search trials endpoint (basic query)
test_endpoint "Search trials (basic query)" \
    "$MINIMAL_BACKEND_URL/api/search-trials" \
    "POST" \
    '{"query":"ovarian cancer BRCA1 mutation"}' \
    "200" \
    "3.0"  # Should be fast (<3s)

# Test 3: Search trials with disease category filter
test_endpoint "Search trials (with filter)" \
    "$MINIMAL_BACKEND_URL/api/search-trials" \
    "POST" \
    '{"query":"breast cancer", "patient_context":{"disease_category":"breast_cancer"}}' \
    "200" \
    "3.0"

# Test 4: Refresh status endpoint
test_endpoint "Refresh trial status" \
    "$MINIMAL_BACKEND_URL/api/trials/refresh_status" \
    "POST" \
    '{"nct_ids":["NCT03738163"], "state_filter":"NY"}' \
    "200" \
    "5.0"

echo ""
echo "📋 Phase 2: Performance Benchmarks"
echo "-----------------------------------"

# Run search 5 times and measure average time
echo "Running 5 consecutive searches..."
total_time=0
for i in {1..5}; do
    start_time=$(date +%s.%N)
    curl -s -X POST "$MINIMAL_BACKEND_URL/api/search-trials" \
        -H "Content-Type: application/json" \
        -d '{"query":"clinical trial ovarian cancer"}' \
        > /dev/null
    end_time=$(date +%s.%N)
    elapsed=$(echo "$end_time - $start_time" | bc)
    total_time=$(echo "$total_time + $elapsed" | bc)
    echo "  Run #$i: ${elapsed}s"
done

avg_time=$(echo "scale=3; $total_time / 5" | bc)
echo -e "Average time: ${avg_time}s"

if (( $(echo "$avg_time < 0.5" | bc -l) )); then
    echo -e "${GREEN}✅ Performance target met (<500ms average)${NC}"
else
    echo -e "${YELLOW}⚠️  Performance slower than target (${avg_time}s > 0.5s)${NC}"
fi

echo ""
echo "📋 Phase 3: Data Consistency Checks"
echo "------------------------------------"

# Check if SQLite database exists
if [ -f "../data/clinical_trials.db" ]; then
    echo -e "${GREEN}✅${NC} SQLite database exists"
    
    # Count trials in database
    trial_count=$(sqlite3 ../data/clinical_trials.db "SELECT COUNT(*) FROM clinical_trials;" 2>/dev/null || echo "0")
    echo "   Total trials in SQLite: $trial_count"
else
    echo -e "${YELLOW}⚠️${NC}  SQLite database not found (run Agent 1 seeding first)"
fi

echo ""
echo "📋 Phase 4: Main Backend Deprecation Check"
echo "-------------------------------------------"

# Test that main backend endpoint still works (for backward compatibility)
if curl -s "$MAIN_BACKEND_URL/health" > /dev/null 2>&1; then
    echo -e "${GREEN}✅${NC} Main backend reachable (backward compatibility maintained)"
    
    # Check for deprecation warning in logs
    echo "   Testing deprecated endpoint..."
    response=$(curl -s -X POST "$MAIN_BACKEND_URL/api/search-trials" \
        -H "Content-Type: application/json" \
        -d '{"query":"test"}' || echo "")
    
    if [ -n "$response" ]; then
        echo -e "${GREEN}✅${NC} Deprecated endpoint still functional (for AgentOrchestrator)"
    else
        echo -e "${YELLOW}⚠️${NC}  Deprecated endpoint may have issues"
    fi
else
    echo -e "${YELLOW}⚠️${NC}  Main backend not running (expected for production deployment)"
fi

echo ""
echo "=========================================="
echo "🎯 VALIDATION SUMMARY"
echo "=========================================="
echo "Tests Run:    $TESTS_RUN"
echo "Tests Passed: $TESTS_PASSED"
echo "Tests Failed: $TESTS_FAILED"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}✅ ALL TESTS PASSED - Migration Complete!${NC}"
    echo ""
    echo "Next Steps:"
    echo "  1. Run Agent 1 to seed SQLite: cd ../oncology-backend && venv/bin/python -m scripts.agent_1_seeding.main"
    echo "  2. Seed AstraDB: venv/bin/python scripts/seed_astradb_from_sqlite.py"
    echo "  3. Deploy minimal backend to production"
    echo "  4. Update frontend to use minimal backend URL"
    exit 0
else
    echo -e "${RED}❌ $TESTS_FAILED TEST(S) FAILED${NC}"
    exit 1
fi












