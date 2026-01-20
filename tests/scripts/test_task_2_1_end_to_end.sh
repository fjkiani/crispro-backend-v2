#!/bin/bash
# Task 2.1 End-to-End Validation Script
# Tests full Food Validator with Phase 2 enhancements

echo "🎯 TASK 2.1: END-TO-END VALIDATION"
echo "=================================="
echo ""

# Test 1: Vitamin D (should resolve to Cholecalciferol)
echo "Test 1: Vitamin D for Ovarian Cancer"
echo "-------------------------------------"
curl -sS -X POST "http://127.0.0.1:8000/api/hypothesis/validate_food_ab_dynamic" \
  -H "Content-Type: application/json" \
  -d '{
    "compound": "Vitamin D",
    "disease": "ovarian_cancer_hgs",
    "use_evo2": false,
    "patient_medications": []
  }' | python3 -m json.tool | grep -E "(compound|spe_percentile|interpretation|canonical|overall_score|confidence|verdict)" | head -20

echo ""
echo "Test 2: Turmeric for Ovarian Cancer (should resolve to Curcumin)"
echo "-----------------------------------------------------------"
curl -sS -X POST "http://127.0.0.1:8000/api/hypothesis/validate_food_ab_dynamic" \
  -H "Content-Type: application/json" \
  -d '{
    "compound": "Turmeric",
    "disease": "ovarian_cancer_hgs",
    "use_evo2": false,
    "patient_medications": []
  }' | python3 -m json.tool | grep -E "(compound|spe_percentile|interpretation|canonical|overall_score|confidence|verdict)" | head -20

echo ""
echo "Test 3: Resveratrol for Ovarian Cancer"
echo "---------------------------------------"
curl -sS -X POST "http://127.0.0.1:8000/api/hypothesis/validate_food_ab_dynamic" \
  -H "Content-Type: application/json" \
  -d '{
    "compound": "Resveratrol",
    "disease": "ovarian_cancer_hgs",
    "use_evo2": false,
    "patient_medications": []
  }' | python3 -m json.tool | grep -E "(compound|spe_percentile|interpretation|canonical|overall_score|confidence|verdict)" | head -20

echo ""
echo "✅ TASK 2.1 VALIDATION COMPLETE"
echo ""
echo "EXPECTED OUTPUTS:"
echo "- compound: Original compound name"
echo "- canonical: Resolved PubChem name (from provenance.compound_resolution)"
echo "- spe_percentile: Calibrated percentile (0-1) or null"
echo "- interpretation: Human-readable percentile (e.g., 'High (top 25%)')"
echo "- overall_score: Raw S/P/E score"
echo "- confidence: Confidence score"
echo "- verdict: SUPPORTED/WEAK_SUPPORT/NOT_SUPPORTED"





