# Reproducibility Guide: MM Drug Efficacy Prediction

**Publication:** Multiple Myeloma Drug Efficacy Prediction via Multi-Modal Genomic Analysis  
**Date:** October 2, 2025  
**Platform:** CrisPRO.ai Oncology Co-Pilot  
**Contact:** [Contact Information]

---

## Executive Summary

This guide provides complete instructions to reproduce all experiments, figures, and metrics reported in our Multiple Myeloma (MM) drug efficacy prediction study. All code, data, and results are provided with reproducible run IDs and provenance tracking.

**Key Results Reproduced:**
- **100% Pathway Alignment Accuracy** (5/5 MAPK variants correctly matched)
- **Average Confidence: 0.49-0.52** across SP and SPE modes
- **Ablation Study:** 7 modes × 7 variants demonstrating component contributions
- **Calibration Metrics:** ECE=0.479, MCE=0.479 for full SPE model

---

## System Requirements

### Hardware
- **CPU:** 4+ cores recommended (8+ for parallel processing)
- **RAM:** 8GB minimum, 16GB recommended
- **Storage:** 5GB free space for models and results
- **Network:** Stable internet connection for Evo2 API access

### Software
- **OS:** macOS 10.15+, Ubuntu 20.04+, or Windows 10+ with WSL2
- **Python:** 3.9.x (tested on 3.9.6)
- **Git:** 2.30+
- **Optional:** Docker 20.10+ for containerized reproduction

---

## Installation

### 1. Clone Repository

```bash
git clone https://github.com/[org]/oncology-copilot.git
cd oncology-copilot/oncology-backend-minimal
```

### 2. Create Python Environment

```bash
python3.9 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
pip install matplotlib numpy  # For plotting
```

### 4. Configure Environment Variables

Create `.env` file in `oncology-backend-minimal/`:

```bash
# Evo2 Model Endpoints (required)
EVO_URL_1B=https://crispro--evo-service-evoservice1b-api-1b.modal.run
EVO_FORCE_MODEL=evo2_1b
EVO_ALLOWED_MODELS=evo2_1b
EVO_USE_DELTA_ONLY=0

# Service Configuration
ENABLE_INSIGHTS_API=1
DISABLE_FUSION=0

# Research Flags (all OFF for publication mode)
RESEARCH_USE_PATHWAY_PRIOR=0
RESEARCH_USE_CLINVAR_CANONICAL=0
RESEARCH_USE_COHORT_OVERLAY=0
RESEARCH_FORCE_CONSIDER_TIERS=0
```

---

## Running Experiments

### Start Backend Service

```bash
cd oncology-backend-minimal
PYTHONPATH=. python3 -m uvicorn api.main:app --host 127.0.0.1 --port 8000
```

Wait for "Application startup complete" message.

### Run Core Experiments

**1. Baseline MM Validation (5 minutes)**

```bash
cd scripts
python3 run_mm_baseline.py
```

Expected output:
```
Pathway Alignment Accuracy: 5/5 (100.0%)
Average Confidence: 0.487
```

**2. Full Ablation Study (30-45 minutes)**

```bash
python3 run_mm_ablations.py
```

Tests 7 ablation modes (S, P, E, SP, SE, PE, SPE) across 7 variants.

Expected key results:
- SP: 100% accuracy, 0.467 confidence
- SPE: 100% accuracy, 0.524 confidence
- S-only, P-only, E-only: 40% accuracy

**3. Generate Calibration Plots (1 minute)**

```bash
python3 generate_calibration_plots.py
```

Generates 4 publication-ready figures:
- `calibration_curve_SP.png`
- `calibration_curve_SPE.png`
- `confidence_distributions.png`
- `ablation_comparison.png`

---

## Test Variants

All experiments use 7 canonical MM variants with verified GRCh38 coordinates:

| Gene  | Variant | Chr | Position  | Ref | Alt | Expected Drug   | Category |
|-------|---------|-----|-----------|-----|-----|-----------------|----------|
| BRAF  | V600E   | 7   | 140753336 | A   | T   | BRAF inhibitor  | MAPK     |
| BRAF  | V600K   | 7   | 140753335 | G   | A   | BRAF inhibitor  | MAPK     |
| KRAS  | G12D    | 12  | 25245350  | C   | T   | MEK inhibitor   | MAPK     |
| KRAS  | G12V    | 12  | 25245350  | C   | A   | MEK inhibitor   | MAPK     |
| NRAS  | Q61K    | 1   | 114716127 | T   | G   | MEK inhibitor   | MAPK     |
| TP53  | R248W   | 17  | 7675088   | C   | T   | None (control)  | TP53     |
| TP53  | R273H   | 17  | 7674220   | G   | A   | None (control)  | TP53     |

