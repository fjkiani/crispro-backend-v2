# 🧬 Pathway Service Package

## Overview
The Pathway Service package provides gene-to-pathway mapping and aggregation logic for drug efficacy predictions. This package manages drug panel configurations, pathway aggregation, and drug-to-pathway mapping utilities with extensible design for easy addition of new drugs and pathways.

## 🏗️ Architecture

```
pathway/
├── __init__.py              # Clean exports and package interface
├── models.py                # DrugPanel dataclass
├── panel_config.py          # Drug panel configuration management
├── aggregation.py           # Sequence score aggregation by pathway
├── drug_mapping.py          # Drug-to-pathway mapping utilities
└── README.md               # This documentation
```

## 🚀 Core Components

### 1. **Panel Configuration** (`panel_config.py`)
**Purpose**: Drug panel configuration management with extensible design

**Key Features**:
- ✅ **Default MM Panel**: Pre-configured Multiple Myeloma drug panel
- ✅ **Extensible Design**: Easy addition of new drugs and pathways
- ✅ **Pathway Weights**: Drug-specific pathway relevance weights
- ✅ **MoA Integration**: Mechanism of action for each drug
- ✅ **Environment Configuration**: Configurable via environment variables

**Default MM Panel**:
```python
DEFAULT_MM_PANEL = [
    {
        "name": "BRAF inhibitor", 
        "moa": "MAPK blockade", 
        "pathway_weights": {"ras_mapk": 0.8, "tp53": 0.2}
    },
    {
        "name": "MEK inhibitor", 
        "moa": "MAPK downstream blockade", 
        "pathway_weights": {"ras_mapk": 0.9, "tp53": 0.1}
    },
    {
        "name": "IMiD", 
        "moa": "immunomodulatory", 
        "pathway_weights": {"ras_mapk": 0.2, "tp53": 0.3}
    },
    {
        "name": "Proteasome inhibitor", 
        "moa": "proteostasis stress", 
        "pathway_weights": {"ras_mapk": 0.3, "tp53": 0.4}
    },
    {
        "name": "Anti-CD38", 
        "moa": "antibody", 
        "pathway_weights": {"ras_mapk": 0.1, "tp53": 0.1}
    }
]
```

**Usage**:
```python
from pathway import get_default_panel

panel = get_default_panel()
for drug in panel:
    print(f"Drug: {drug['name']}")
    print(f"MoA: {drug['moa']}")
    print(f"Pathway Weights: {drug['pathway_weights']}")
```

### 2. **Pathway Aggregation** (`aggregation.py`)
**Purpose**: Sequence score aggregation by pathway with weighted scoring

**Key Features**:
- ✅ **Weighted Aggregation**: Drug-specific pathway weights
- ✅ **Average Calculation**: Pathway scores averaged across variants
- ✅ **Flexible Input**: Handles various sequence score formats
- ✅ **Error Resilience**: Safe handling of invalid or missing data
- ✅ **Pathway Tracking**: Counts and totals for each pathway

**Aggregation Algorithm**:
```python
def aggregate_pathways(seq_scores):
    pathway_totals = {}
    pathway_counts = {}
    
    for score in seq_scores:
        pathway_weights = score.get("pathway_weights", {})
        sequence_disruption = float(score.get("sequence_disruption", 0.0))
        
        # Aggregate by pathway
        for pathway, weight in pathway_weights.items():
            if pathway not in pathway_totals:
                pathway_totals[pathway] = 0.0
                pathway_counts[pathway] = 0
            
            pathway_totals[pathway] += sequence_disruption * weight
            pathway_counts[pathway] += 1
    
    # Compute average scores
    pathway_scores = {}
    for pathway in pathway_totals:
        if pathway_counts[pathway] > 0:
            pathway_scores[pathway] = pathway_totals[pathway] / pathway_counts[pathway]
        else:
            pathway_scores[pathway] = 0.0
    
    return pathway_scores
```

