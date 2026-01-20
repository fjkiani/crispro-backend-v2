# 🧪 EVO2 PAPER CAPABILITIES VALIDATION TESTS

## 🎯 Purpose

Validate key Evo2 capabilities mentioned in the paper review (`.cursor/concept/evo2-paper-review.md`).

These tests prove that our platform can leverage Evo2's core capabilities:
- Zero-shot variant prediction (BRCA1, noncoding)
- Exon-intron boundary detection (SAE features)
- Genome-scale generation
- Cross-domain generalization
- Frameshift/stop codon sensitivity
- Noncoding variant SOTA performance

---

## 🧪 Test Cases

### **Test 1: BRCA1 Zero-Shot Prediction**
- **Paper claim:** "Zero-shot sets SOTA on BRCA1 noncoding SNVs"
- **Test:** Score known BRCA1 pathogenic variants (coding + noncoding)
- **Expected:** Non-zero delta scores, higher magnitude for pathogenic

### **Test 2: Exon-Intron Boundary Detection**
- **Paper claim:** "SAE features reveal exon/intron boundaries"
- **Test:** Score variants at exon boundaries vs intron centers
- **Expected:** Higher delta magnitude at exon boundaries (more constrained)

### **Test 3: Genome-Scale Generation**
- **Paper claim:** "Generates 16kb mitochondrial, 580kb prokaryotic, 330kb yeast chromosomes"
- **Test:** Generate therapeutic guide RNA sequences (smaller scale validation)
- **Expected:** Biologically plausible sequences with proper PAM sites

### **Test 4: Cross-Domain Generalization**
- **Paper claim:** "Zero-shot predictions work across DNA/RNA/protein and domains of life"
- **Test:** Score variants in human (eukaryote) context
- **Expected:** Valid scores demonstrating cross-domain capability

### **Test 5: Frameshift/Stop Codon Sensitivity**
- **Paper claim:** "Stronger disruption for nonsyn, frameshift, stop"
- **Test:** Compare missense vs frameshift variants
- **Expected:** Frameshift should have higher magnitude deltas

### **Test 6: Noncoding Variant SOTA**
- **Paper claim:** "State-of-the-art for noncoding SNVs/non-SNVs"
- **Test:** Score noncoding variants (intronic, intergenic)
- **Expected:** Valid scores for noncoding variants (not just coding)

---

## ⚡ How to Run

### **Option 1: Run Full Suite**
```bash
cd oncology-coPilot/oncology-backend-minimal

# Using pytest
PYTHONPATH=. venv/bin/pytest tests/test_evo2_paper_capabilities.py::test_master_validation_suite -v -s

# OR directly with Python
PYTHONPATH=. venv/bin/python tests/test_evo2_paper_capabilities.py
```

### **Option 2: Run Individual Tests**
```bash
# Test 1: BRCA1 Zero-Shot
PYTHONPATH=. venv/bin/pytest tests/test_evo2_paper_capabilities.py::test_1_brca1_zero_shot_prediction -v -s

# Test 2: Exon-Intron Boundaries
PYTHONPATH=. venv/bin/pytest tests/test_evo2_paper_capabilities.py::test_2_exon_intron_boundary_detection -v -s

# Test 3: Generation
PYTHONPATH=. venv/bin/pytest tests/test_evo2_paper_capabilities.py::test_3_genome_scale_generation -v -s

# Test 4: Cross-Domain
PYTHONPATH=. venv/bin/pytest tests/test_evo2_paper_capabilities.py::test_4_cross_domain_generalization -v -s

# Test 5: Frameshift Sensitivity
PYTHONPATH=. venv/bin/pytest tests/test_evo2_paper_capabilities.py::test_5_frameshift_stop_sensitivity -v -s

# Test 6: Noncoding SOTA
PYTHONPATH=. venv/bin/pytest tests/test_evo2_paper_capabilities.py::test_6_noncoding_variant_sota -v -s
```

---

## 📊 Expected Results

### **Success Criteria:**
- ✅ All 6 tests should pass
- ✅ Delta scores should be non-zero for pathogenic variants
- ✅ Exon boundaries should show higher sensitivity than intron centers
- ✅ Generated sequences should be biologically plausible (no N bases, proper length)
- ✅ Frameshift variants should show higher magnitude than missense
- ✅ Noncoding variants should return valid scores

### **Output Files:**
- `evo2_paper_validation_results.json` - Complete test results with metrics

---

## 🔧 Configuration

### **Model Selection:**
- Default: `evo2_1b` (cost-controlled)
- Can upgrade to `evo2_7b` or `evo2_40b` for validation (update `model_id` parameter)

### **Cost Estimate:**
- `evo2_1b`: <$0.01 total for all tests
- `evo2_7b`: ~$0.05-0.10 total
- `evo2_40b`: ~$0.20-0.50 total

---

## 📚 Related Documentation

- **Paper Review:** `.cursor/concept/evo2-paper-review.md`
- **Evo2 Validation Tests:** `tests/test_evo2_real_validation.py`
- **Evo2 Router:** `api/routers/evo.py`
- **Design Router:** `api/routers/design.py`

---

## ⚠️ Notes

- These tests validate **capabilities**, not exact performance metrics
- Actual performance may vary based on model size and context
- Some tests require specific genomic coordinates (may need updates for different builds)
- Results are saved to JSON for analysis and comparison

---

**Status:** ✅ Ready to run  
**Last Updated:** January 13, 2025

