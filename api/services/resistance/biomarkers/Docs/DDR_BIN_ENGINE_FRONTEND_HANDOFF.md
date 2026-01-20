# 🎨 DDR_bin Engine - Front-End Integration Handoff

**Date:** January 13, 2026  
**Status:** 📋 **READY FOR FRONT-END INTEGRATION**  
**Priority:** **P1 - High Priority**  
**Owner:** Front-End Team

---

## 🎯 Objective

This document provides a comprehensive handoff for integrating the **DDR_bin Scoring Engine** into the front-end application. The DDR_bin engine is a pan-solid-tumor DDR deficiency classifier that determines whether a patient has `DDR_defective`, `DDR_proficient`, or `unknown` DDR status.

---

## 📋 What Was Built (Backend)

### **Backend Components Completed:**

1. **DDR Config System** (`config/ddr_config.py`)
   - Disease-specific configurations for ovary, breast, pancreas, prostate, default
   - Configurable HRD cutoffs, gene lists, rules priority

2. **DDR Scoring Engine** (`biomarkers/diagnostic/ddr_bin_scoring.py`)
   - Core `assign_ddr_status()` function
   - Priority-ordered rules (BRCA > HRD > core HRR > extended DDR)
   - Biallelic loss detection
   - HRD inference (score vs status)

3. **Unit Tests** (`test_ddr_bin_scoring.py`)
   - 12 comprehensive test cases - ALL PASSING (12/12)

### **Backend API Status:**

**Current State:** DDR_bin engine is ready but **NOT YET EXPOSED** via REST API endpoints.  
**Front-End Requirement:** Backend team needs to expose DDR_bin scoring via API endpoints.

---

## 🔌 Backend API Requirements (For Backend Team)

### **Recommended API Endpoint:**

```
POST /api/resistance/ddr-status
```

**Request Body:**
```typescript
interface DDRStatusRequest {
  patient_id: string;
  disease_site: 'ovary' | 'breast' | 'pancreas' | 'prostate' | 'other';
  tumor_subtype?: string | null;  // e.g., "HGSOC", "TNBC", "PDAC"
  
  // Mutation data (required)
  mutations: Array<{
    gene_symbol: string;              // e.g., "BRCA1", "BRCA2", "ATM"
    variant_classification: string;    // "pathogenic", "likely_pathogenic", "VUS", "benign"
    variant_type?: string;             // "SNV", "indel", "rearrangement"
  }>;
  
  // Copy-number alterations (optional)
  cna?: Array<{
    gene_symbol: string;
    copy_number_state: string;        // "deletion", "loss", "neutral", "gain", "amplification"
    copy_number?: number;              // Optional numeric value
  }>;
  
  // HRD assay results (optional)
  hrd_assay?: {
    hrd_score?: number | null;        // Continuous HRD score (e.g., 45.0)
    hrd_status?: string | null;       // "HRD_positive", "HRD_negative", "equivocal", "unknown"
    assay_name?: string;               // "Myriad", "Leuven", "Geneva", "other"
  };
}
```

**Response Body:**
```typescript
interface DDRStatusResponse {
  patient_id: string;
  disease_site: string;
  tumor_subtype: string | null;
  
  // Primary classification
  DDR_bin_status: 'DDR_defective' | 'DDR_proficient' | 'unknown';
  
  // HRD information
  HRD_status_inferred: 'HRD_positive' | 'HRD_negative' | 'unknown';
  HRD_score_raw: number | null;
  
  // Flags
  BRCA_pathogenic: boolean;
  core_HRR_pathogenic: boolean;
  extended_DDR_pathogenic: boolean;
  
  // Scoring
  DDR_score: number;                   // Weighted sum (0.0-8.0)
  DDR_features_used: string[] | null;  // Which rules fired, e.g., ["BRCA_pathogenic"]
  
  // Metadata
  timestamp: string;                   // ISO 8601 timestamp
  config_used: {
    disease_site: string;
    hrd_score_cutoff: number;
    core_hrr_genes: string[];
    extended_ddr_genes: string[];
  };
}
```

### **Alternative: Batch Endpoint**

For multiple patients:

```
POST /api/resistance/ddr-status/batch
```

**Request Body:**
```typescript
interface DDRStatusBatchRequest {
  patients: DDRStatusRequest[];
}
```

