# 🔬 Insights Client Package

## Overview
The Insights Client package provides orchestrated access to multiple insights endpoints, bundling results from functionality, chromatin, essentiality, and regulatory analysis. This package implements parallel execution with comprehensive error handling and provenance tracking.

## 🏗️ Architecture

```
insights/
├── __init__.py              # Clean exports and package interface
├── models.py                # InsightsBundle dataclass
├── bundle_client.py         # Insights endpoint orchestration
└── README.md               # This documentation
```

## 🚀 Core Components

### 1. **Bundle Client** (`bundle_client.py`)
**Purpose**: Orchestrates multiple insights endpoints with parallel execution

**Key Features**:
- ✅ **Multi-Endpoint Orchestration**: Functionality, chromatin, essentiality, regulatory
- ✅ **Parallel Execution**: Concurrent API calls with timeout handling
- ✅ **Result Bundling**: Unified insights package with provenance
- ✅ **Error Resilience**: Individual endpoint failures don't break the bundle
- ✅ **Conditional Execution**: Only calls endpoints when required data is available
- ✅ **Provenance Tracking**: Complete audit trail of all operations

**Supported Endpoints**:
- `/api/insights/predict_protein_functionality_change`
- `/api/insights/predict_chromatin_accessibility`
- `/api/insights/predict_gene_essentiality`
- `/api/insights/predict_splicing_regulatory`

**Usage**:
```python
from insights import bundle

result = await bundle(
    api_base="http://127.0.0.1:8000",
    gene="BRAF",
    variant={
        "chrom": "7",
        "pos": 140453136,
        "ref": "T",
        "alt": "A"
    },
    hgvs_p="V600E"
)

print(f"Functionality: {result.functionality}")
print(f"Chromatin: {result.chromatin}")
print(f"Essentiality: {result.essentiality}")
print(f"Regulatory: {result.regulatory}")
```

### 2. **Data Models** (`models.py`)
**Purpose**: Structured data classes for insights results

**Key Models**:
- `InsightsBundle`: Bundled insights results with provenance

## 📊 Data Models

### **InsightsBundle**
```python
@dataclass
class InsightsBundle:
    functionality: Optional[float] = None      # Protein functionality change score
    chromatin: Optional[float] = None          # Chromatin accessibility score
    essentiality: Optional[float] = None       # Gene essentiality score
    regulatory: Optional[float] = None         # Regulatory impact score
    provenance: Dict[str, Any] = None          # Provenance tracking
```

## 🔧 Configuration

### API Configuration
```python
# Insights endpoint configuration
INSIGHTS_ENDPOINTS = {
    "functionality": "/api/insights/predict_protein_functionality_change",
    "chromatin": "/api/insights/predict_chromatin_accessibility", 
    "essentiality": "/api/insights/predict_gene_essentiality",
    "regulatory": "/api/insights/predict_splicing_regulatory"
}

# Timeout configuration
INSIGHTS_TIMEOUT = 40.0  # seconds
```

### Payload Requirements
```python
# Functionality endpoint
func_payload = {
    "gene": "BRAF",
    "hgvs_p": "V600E"
}

# Chromatin endpoint
chrom_payload = {
    "chrom": "7",
    "pos": 140453136,
    "radius": 500
}

# Essentiality endpoint
ess_payload = {
    "gene": "BRAF",
    "variants": [{
        "gene": "BRAF",
        "chrom": "7", 
        "pos": 140453136,
        "ref": "T",
        "alt": "A",
        "consequence": "missense_variant"
    }]
}

# Regulatory endpoint
reg_payload = {
    "chrom": "7",
    "pos": 140453136,
    "ref": "T",
    "alt": "A"
}
```

## 🧪 Usage Examples

### Basic Insights Bundling
```python
from insights import bundle

# Get complete insights bundle
result = await bundle(
    api_base="http://127.0.0.1:8000",
    gene="BRAF",
    variant={
        "chrom": "7",
        "pos": 140453136,
        "ref": "T",
        "alt": "A"
    },
    hgvs_p="V600E"
)

# Access individual insights
print(f"Functionality Score: {result.functionality}")
print(f"Chromatin Score: {result.chromatin}")
print(f"Essentiality Score: {result.essentiality}")
print(f"Regulatory Score: {result.regulatory}")

# Check provenance
print(f"Provenance: {result.provenance}")
```

### Conditional Insights (Partial Data)
```python
# Only gene and HGVS available
result = await bundle(
    api_base="http://127.0.0.1:8000",
    gene="BRAF",
    variant={},  # No variant data
    hgvs_p="V600E"
)

# Only functionality and essentiality will be called
print(f"Functionality: {result.functionality}")  # Available
print(f"Chromatin: {result.chromatin}")          # None (no variant data)
print(f"Essentiality: {result.essentiality}")    # Available
print(f"Regulatory: {result.regulatory}")        # None (no variant data)
```

