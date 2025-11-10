# ⚔️ Efficacy Orchestrator Package

## Overview
The Efficacy Orchestrator is the **central command center** for drug efficacy prediction, orchestrating multi-modal scoring across sequence disruption, pathway alignment, and evidence strength. This package implements the **S/P/E Framework** (Sequence/Pathway/Evidence) with insights integration and confidence modulation.

## 🏗️ Architecture

```
efficacy_orchestrator/
├── __init__.py              # Clean exports and package interface
├── models.py                # Request/response models and data classes
├── sequence_processor.py    # Sequence scoring orchestration
├── drug_scorer.py          # Individual drug scoring logic
├── orchestrator.py         # Main composition and workflow management
└── README.md               # This documentation
```

## 🚀 Core Components

### 1. **EfficacyOrchestrator** (`orchestrator.py`)
**Purpose**: Main orchestration engine for efficacy prediction workflow

**Key Features**:
- ✅ **Multi-Modal Integration**: Sequence (S) + Pathway (P) + Evidence (E)
- ✅ **Insights Bundle**: Functionality, chromatin, essentiality, regulatory
- ✅ **Parallel Evidence Gathering**: Concurrent literature and ClinVar calls
- ✅ **Drug Ranking**: Confidence-based drug prioritization
- ✅ **Provenance Tracking**: Complete audit trail of all operations
- ✅ **Error Resilience**: Graceful degradation with partial results

**Usage**:
```python
from efficacy_orchestrator import EfficacyOrchestrator, EfficacyRequest

orchestrator = EfficacyOrchestrator()
request = EfficacyRequest(
    mutations=[{"gene": "BRAF", "hgvs_p": "V600E", "chrom": "7", "pos": 140453136, "ref": "T", "alt": "A"}],
    model_id="evo2_7b",
    options={"adaptive": True, "ensemble": True}
)

response = await orchestrator.predict(request)
```

### 2. **SequenceProcessor** (`sequence_processor.py`)
**Purpose**: Orchestrates sequence scoring using appropriate engines

**Key Features**:
- ✅ **Hierarchical Scoring**: Fusion → Evo2 → Massive Oracle
- ✅ **Feature Flag Integration**: Respects disable flags
- ✅ **Adaptive Windows**: Configurable window sizes
- ✅ **Ensemble Support**: Multiple model testing
- ✅ **Massive Modes**: Synthetic and real-context scoring

**Scoring Strategy**:
1. **Fusion Engine** (if available and enabled)
2. **Evo2 Adaptive** (with ensemble models)
3. **Massive Oracle** (synthetic and real-context)

### 3. **DrugScorer** (`drug_scorer.py`)
**Purpose**: Individual drug scoring with multi-modal integration

**Key Features**:
- ✅ **S/P/E Integration**: Sequence + Pathway + Evidence scoring
- ✅ **Confidence Computation**: Tier-based confidence with insights modulation
- ✅ **Evidence Badges**: RCT, Guideline, ClinVar-Strong, PathwayAligned
- ✅ **Rationale Breakdown**: Transparent scoring explanation
- ✅ **Efficacy Calculation**: Likelihood of benefit computation

**Scoring Formula**:
```
Efficacy Score = 0.3 × Sequence_Percentile + 0.4 × Pathway_Percentile + 0.3 × Evidence_Strength + ClinVar_Prior
```

### 4. **Data Models** (`models.py`)
**Purpose**: Structured data classes for requests and responses

**Key Models**:
- `EfficacyRequest`: Input parameters and options
- `EfficacyResponse`: Complete prediction response
- `DrugScoreResult`: Individual drug scoring result

## 📊 Data Models

### **EfficacyRequest**
```python
@dataclass
class EfficacyRequest:
    mutations: List[Dict[str, Any]]     # Variant list
    model_id: str = "evo2_7b"          # Scoring model
    options: Dict[str, Any] = None      # Scoring options
    api_base: str = "http://127.0.0.1:8000"  # API base URL
    disease: Optional[str] = None       # Disease context
    moa_terms: Optional[List[str]] = None  # MoA terms
```

### **EfficacyResponse**
```python
@dataclass
class EfficacyResponse:
    drugs: List[Dict[str, Any]]         # Ranked drug results
    run_signature: str                  # Unique run identifier
    scoring_strategy: Dict[str, Any]    # Strategy metadata
    evidence_tier: str                  # Overall evidence tier
    provenance: Dict[str, Any]          # Complete audit trail
```

### **DrugScoreResult**
```python
@dataclass
class DrugScoreResult:
    name: str                           # Drug name
    moa: str                           # Mechanism of action
    efficacy_score: float              # Efficacy score [0,1]
    confidence: float                  # Confidence score [0,1]
    evidence_tier: str                 # Evidence tier
    badges: List[str]                  # Evidence badges
    evidence_strength: float           # Evidence strength
    citations: List[str]               # Citation PMIDs
    citations_count: int               # Citation count
    clinvar: Dict[str, Any]            # ClinVar data
    evidence_manifest: Dict[str, Any]  # Evidence manifest
    insights: Dict[str, float]         # Insights scores
    rationale: List[Dict[str, Any]]    # Rationale breakdown
    meets_evidence_gate: bool          # Evidence gate status
    insufficient_signal: bool          # Insufficient signal flag
```

## 🔧 Configuration

### Environment Variables
```bash
# Fusion Engine
FUSION_AM_URL=https://your-fusion-endpoint.com

# Feature Flags
DISABLE_FUSION=1                 # Disable Fusion Engine
DISABLE_EVO2=1                   # Disable Evo2 scoring
DISABLE_LITERATURE=1             # Disable literature search
ENABLE_MASSIVE_MODES=1           # Enable Massive Oracle modes

# Evo2 Configuration
EVO_FORCE_MODEL=evo2_1b          # Force specific model
EVO_USE_DELTA_ONLY=1             # Delta-only mode
EVO_SPAM_SAFE=1                  # Spam safety mode
```