**Response Body:**
```typescript
interface DDRStatusBatchResponse {
  results: DDRStatusResponse[];
  total: number;
  successful: number;
  errors: Array<{
    patient_id: string;
    error: string;
  }>;
}
```

---

## 🎨 Front-End Integration Requirements

### **1. Data Input Forms**

#### **1.1 Patient Information Form**
- **Disease Site Dropdown:**
  - Options: `ovary`, `breast`, `pancreas`, `prostate`, `other`
  - Required field
  
- **Tumor Subtype Input (Optional):**
  - Free text or dropdown
  - Examples: "HGSOC", "TNBC", "PDAC", etc.
  - Optional field

#### **1.2 Mutation Input Form**
- **Gene Symbol Input:**
  - Type-ahead search or dropdown
  - Common DDR genes: BRCA1, BRCA2, PALB2, ATM, ATR, CHEK2, RAD51C, RAD51D, etc.
  - Required for each mutation
  
- **Variant Classification Dropdown:**
  - Options: `pathogenic`, `likely_pathogenic`, `VUS`, `benign`, `likely_benign`
  - Required for each mutation
  
- **Variant Type Input (Optional):**
  - Options: `SNV`, `indel`, `rearrangement`, etc.
  - Optional field

- **Add/Remove Mutations:**
  - Allow adding multiple mutations
  - Remove button for each mutation row
  - Minimum 0 mutations (optional)

#### **1.3 Copy-Number Alterations (CNA) Input Form (Optional)**
- **Gene Symbol Input:**
  - Type-ahead search or dropdown
  - Should match genes from mutations (optional)
  
- **Copy-Number State Dropdown:**
  - Options: `deletion`, `loss`, `neutral`, `gain`, `amplification`
  - Required for each CNA
  
- **Copy Number Input (Optional):**
  - Numeric input
  - Optional field

#### **1.4 HRD Assay Results Input Form (Optional)**
- **HRD Score Input:**
  - Numeric input (float)
  - Optional (can use status instead)
  
- **HRD Status Dropdown:**
  - Options: `HRD_positive`, `HRD_negative`, `equivocal`, `unknown`
  - Optional (can use score instead)
  
- **Assay Name Input:**
  - Options: `Myriad`, `Leuven`, `Geneva`, `other`
  - Free text or dropdown
  - Optional field

### **2. DDR Status Display Components**

#### **2.1 Primary Status Card**
```typescript
interface DDRStatusCardProps {
  ddr_bin_status: 'DDR_defective' | 'DDR_proficient' | 'unknown';
  confidence?: number;  // Optional confidence score
}

// Visual Design:
// - DDR_defective: Red badge/alert (critical)
// - DDR_proficient: Green badge (normal)
// - unknown: Gray badge (insufficient data)
```

**Display Elements:**
- **Status Badge:** Large, color-coded badge with status text
- **Interpretation Text:** 
  - `DDR_defective`: "Patient has DDR deficiency. May benefit from PARPi therapy."
  - `DDR_proficient`: "Patient has intact DDR pathway. Consider alternative therapies."
  - `unknown`: "Insufficient data to determine DDR status."
- **DDR Score:** Numeric score (0.0-8.0) with visual bar/progress indicator

#### **2.2 Feature Breakdown Component**
Display which rules fired:

```typescript
interface FeatureBreakdownProps {
  DDR_features_used: string[];
  BRCA_pathogenic: boolean;
  core_HRR_pathogenic: boolean;
  extended_DDR_pathogenic: boolean;
  HRD_status_inferred: string;
}
```

**Display Elements:**
- **Checklist/List:**
  - ✅ BRCA Pathogenic (if `BRCA_pathogenic === true`)
  - ✅ HRD Positive (if `HRD_status_inferred === "HRD_positive"`)
  - ✅ Core HRR Pathogenic (if `core_HRR_pathogenic === true`)
  - ✅ Extended DDR Pathogenic (if `extended_DDR_pathogenic === true`)
- **Visual Hierarchy:** Show active features prominently, inactive features grayed out

#### **2.3 HRD Information Panel**
```typescript
interface HRDPanelProps {
  HRD_status_inferred: string;
  HRD_score_raw: number | null;
  hrd_score_cutoff: number;  // From config (e.g., 42)
}
```

