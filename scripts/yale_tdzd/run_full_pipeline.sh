#!/bin/bash
#
# YALE T-DXd RESISTANCE PROJECT - COMPLETE PIPELINE
# Runs end-to-end: Extract → Label → Train → Validate
#
# Usage: ./run_full_pipeline.sh
#

set -e  # Exit on error

# Paths
ROOT_DIR="/Users/fahadkiani/Desktop/development/crispr-assistant-main"
PYTHON="${ROOT_DIR}/venv/bin/python"
SCRIPTS_DIR="${ROOT_DIR}/oncology-coPilot/oncology-backend-minimal/scripts/yale_tdzd"
DATA_DIR="${ROOT_DIR}/oncology-coPilot/oncology-backend-minimal/data/yale_tdzd_project"

echo "================================================================================"
echo "🎯 YALE T-DXd RESISTANCE PROJECT - COMPLETE PIPELINE"
echo "================================================================================"
echo "Start time: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# Step 1: Extract TCGA/METABRIC data
echo "📊 STEP 1: EXTRACTING TCGA/METABRIC BREAST CANCER DATA"
echo "--------------------------------------------------------------------------------"
${PYTHON} ${SCRIPTS_DIR}/extract_tcga_brca.py
if [ $? -eq 0 ]; then
    echo "✅ Extraction complete"
else
    echo "❌ Extraction failed"
    exit 1
fi
echo ""

# Step 2: Generate resistance labels
echo "🏷️  STEP 2: GENERATING RESISTANCE LABELS"
echo "--------------------------------------------------------------------------------"
${PYTHON} ${SCRIPTS_DIR}/label_adc_resistance.py
if [ $? -eq 0 ]; then
    echo "✅ Labeling complete"
else
    echo "❌ Labeling failed"
    exit 1
fi
echo ""

# Step 3: Train prediction models
echo "🤖 STEP 3: TRAINING PREDICTION MODELS"
echo "--------------------------------------------------------------------------------"
${PYTHON} ${SCRIPTS_DIR}/train_adc_models.py
if [ $? -eq 0 ]; then
    echo "✅ Training complete"
else
    echo "❌ Training failed"
    exit 1
fi
echo ""

# Summary
echo "================================================================================"
echo "✅ PIPELINE COMPLETE"
echo "================================================================================"
echo "End time: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""
echo "📦 Deliverables:"
echo "   Data:   ${DATA_DIR}/processed/brca_adc_resistance_cohort.csv"
echo "   Models: ${DATA_DIR}/models/"
echo "   Results: ${DATA_DIR}/results/"
echo ""
echo "📊 Check results:"
echo "   cat ${DATA_DIR}/results/model_performance_summary.csv"
echo ""
echo "🎯 Next steps:"
echo "   1. Review model performance (target: AUROC ≥0.70)"
echo "   2. If Dr. Lustberg shares Yale data, run external validation"
echo "   3. Generate manuscript figures"
echo ""

