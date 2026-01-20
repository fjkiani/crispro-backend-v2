# ⚔️ PLUMBER TIER 1 DEEP DIVE - EXACT CODE & FORMULAS

**Date:** January 13, 2025  
**Agent:** Plumber (Zo)  
**Mission:** Answer TIER 1 questions with exact code snippets, formulas, and parameters

---

## 🔬 Q1: EVO2 API CONTRACT

### **File:** `api/services/sequence_scorers/evo2_scorer.py`

### **ACTUAL CODE:**

```python
# Lines 328-339: Evo2 API Endpoint Calls
multi = await client.post(
    f"{self.api_base}/api/evo/score_variant_multi",
    json={
        "assembly": build,  # GRCh37 or GRCh38
        "chrom": chrom, 
        "pos": pos, 
        "ref": ref, 
        "alt": alt, 
        "model_id": model_id
    },
    headers={"Content-Type": "application/json"}
)

# Lines 365-377: Exon-specific scoring
exon = await client.post(
    f"{self.api_base}/api/evo/score_variant_exon",
    json={
        "assembly": build,
        "chrom": chrom, 
        "pos": pos, 
        "ref": ref, 
        "alt": alt, 
        "flank": int(flank),  # Window size: 4096, 8192, 16384, 25000
        "model_id": model_id
    },
    headers={"Content-Type": "application/json"}
)
```

### **ANSWERS:**

1. **Endpoints Called:**
   - `/api/evo/score_variant_multi` - Multi-window min_delta scoring
   - `/api/evo/score_variant_exon` - Exon-context scoring with flanks

2. **Input Format:**
   - **Coordinates:** `chrom`, `pos`, `ref`, `alt` (VCF-style)
   - **Assembly:** `GRCh37` or `GRCh38` (auto-detected from mutation.build)
   - **Window Flanks:** `[4096, 8192, 16384, 25000]` (default, line 48)
   - **Model ID:** `evo2_1b`, `evo2_7b`, `evo2_40b` (ensemble mode, line 213)

3. **Output Structure:**
   ```python
   # From score_variant_multi:
   {
       "min_delta": float,  # Minimum delta across all windows
   }
   
   # From score_variant_exon:
   {
       "exon_delta": float,  # Exon-context delta for specific flank
   }
   ```

4. **Context Window Handling:**
   - **NOT using 1M token window** - Using adaptive windows (4096-25000 bp flanks)
   - **Multi-window probing:** Tests 4 different flank sizes, picks best
   - **Exon scanning:** Optional (can be disabled via `evo_use_delta_only` flag, line 348)

5. **Zero-shot vs Supervised:**
   - **Zero-shot** - No training data required, Evo2 is pre-trained
   - **Calibration:** Post-hoc percentile mapping (not supervised learning)

6. **Response Time:**
   - **Timeout:** 180 seconds per variant (line 77)
   - **Blocking:** Yes, async but sequential per variant
   - **Caching:** Results cached for 3600 seconds (1 hour, line 316)

7. **Failure Handling:**
   ```python
   # Lines 90-194: Curated Fallback Priors
   def _curated_disruption_prior(mv: Dict[str, Any]) -> Optional[SeqScore]:
       # PGx hotspots (DPYD, TPMT, UGT1A1) - hardcoded scores
       # LoF consequences → 0.90 disruption
       # Missense → 0.30 disruption
       # Default → 0.10 disruption
   ```
   - **Fallback Strategy:** If Evo2 API fails OR missing alleles, use curated priors
   - **Missing alleles:** If `ref`/`alt` not in `{"A","C","G","T"}`, use fallback (line 185)

### **SPECIFIC CODE - Hotspot Detection (Line 147):**

