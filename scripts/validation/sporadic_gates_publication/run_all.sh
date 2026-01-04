#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../../../.." && pwd)"  # .../oncology-backend-minimal
PUB_DIR="$ROOT_DIR/scripts/validation/sporadic_gates_publication"

cd "$ROOT_DIR"

TS="$(date -u +%Y%m%d_%H%M%S)"
OUT_DIR="$PUB_DIR/receipts/$TS"
LATEST_DIR="$PUB_DIR/receipts/latest"

mkdir -p "$OUT_DIR" "$LATEST_DIR"

# 1) Unit-style policy checks (stdout captured)
python3 scripts/validation/validate_sporadic_gates.py | tee "$OUT_DIR/validate_sporadic_gates.txt" > "$LATEST_DIR/validate_sporadic_gates.txt"
cp -f scripts/validation/out/sporadic_gates/report.json "$OUT_DIR/validate_sporadic_gates_report.json" || true
cp -f scripts/validation/out/sporadic_gates/report.json "$LATEST_DIR/validate_sporadic_gates_report.json" || true

# 2) Quick intake (15 cancers) (stdout captured + raw report)
python3 scripts/validation/validate_quick_intake.py | tee "$OUT_DIR/quick_intake_run.txt" > "$LATEST_DIR/quick_intake_run.txt"
cp -f scripts/validation/out/quick_intake/report.json "$OUT_DIR/quick_intake_report.json" || true
cp -f scripts/validation/out/quick_intake/report.json "$LATEST_DIR/quick_intake_report.json" || true

# Write a stable, publication-friendly JSON artifact (subset of report)
python3 - <<PY
import json
from pathlib import Path
src = Path('scripts/validation/out/quick_intake/report.json')
out_dir = Path('$OUT_DIR')
latest_dir = Path('$LATEST_DIR')

d = json.loads(src.read_text())
compact = {
  'timestamp': d.get('timestamp'),
  'total_cancers': d.get('total_cancers'),
  'passed': d.get('passed'),
  'failed': d.get('failed'),
  'results': {k: (v.get('data') if isinstance(v, dict) else v) for k,v in (d.get('results') or {}).items()},
  'status': d.get('status'),
}
(out_dir / 'quick_intake_15cancers.json').write_text(json.dumps(compact, indent=2))
(latest_dir / 'quick_intake_15cancers.json').write_text(json.dumps(compact, indent=2))
print('✅ wrote quick_intake_15cancers.json')
PY

# 3) E2E smoke (requires backend running at API_BASE)
API_BASE="${API_BASE:-http://localhost:8000}"
API_BASE="$API_BASE" bash scripts/validation/e2e_sporadic_workflow.sh

cp -f scripts/validation/out/e2e_sporadic/tumor_context.json "$OUT_DIR/e2e_tumor_context.json"
cp -f scripts/validation/out/e2e_sporadic/tumor_context.json "$LATEST_DIR/e2e_tumor_context.json"

cp -f scripts/validation/out/e2e_sporadic/efficacy_response.json "$OUT_DIR/e2e_efficacy_response.json"
cp -f scripts/validation/out/e2e_sporadic/efficacy_response.json "$LATEST_DIR/e2e_efficacy_response.json"

cp -f scripts/validation/out/e2e_sporadic/test.log "$OUT_DIR/e2e_sporadic_workflow.txt"
cp -f scripts/validation/out/e2e_sporadic/test.log "$LATEST_DIR/e2e_sporadic_workflow.txt"

# 4) Scenario-suite benchmark (system vs naive)
python3 scripts/validation/sporadic_gates_publication/scripts/compute_benchmark_gate_effects.py \
  --scenario scripts/validation/sporadic_gates_publication/data/scenario_suite_25_20251231_080940.json \
  --out "$OUT_DIR/benchmark_gate_effects.json"
cp -f "$OUT_DIR/benchmark_gate_effects.json" "$LATEST_DIR/benchmark_gate_effects.json"

echo "✅ receipts written under: $OUT_DIR"
echo "✅ latest updated: $LATEST_DIR"
