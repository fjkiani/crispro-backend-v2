# 🎯 Confidence Service Package

## Overview
The Confidence Service package provides evidence tier computation and confidence modulation for drug efficacy predictions. This package implements sophisticated confidence scoring based on multi-modal evidence integration, insights analysis, and configurable thresholds.

## 🏗️ Architecture

```
confidence/
├── __init__.py              # Clean exports and package interface
├── models.py                # ConfidenceConfig dataclass
├── tier_computation.py      # Evidence tier determination logic
├── confidence_computation.py # Core confidence calculation
├── badge_computation.py     # Evidence badge determination
├── insights_lifts.py        # Insights-based confidence lifts
├── manifest_computation.py  # Evidence manifest generation
├── rationale_computation.py # Rationale breakdown generation
├── config_factory.py        # Configuration creation utilities
└── README.md               # This documentation
```

## 🚀 Core Components

### 1. **Evidence Tier Computation** (`tier_computation.py`)
**Purpose**: Determines evidence tiers based on multi-modal evidence strength

**Key Features**:
- ✅ **Evidence Gates**: Strong literature OR ClinVar-Strong + pathway alignment
- ✅ **Insufficient Signal Detection**: Low sequence, pathway, and evidence scores
- ✅ **Configurable Thresholds**: Customizable evidence gate and alignment thresholds
- ✅ **Three-Tier System**: Supported/Consider/Insufficient classification

**Tier Logic**:
```python
def compute_evidence_tier(s_seq, s_path, s_evd, badges, config):
    # Evidence gate: strong evidence OR ClinVar-Strong + pathway alignment
    evidence_gate = (
        s_evd >= config.evidence_gate_threshold or 
        ("ClinVar-Strong" in badges and s_path >= config.pathway_alignment_threshold)
    )
    
    # Insufficient signal detection
    insufficient = (
        s_seq < config.insufficient_signal_threshold and 
        s_path < 0.05 and 
        s_evd < 0.2
    )
    
    if evidence_gate:
        return "supported"
    elif insufficient:
        return "insufficient"
    else:
        return "consider"
```

### 2. **Confidence Computation** (`confidence_computation.py`)
**Purpose**: Core confidence calculation with insights modulation

**Key Features**:
- ✅ **Tier-Based Confidence**: Different confidence levels per evidence tier
- ✅ **Insights Modulation**: Functionality, chromatin, essentiality, regulatory lifts
- ✅ **Fusion-Aware Scoring**: Special handling for fusion engine active state
- ✅ **Configurable Lifts**: Customizable insights-based confidence boosts

**Confidence Formula**:
```python
# Base confidence by tier
if tier == "supported":
    confidence = 0.6 + 0.2 * max(seq_pct, path_pct)
elif tier == "consider":
    confidence = 0.3 + 0.1 * seq_pct + 0.1 * path_pct
else:  # insufficient
    if config.fusion_active:
        confidence = 0.1 + 0.15 * seq_pct + 0.10 * path_pct
    else:
        confidence = 0.0

# Insights modulation
confidence += 0.05 if func >= 0.6 else 0.0      # Functionality
confidence += 0.03 if chrom >= 0.5 else 0.0     # Chromatin
confidence += 0.07 if ess >= 0.7 else 0.0       # Essentiality
confidence += 0.02 if reg >= 0.6 else 0.0       # Regulatory
```

### 3. **Badge Computation** (`badge_computation.py`)
**Purpose**: Evidence badge determination based on various signals

**Key Features**:
- ✅ **Literature Strength Badges**: StrongLiterature, ModerateLiterature
- ✅ **Publication Type Badges**: RCT, Guideline detection
- ✅ **ClinVar Badges**: ClinVar-Strong based on classification and review
- ✅ **Pathway Alignment**: PathwayAligned badge for pathway scores ≥0.2

**Badge Types**:
- **StrongLiterature**: Evidence strength ≥0.7
- **ModerateLiterature**: Evidence strength ≥0.4
- **RCT**: Randomized controlled trial detection
- **Guideline**: Practice guideline detection
- **ClinVar-Strong**: Pathogenic + expert/practice review
- **PathwayAligned**: Pathway score ≥0.2

### 4. **Insights Lifts** (`insights_lifts.py`)
**Purpose**: Confidence lift computation from insights scores

