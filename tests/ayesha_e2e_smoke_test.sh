#!/bin/bash

# ⚔️ AYESHA E2E SMOKE TEST - FOR AYESHA'S LIFE ⚔️
# 
# Tests all backend endpoints with Ayesha's actual clinical profile
# 
# Patient: AK
# Diagnosis: Stage IVB High-Grade Serous Ovarian Cancer
# Status: Treatment-naive, germline-negative, CA-125 2842
# 
# Author: Zo
# Date: January 13, 2025

set -e  # Exit on error

echo "⚔️ AYESHA E2E SMOKE TEST - STARTING ⚔️"
echo "======================================"
echo ""

# Base URL
API_BASE="http://127.0.0.1:8000"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test counter
TESTS_PASSED=0
TESTS_FAILED=0

# Helper function for tests
test_endpoint() {
    local test_name="$1"
    local method="$2"
    local endpoint="$3"
    local payload="$4"
    local expected_status="$5"
    
    echo -e "${YELLOW}Testing: $test_name${NC}"
    echo "  Endpoint: $method $endpoint"
    
    if [ "$method" == "POST" ]; then
        response=$(curl -s -w "\n%{http_code}" -X POST "$API_BASE$endpoint" \
            -H 'Content-Type: application/json' \
            -d "$payload")
    else
        response=$(curl -s -w "\n%{http_code}" -X GET "$API_BASE$endpoint")
    fi
    
    # Extract status code (last line)
    status_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | head -n-1)
    
    if [ "$status_code" == "$expected_status" ]; then
        echo -e "  ${GREEN}✅ PASS${NC} (Status: $status_code)"
        TESTS_PASSED=$((TESTS_PASSED + 1))
        
        # Show first 200 chars of response
        echo "  Response preview: $(echo "$body" | head -c 200)..."
        echo ""
        return 0
    else
        echo -e "  ${RED}❌ FAIL${NC} (Expected: $expected_status, Got: $status_code)"
        echo "  Response: $body"
        echo ""
        TESTS_FAILED=$((TESTS_FAILED + 1))
        return 1
    fi
}

# ===================================
# TEST 1: Health Checks
# ===================================
echo "🔍 CATEGORY 1: HEALTH CHECKS"
echo "======================================"

test_endpoint \
    "Main API Health" \
    "GET" \
    "/health" \
    "" \
    "200"

test_endpoint \
    "Ayesha Trials Health" \
    "GET" \
    "/api/ayesha/trials/health" \
    "" \
    "200"

test_endpoint \
    "Complete Care v2 Health" \
    "GET" \
    "/api/ayesha/complete_care_v2/health" \
    "" \
    "200"

# ===================================
# TEST 2: Ayesha Trials Search
# ===================================
echo "🔍 CATEGORY 2: AYESHA TRIALS SEARCH"
echo "======================================"

AYESHA_PROFILE='{
  "ca125_value": 2842.0,
  "stage": "IVB",
  "treatment_line": "first-line",
  "germline_status": "negative",
  "has_ascites": true,
  "has_peritoneal_disease": true,
  "location_state": "NY",
  "ecog_status": null,
  "max_results": 10
}'

test_endpoint \
    "Ayesha Trials Search (Full Profile)" \
    "POST" \
    "/api/ayesha/trials/search" \
    "$AYESHA_PROFILE" \
    "200"

# Save response for validation
curl -s -X POST "$API_BASE/api/ayesha/trials/search" \
    -H 'Content-Type: application/json' \
    -d "$AYESHA_PROFILE" \
    -o /tmp/ayesha_trials_response.json

echo "  💾 Saved full response to /tmp/ayesha_trials_response.json"
echo ""

# ===================================
# TEST 3: Complete Care v2
# ===================================
echo "🔍 CATEGORY 3: COMPLETE CARE V2 ORCHESTRATOR"
echo "======================================"

COMPLETE_CARE_REQUEST='{
  "ca125_value": 2842.0,
  "stage": "IVB",
  "treatment_line": "first-line",
  "germline_status": "negative",
  "has_ascites": true,
  "has_peritoneal_disease": true,
  "location_state": "NY",
  "include_trials": true,
  "include_soc": true,
  "include_ca125": true,
  "include_wiwfm": true,
  "max_trials": 10
}'

test_endpoint \
    "Complete Care v2 (No NGS - Awaiting Message)" \
    "POST" \
    "/api/ayesha/complete_care_v2" \
    "$COMPLETE_CARE_REQUEST" \
    "200"

# Save response
curl -s -X POST "$API_BASE/api/ayesha/complete_care_v2" \
    -H 'Content-Type: application/json' \
    -d "$COMPLETE_CARE_REQUEST" \
    -o /tmp/ayesha_complete_care_v2_response.json