```python
# Lines 258-271: Hotspot Floor Enforcement
HOTSPOT_FLOOR = 1e-4  # Maps to path_pct≈1.0 in DrugScorer
if gene_sym == "BRAF" and "V600" in hgvs_p:
    sequence_disruption = max(sequence_disruption, HOTSPOT_FLOOR)
if gene_sym in {"KRAS", "NRAS", "HRAS"} and any(k in hgvs_p for k in ("G12", "G13", "Q61")):
    sequence_disruption = max(sequence_disruption, HOTSPOT_FLOOR)
# TP53 hotspots: support both 1-letter (R175) and 3-letter (Arg175) codes
if gene_sym == "TP53" and any(k in hgvs_p for k in ("R175", "ARG175", "R248", "ARG248", "R273", "ARG273")):
    sequence_disruption = max(sequence_disruption, HOTSPOT_FLOOR)
```

### **SPECIFIC CODE - Calibrated Percentile (Line 169):**

```python
# Lines 280-293: Percentile Mapping
pct = percentile_like(sequence_disruption)  # From utils.py

# Percentile mapping function (utils.py:7-23):
def percentile_like(value: float) -> float:
    v = float(max(0.0, value))
    if v <= 0.005: return 0.05
    if v <= 0.01: return 0.10
    if v <= 0.02: return 0.20
    if v <= 0.05: return 0.50
    if v <= 0.10: return 0.80
    return 1.0

# Hotspot-aware minimums (lines 285-291):
if gene_sym == "BRAF" and "V600" in hgvs_p:
    pct = max(pct, 0.90)
elif gene_sym in {"KRAS", "NRAS", "HRAS"} and any(k in hgvs_p for k in ("G12", "G13", "Q61")):
    pct = max(pct, 0.80)
elif gene_sym == "TP53" and any(k in hgvs_p for k in ("R175", "ARG175", "R248", "ARG248", "R273", "ARG273")):
    pct = max(pct, 0.80)
```

### **EXPLANATION:**

- **Calibrated Percentile:** NOT gene-calibrated - it's a **global piecewise mapping** of raw disruption → percentile
- **Calibration Dataset:** None - heuristic mapping based on disruption magnitude
- **TP53 R175H:** NOT hardcoded to 0.8 - it's **enforced minimum** if Evo2 returns lower
- **Fallback for Novel Genes:** Uses same global percentile mapping (no gene-specific calibration)

### **PARAMETERS:**

- **Window Flanks:** `[4096, 8192, 16384, 25000]` (default)
- **Timeout:** 180 seconds
- **Cache TTL:** 3600 seconds
- **Hotspot Floor:** `1e-4` (minimum disruption for known hotspots)
- **TP53 R175H Minimum Percentile:** 0.80 (enforced, not learned)

### **EDGE CASES:**

- **Missing Alleles:** Falls back to curated priors (PGx hotspots, LoF, missense)
- **API Failure:** Returns empty list, falls back to curated priors
- **Invalid Coordinates:** Uses curated fallback
- **Symmetry:** Forward/reverse averaging (can be disabled via `evo_disable_symmetry` flag, line 410)

---

## 🧬 Q4: PATHWAY ASSIGNMENT LOGIC

### **File:** `api/services/pathway/drug_mapping.py` (gene→pathway)  
### **File:** `api/services/pathway/aggregation.py` (aggregation formula)

### **ACTUAL CODE - Gene→Pathway Mapping:**

```python
# Lines 43-107: get_pathway_weights_for_gene()
def get_pathway_weights_for_gene(gene_symbol: str) -> Dict[str, float]:
    g = gene_symbol.strip().upper()
    
    # MAPK/RAS pathway
    if g in {"BRAF", "KRAS", "NRAS", "EGFR", "MAP2K1", "MAPK1", "MEK1", "MEK2"}:
        return {"ras_mapk": 1.0}
    
    # DDR pathway (separate from TP53)
    if g in {"BRCA1", "BRCA2", "ATM", "ATR", "CDK12", "ARID1A", "CHEK1", "RAD50", 
             "PALB2", "RAD51", "RAD51C", "RAD51D", "BARD1", "NBN", "MBD4"}:
        return {"ddr": 1.0}
    
    # TP53 pathway (separate from DDR)
    if g in {"TP53", "MDM2", "CHEK2"}:
        return {"tp53": 1.0}
    
    # PI3K pathway
    if g in {"PTEN", "PIK3CA", "PIK3CB", "PIK3CD", "AKT1", "AKT2", "AKT3", "MTOR"}:
        return {"pi3k": 1.0}
    
    # VEGF pathway
    if g in {"VEGFA", "VEGFR1", "VEGFR2", "KDR", "FLT1"}:
        return {"vegf": 1.0}
    
    return {}
```