**Key Features**:
- ✅ **Functionality Lift**: +0.05 for scores ≥0.6
- ✅ **Chromatin Lift**: +0.03 for scores ≥0.5
- ✅ **Essentiality Lift**: +0.07 for scores ≥0.7
- ✅ **Regulatory Lift**: +0.02 for scores ≥0.6

### 5. **Evidence Manifest** (`manifest_computation.py`)
**Purpose**: Evidence manifest generation for provenance tracking

**Key Features**:
- ✅ **Citation Management**: Top 3 citations with PMIDs
- ✅ **ClinVar Integration**: Classification and review status
- ✅ **PubMed Query Tracking**: Query string preservation
- ✅ **Provenance Data**: Complete evidence source tracking

### 6. **Rationale Computation** (`rationale_computation.py`)
**Purpose**: Rationale breakdown generation for transparency

**Key Features**:
- ✅ **Sequence Breakdown**: Score, percentile, and impact
- ✅ **Pathway Breakdown**: RAS/MAPK, TP53 pathway scores
- ✅ **Evidence Breakdown**: Literature strength and sources
- ✅ **Transparent Scoring**: Clear explanation of all components

## 📊 Data Models

### **ConfidenceConfig**
```python
@dataclass
class ConfidenceConfig:
    evidence_gate_threshold: float = 0.7        # Evidence gate threshold
    pathway_alignment_threshold: float = 0.2    # Pathway alignment threshold
    insufficient_signal_threshold: float = 0.02 # Insufficient signal threshold
    fusion_active: bool = False                 # Fusion engine active state
```

## 🔧 Configuration

### Default Configuration
```python
from confidence import get_default_confidence_config

config = get_default_confidence_config()
# evidence_gate_threshold: 0.7
# pathway_alignment_threshold: 0.2
# insufficient_signal_threshold: 0.02
# fusion_active: False
```

### Custom Configuration
```python
from confidence import create_confidence_config

config = create_confidence_config(
    evidence_gate_threshold=0.8,      # Stricter evidence gate
    pathway_alignment_threshold=0.3,  # Higher pathway requirement
    insufficient_signal_threshold=0.01, # Lower insufficient threshold
    fusion_active=True                # Fusion engine enabled
)
```

## 🧪 Usage Examples

### Basic Confidence Computation
```python
from confidence import (
    compute_evidence_tier, 
    compute_confidence, 
    get_default_confidence_config
)

# Get configuration
config = get_default_confidence_config()

# Compute evidence tier
tier = compute_evidence_tier(
    s_seq=0.5,      # Sequence score
    s_path=0.3,     # Pathway score
    s_evd=0.8,      # Evidence score
    badges=["RCT", "ClinVar-Strong"],  # Evidence badges
    config=config
)

# Compute confidence
confidence = compute_confidence(
    tier=tier,
    seq_pct=0.75,   # Sequence percentile
    path_pct=0.60,  # Pathway percentile
    insights={
        "functionality": 0.7,
        "chromatin": 0.6,
        "essentiality": 0.8,
        "regulatory": 0.5
    },
    config=config
)

print(f"Tier: {tier}")           # "supported"
print(f"Confidence: {confidence:.3f}")  # 0.850
```

### Badge Computation
```python
from confidence import compute_evidence_badges

badges = compute_evidence_badges(
    evidence_strength=0.8,
    citations=[
        {"title": "Randomized trial of...", "publication_types": ["Randomized Controlled Trial"]},
        {"title": "Clinical practice guidelines...", "publication_types": ["Practice Guideline"]}
    ],
    clinvar_data={
        "classification": "Pathogenic",
        "review_status": "reviewed by expert panel"
    },
    pathway_score=0.25
)

print(f"Badges: {badges}")
# ["StrongLiterature", "RCT", "Guideline", "ClinVar-Strong", "PathwayAligned"]
```

### Insights Lifts
```python
from confidence import compute_insights_lifts

lifts = compute_insights_lifts({
    "functionality": 0.7,    # ≥0.6 → +0.05
    "chromatin": 0.6,        # ≥0.5 → +0.03
    "essentiality": 0.8,     # ≥0.7 → +0.07
    "regulatory": 0.5        # <0.6 → +0.00
})

print(f"Lifts: {lifts}")
# {"functionality": 0.05, "chromatin": 0.03, "essentiality": 0.07}
```