### Error Handling Example
```python
from insights import bundle

try:
    result = await bundle(
        api_base="http://127.0.0.1:8000",
        gene="BRAF",
        variant={
            "chrom": "7",
            "pos": 140453136,
            "ref": "T",
            "alt": "A"
        },
        hgvs_p="V600E"
    )
    
    # Check for errors in provenance
    if "bundle_error" in result.provenance:
        print(f"Bundle Error: {result.provenance['bundle_error']}")
    
    # Check individual endpoint errors
    for endpoint in ["functionality", "chromatin", "essentiality", "regulatory"]:
        if f"{endpoint}_error" in result.provenance:
            print(f"{endpoint} Error: {result.provenance[f'{endpoint}_error']}")
    
except Exception as e:
    print(f"Critical Error: {e}")
```

### Integration with Efficacy Prediction
```python
from insights import bundle
from efficacy_orchestrator import EfficacyOrchestrator

# Get insights for efficacy prediction
insights = await bundle(
    api_base="http://127.0.0.1:8000",
    gene="BRAF",
    variant={
        "chrom": "7",
        "pos": 140453136,
        "ref": "T",
        "alt": "A"
    },
    hgvs_p="V600E"
)

# Use in efficacy prediction
orchestrator = EfficacyOrchestrator()
request = EfficacyRequest(
    mutations=[{
        "gene": "BRAF",
        "hgvs_p": "V600E",
        "chrom": "7",
        "pos": 140453136,
        "ref": "T",
        "alt": "A"
    }]
)

response = await orchestrator.predict(request)
# Insights are automatically integrated into confidence scoring
```

## 🎯 Insights Types

### **Functionality** 🧬
**Purpose**: Protein functionality change prediction
**Endpoint**: `/api/insights/predict_protein_functionality_change`
**Requirements**: Gene name and HGVS protein notation
**Output**: Functionality score [0, 1]

### **Chromatin** 🧪
**Purpose**: Chromatin accessibility impact assessment
**Endpoint**: `/api/insights/predict_chromatin_accessibility`
**Requirements**: Chromosome, position, and radius
**Output**: Accessibility score [0, 1]

### **Essentiality** ⚡
**Purpose**: Gene essentiality scoring
**Endpoint**: `/api/insights/predict_gene_essentiality`
**Requirements**: Gene name and variant information
**Output**: Essentiality score [0, 1]

### **Regulatory** 🎛️
**Purpose**: Splicing and regulatory impact assessment
**Endpoint**: `/api/insights/predict_splicing_regulatory`
**Requirements**: Chromosome, position, reference, and alternate alleles
**Output**: Regulatory impact score [0, 1]

## 🚨 Error Handling

The insights client implements **comprehensive error handling**:
- ✅ **Individual Endpoint Failures**: One failure doesn't break the entire bundle
- ✅ **Timeout Handling**: 40-second timeout for all operations
- ✅ **Invalid Payloads**: Conditional execution based on available data
- ✅ **Network Issues**: Graceful degradation with error tracking
- ✅ **Provenance Tracking**: All errors logged with full context

### Error Types
- **Bundle Errors**: Critical errors that affect the entire bundle
- **Endpoint Errors**: Individual endpoint failures
- **Timeout Errors**: Request timeout errors
- **Validation Errors**: Invalid input data errors

## 📈 Performance Characteristics

| **Component** | **Speed** | **Reliability** | **Coverage** | **Use Case** |
|---------------|-----------|-----------------|--------------|--------------|
| **Bundle Client** | ⚡⚡ | 🎯🎯🎯 | 🎯🎯🎯 | Multi-endpoint orchestration |
| **Parallel Execution** | ⚡⚡⚡ | 🎯🎯 | 🎯🎯🎯 | Concurrent API calls |
| **Error Handling** | ⚡⚡⚡ | 🎯🎯🎯 | 🎯🎯🎯 | Graceful degradation |

## 🔮 Future Enhancements

- **Caching**: Redis-based result caching for improved performance
- **Batch Processing**: Batch insights requests for multiple variants
- **Real-Time Updates**: Live insights updates with new data
- **Advanced Filtering**: ML-based insights relevance filtering
- **Custom Endpoints**: Support for additional insights endpoints

---

**⚔️ Package Status: BATTLE-READY**  
**🏛️ Architecture: MODULAR SUPREMACY**  
**🚀 Performance: OPTIMIZED FOR CONQUEST**