**Display Elements:**
- **HRD Status Badge:** Color-coded (positive=red, negative=green, unknown=gray)
- **HRD Score Display:**
  - If `HRD_score_raw` available: Show score vs cutoff (e.g., "45.0 (cutoff: 42)")
  - Visual indicator: Red if above cutoff, green if below
- **Assay Name:** Display if available

#### **2.4 Mutation Summary Table**
Display detected mutations that contributed to DDR status:

```typescript
interface MutationSummaryTableProps {
  mutations: Array<{
    gene_symbol: string;
    variant_classification: string;
    contribution: 'BRCA' | 'core_HRR' | 'extended_DDR';
  }>;
}
```

**Columns:**
- Gene Symbol
- Variant Classification
- Contribution (BRCA/Core HRR/Extended DDR)
- Badge/Indicator

### **3. Clinical Decision Support UI**

#### **3.1 Recommendations Panel**
Based on DDR_bin_status, show treatment recommendations:

```typescript
interface RecommendationsPanelProps {
  ddr_bin_status: 'DDR_defective' | 'DDR_proficient' | 'unknown';
  disease_site: string;
}
```

**Recommendations:**

**If `DDR_defective`:**
- ✅ Consider PARPi therapy (olaparib, niraparib, rucaparib)
- ✅ Consider ATR inhibitors
- ✅ Consider WEE1 inhibitors
- ⚠️ Monitor for resistance mechanisms

**If `DDR_proficient`:**
- ⚠️ PARPi therapy likely less effective
- ✅ Consider alternative therapies (standard chemo, targeted therapy)
- ℹ️ DDR pathway intact

**If `unknown`:**
- ⚠️ Insufficient data for DDR classification
- ✅ Consider additional genomic testing
- ℹ️ Cannot make DDR-based treatment recommendations

#### **3.2 Treatment Eligibility Indicator**
Visual indicator for PARPi eligibility:

```typescript
interface EligibilityIndicatorProps {
  ddr_bin_status: 'DDR_defective' | 'DDR_proficient' | 'unknown';
  disease_site: string;
}

// Visual Design:
// - DDR_defective: Green "ELIGIBLE" badge
// - DDR_proficient: Red "NOT ELIGIBLE" badge
// - unknown: Yellow "INSUFFICIENT DATA" badge
```

### **4. Data Validation & Error Handling**

#### **4.1 Input Validation**
- **Required Fields:**
  - `patient_id` (required)
  - `disease_site` (required)
  - `mutations` (required, but can be empty array)
  
- **Optional Fields:**
  - `tumor_subtype` (optional)
  - `cna` (optional)
  - `hrd_assay` (optional)

#### **4.2 Error States**
- **No Mutations, No HRD Data:**
  - Show warning: "Insufficient data - DDR status will be 'unknown'"
  - Allow submission but show expected result
  
- **Invalid Gene Symbols:**
  - Show validation error
  - Suggest correct gene symbols (type-ahead)
  
- **Invalid Variant Classification:**
  - Show validation error
  - Only allow valid options: `pathogenic`, `likely_pathogenic`, `VUS`, `benign`, `likely_benign`
  
- **API Errors:**
  - Display error message from backend
  - Retry button
  - Support/contact information

### **5. User Experience Flow**

#### **5.1 Typical User Flow:**

1. **Patient Selection/Entry**
   - User selects or enters patient ID
   - Selects disease site from dropdown
   - Optionally enters tumor subtype

2. **Mutation Entry**
   - User adds mutations (one or more)
   - For each mutation: selects gene, variant classification, optional variant type
   - Can add/remove mutations dynamically

3. **Optional Data Entry**
   - User can optionally add CNA data
   - User can optionally add HRD assay results

4. **Submission**
   - User clicks "Calculate DDR Status" button
   - Loading spinner while API call in progress
   - Results displayed below form

5. **Results Display**
   - Primary status card (large, prominent)
   - Feature breakdown
   - HRD information panel
   - Mutation summary table
   - Recommendations panel
   - Treatment eligibility indicator

#### **5.2 Quick Actions:**
- **Save Results:** Export to PDF/CSV
- **Print:** Print-friendly view
- **Share:** Share results with clinical team
- **History:** View previous DDR status calculations for same patient

---

