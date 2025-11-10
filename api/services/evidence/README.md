# 📚 Evidence Client Package

## Overview
The Evidence Client package provides literature search and ClinVar prior analysis capabilities for drug efficacy predictions. This package integrates with multiple evidence sources to provide comprehensive evidence assessment with MoA-aware filtering and provenance tracking.

## 🏗️ Architecture

```
evidence/
├── __init__.py              # Clean exports and package interface
├── models.py                # EvidenceHit, ClinvarPrior dataclasses
├── literature_client.py     # Literature search functionality
├── clinvar_client.py        # ClinVar prior analysis
├── badge_computation.py     # Badge determination logic
├── conversion_utils.py      # Data conversion utilities
└── README.md               # This documentation
```

## 🚀 Core Components

### 1. **Literature Client** (`literature_client.py`)
**Purpose**: Literature search with MoA-aware filtering and evidence scoring

**Key Features**:
- ✅ **PubMed Integration**: Comprehensive literature search
- ✅ **MoA-Aware Filtering**: Drug mechanism of action boosting
- ✅ **Publication Type Scoring**: RCT > Guideline > Review > Other
- ✅ **Evidence Strength Calculation**: Weighted scoring based on publication types
- ✅ **Timeout Handling**: 60-second timeout for literature calls
- ✅ **Error Resilience**: Graceful degradation with provenance tracking

**Scoring Algorithm**:
```python
def _score_evidence_from_results(top_results):
    score = 0.0
    for result in top_results[:3]:
        pub_types = " ".join([str(t).lower() for t in result.get("publication_types", [])])
        title = str(result.get("title", "")).lower()
        
        if "randomized" in pub_types or "randomized" in title:
            score += 0.5      # RCT
        elif "guideline" in pub_types or "practice" in title:
            score += 0.35     # Guideline
        elif "review" in pub_types or "meta" in title:
            score += 0.25     # Review
        else:
            score += 0.15     # Other
    
    return min(1.0, score)
```

**Usage**:
```python
from evidence import literature

result = await literature(
    api_base="http://127.0.0.1:8000",
    gene="BRAF",
    hgvs_p="V600E",
    drug_name="vemurafenib",
    drug_moa="BRAF inhibitor",
    disease="multiple myeloma"
)

print(f"Strength: {result.strength}")
print(f"MoA Hits: {result.moa_hits}")
print(f"Citations: {len(result.filtered)}")
```

### 2. **ClinVar Client** (`clinvar_client.py`)
**Purpose**: ClinVar prior analysis with classification and review status

**Key Features**:
- ✅ **Deep Analysis Integration**: Calls `/api/evidence/deep_analysis`
- ✅ **Classification Parsing**: Pathogenic, likely_pathogenic, benign, likely_benign
- ✅ **Review Status Assessment**: Expert panel, practice guideline, criteria provided
- ✅ **Prior Strength Calculation**: Weighted by classification and review strength
- ✅ **GRCh38 Support**: Assembly-aware variant lookup
- ✅ **Timeout Handling**: 40-second timeout for ClinVar calls

**Prior Calculation**:
```python
# Pathogenic variants
if classification in ("pathogenic", "likely_pathogenic"):
    prior = 0.2 if strong else (0.1 if moderate else 0.05)

# Benign variants  
elif classification in ("benign", "likely_benign"):
    prior = -0.2 if strong else (-0.1 if moderate else -0.05)
```

**Usage**:
```python
from evidence import clinvar_prior

result = await clinvar_prior(
    api_base="http://127.0.0.1:8000",
    gene="BRAF",
    variant={
        "chrom": "7",
        "pos": 140453136,
        "ref": "T",
        "alt": "A",
        "hgvs_p": "V600E"
    }
)

print(f"Prior: {result.prior}")
print(f"Classification: {result.deep_analysis['clinvar']['classification']}")
```

### 3. **Badge Computation** (`badge_computation.py`)
**Purpose**: Evidence badge determination based on literature and ClinVar results

