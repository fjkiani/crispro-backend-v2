# 📄 Data Extraction Agent - Module 01

**Status:** ✅ **COMPLETE**  
**Priority:** 🔴 CRITICAL | **Dependencies:** None | **Consumers:** All downstream agents

---

## 📋 Overview

The Data Extraction Agent extracts structured patient data from various file formats:
- **VCF** (Variant Call Format) - Standard NGS output
- **MAF** (Mutation Annotation Format) - TCGA-style format
- **PDF** (NGS reports) - LLM-based extraction
- **JSON** (Structured mutation data)
- **TXT/CSV** (Clinical notes) - Pattern-based extraction

---

## 🏗️ Architecture

```
DataExtractionAgent
    │
    ├── VCFParser
    │   ├── Parse header lines
    │   ├── Extract variants
    │   └── Extract VAF, coverage
    │
    ├── MAFParser
    │   ├── Parse tab-delimited format
    │   └── Extract mutations
    │
    ├── PDFParser
    │   ├── PyMuPDF text extraction
    │   └── LLM-based structured extraction (Gemini)
    │
    ├── JSONParser
    │   └── Direct JSON parsing
    │
    └── TextParser
        └── Pattern-based mutation extraction
```

---

## 📁 File Structure

```
api/services/extraction/
├── __init__.py
├── extraction_agent.py        # Main agent class
├── models.py                   # PatientProfile, Mutation, etc.
├── parsers/
│   ├── __init__.py
│   ├── vcf_parser.py          # VCF parsing
│   ├── maf_parser.py          # MAF parsing
│   ├── pdf_parser.py          # PDF + LLM extraction
│   ├── json_parser.py         # JSON parsing
│   └── text_parser.py         # Text pattern matching
└── README.md                   # This file
```

---

## 🚀 Core Components

### **DataExtractionAgent** (`extraction_agent.py`)

Main agent class that orchestrates extraction:

**Key Methods:**
- `extract(file, file_type, metadata)` - Main extraction method
- `_extract_mutations()` - Extract mutation objects
- `_build_mutation()` - Build Mutation from dict
- `_validate_mutation()` - Validate mutation data
- `_extract_clinical_data()` - Extract clinical information
- `_extract_demographics()` - Extract demographics
- `_check_data_quality()` - Generate quality flags

**Process:**
1. Select parser based on file_type
2. Parse file to raw data
3. Extract mutations
4. Validate and normalize mutations
5. Extract clinical data and demographics
6. Check data quality
7. Build PatientProfile

### **Parsers**

#### **VCFParser** (`parsers/vcf_parser.py`)
- Parses VCF 4.1, 4.2, 4.3
- Extracts gene, variant, HGVS notation
- Extracts VAF from FORMAT fields
- Handles multi-sample VCFs (uses first sample)
- Supports gzipped VCF files

#### **MAFParser** (`parsers/maf_parser.py`)
- Parses tab-delimited MAF format
- Handles various column name variations
- Extracts gene, variant, HGVS, VAF, coverage

#### **PDFParser** (`parsers/pdf_parser.py`)
- Uses PyMuPDF for text extraction
- Uses Gemini LLM for structured extraction
- Falls back to pattern matching if LLM unavailable
- Supports Foundation Medicine, Tempus, Guardant reports

#### **JSONParser** (`parsers/json_parser.py`)
- Direct JSON parsing
- Handles both list and dict formats

#### **TextParser** (`parsers/text_parser.py`)
- Pattern-based mutation extraction
- Simple regex matching for gene mutations
- Note: Less accurate than structured formats

---

## 📊 Data Models

### **PatientProfile**

```python
@dataclass
class PatientProfile:
    patient_id: str
    disease: str
    mutations: List[Mutation]
    germline_panel: Optional[GermlinePanel]
    clinical_data: Optional[ClinicalData]
    demographics: Optional[Demographics]
    data_quality_flags: List[str]
    extraction_provenance: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
```

### **Mutation**

```python
@dataclass
class Mutation:
    gene: str
    variant: str
    hgvs_c: Optional[str]
    hgvs_p: Optional[str]
    chromosome: Optional[str]
    position: Optional[int]
    ref: Optional[str]
    alt: Optional[str]
    vaf: Optional[float]
    coverage: Optional[int]
    zygosity: Zygosity
    source: MutationSource
    classification: Optional[str]
```

---

## 🔗 Integration

### **Orchestrator Integration**

The agent is wired to the orchestrator in `orchestrator.py`:

```python
async def _run_extraction_phase(self, state: PatientState, file: BinaryIO, file_type: str):
    from ..extraction import DataExtractionAgent
    
    agent = DataExtractionAgent()
    profile = await agent.extract(
        file=file,
        file_type=file_type,
        metadata={'patient_id': state.patient_id}
    )
    
    state.patient_profile = profile.to_dict()
    state.mutations = [m.to_dict() for m in profile.mutations]
    state.disease = profile.disease
```

### **Pipeline Flow**

```
Phase 1: EXTRACTING
├── User uploads file (VCF, PDF, MAF, etc.)
├── DataExtractionAgent.extract()
├── Parse file → Extract mutations
└── Store in state.patient_profile
```

---

## ✅ Features

- **Multi-format Support**: VCF, MAF, PDF, JSON, TXT/CSV
- **LLM-based PDF Extraction**: Uses Gemini for intelligent extraction
- **Pattern Fallback**: Pattern matching when LLM unavailable
- **Data Validation**: Validates mutations before storage
- **Quality Flags**: Flags missing data (VAF, HGVS, etc.)
- **Provenance Tracking**: Tracks extraction method and confidence

---

## 🧪 Testing

**Unit Tests Needed:**
- VCF parser with sample files
- MAF parser with sample files
- PDF parser (with and without LLM)
- JSON parser
- Text parser
- DataExtractionAgent integration

**Target Coverage:** >80%

---

## 📝 Usage Example

```python
from api.services.extraction import DataExtractionAgent

agent = DataExtractionAgent()

# Extract from VCF
with open('patient.vcf', 'rb') as f:
    profile = await agent.extract(
        file=f,
        file_type='vcf',
        metadata={'patient_id': 'PT-12345', 'lab': 'Foundation Medicine'}
    )

print(f"Extracted {len(profile.mutations)} mutations")
print(f"Disease: {profile.disease}")
print(f"Quality flags: {profile.data_quality_flags}")
```

---

## 🔗 Dependencies

### **Required**
- Python 3.9+

### **Optional (for PDF)**
- `PyMuPDF` (fitz) - PDF text extraction
- `google-genai` - LLM-based extraction

**Note:** PDF parsing will use pattern matching if LLM is unavailable.

---

**Module Status:** ✅ **COMPLETE**  
**Last Updated:** January 2025  
**Owner:** Auto (JR Agent D)