### Evidence Manifest
```python
from confidence import compute_evidence_manifest

manifest = compute_evidence_manifest(
    citations=[
        {"pmid": "12345678", "title": "Study Title", "publication_types": ["RCT"]},
        {"pmid": "87654321", "title": "Guideline Title", "publication_types": ["Guideline"]}
    ],
    clinvar_data={
        "classification": "Pathogenic",
        "review_status": "reviewed by expert panel"
    },
    pubmed_query="BRAF V600E multiple myeloma"
)

print(f"Manifest: {manifest}")
```

### Rationale Breakdown
```python
from confidence import compute_rationale_breakdown

rationale = compute_rationale_breakdown(
    seq_score=0.5,
    seq_pct=0.75,
    pathway_scores={"ras_mapk": 0.3, "tp53": 0.2},
    path_pct=0.60,
    evidence_strength=0.8
)

print(f"Rationale: {rationale}")
# [
#   {"type": "sequence", "value": 0.5, "percentile": 0.75},
#   {"type": "pathway", "percentile": 0.60, "breakdown": {"ras_mapk": 0.3, "tp53": 0.2}},
#   {"type": "evidence", "strength": 0.8}
# ]
```

## 🎯 Evidence Tiers

### **Supported** 🟢
**Criteria**:
- Strong literature evidence (≥0.7) OR
- ClinVar-Strong + pathway alignment (≥0.2)

**Confidence Range**: 0.6 - 1.0
**Use Case**: High-confidence clinical decisions

### **Consider** 🟡
**Criteria**:
- Moderate evidence strength
- Some pathway alignment
- Not meeting supported criteria
- Not insufficient

**Confidence Range**: 0.3 - 0.6
**Use Case**: Research prioritization, hypothesis generation

### **Insufficient** 🔴
**Criteria**:
- Low sequence score (<0.02)
- Low pathway score (<0.05)
- Low evidence score (<0.2)

**Confidence Range**: 0.0 - 0.3
**Use Case**: Requires additional validation

## 🏆 Badge System

### **Literature Badges**
- **StrongLiterature**: Evidence strength ≥0.7
- **ModerateLiterature**: Evidence strength ≥0.4

### **Publication Type Badges**
- **RCT**: Randomized controlled trial
- **Guideline**: Practice guideline or clinical practice

### **ClinVar Badges**
- **ClinVar-Strong**: Pathogenic + expert/practice review
- **ClinVar-Moderate**: Pathogenic + criteria provided
- **ClinVar-Benign**: Benign classification

### **Pathway Badges**
- **PathwayAligned**: Pathway score ≥0.2

## 🚨 Error Handling

The confidence service implements **robust error handling**:
- ✅ **Invalid Inputs**: Safe defaults for missing or invalid data
- ✅ **Type Safety**: Automatic type conversion with fallbacks
- ✅ **Boundary Checks**: Confidence scores clamped to [0, 1]
- ✅ **Graceful Degradation**: Partial results when components fail

## 📈 Performance Characteristics

| **Function** | **Speed** | **Accuracy** | **Reliability** | **Use Case** |
|--------------|-----------|--------------|-----------------|--------------|
| **Tier Computation** | ⚡⚡⚡ | 🎯🎯🎯 | 🎯🎯🎯 | Evidence classification |
| **Confidence Computation** | ⚡⚡⚡ | 🎯🎯🎯 | 🎯🎯🎯 | Confidence scoring |
| **Badge Computation** | ⚡⚡⚡ | 🎯🎯 | 🎯🎯🎯 | Badge determination |
| **Insights Lifts** | ⚡⚡⚡ | 🎯🎯 | 🎯🎯🎯 | Confidence modulation |

## 🔮 Future Enhancements

- **Machine Learning**: ML-based confidence prediction
- **Dynamic Thresholds**: Adaptive thresholds based on context
- **Cross-Validation**: Confidence calibration with validation data
- **Real-Time Updates**: Live confidence updates with new evidence
- **Custom Badges**: User-defined badge criteria

---

**⚔️ Package Status: BATTLE-READY**  
**🏛️ Architecture: MODULAR SUPREMACY**  
**🚀 Performance: OPTIMIZED FOR CONQUEST**