**Usage**:
```python
from pathway import aggregate_pathways

seq_scores = [
    {
        "sequence_disruption": 0.5,
        "pathway_weights": {"ras_mapk": 0.8, "tp53": 0.2}
    },
    {
        "sequence_disruption": 0.3,
        "pathway_weights": {"ras_mapk": 0.9, "tp53": 0.1}
    }
]

pathway_scores = aggregate_pathways(seq_scores)
print(f"RAS/MAPK Score: {pathway_scores.get('ras_mapk', 0):.3f}")
print(f"TP53 Score: {pathway_scores.get('tp53', 0):.3f}")
```

### 3. **Drug Mapping** (`drug_mapping.py`)
**Purpose**: Drug-to-pathway mapping utilities and lookup functions

**Key Features**:
- ✅ **Pathway Weight Lookup**: Get pathway weights for specific drugs
- ✅ **MoA Lookup**: Get mechanism of action for specific drugs
- ✅ **Flexible Search**: Case-insensitive drug name matching
- ✅ **Default Handling**: Safe defaults for unknown drugs
- ✅ **Extensible Design**: Easy addition of new drug mappings

**Usage**:
```python
from pathway import get_pathway_weights_for_drug, get_drug_moa

# Get pathway weights for a drug
weights = get_pathway_weights_for_drug("BRAF inhibitor")
print(f"Pathway Weights: {weights}")
# {"ras_mapk": 0.8, "tp53": 0.2}

# Get mechanism of action
moa = get_drug_moa("BRAF inhibitor")
print(f"MoA: {moa}")
# "MAPK blockade"
```

### 4. **Data Models** (`models.py`)
**Purpose**: Structured data classes for pathway-related data

**Key Models**:
- `DrugPanel`: Drug panel configuration with pathway weights

## 📊 Data Models

### **DrugPanel**
```python
@dataclass
class DrugPanel:
    name: str                           # Drug name
    moa: str                           # Mechanism of action
    pathway_weights: Dict[str, float]   # Pathway weight mapping
```

## 🔧 Configuration

### Environment Variables
```python
# Custom panel configuration (future enhancement)
CUSTOM_DRUG_PANEL_PATH = "/path/to/custom/panel.json"

# Pathway configuration
DEFAULT_PATHWAYS = ["ras_mapk", "tp53", "dna_repair", "cell_cycle"]
```

### Custom Panel Configuration
```python
# Example custom panel
CUSTOM_PANEL = [
    {
        "name": "PARP inhibitor",
        "moa": "DNA repair blockade",
        "pathway_weights": {"dna_repair": 0.9, "tp53": 0.3}
    },
    {
        "name": "CDK4/6 inhibitor", 
        "moa": "Cell cycle blockade",
        "pathway_weights": {"cell_cycle": 0.8, "tp53": 0.2}
    }
]
```

## 🧪 Usage Examples

### Basic Panel Management
```python
from pathway import get_default_panel

# Get default panel
panel = get_default_panel()

# Display panel information
for drug in panel:
    print(f"Drug: {drug['name']}")
    print(f"Mechanism: {drug['moa']}")
    print(f"Pathway Weights: {drug['pathway_weights']}")
    print("---")
```

### Pathway Aggregation
```python
from pathway import aggregate_pathways

# Example sequence scores from multiple variants
seq_scores = [
    {
        "sequence_disruption": 0.6,
        "pathway_weights": {"ras_mapk": 0.8, "tp53": 0.2}
    },
    {
        "sequence_disruption": 0.4,
        "pathway_weights": {"ras_mapk": 0.9, "tp53": 0.1}
    },
    {
        "sequence_disruption": 0.3,
        "pathway_weights": {"ras_mapk": 0.2, "tp53": 0.3}
    }
]

# Aggregate pathway scores
pathway_scores = aggregate_pathways(seq_scores)

# Display results
for pathway, score in pathway_scores.items():
    print(f"{pathway}: {score:.3f}")
```

### Drug Mapping
```python
from pathway import get_pathway_weights_for_drug, get_drug_moa

# Get pathway weights for different drugs
drugs = ["BRAF inhibitor", "MEK inhibitor", "IMiD", "Proteasome inhibitor"]

for drug in drugs:
    weights = get_pathway_weights_for_drug(drug)
    moa = get_drug_moa(drug)
    print(f"{drug}:")
    print(f"  MoA: {moa}")
    print(f"  Pathway Weights: {weights}")
    print()
```