## 🧪 Front-End Testing Requirements

### **Unit Tests:**
- [ ] Form validation tests
- [ ] Data transformation tests (request → API format)
- [ ] Display component tests (all DDR_bin_status states)
- [ ] Error handling tests

### **Integration Tests:**
- [ ] API call tests (mock backend)
- [ ] End-to-end flow tests (form submission → results display)
- [ ] Error state handling tests

### **Test Cases:**

1. **BRCA Pathogenic Case:**
   - Input: BRCA1 pathogenic mutation
   - Expected: `DDR_bin_status = "DDR_defective"`, `BRCA_pathogenic = true`

2. **HRD Positive Case:**
   - Input: HRD score = 45 (above cutoff of 42)
   - Expected: `DDR_bin_status = "DDR_defective"`, `HRD_status_inferred = "HRD_positive"`

3. **No Data Case:**
   - Input: No mutations, no HRD data
   - Expected: `DDR_bin_status = "unknown"`, warning message displayed

4. **Multiple Disease Sites:**
   - Test ovary, breast, pancreas, prostate, other
   - Verify different configurations are used

---

## 📊 Example Use Cases

### **Example 1: Ovarian Cancer Patient (BRCA1 Pathogenic)**

**Input:**
```json
{
  "patient_id": "OV-001",
  "disease_site": "ovary",
  "tumor_subtype": "HGSOC",
  "mutations": [
    {
      "gene_symbol": "BRCA1",
      "variant_classification": "pathogenic",
      "variant_type": "SNV"
    }
  ]
}
```

**Expected Output:**
```json
{
  "patient_id": "OV-001",
  "disease_site": "ovary",
  "tumor_subtype": "HGSOC",
  "DDR_bin_status": "DDR_defective",
  "HRD_status_inferred": "unknown",
  "HRD_score_raw": null,
  "BRCA_pathogenic": true,
  "core_HRR_pathogenic": false,
  "extended_DDR_pathogenic": false,
  "DDR_score": 3.0,
  "DDR_features_used": ["BRCA_pathogenic"]
}
```

**UI Display:**
- **Status Badge:** 🔴 RED - "DDR_DEFECTIVE"
- **Recommendation:** "Consider PARPi therapy (olaparib, niraparib, rucaparib)"
- **Eligibility:** ✅ "PARPi ELIGIBLE"

### **Example 2: Breast Cancer Patient (HRD Positive)**

**Input:**
```json
{
  "patient_id": "BR-002",
  "disease_site": "breast",
  "tumor_subtype": "TNBC",
  "mutations": [],
  "hrd_assay": {
    "hrd_score": 48,
    "hrd_status": null,
    "assay_name": "Myriad"
  }
}
```

**Expected Output:**
```json
{
  "patient_id": "BR-002",
  "disease_site": "breast",
  "tumor_subtype": "TNBC",
  "DDR_bin_status": "DDR_defective",
  "HRD_status_inferred": "HRD_positive",
  "HRD_score_raw": 48.0,
  "BRCA_pathogenic": false,
  "core_HRR_pathogenic": false,
  "extended_DDR_pathogenic": false,
  "DDR_score": 2.5,
  "DDR_features_used": ["HRD_score_high"]
}
```

**UI Display:**
- **Status Badge:** 🔴 RED - "DDR_DEFECTIVE"
- **HRD Score:** "48.0 (cutoff: 42)" - Above cutoff indicator
- **Recommendation:** "Consider PARPi therapy"

### **Example 3: Insufficient Data Case**

**Input:**
```json
{
  "patient_id": "PA-003",
  "disease_site": "pancreas",
  "tumor_subtype": "PDAC",
  "mutations": [],
  "hrd_assay": null
}
```

**Expected Output:**
```json
{
  "patient_id": "PA-003",
  "disease_site": "pancreas",
  "tumor_subtype": "PDAC",
  "DDR_bin_status": "unknown",
  "HRD_status_inferred": "unknown",
  "HRD_score_raw": null,
  "BRCA_pathogenic": false,
  "core_HRR_pathogenic": false,
  "extended_DDR_pathogenic": false,
  "DDR_score": 0.0,
  "DDR_features_used": null
}
```