### **ACTUAL CODE - Pathway Aggregation:**

```python
# Lines 18-70: aggregate_pathways()
def aggregate_pathways(seq_scores: List[Dict[str, Any]]) -> Dict[str, float]:
    pathway_totals: Dict[str, float] = {}
    pathway_counts: Dict[str, int] = {}
    
    for score in seq_scores:
        pathway_weights = score.get("pathway_weights") or {}
        variant = score.get("variant") or {}
        gene = str((variant.get("gene") or "")).strip().upper()
        consequence = str((variant.get("consequence") or "")).lower()
        
        # Raw disruption is primary signal
        raw = float(score.get("sequence_disruption") or 0.0)
        pct = float(score.get("calibrated_seq_percentile") or 0.0)
        
        # Selective hotspot lift (TP53/BRAF/KRAS/NRAS only)
        signal = raw
        if gene in HOTSPOT_GENES and pct >= 0.7:  # HOTSPOT_GENES = {"TP53", "BRAF", "KRAS", "NRAS"}
            signal = max(signal, 0.5 * pct)  # Bounded lift: 50% of percentile
        
        for pathway, weight in pathway_weights.items():
            # Conservative DDR missense gating
            if pathway == "ddr" and "missense" in consequence and raw < 0.02:
                continue  # Skip low-disruption missense from DDR
            
            pathway_totals[pathway] = pathway_totals.get(pathway, 0.0) + (signal * float(weight))
            pathway_counts[pathway] = pathway_counts.get(pathway, 0) + 1
    
    # Compute average scores
    pathway_scores: Dict[str, float] = {}
    for pathway, total in pathway_totals.items():
        n = pathway_counts.get(pathway, 0)
        pathway_scores[pathway] = (total / n) if n else 0.0
    
    return pathway_scores
```

### **ANSWERS:**

1. **Gene→Pathway Mapping:**
   - **Hardcoded dictionary** (not database)
   - **One-to-one mapping:** Each gene maps to ONE pathway with weight 1.0
   - **No multi-pathway genes:** A gene belongs to exactly one pathway

2. **Pathways Beyond DDR/TP53:**
   - `ras_mapk` (MAPK/RAS): BRAF, KRAS, NRAS, EGFR, MAP2K1, MAPK1, MEK1, MEK2
   - `ddr` (DNA Damage Response): BRCA1, BRCA2, ATM, ATR, CDK12, ARID1A, CHEK1, RAD50, PALB2, RAD51, RAD51C, RAD51D, BARD1, NBN, **MBD4**
   - `tp53` (TP53 pathway): TP53, MDM2, CHEK2
   - `pi3k` (PI3K/AKT): PTEN, PIK3CA, PIK3CB, PIK3CD, AKT1, AKT2, AKT3, MTOR
   - `vegf` (VEGF/Angiogenesis): VEGFA, VEGFR1, VEGFR2, KDR, FLT1

3. **Genes Per Pathway:**
   - **DDR:** 15 genes (BRCA1, BRCA2, ATM, ATR, CDK12, ARID1A, CHEK1, RAD50, PALB2, RAD51, RAD51C, RAD51D, BARD1, NBN, MBD4)
   - **MAPK:** 8 genes
   - **TP53:** 3 genes
   - **PI3K:** 8 genes
   - **VEGF:** 5 genes

4. **Multi-Pathway Genes:**
   - **NOT SUPPORTED** - Each gene maps to exactly one pathway
   - **TP53 is separate from DDR** - They are different pathways

5. **Normalization:**
   - **Average:** `pathway_score = sum(signal * weight) / count`
   - **NOT max, NOT sum, NOT weighted average** - Simple arithmetic mean