### Integration with Efficacy Prediction
```python
from pathway import get_default_panel, aggregate_pathways, get_pathway_weights_for_drug
from sequence_scorers import SeqScore

# Get drug panel
panel = get_default_panel()

# Simulate sequence scores
seq_scores = [
    SeqScore(
        variant={"gene": "BRAF"},
        sequence_disruption=0.5,
        scoring_mode="evo2_adaptive"
    )
]

# Convert to pathway aggregation format
pathway_input = []
for score in seq_scores:
    pathway_input.append({
        "sequence_disruption": score.sequence_disruption,
        "pathway_weights": get_pathway_weights_for_drug(score.variant.get("gene", ""))
    })

# Aggregate pathway scores
pathway_scores = aggregate_pathways(pathway_input)

# Use in drug scoring
for drug in panel:
    drug_weights = get_pathway_weights_for_drug(drug["name"])
    drug_pathway_score = sum(
        pathway_scores.get(pathway, 0.0) * weight 
        for pathway, weight in drug_weights.items()
    )
    print(f"{drug['name']}: {drug_pathway_score:.3f}")
```

## 🎯 Pathway Types

### **RAS/MAPK Pathway** 🧬
**Description**: Mitogen-activated protein kinase signaling pathway
**Key Genes**: BRAF, KRAS, NRAS, MEK, ERK
**Drug Targets**: BRAF inhibitors, MEK inhibitors
**Weight Range**: 0.8-0.9 for targeted drugs

### **TP53 Pathway** ⚡
**Description**: Tumor suppressor p53 pathway
**Key Genes**: TP53, MDM2, MDM4, ATM, ATR
**Drug Targets**: MDM2 inhibitors, PARP inhibitors
**Weight Range**: 0.1-0.4 for various drugs

### **DNA Repair Pathway** 🔧
**Description**: DNA damage response and repair
**Key Genes**: BRCA1, BRCA2, PARP1, ATM, ATR
**Drug Targets**: PARP inhibitors, DNA damage agents
**Weight Range**: 0.9 for PARP inhibitors

### **Cell Cycle Pathway** 🔄
**Description**: Cell cycle regulation and checkpoints
**Key Genes**: CDK4, CDK6, RB1, CCND1, CCNE1
**Drug Targets**: CDK4/6 inhibitors
**Weight Range**: 0.8 for CDK4/6 inhibitors

## 🚨 Error Handling

The pathway service implements **robust error handling**:
- ✅ **Invalid Inputs**: Safe defaults for missing or invalid data
- ✅ **Type Safety**: Automatic type conversion with fallbacks
- ✅ **Missing Drugs**: Default empty weights for unknown drugs
- ✅ **Division by Zero**: Safe handling of empty pathway counts
- ✅ **Data Validation**: Input validation for all functions

## 📈 Performance Characteristics

| **Component** | **Speed** | **Accuracy** | **Reliability** | **Use Case** |
|---------------|-----------|--------------|-----------------|--------------|
| **Panel Config** | ⚡⚡⚡ | 🎯🎯🎯 | 🎯🎯🎯 | Drug panel management |
| **Aggregation** | ⚡⚡⚡ | 🎯🎯🎯 | 🎯🎯🎯 | Pathway scoring |
| **Drug Mapping** | ⚡⚡⚡ | 🎯🎯 | 🎯🎯🎯 | Drug lookup |

## 🔮 Future Enhancements

- **Dynamic Panels**: Runtime panel configuration
- **Custom Pathways**: User-defined pathway definitions
- **Pathway Networks**: Complex pathway interaction modeling
- **Machine Learning**: ML-based pathway weight optimization
- **Real-Time Updates**: Live pathway data integration

---

**⚔️ Package Status: BATTLE-READY**  
**🏛️ Architecture: MODULAR SUPREMACY**  
**🚀 Performance: OPTIMIZED FOR CONQUEST**

