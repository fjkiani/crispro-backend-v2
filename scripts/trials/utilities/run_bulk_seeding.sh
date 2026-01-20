#!/bin/bash
# Bulk Seed Clinical Trials - Background Runner
# Run this to seed 5,000-10,000 trials overnight

cd "$(dirname "$0")/.."
SCRIPT_DIR="$(pwd)/scripts"
LOG_DIR="$(pwd)/logs"
mkdir -p "$LOG_DIR"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="$LOG_DIR/bulk_seeding_${TIMESTAMP}.log"

echo "🚀 Starting bulk trial seeding..."
echo "   Log file: $LOG_FILE"
echo "   Target: 10,000 trials"
echo ""
echo "   Run in background with: nohup bash scripts/run_bulk_seeding.sh > $LOG_FILE 2>&1 &"
echo ""

# Run the seeding script
python3 "$SCRIPT_DIR/bulk_seed_trials.py" --target 10000 2>&1 | tee "$LOG_FILE"

echo ""
echo "✅ Seeding complete! Check log: $LOG_FILE"