6. **MBD4 (1.0) + TP53 (0.8) → DDR Formula:**
   - **MBD4 maps to `ddr` pathway** (weight 1.0)
   - **TP53 maps to `tp53` pathway** (weight 1.0)
   - **TP53→DDR contribution:** Handled in `pathway_to_mechanism_vector.py` line 245:
     ```python
     # TP53 contributes 50% to DDR in mechanism vector
     mechanism_vector[ddr_idx] = ddr_score + (tp53_score * 0.5)
     ```
   - **NOT in pathway aggregation** - TP53 stays as separate `tp53` pathway, only combined in mechanism vector

### **PARAMETERS:**

- **Hotspot Genes:** `{"TP53", "BRAF", "KRAS", "NRAS"}` (line 15 in aggregation.py)
- **Hotspot Lift Threshold:** `pct >= 0.7` (line 49)
- **Hotspot Lift Formula:** `signal = max(raw, 0.5 * pct)` (line 51)
- **DDR Missense Gate:** `raw < 0.02` (line 59)

### **EDGE CASES:**

- **Missing Pathway Weights:** Returns empty dict `{}`
- **Zero Count:** Pathway score = 0.0 (line 68)
- **Low-Disruption Missense in DDR:** Skipped entirely (line 59-60)
- **Unknown Gene:** Returns empty dict, no pathway assignment

---

## 🎯 Q5: 7D MECHANISM VECTOR FORMULA

### **File:** `api/services/pathway_to_mechanism_vector.py`

### **ACTUAL CODE:**

```python
# Lines 198-269: convert_pathway_scores_to_mechanism_vector()
def convert_pathway_scores_to_mechanism_vector(
    pathway_scores: Dict[str, float],
    tumor_context: Optional[Dict[str, Any]] = None,
    tmb: Optional[float] = None,
    msi_status: Optional[str] = None,
    use_7d: bool = False
) -> Tuple[List[float], str]:
    
    # Normalize pathway names
    normalized_scores = {}
    for pathway, score in pathway_scores.items():
        normalized = normalize_pathway_name(pathway)
        if normalized:
            normalized_scores[normalized] = float(score)
    
    # Detect dimension (prefer 7D if HER2 present)
    if 'her2' in normalized_scores or any('her2' in k for k in normalized_scores.keys()):
        use_7d = True
    
    mechanism_map = MECHANISM_INDICES_7D if use_7d else MECHANISM_INDICES_6D
    vector_size = 7 if use_7d else 6
    
    # Build mechanism vector
    mechanism_vector = [0.0] * vector_size
    
    # Handle TP53 → DDR mapping with 50% contribution
    ddr_idx = mechanism_map.get('ddr', 0)
    tp53_score = normalized_scores.get('tp53', 0.0)
    ddr_score = normalized_scores.get('ddr', 0.0)
    
    # Combine DDR + 50% of TP53
    mechanism_vector[ddr_idx] = ddr_score + (tp53_score * 0.5)  # LINE 245
    
    # Map other pathways (skip tp53 and ddr since already handled)
    for pathway, score in normalized_scores.items():
        if pathway in ('tp53', 'ddr'):
            continue
        idx = mechanism_map.get(pathway)
        if idx is not None:
            # Accumulate if pathway already has a value
            mechanism_vector[idx] = max(mechanism_vector[idx], float(score))
    
    # Calculate IO score from tumor context
    io_idx = 4 if use_7d else 4  # IO is always index 4
    if tumor_context:
        tmb = tumor_context.get('tmb', 0)
        msi_status = tumor_context.get('msi_status', '')
    
    if tmb and tmb >= 20:
        mechanism_vector[io_idx] = 1.0
    elif msi_status and msi_status.upper() in ['MSI-H', 'MSI-HIGH', 'MSI-H']:
        mechanism_vector[io_idx] = 1.0
    else:
        mechanism_vector[io_idx] = 0.0
    
    return mechanism_vector, dimension_used
```

### **MECHANISM VECTOR INDICES:**