**Key Features**:
- ✅ **Literature Badges**: StrongLiterature, ModerateLiterature
- ✅ **MoA Alignment**: MoAAligned badge for mechanism hits
- ✅ **ClinVar Badges**: ClinVarStrong, ClinVarModerate, ClinVarBenign
- ✅ **Publication Type Badges**: RCT, Guideline detection
- ✅ **Comprehensive Coverage**: All evidence types covered

**Badge Types**:
- **StrongLiterature**: Evidence strength ≥0.7
- **ModerateLiterature**: Evidence strength ≥0.4
- **MoAAligned**: MoA hits >0
- **ClinVarStrong**: Pathogenic + expert/practice review
- **ClinVarModerate**: Pathogenic + criteria provided
- **ClinVarBenign**: Benign classification
- **RCT**: Randomized controlled trial
- **Guideline**: Practice guideline

### 4. **Data Models** (`models.py`)
**Purpose**: Structured data classes for evidence results

**Key Models**:
- `EvidenceHit`: Literature evidence result
- `ClinvarPrior`: ClinVar prior analysis result

## 📊 Data Models

### **EvidenceHit**
```python
@dataclass
class EvidenceHit:
    top_results: List[Dict[str, Any]]    # All literature results
    filtered: List[Dict[str, Any]]       # MoA-filtered results
    strength: float                      # Evidence strength [0,1]
    pubmed_query: Optional[str] = None   # PubMed query string
    moa_hits: int = 0                   # MoA reference count
    provenance: Dict[str, Any] = None    # Provenance tracking
```

### **ClinvarPrior**
```python
@dataclass
class ClinvarPrior:
    deep_analysis: Optional[Dict[str, Any]]  # Full ClinVar analysis
    prior: float                             # Prior strength [-0.2, 0.2]
    provenance: Dict[str, Any] = None        # Provenance tracking
```

## 🔧 Configuration

### API Configuration
```python
# Literature search parameters
literature_params = {
    "time_window": "since 2015",      # Publication time window
    "max_results": 8,                 # Maximum results to fetch
    "include_abstracts": True,        # Include abstracts
    "synthesize": True,               # Synthesize results
    "moa_terms": ["vemurafenib", "BRAF inhibitor"]  # MoA terms
}

# ClinVar analysis parameters
clinvar_params = {
    "assembly": "GRCh38",             # Assembly version
    "chrom": "7",                     # Chromosome
    "pos": 140453136,                 # Position
    "ref": "T",                       # Reference allele
    "alt": "A"                        # Alternate allele
}
```

### Timeout Configuration
```python
# Literature search timeout
LITERATURE_TIMEOUT = 60.0  # seconds

# ClinVar analysis timeout  
CLINVAR_TIMEOUT = 40.0     # seconds
```

## 🧪 Usage Examples

### Basic Literature Search
```python
from evidence import literature

# Search for BRAF V600E literature
result = await literature(
    api_base="http://127.0.0.1:8000",
    gene="BRAF",
    hgvs_p="V600E",
    drug_name="vemurafenib",
    drug_moa="BRAF inhibitor",
    disease="melanoma"
)

print(f"Evidence Strength: {result.strength:.3f}")
print(f"Total Results: {len(result.top_results)}")
print(f"MoA-Filtered: {len(result.filtered)}")
print(f"MoA Hits: {result.moa_hits}")
print(f"PubMed Query: {result.pubmed_query}")
```

### ClinVar Prior Analysis
```python
from evidence import clinvar_prior

# Get ClinVar prior for BRAF V600E
result = await clinvar_prior(
    api_base="http://127.0.0.1:8000",
    gene="BRAF",
    variant={
        "chrom": "7",
        "pos": 140453136,
        "ref": "T",
        "alt": "A",
        "hgvs_p": "V600E"
    }
)

print(f"Prior Strength: {result.prior:.3f}")
if result.deep_analysis:
    clinvar = result.deep_analysis.get("clinvar", {})
    print(f"Classification: {clinvar.get('classification')}")
    print(f"Review Status: {clinvar.get('review_status')}")
```

### Badge Computation
```python
from evidence import compute_evidence_badges

# Compute badges from evidence results
badges = compute_evidence_badges(evidence_hit, clinvar_prior)

print(f"Evidence Badges: {badges}")
# Example output: ["StrongLiterature", "MoAAligned", "ClinVarStrong", "RCT"]
```