**UI Display:**
- **Status Badge:** ⚪ GRAY - "UNKNOWN"
- **Warning Message:** "Insufficient data - DDR status cannot be determined"
- **Recommendation:** "Consider additional genomic testing"

---

## 🎨 UI/UX Design Recommendations

### **Color Scheme:**
- **DDR_defective:** Red (#dc3545) - Critical/Warning
- **DDR_proficient:** Green (#28a745) - Normal/Safe
- **unknown:** Gray (#6c757d) - Unknown/Neutral

### **Typography:**
- **Status Badge:** Large, bold, all caps (e.g., "DDR_DEFECTIVE")
- **Recommendations:** Clear, readable, bullet points
- **Technical Details:** Smaller font, collapsible sections

### **Layout:**
- **Primary Status:** Top of results, large and prominent
- **Feature Breakdown:** Below status, collapsible if needed
- **Recommendations:** Sidebar or below features
- **Technical Details:** Collapsible section at bottom

### **Accessibility:**
- Color-blind friendly (use icons + colors)
- Screen reader support
- Keyboard navigation
- ARIA labels for status badges

---

## 📚 Backend Integration Details

### **Current Backend Location:**
- **Engine:** `api/services/resistance/biomarkers/diagnostic/ddr_bin_scoring.py`
- **Config:** `api/services/resistance/config/ddr_config.py`

### **Backend Function Signature:**
```python
assign_ddr_status(
    mutations_table: List[Dict[str, Any]],
    clinical_table: List[Dict[str, Any]],
    cna_table: Optional[List[Dict[str, Any]]] = None,
    hrd_assay_table: Optional[List[Dict[str, Any]]] = None,
    config: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]
```

### **Backend Response Format:**
Matches `DDRStatusResponse` TypeScript interface above.

---

## ⚠️ Important Notes

### **1. DDR_bin is PROGNOSTIC, NOT PREDICTIVE**
- **Prognostic:** Predicts overall survival (HR=0.62, p=0.013) ✅
- **NOT Predictive:** Does NOT predict platinum response at baseline (AUROC=0.52, p=0.80) ❌
- **Front-End Display:** Should make this distinction clear in UI

### **2. Disease-Specific Behavior**
- All differences between diseases are driven by `DDR_CONFIG`
- No hard-coded "ovary only" logic
- Front-end should display which disease site configuration is being used

### **3. Gene-Based Engine**
- This is a **gene-based** engine (variant classification + HRD assay)
- **Different** from SAE-based DDR_bin (which uses diamond features)
- Front-end should distinguish between these two approaches if both are available

### **4. Optional Fields**
- CNA and HRD assay are **optional**
- Engine works with mutations alone
- If no mutations and no HRD, result will be `unknown`

---

## 🚀 Implementation Checklist

### **Backend Team:**
- [ ] Create `/api/resistance/ddr-status` endpoint
- [ ] Create `/api/resistance/ddr-status/batch` endpoint (optional)
- [ ] Add request/response validation
- [ ] Add error handling
- [ ] Add API documentation (OpenAPI/Swagger)
- [ ] Add integration tests

### **Front-End Team:**
- [ ] Design DDR status input form
- [ ] Design DDR status display components
- [ ] Implement API integration
- [ ] Implement form validation
- [ ] Implement error handling
- [ ] Implement recommendations panel
- [ ] Implement treatment eligibility indicator
- [ ] Add unit tests
- [ ] Add integration tests
- [ ] Add accessibility features
- [ ] Add print/export functionality

---

## 📞 Questions & Support

### **Backend Questions:**
- Contact: Resistance Prophet Team
- Documentation: `api/services/resistance/DDR_BIN_ENGINE.md`

### **Front-End Questions:**
- Contact: Front-End Team Lead
- Design System: (reference your design system docs)

---

## 📋 Next Steps

1. **Backend Team:** Implement API endpoints (Priority 1)
2. **Front-End Team:** Design UI mockups (Priority 1)
3. **Front-End Team:** Implement form components (Priority 2)
4. **Front-End Team:** Implement display components (Priority 2)
5. **Front-End Team:** Integration testing (Priority 3)
6. **Both Teams:** End-to-end testing (Priority 3)

---

**Last Updated:** January 13, 2026  
**Status:** 📋 **READY FOR FRONT-END INTEGRATION**  
**Next Review:** After API endpoints are implemented