```python
# Lines 49-58: 7D Mechanism Vector
MECHANISM_INDICES_7D = {
    'ddr': 0,
    'ras_mapk': 1,
    'pi3k': 2,
    'vegf': 3,
    'her2': 4,
    'io': 5,
    'efflux': 6
}
```

### **ANSWERS:**

1. **Exact Formula Per Dimension:**

   - **DDR (Index 0):** `ddr_score + (tp53_score * 0.5)`
     - Combines DDR pathway score + 50% of TP53 pathway score
   
   - **MAPK (Index 1):** `ras_mapk_score` (direct mapping)
   
   - **PI3K (Index 2):** `pi3k_score` (direct mapping)
   
   - **VEGF (Index 3):** `vegf_score` (direct mapping)
   
   - **HER2 (Index 4):** `her2_score` (direct mapping, 7D only)
   
   - **IO (Index 5):** 
     ```python
     if tmb >= 20: 1.0
     elif msi_status == "MSI-H": 1.0
     else: 0.0
     ```
   
   - **Efflux (Index 6):** `efflux_score` (direct mapping, 7D only)

2. **Dimension Independence:**
   - **Independent** - Each dimension calculated separately
   - **Exception:** TP53 contributes 50% to DDR (line 245)

3. **Normalization Strategy:**
   - **NO normalization** - Raw pathway scores used directly
   - **IO is binary:** 0.0 or 1.0 (based on TMB/MSI thresholds)
   - **Other dimensions:** Continuous [0, 1] from pathway aggregation

4. **Missing Pathway Data:**
   - **Set to 0.0** - Initialized as `[0.0] * vector_size` (line 237)
   - **No prior/default** - Missing pathways = 0.0

5. **All Zeros:**
   - **Returns all-zero vector** - No mechanism disruption detected
   - **Mechanism fit will be disabled** - Warning logged (line 124)

### **PARAMETERS:**

- **TP53→DDR Contribution:** 50% (0.5 multiplier, line 245)
- **TMB Threshold:** ≥20 mut/Mb → IO = 1.0 (line 262)
- **MSI Threshold:** MSI-H → IO = 1.0 (line 264)
- **IO Index:** Always 4 (both 6D and 7D)

### **EDGE CASES:**

- **Missing Tumor Context:** TMB/MSI default to 0/empty → IO = 0.0
- **Invalid Pathway Name:** Normalized to lowercase, may not match → skipped
- **Multiple Pathways to Same Index:** Uses `max()` to accumulate (line 254)
- **TP53 Without DDR:** TP53 still contributes 50% to DDR index (even if ddr_score = 0)

---

## 🎯 Q6: DRUG RANKING CONFIDENCE FORMULA

### **File:** `api/services/efficacy_orchestrator/drug_scorer.py`  
### **File:** `api/services/confidence/confidence_computation.py`

### **ACTUAL CODE - Base Confidence:**

```python
# Lines 147-154: Base Confidence Calculation
insights_dict = {
    "functionality": insights.functionality or 0.0,
    "chromatin": insights.chromatin or 0.0,
    "essentiality": insights.essentiality or 0.0,
    "regulatory": insights.regulatory or 0.0,
}
confidence = compute_confidence(tier, seq_pct, path_pct, insights_dict, confidence_config)
```

### **ACTUAL CODE - Confidence Computation (V2):**

```python
# Lines 111-160: compute_confidence_v2() (if CONFIDENCE_V2=1)
def compute_confidence_v2(tier: str, seq_pct: float, path_pct: float, 
                         insights: Dict[str, float], config: ConfidenceConfig) -> float:
    func = insights.get("functionality", 0.0)
    chrom = insights.get("chromatin", 0.0)
    ess = insights.get("essentiality", 0.0)
    reg = insights.get("regulatory", 0.0)
    
    # Convert tier to evidence score (E component)
    if tier == "supported":
        e_score = 0.05
    elif tier == "consider":
        e_score = 0.02
    else:  # insufficient
        e_score = 0.00
    
    # Calculate lifts
    lifts = 0.0
    lifts += 0.04 if func >= 0.6 else 0.0      # Functionality
    lifts += 0.02 if chrom >= 0.5 else 0.0     # Chromatin
    lifts += 0.02 if ess >= 0.7 else 0.0       # Essentiality
    lifts += 0.02 if reg >= 0.6 else 0.0       # Regulatory
    
    # Cap total lifts at +0.08
    lifts = min(lifts, 0.08)
    
    # Linear S/P/E formula
    confidence = 0.5 * seq_pct + 0.2 * path_pct + 0.3 * e_score + lifts
    
    # Clamp to [0, 1] and round to 2 decimals
    confidence = clamp01(confidence)
    return round(confidence, 2)
```

