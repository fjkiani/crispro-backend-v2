#!/bin/bash
# Test script for auth endpoints
# Usage: ./test_auth_endpoints.sh

API_ROOT="${API_ROOT:-http://localhost:8000}"

echo "🔍 Testing Auth Endpoints"
echo "========================="
echo ""

# Test health check
echo "1. Testing auth health check..."
curl -s "$API_ROOT/api/auth/health" | jq '.' || echo "❌ Health check failed"
echo ""

# Test signup
echo "2. Testing signup..."
SIGNUP_RESPONSE=$(curl -s -X POST "$API_ROOT/api/auth/signup" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "testpassword123",
    "full_name": "Test User",
    "institution": "Test University",
    "role": "researcher"
  }')

echo "$SIGNUP_RESPONSE" | jq '.' || echo "❌ Signup failed"
ACCESS_TOKEN=$(echo "$SIGNUP_RESPONSE" | jq -r '.data.session.access_token // empty')

if [ -z "$ACCESS_TOKEN" ]; then
  echo "⚠️  No access token received. Signup may require email confirmation."
  echo "   Please check your email and confirm before testing login."
else
  echo "✅ Signup successful! Access token received."
  echo ""
  
  # Test profile
  echo "3. Testing get profile..."
  curl -s -X GET "$API_ROOT/api/auth/profile" \
    -H "Authorization: Bearer $ACCESS_TOKEN" | jq '.' || echo "❌ Get profile failed"
  echo ""
  
  # Test login
  echo "4. Testing login..."
  LOGIN_RESPONSE=$(curl -s -X POST "$API_ROOT/api/auth/login" \
    -H "Content-Type: application/json" \
    -d '{
      "email": "test@example.com",
      "password": "testpassword123"
    }')
  
  echo "$LOGIN_RESPONSE" | jq '.' || echo "❌ Login failed"
  LOGIN_TOKEN=$(echo "$LOGIN_RESPONSE" | jq -r '.data.session.access_token // empty')
  
  if [ -n "$LOGIN_TOKEN" ]; then
    echo "✅ Login successful!"
    echo ""
    
    # Test protected endpoint (efficacy)
    echo "5. Testing protected endpoint (efficacy)..."
    curl -s -X POST "$API_ROOT/api/efficacy/predict" \
      -H "Authorization: Bearer $LOGIN_TOKEN" \
      -H "Content-Type: application/json" \
      -d '{
        "model_id": "evo2_1b",
        "mutations": [{"gene": "BRAF", "hgvs_p": "V600E"}],
        "options": {}
      }' | jq -r '.drugs[0].drug_name // .message // .detail // "Response received"' || echo "❌ Protected endpoint failed"
    echo ""
  fi
fi

echo "✅ Auth endpoint testing complete!"