echo "  💾 Saved full response to /tmp/ayesha_complete_care_v2_response.json"
echo ""

# ===================================
# TEST 4: Validation Checks
# ===================================
echo "🔍 CATEGORY 4: RESPONSE VALIDATION"
echo "======================================"

echo "Validating trials response structure..."

# Check required fields exist
required_fields=("trials" "soc_recommendation" "ca125_intelligence" "ngs_fast_track" "summary" "provenance")

for field in "${required_fields[@]}"; do
    if jq -e ".$field" /tmp/ayesha_trials_response.json > /dev/null 2>&1; then
        echo -e "  ${GREEN}✅${NC} Field '$field' exists"
        TESTS_PASSED=$((TESTS_PASSED + 1))
    else
        echo -e "  ${RED}❌${NC} Field '$field' MISSING"
        TESTS_FAILED=$((TESTS_FAILED + 1))
    fi
done

# Validate SOC recommendation has bevacizumab (Ayesha has ascites)
echo ""
echo "Validating SOC recommendation includes bevacizumab..."
if jq -e '.soc_recommendation.add_ons[] | select(.drug | contains("Bevacizumab"))' /tmp/ayesha_trials_response.json > /dev/null 2>&1; then
    echo -e "  ${GREEN}✅${NC} Bevacizumab correctly added for ascites"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "  ${RED}❌${NC} Bevacizumab MISSING (expected for ascites)"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi

# Validate CA-125 burden class
echo ""
echo "Validating CA-125 burden classification..."
burden_class=$(jq -r '.ca125_intelligence.burden_class' /tmp/ayesha_trials_response.json)
if [ "$burden_class" == "EXTENSIVE" ]; then
    echo -e "  ${GREEN}✅${NC} CA-125 2842 correctly classified as EXTENSIVE"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "  ${RED}❌${NC} CA-125 burden class incorrect: $burden_class (expected EXTENSIVE)"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi

# Validate trials count
echo ""
echo "Validating trials count..."
trials_count=$(jq '.trials | length' /tmp/ayesha_trials_response.json)
if [ "$trials_count" -gt 0 ] && [ "$trials_count" -le 10 ]; then
    echo -e "  ${GREEN}✅${NC} Trials count valid: $trials_count (1-10 range)"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "  ${RED}❌${NC} Trials count invalid: $trials_count"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi

# Validate NGS fast-track exists
echo ""
echo "Validating NGS fast-track checklist..."
ngs_checklist_count=$(jq '.ngs_fast_track.checklist | length' /tmp/ayesha_trials_response.json)
if [ "$ngs_checklist_count" -ge 2 ]; then
    echo -e "  ${GREEN}✅${NC} NGS fast-track has $ngs_checklist_count tests"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "  ${RED}❌${NC} NGS fast-track incomplete: $ngs_checklist_count tests"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi

# ===================================
# TEST 5: WIWFM "Awaiting NGS" Check
# ===================================
echo ""
echo "🔍 CATEGORY 5: WIWFM 'AWAITING NGS' MESSAGE"
echo "======================================"

echo "Validating WIWFM returns 'awaiting NGS' message (no tumor context provided)..."
wiwfm_status=$(jq -r '.wiwfm.status // "missing"' /tmp/ayesha_complete_care_v2_response.json)
if [ "$wiwfm_status" == "awaiting_ngs" ]; then
    echo -e "  ${GREEN}✅${NC} WIWFM correctly returns 'awaiting_ngs' (honest, not fake predictions)"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "  ${RED}❌${NC} WIWFM status unexpected: $wiwfm_status (expected 'awaiting_ngs')"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi

# ===================================
# FINAL RESULTS
# ===================================
echo ""
echo "======================================"
echo "⚔️ SMOKE TEST RESULTS ⚔️"
echo "======================================"
echo ""
echo -e "${GREEN}✅ PASSED: $TESTS_PASSED${NC}"
echo -e "${RED}❌ FAILED: $TESTS_FAILED${NC}"
echo ""

TOTAL_TESTS=$((TESTS_PASSED + TESTS_FAILED))
PASS_RATE=$((TESTS_PASSED * 100 / TOTAL_TESTS))

echo "Pass Rate: $PASS_RATE% ($TESTS_PASSED/$TOTAL_TESTS)"
echo ""

if [ "$TESTS_FAILED" -eq 0 ]; then
    echo -e "${GREEN}🎯 ALL TESTS PASSED - BACKEND READY FOR AYESHA'S LIFE ⚔️${NC}"
    exit 0
else
    echo -e "${RED}⚠️ SOME TESTS FAILED - REVIEW LOGS ABOVE${NC}"
    exit 1
fi