### **ACTUAL CODE - Confidence Computation (LEGACY):**

```python
# Lines 70-108: compute_confidence() (default, if CONFIDENCE_V2=0)
def compute_confidence(tier: str, seq_pct: float, path_pct: float, 
                      insights: Dict[str, float], config: ConfidenceConfig) -> float:
    func = insights.get("functionality", 0.0)
    chrom = insights.get("chromatin", 0.0)
    ess = insights.get("essentiality", 0.0)
    reg = insights.get("regulatory", 0.0)
    
    # Base confidence by tier
    if tier == "supported":
        confidence = 0.6 + 0.2 * max(seq_pct, path_pct)
    elif tier == "consider":
        if config.fusion_active and max(seq_pct, path_pct) >= 0.7:
            confidence = 0.5 + 0.2 * max(seq_pct, path_pct)
        else:
            confidence = 0.3 + 0.1 * seq_pct + 0.1 * path_pct
    else:  # insufficient
        max_sp = max(seq_pct, path_pct)
        min_sp = min(seq_pct, path_pct)
        base = 0.20 + 0.35 * max_sp + 0.15 * min_sp
        if config.fusion_active:
            confidence = max(0.25, base)
        else:
            confidence = base
    
    # Insights modulation
    confidence += 0.05 if func >= 0.6 else 0.0
    confidence += 0.04 if chrom >= 0.5 else 0.0
    confidence += 0.07 if ess >= 0.7 else 0.0
    confidence += 0.02 if reg >= 0.6 else 0.0
    
    # Alignment margin boost
    margin = abs(seq_pct - path_pct)
    if margin >= 0.2:
        confidence += 0.05
    
    return float(min(1.0, max(0.0, confidence)))
```

### **ACTUAL CODE - Drug-Specific Boosts:**

```python
# Lines 157-223: Drug-Specific Confidence Modifications

# DDR-class gating (line 164)
if ddr_signal < 0.02 and path_pct < 0.05:
    confidence -= 0.10  # Penalty for low DDR signal on PARP/platinum

# ClinVar boost (line 173)
if clinvar_prior > 0 and path_pct >= 0.2:
    confidence += min(0.1, clinvar_prior)

# HRR→PARP boost (line 189)
if primary_gene in {"BRCA1", "BRCA2", "PALB2", "RAD51C", "RAD51D", "ATM", "CDK12", "MBD4"}:
    if is_parp:
        confidence += 0.08
    if is_atr:
        confidence -= 0.02
    if is_wee1:
        confidence -= 0.02

# ARID1A→ATR boost (line 206)
if primary_gene == "ARID1A":
    if is_atr:
        confidence += 0.06
    if is_wee1:
        confidence -= 0.02

# Gene-drug target match (line 218)
if primary_gene == "BRAF" and drug_name == "BRAF inhibitor":
    confidence += 0.01
elif primary_gene in {"KRAS", "NRAS"} and drug_name == "MEK inhibitor":
    confidence += 0.01
```

### **ANSWERS:**

1. **EXACT Confidence Formula (V2):**
   ```
   confidence = 0.5 * seq_pct + 0.2 * path_pct + 0.3 * e_score + lifts
   
   Where:
   - seq_pct = calibrated_seq_percentile (from Evo2)
   - path_pct = normalized pathway percentile (s_path / 0.005)
   - e_score = 0.05 (supported), 0.02 (consider), 0.00 (insufficient)
   - lifts = sum of insights lifts (capped at 0.08)
   ```