---

## Output Files

All results are saved with timestamps and provenance tracking:

### Results Directory Structure

```
results/
├── mm_baseline/
│   └── mm_efficacy_results_[timestamp].json
├── mm_ablations/
│   └── ablation_results_[timestamp].json
└── mm_calibration/
    ├── calibration_curve_SP.png
    ├── calibration_curve_SPE.png
    ├── confidence_distributions.png
    ├── ablation_comparison.png
    └── calibration_metrics.json
```

### Key Metrics Files

**Baseline Results** (`mm_baseline/mm_efficacy_results_*.json`):
- Per-variant predictions with all drugs ranked
- Confidence scores, evidence tiers, badges
- Provenance: model ID, ablation mode, run timestamp

**Ablation Results** (`mm_ablations/ablation_results_*.json`):
```json
{
  "summary": {
    "SP": {
      "pathway_accuracy": 1.0,
      "avg_confidence": 0.467,
      "mapk_correct": 5,
      "mapk_total": 5
    },
    "SPE": { ... }
  }
}
```

**Calibration Metrics** (`mm_calibration/calibration_metrics.json`):
```json
{
  "SPE": {
    "ece": 0.479,
    "mce": 0.479,
    "bin_accuracies": [1.0],
    "bin_confidences": [0.521]
  }
}
```

---

## Validation Checks

### 1. Backend Health Check

```bash
curl http://127.0.0.1:8000/health
```

Expected: `{"status": "healthy"}`

### 2. Evo2 Connectivity

```bash
curl -X POST http://127.0.0.1:8000/api/evo/warmup
```

Expected: `{"status": "ready", "model": "evo2_1b"}`

### 3. Quick Smoke Test

```bash
python3 run_mm_baseline.py --smoke
```

Runs 3 variants only (BRAF V600E/K, KRAS G12D). Expected: 3/3 correct.

---

## Troubleshooting

### Common Issues

**1. ModuleNotFoundError**
```bash
# Ensure virtual environment is activated
source venv/bin/activate
pip install -r requirements.txt
```

**2. Evo2 Connection Timeout**
```bash
# Check Evo2 service availability
curl https://crispro--evo-service-evoservice1b-api-1b.modal.run/health

# If unavailable, wait and retry (service may be cold-starting)
```

**3. Low Pathway Accuracy (<100%)**
```bash
# Verify all research flags are OFF
unset RESEARCH_USE_PATHWAY_PRIOR RESEARCH_USE_CLINVAR_CANONICAL \
      RESEARCH_USE_COHORT_OVERLAY RESEARCH_FORCE_CONSIDER_TIERS
```

**4. Backend Fails to Start**
```bash
# Check if port 8000 is in use
lsof -i :8000
kill -9 [PID]

# Restart with full logging
PYTHONPATH=. python3 -m uvicorn api.main:app --host 127.0.0.1 --port 8000 --log-level debug
```

---

## Computational Cost

**Estimated runtime and API calls:**

| Experiment          | Runtime    | API Calls | Evo2 Calls |
|---------------------|------------|-----------|------------|
| Baseline (7 vars)   | 5 min      | ~35       | ~140       |
| Ablations (7×7)     | 30-45 min  | ~245      | ~980       |
| Calibration plots   | 1 min      | 0         | 0          |
| **Total**           | **~50 min**| **~280**  | **~1120**  |

**Cost estimate:** ~$0.50-$1.00 (depending on Evo2 API pricing)

---

## Citations & References

If you use this code or reproduce our results, please cite:

```bibtex
@article{mm_drug_efficacy_2025,
  title={Multiple Myeloma Drug Efficacy Prediction via Multi-Modal Genomic Analysis},
  author={[Authors]},
  journal={[Journal]},
  year={2025},
  doi={[DOI]}
}
```

**Data Sources:**
- Variant coordinates: GRCh38/hg38 (UCSC Genome Browser)
- Drug mechanisms: DrugBank, FDA labels
- Pathway annotations: KEGG, Reactome

---

## Contact & Support

**Questions or issues?**
- GitHub Issues: https://github.com/[org]/oncology-copilot/issues
- Email: [contact email]
- Documentation: https://[docs site]

**License:** [License Type]

---

## Changelog

**v1.0 (Oct 2, 2025):** Initial publication release
- 100% pathway alignment on canonical MM variants
- Complete ablation study (S, P, E combinations)
- Publication-ready calibration plots
- Full reproducibility documentation

