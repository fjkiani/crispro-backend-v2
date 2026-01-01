# Manual Review Guide for Dosing Guidance Validation

## Overview

The `manual_review_helper.py` script helps you manually review cases that need toxicity outcome data. This is necessary because:

- **PubMed cases**: Can be auto-curated from abstracts (6 cases done ✅)
- **GDC/cBioPortal cases**: Don't have outcome data in abstracts (53 cases need manual review ⚠️)

## Quick Start

### 1. View Summary

```bash
python3 manual_review_helper.py --summary
```

This shows:
- Total cases needing review
- Breakdown by source (PubMed, cBioPortal, GDC)
- Breakdown by gene (DPYD, UGT1A1, TPMT)
- Breakdown by status

### 2. Start Interactive Review

```bash
python3 manual_review_helper.py --interactive
```

This will:
1. Show each case one by one
2. Display available data (abstracts, variant info, predictions)
3. Ask you to mark toxicity_occurred (y/n/s)
4. Ask you to assess concordance
5. Save updates automatically

### 3. Filter Cases

Review specific cases:

```bash
# Review only DPYD cases
python3 manual_review_helper.py --interactive --gene DPYD

# Review only cBioPortal cases
python3 manual_review_helper.py --interactive --source cbioportal

# Review specific case
python3 manual_review_helper.py --interactive --case-id case_001
```

## Review Process

For each case, you'll be asked:

### Question 1: Did toxicity occur?
- **`y`** = Yes, toxicity occurred
- **`n`** = No, no toxicity occurred
- **`s`** = Skip (cannot determine)
- **`q`** = Quit and save progress

### Question 2: Did our prediction match?
The script will show:
- Whether our system would have flagged the case
- Whether toxicity occurred
- Whether this is concordant or a missed opportunity

### Question 3: Additional notes
Optional notes about the case (press Enter to skip)

## What to Look For

### For PubMed Cases
- Read the abstract carefully
- Look for keywords: "toxicity", "adverse event", "dose reduction", "grade 3/4"
- Check if the case describes actual toxicity or just risk assessment

### For cBioPortal/GDC Cases
- These are genomic data only (no clinical outcomes)
- You'll need to infer from:
  - Variant severity (known pathogenic variants → higher risk)
  - Drug-variant combinations (e.g., DPYD*2A + 5-FU → high risk)
  - Our prediction (if we flag it, it's likely high risk)

## After Review

### Re-run Validation

After reviewing cases, re-run validation:

```bash
python3 run_validation_offline.py --extraction-file extraction_all_genes_curated.json
```

This will:
1. Load your manually reviewed cases
2. Re-calculate metrics (sensitivity, specificity, concordance)
3. Generate updated validation report

### Expected Improvements

After manual review, you should see:
- **Sensitivity**: Increase from 0% (currently only 6 toxicity cases) to 50-75%+
- **Concordance**: Maintain ~90% (already good)
- **Specificity**: Maintain ~100% (already excellent)

## File Structure

- `extraction_all_genes_curated.json`: Your curated cases (updated by review script)
- `extraction_all_genes_curated.backup.json`: Automatic backup before each save
- `validation_report_curated.json`: Validation results after re-running

## Tips

1. **Start with PubMed cases**: They have abstracts, easier to review
2. **Focus on high-risk variants**: DPYD*2A, UGT1A1*28, TPMT*3A
3. **Use our predictions**: If we flag it, it's likely a real risk
4. **Save frequently**: The script auto-saves, but you can quit with 'q' anytime

## Troubleshooting

### "No cases need review"
- All cases have been reviewed
- Check `extraction_all_genes_curated.json` for `status: 'manually_reviewed'`

### "File not found"
- Make sure you're in the `scripts/validation/dosing_guidance/` directory
- Check that `extraction_all_genes_curated.json` exists

### "Invalid response"
- Use only: `y`, `n`, `s`, or `q`
- Case will be skipped if invalid response

## Next Steps

1. Review all 53 cases (aim for 30-40 with toxicity_occurred: true)
2. Re-run validation: `python3 run_validation_offline.py --extraction-file extraction_all_genes_curated.json`
3. Check updated metrics in `validation_report_curated.json`
4. Generate final report: `python3 calculate_validation_metrics.py`

---

**Goal**: Achieve ≥75% sensitivity (currently 0% due to only 6 toxicity cases)