2. **Insights Lifts:**
   - **Functionality ≥ 0.6:** +0.04
   - **Chromatin ≥ 0.5:** +0.02
   - **Essentiality ≥ 0.7:** +0.07 (LEGACY) or +0.02 (V2)
   - **Regulatory ≥ 0.6:** +0.02
   - **Total Cap:** +0.08 (V2) or unlimited (LEGACY)

3. **Drug Ranking with Identical Confidence:**
   - **NOT EXPLICITLY HANDLED** - No secondary sort key in code
   - **Likely:** Sorted by confidence descending, ties remain

4. **Mechanism Fit Calculation:**
   - **NOT in drug_scorer.py** - Mechanism fit is separate (in trial matching)
   - **Pathway alignment:** Uses `path_pct` (normalized pathway score)

5. **Off-Target Penalty:**
   - **DDR-class gating:** -0.10 if DDR signal < 0.02 and path_pct < 0.05 (line 167)
   - **ATR/WEE1 penalty:** -0.02 when HRR genes present (lines 193, 195)

6. **Synthetic Lethality Scoring:**
   - **NOT in drug_scorer.py** - Synthetic lethality is separate service
   - **Gene-drug boosts:** +0.08 for PARP on HRR genes (line 191)

### **PARAMETERS:**

- **S/P/E Weights (V2):** 0.5 (S), 0.2 (P), 0.3 (E)
- **Pathway Normalization Max:** 0.005 (line 55 in drug_scorer.py)
- **DDR Gate Threshold:** 0.02 (line 166)
- **ClinVar Boost Max:** 0.1 (line 174)
- **HRR→PARP Boost:** +0.08 (line 191)
- **ARID1A→ATR Boost:** +0.06 (line 207)
- **Target Match Boost:** +0.01 (lines 219, 221)

### **EDGE CASES:**

- **Missing Insights:** All insights default to 0.0
- **Evidence Timeout:** Tier = "insufficient", e_score = 0.00
- **Zero Pathway Score:** path_pct = 0.0
- **All Zeros:** Confidence = 0.0 (no base confidence floor in V2)

---

## 📊 SUMMARY: TIER 1 ANSWERS

### **Q1: Evo2 API Contract**
- **Endpoints:** `/api/evo/score_variant_multi`, `/api/evo/score_variant_exon`
- **Input:** VCF coordinates (chrom, pos, ref, alt), assembly, window flanks
- **Output:** `min_delta`, `exon_delta` (raw disruption scores)
- **Calibration:** Global piecewise mapping (NOT gene-specific)
- **Fallback:** Curated priors for missing alleles/API failures

### **Q4: Pathway Assignment**
- **Mapping:** Hardcoded dictionary (gene → pathway, weight 1.0)
- **Pathways:** DDR (15 genes), TP53 (3 genes), MAPK (8 genes), PI3K (8 genes), VEGF (5 genes)
- **Aggregation:** `sum(signal * weight) / count` (arithmetic mean)
- **TP53→DDR:** 50% contribution in mechanism vector (NOT in pathway aggregation)

### **Q5: 7D Mechanism Vector**
- **Formula:** Direct mapping + TP53 50% to DDR + IO binary (TMB≥20 or MSI-H)
- **Dimensions:** [DDR, MAPK, PI3K, VEGF, HER2, IO, Efflux]
- **Normalization:** None - raw pathway scores used directly
- **Missing Data:** Set to 0.0

### **Q6: Drug Ranking Confidence**
- **Formula (V2):** `0.5*S + 0.2*P + 0.3*E + lifts` (capped at 0.08)
- **Insights Lifts:** Functionality (+0.04), Chromatin (+0.02), Essentiality (+0.02), Regulatory (+0.02)
- **Drug Boosts:** HRR→PARP (+0.08), ARID1A→ATR (+0.06), target match (+0.01)
- **Penalties:** DDR-class gating (-0.10), ATR/WEE1 on HRR (-0.02)

---

**END OF TIER 1 DEEP DIVE**
