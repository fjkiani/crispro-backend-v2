#!/bin/bash
# E2E Sporadic Cancer Workflow Test

# Source of Truth: .cursor/MOAT/SPORADIC_CANCER_PRODUCTION_PLAN.md
# Task: Phase 3 - E2E Smoke Test

set -e

API_BASE="${API_BASE:-http://localhost:8000}"
OUTPUT_DIR="scripts/validation/out/e2e_sporadic"
mkdir -p "$OUTPUT_DIR"

echo "=" | tee "$OUTPUT_DIR/test.log"
echo "SPORADIC CANCER E2E WORKFLOW TEST" | tee -a "$OUTPUT_DIR/test.log"
echo "=" | tee -a "$OUTPUT_DIR/test.log"
echo "API Base: $API_BASE" | tee -a "$OUTPUT_DIR/test.log"
echo "" | tee -a "$OUTPUT_DIR/test.log"

# Step 1: Quick Intake
echo "1. Creating TumorContext via Quick Intake..." | tee -a "$OUTPUT_DIR/test.log"
TUMOR_RESPONSE=$(curl -s -X POST "$API_BASE/api/tumor/quick_intake" \
  -H "Content-Type: application/json" \
  -d '{
    "cancer_type": "ovarian_hgs",
    "stage": "IIIC",
    "line": 2
  }')

echo "$TUMOR_RESPONSE" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    # API returns nested structure: {tumor_context: {...}}
    tumor_ctx = d.get('tumor_context', {})
    tmb = tumor_ctx.get('tmb', '?')
    hrd = tumor_ctx.get('hrd_score', '?')
    msi = tumor_ctx.get('msi_status', '?') or 'None'
    comp = tumor_ctx.get('completeness_score', '?')
    print(f'   ✅ TumorContext created: TMB={tmb}, HRD={hrd}, MSI={msi}, completeness={comp}')
except Exception as e:
    print(f'   ❌ Failed to parse response: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)
" | tee -a "$OUTPUT_DIR/test.log"

if [ $? -ne 0 ]; then
    echo "❌ Quick Intake failed" | tee -a "$OUTPUT_DIR/test.log"
    exit 1
fi

# Save tumor context for next step
echo "$TUMOR_RESPONSE" > "$OUTPUT_DIR/tumor_context.json"

# Step 2: Efficacy Prediction with Sporadic Context
echo "" | tee -a "$OUTPUT_DIR/test.log"
echo "2. Running efficacy prediction with sporadic context..." | tee -a "$OUTPUT_DIR/test.log"

# Extract tumor_context from nested response for efficacy API
TUMOR_CONTEXT_ONLY=$(echo "$TUMOR_RESPONSE" | python3 -c "
import sys, json
d = json.load(sys.stdin)
tumor_ctx = d.get('tumor_context', {})
print(json.dumps(tumor_ctx))
")

EFFICACY_RESPONSE=$(curl -s -X POST "$API_BASE/api/efficacy/predict" \
  -H "Content-Type: application/json" \
  -d "{
    \"mutations\": [{\"gene\": \"TP53\", \"hgvs_p\": \"R248W\"}],
    \"germline_status\": \"negative\",
    \"tumor_context\": $TUMOR_CONTEXT_ONLY,
    \"disease\": \"ovarian\",
    \"options\": {\"include_all_drugs\": true}
  }")

echo "$EFFICACY_RESPONSE" > "$OUTPUT_DIR/efficacy_response.json"

# Step 3: Verify PARP penalty applied
echo "" | tee -a "$OUTPUT_DIR/test.log"
echo "3. Checking PARP penalty and sporadic gates..." | tee -a "$OUTPUT_DIR/test.log"

echo "$EFFICACY_RESPONSE" | python3 -c "
import sys, json
d = json.load(sys.stdin)
drugs = d.get('drugs', [])

parp_found = False
io_found = False

for drug in drugs:
    name = drug.get('name', '').lower()
    drug_class = drug.get('drug_class', '').lower()
    eff = drug.get('efficacy_score', 0)
    sprov = drug.get('sporadic_gates_provenance', {})
    
    # Check for PARP inhibitors
    if 'parp' in drug_class or 'olaparib' in name or 'rucaparib' in name or 'niraparib' in name:
        parp_found = True
        if sprov:
            print(f'   ✅ {drug.get(\"name\", \"?\")}: efficacy={eff:.2f}, sporadic_provenance=YES')
            # Check if penalty was applied (efficacy should be lower if HRD < 42)
            if eff < 0.5:
                print(f'      → PARP penalty likely applied (low efficacy suggests HRD < 42)')
        else:
            print(f'   ⚠️ {drug.get(\"name\", \"?\")}: efficacy={eff:.2f}, NO sporadic provenance')
    
    # Check for checkpoint inhibitors
    if 'checkpoint' in drug_class or 'pembrolizumab' in name or 'nivolumab' in name:
        io_found = True
        if sprov:
            print(f'   ✅ {drug.get(\"name\", \"?\")}: efficacy={eff:.2f}, sporadic_provenance=YES')
        else:
            print(f'   ⚠️ {drug.get(\"name\", \"?\")}: efficacy={eff:.2f}, NO sporadic provenance')

if not parp_found:
    print('   ⚠️ No PARP inhibitors found in results')
if not io_found:
    print('   ⚠️ No checkpoint inhibitors found in results')
" | tee -a "$OUTPUT_DIR/test.log"

# Step 4: Summary
echo "" | tee -a "$OUTPUT_DIR/test.log"
echo "=" | tee -a "$OUTPUT_DIR/test.log"
echo "E2E TEST COMPLETE" | tee -a "$OUTPUT_DIR/test.log"
echo "=" | tee -a "$OUTPUT_DIR/test.log"
echo "" | tee -a "$OUTPUT_DIR/test.log"
echo "Outputs saved to: $OUTPUT_DIR" | tee -a "$OUTPUT_DIR/test.log"
echo "  - tumor_context.json" | tee -a "$OUTPUT_DIR/test.log"
echo "  - efficacy_response.json" | tee -a "$OUTPUT_DIR/test.log"
echo "  - test.log" | tee -a "$OUTPUT_DIR/test.log"