### Data Conversion
```python
from evidence import evidence_to_dict, clinvar_to_dict

# Convert to dictionary format
evidence_dict = evidence_to_dict(evidence_hit)
clinvar_dict = clinvar_to_dict(clinvar_prior)

# Use in JSON serialization
import json
evidence_json = json.dumps(evidence_dict)
clinvar_json = json.dumps(clinvar_dict)
```

### Complete Evidence Workflow
```python
from evidence import literature, clinvar_prior, compute_evidence_badges

async def get_complete_evidence(gene, variant, drug_name, drug_moa):
    # Get literature evidence
    lit_result = await literature(
        api_base="http://127.0.0.1:8000",
        gene=gene,
        hgvs_p=variant.get("hgvs_p"),
        drug_name=drug_name,
        drug_moa=drug_moa
    )
    
    # Get ClinVar prior
    clinvar_result = await clinvar_prior(
        api_base="http://127.0.0.1:8000",
        gene=gene,
        variant=variant
    )
    
    # Compute badges
    badges = compute_evidence_badges(lit_result, clinvar_result)
    
    return {
        "literature": lit_result,
        "clinvar": clinvar_result,
        "badges": badges,
        "evidence_strength": lit_result.strength,
        "clinvar_prior": clinvar_result.prior
    }

# Usage
evidence = await get_complete_evidence(
    gene="BRAF",
    variant={"chrom": "7", "pos": 140453136, "ref": "T", "alt": "A", "hgvs_p": "V600E"},
    drug_name="vemurafenib",
    drug_moa="BRAF inhibitor"
)
```

## 🎯 Evidence Scoring

### **Literature Strength Scoring**
- **RCT**: +0.5 points
- **Guideline**: +0.35 points  
- **Review**: +0.25 points
- **Other**: +0.15 points
- **MoA Boost**: +0.10 × moa_hits

### **ClinVar Prior Scoring**
- **Pathogenic + Expert Review**: +0.2
- **Pathogenic + Practice Review**: +0.2
- **Pathogenic + Criteria**: +0.1
- **Pathogenic + Other**: +0.05
- **Benign + Expert Review**: -0.2
- **Benign + Practice Review**: -0.2
- **Benign + Criteria**: -0.1
- **Benign + Other**: -0.05

### **Badge Thresholds**
- **StrongLiterature**: Evidence strength ≥0.7
- **ModerateLiterature**: Evidence strength ≥0.4
- **MoAAligned**: MoA hits >0
- **PathwayAligned**: Pathway score ≥0.2

## 🚨 Error Handling

The evidence client implements **comprehensive error handling**:
- ✅ **HTTP Errors**: Graceful handling of 4xx/5xx responses
- ✅ **Timeout Handling**: Configurable timeouts for all operations
- ✅ **Invalid Data**: Safe parsing with fallback values
- ✅ **Network Issues**: Retry logic and error recovery
- ✅ **Provenance Tracking**: All errors logged with full context

## 📈 Performance Characteristics

| **Component** | **Speed** | **Accuracy** | **Coverage** | **Use Case** |
|---------------|-----------|--------------|--------------|--------------|
| **Literature Client** | ⚡⚡ | 🎯🎯🎯 | 🎯🎯🎯 | Literature search |
| **ClinVar Client** | ⚡⚡⚡ | 🎯🎯🎯 | 🎯🎯 | ClinVar analysis |
| **Badge Computation** | ⚡⚡⚡ | 🎯🎯 | 🎯🎯🎯 | Badge determination |

## 🔮 Future Enhancements

- **Multiple Providers**: Integration with additional literature sources
- **Real-Time Updates**: Live evidence updates with new publications
- **Advanced Filtering**: ML-based relevance filtering
- **Citation Analysis**: Citation network analysis
- **Evidence Synthesis**: Automated evidence synthesis and summarization

---

**⚔️ Package Status: BATTLE-READY**  
**🏛️ Architecture: MODULAR SUPREMACY**  
**🚀 Performance: OPTIMIZED FOR CONQUEST**