### Scoring Options
```python
options = {
    "adaptive": True,              # Use adaptive windows
    "ensemble": True,              # Use ensemble models
    "massive_impact": False,       # Enable massive impact scoring
    "massive_real_context": False  # Enable real-context scoring
}
```

## 🧪 Usage Examples

### Basic Efficacy Prediction
```python
from efficacy_orchestrator import create_efficacy_orchestrator, EfficacyRequest

# Create orchestrator
orchestrator = create_efficacy_orchestrator()

# Prepare request
request = EfficacyRequest(
    mutations=[
        {
            "gene": "BRAF",
            "hgvs_p": "V600E",
            "chrom": "7",
            "pos": 140453136,
            "ref": "T",
            "alt": "A"
        }
    ],
    model_id="evo2_7b",
    options={"adaptive": True, "ensemble": True}
)

# Get prediction
response = await orchestrator.predict(request)

# Process results
for drug in response.drugs:
    print(f"Drug: {drug['name']}")
    print(f"Efficacy: {drug['efficacy_score']:.3f}")
    print(f"Confidence: {drug['confidence']:.3f}")
    print(f"Tier: {drug['evidence_tier']}")
    print(f"Badges: {drug['badges']}")
    print("---")
```

### Advanced Configuration
```python
# Custom orchestrator with specific scorers
from sequence_scorers import FusionAMScorer, Evo2Scorer, MassiveOracleScorer
from efficacy_orchestrator import EfficacyOrchestrator, SequenceProcessor

# Create custom scorers
fusion_scorer = FusionAMScorer()
evo_scorer = Evo2Scorer(api_base="http://custom-api:8000")
massive_scorer = MassiveOracleScorer()

# Create custom processor
sequence_processor = SequenceProcessor(fusion_scorer, evo_scorer, massive_scorer)

# Create custom orchestrator
orchestrator = EfficacyOrchestrator(sequence_processor=sequence_processor)

# Use with custom options
request = EfficacyRequest(
    mutations=variants,
    model_id="evo2_40b",
    options={
        "adaptive": True,
        "ensemble": True,
        "massive_impact": True,
        "massive_real_context": True
    }
)
```

### Explanation Generation
```python
# Get explanation for prediction
explanation = await orchestrator.explain(request)
print(f"Method: {explanation['method']}")
print(f"Explanation: {explanation['explanation']}")
```

## 🎯 S/P/E Framework

### **Sequence (S) Scoring**
- **Fusion Engine**: AlphaMissense integration for GRCh38 missense
- **Evo2 Adaptive**: Multi-window analysis with ensemble models
- **Massive Oracle**: Synthetic and real-context scoring
- **Calibration**: Gene-specific percentile conversion

### **Pathway (P) Scoring**
- **Gene-to-Pathway Mapping**: Variant impact on biological pathways
- **Drug Pathway Weights**: Drug-specific pathway relevance
- **Aggregation**: Weighted pathway impact scoring
- **Alignment**: Pathway-drug mechanism alignment

### **Evidence (E) Scoring**
- **Literature Search**: PubMed integration with MoA filtering
- **ClinVar Integration**: Classification and review status
- **Publication Types**: RCT > Guideline > Review weighting
- **Evidence Tiers**: Supported/Consider/Insufficient classification

### **Insights Integration**
- **Functionality**: Protein function change prediction
- **Chromatin**: Regulatory impact assessment
- **Essentiality**: Gene dependency scoring
- **Regulatory**: Splicing and non-coding impact

## 🏆 Evidence Tiers

### **Supported**
- Strong literature evidence (≥0.7) OR
- ClinVar-Strong + pathway alignment (≥0.2)
- High confidence predictions

### **Consider**
- Moderate evidence strength
- Some pathway alignment
- Moderate confidence predictions

### **Insufficient**
- Low sequence, pathway, and evidence scores
- Limited confidence
- Requires additional validation

## 🚨 Error Handling

The orchestrator implements **comprehensive error handling**:
- ✅ **Service Failures**: Graceful degradation with partial results
- ✅ **Invalid Inputs**: Validation with clear error messages
- ✅ **Timeout Handling**: Configurable timeouts for all operations
- ✅ **Provenance Tracking**: All errors logged with full context
- ✅ **Fallback Strategies**: Multiple scoring engines for reliability

## 📈 Performance Characteristics

| **Component** | **Speed** | **Accuracy** | **Reliability** | **Use Case** |
|---------------|-----------|--------------|-----------------|--------------|
| **Orchestrator** | ⚡⚡ | 🎯🎯🎯 | 🎯🎯🎯 | Full workflow |
| **Sequence Processor** | ⚡⚡⚡ | 🎯🎯🎯 | 🎯🎯 | Sequence scoring |
| **Drug Scorer** | ⚡⚡⚡ | 🎯🎯🎯 | 🎯🎯🎯 | Drug evaluation |

## 🔮 Future Enhancements

- **Real-Time Updates**: Live evidence integration
- **Cross-Study Validation**: Multi-cohort benchmarking
- **Advanced ML**: Deep learning integration
- **Custom Panels**: User-defined drug panels
- **Batch Processing**: Optimized batch predictions

---

**⚔️ Package Status: BATTLE-READY**  
**🏛️ Architecture: MODULAR SUPREMACY**  
**🚀 Performance: OPTIMIZED FOR CONQUEST**

