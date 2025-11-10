# 🧬 Clinical Literature RAG System

## Overview

The **Retrieval Augmented Generation (RAG) System** transforms the static PubMed literature search into an intelligent, conversational clinical assistant. Instead of just returning raw text dumps, it provides:

- **Conversational Queries**: Ask natural language questions about genetic variants
- **Evidence-Based Answers**: Responses grounded in scientific literature
- **Clinical Context**: Answers tailored to specific diseases and variants
- **Confidence Scoring**: Transparency about answer reliability
- **Source Citations**: Direct links to supporting research papers

## 🚀 Quick Start

### 1. Interactive Chat Mode
```bash
cd /Users/fahadkiani/Desktop/development/crispr-assistant-main/oncology-coPilot/oncology-backend-minimal/Pubmed-LLM-Agent-main

# Start interactive chat
python rag_agent.py --chat
```

Example interaction:
```
❓ Your question: What is the functional impact of BRAF p.Val600Glu?
🤔 Thinking...
🤖 Answer (Evidence: Strong): The BRAF p.Val600Glu mutation is a well-characterized oncogenic driver...
📚 Supporting Evidence:
  1. BRAF V600E mutation and response to targeted therapy... (Relevance: 0.95)
```

### 2. Single Query Mode
```bash
python rag_agent.py --query "How common is KRAS G12D in colorectal cancer?"
```

### 3. Add Variants to Knowledge Base
```bash
python rag_agent.py --add-variant TP53 p.Arg175His "breast cancer"
```

## 🏗️ Architecture

### Core Components

#### 1. **Vector Embeddings Service** (`core/vector_embeddings.py`)
- Converts clinical papers into semantic vector representations
- Supports multiple embedding providers (Gemini, OpenAI, Cohere)
- Intelligent caching to avoid recomputing embeddings
- Similarity search for finding relevant papers

#### 2. **Knowledge Base** (`core/knowledge_base.py`)
- Persistent storage for processed clinical papers
- Thread-safe operations for concurrent access
- Metadata tracking (genes, diseases, publication years)
- Import/export capabilities for knowledge sharing

#### 3. **RAG Query Processor** (`core/rag_query_processor.py`)
- Classifies query types (functional impact, clinical outcomes, etc.)
- Retrieves relevant context using semantic search
- Generates answers using LLM with retrieved context
- Assesses answer confidence and evidence level

#### 4. **Enhanced PubMed Client** (`core/pubmed_client_enhanced.py`)
- Rate limiting with exponential backoff
- Intelligent caching of API responses
- Batch processing for efficiency
- Graceful error handling

#### 5. **Clinical Insights Processor** (`core/clinical_insights_processor.py`)
- Extracts clinical insights from paper text
- Categorizes findings (functional impact, therapeutic implications, etc.)
- Generates clinical recommendations
- Evidence level assessment

## 🔧 Setup & Configuration

### Environment Variables
```bash
# Required
export GEMINI_API_KEY="your-gemini-api-key"

# Optional (for higher PubMed rate limits)
export NCBI_API_KEY="your-ncbi-api-key"
export NCBI_EMAIL="your-email@example.com"

# Optional (alternative LLM)
export OPENAI_API_KEY="your-openai-api-key"
```

### Dependencies
```bash
pip install -r requirements.txt

# Additional dependencies for RAG
pip install numpy scikit-learn requests
```

## 📡 API Integration

### Backend Endpoints

#### POST `/api/evidence/rag-query`
Conversational query processing
```json
{
  "query": "What is the functional impact of BRAF p.Val600Glu?",
  "gene": "BRAF",
  "hgvs_p": "p.Val600Glu",
  "disease": "melanoma",
  "max_context_papers": 5
}
```

Response:
```json
{
  "query": "What is the functional impact of BRAF p.Val600Glu?",
  "query_type": "variant_functional_impact",
  "answer": "The BRAF p.Val600Glu mutation is a well-characterized oncogenic driver...",
  "evidence_level": "Strong",
  "confidence_score": 0.87,
  "supporting_papers": [...],
  "total_papers_found": 12
}
```

#### POST `/api/evidence/rag-add-variant`
Add papers about a variant to knowledge base
```json
{
  "gene": "KRAS",
  "hgvs_p": "p.Gly12Asp",
  "disease": "colorectal cancer",
  "max_papers": 50
}
```

#### GET `/api/evidence/rag-stats`
Get knowledge base statistics
```json
{
  "total_papers": 1250,
  "last_updated": "2024-01-15T10:30:00Z",
  "embedding_provider": "gemini",
  "genes_covered": ["BRAF", "KRAS", "TP53", "EGFR"],
  "diseases_covered": ["melanoma", "colorectal cancer", "lung cancer"]
}
```

## 🎯 Query Types Supported

### 1. Functional Impact
- "What is the functional impact of BRAF p.Val600Glu?"
- "How does KRAS G12D affect protein function?"
- "Is TP53 R175H a loss-of-function mutation?"

### 2. Clinical Outcomes
- "What are the clinical outcomes for EGFR mutations?"
- "How does BRAF V600E affect survival?"
- "What is the prognosis for patients with KRAS variants?"

### 3. Treatment Options
- "What drugs are effective against BRAF mutations?"
- "Are there targeted therapies for TP53 variants?"
- "What treatment options exist for KRAS G12D?"

### 4. Population Frequency
- "How common is BRAF V600E in melanoma?"
- "What is the frequency of KRAS mutations in colorectal cancer?"
- "How often does TP53 R175H occur in breast cancer?"

### 5. Biomarker Associations
- "What are the biomarkers for EGFR variants?"
- "Is BRAF V600E a companion diagnostic?"
- "What molecular markers are associated with KRAS mutations?"

## 📊 Evidence Levels

- **Strong**: Multiple high-quality papers with consistent findings
- **Moderate**: Several papers with supporting evidence
- **Limited**: Few papers or preliminary evidence
- **Insufficient**: No relevant literature found

## 🔬 Advanced Features

### Semantic Search
- Uses vector embeddings for meaning-based retrieval
- Not just keyword matching - understands clinical context
- Multi-aspect embeddings (title, abstract, insights)

### Adaptive Rate Limiting
- Monitors API usage patterns
- Automatically adjusts request frequency
- Exponential backoff on rate limits

### Clinical Insight Extraction
- Pattern-based extraction of clinical findings
- Categorization by clinical significance
- Evidence quality assessment

### Knowledge Base Management
- Persistent storage of processed papers
- Incremental updates without reprocessing
- Export/import for collaboration

## 🧪 Testing & Validation

### Run the Demo
```bash
python RAG_DEMO.py
```

### Test Individual Components
```bash
# Test vector embeddings
python -c "from core.vector_embeddings import VectorEmbeddingsService; print('Embeddings working')"

# Test knowledge base
python -c "from core.knowledge_base import KnowledgeBase; kb = KnowledgeBase(); print(f'Papers: {len(kb.papers)}')"

# Test RAG agent
python rag_agent.py --query "test query"
```

## 🔍 Troubleshooting

### Common Issues

1. **"RAG agent not available"**
   - Check if all dependencies are installed
   - Verify GEMINI_API_KEY is set
   - Check Python path includes the agent directory

2. **Rate limiting errors**
   - Set NCBI_API_KEY for higher limits
   - Wait between requests
   - Check internet connection

3. **Poor answer quality**
   - Add more papers to knowledge base
   - Check variant spelling and formatting
   - Try more specific queries

4. **Memory issues**
   - Reduce max_papers parameter
   - Clear knowledge base cache
   - Restart the service

## 📈 Performance Optimization

### Knowledge Base Tuning
- **Size**: 1000-5000 papers for optimal performance
- **Updates**: Add new variants incrementally
- **Cache**: Clear periodically to refresh embeddings

### Query Optimization
- **Specificity**: Include gene, variant, and disease
- **Context**: Provide clinical scenario details
- **Follow-up**: Ask clarifying questions if needed

### API Optimization
- **Batch Processing**: Process multiple papers together
- **Caching**: Reuse embeddings across sessions
- **Rate Limiting**: Respect API limits to avoid blocks

## 🚀 Future Enhancements

### Planned Features
- **Multi-modal embeddings**: Include images and figures
- **Clinical trial integration**: Direct links to relevant trials
- **Patient-specific queries**: Incorporate clinical data
- **Multi-language support**: Non-English literature
- **Real-time updates**: Automatic literature monitoring

### Integration Opportunities
- **Electronic Health Records**: Patient-specific literature
- **Clinical Decision Support**: Treatment recommendations
- **Research Automation**: Systematic review assistance
- **Medical Education**: Interactive learning tools

## 📚 Examples

### Clinical Decision Support
```
Query: "Should a patient with BRAF p.Val600Glu melanoma receive immunotherapy?"
Answer: Based on current evidence, patients with BRAF V600E mutations typically respond better to targeted therapies (BRAF/MEK inhibitors) than immunotherapy alone. Combination approaches are being investigated in clinical trials...
```

### Research Question Answering
```
Query: "What is the mechanism of resistance to EGFR inhibitors?"
Answer: Resistance to EGFR inhibitors can occur through several mechanisms: T790M mutation, MET amplification, HER2 amplification, and transformation to small cell lung cancer. Recent studies suggest...
```

### Treatment Planning
```
Query: "What are the treatment options for KRAS G12D colorectal cancer?"
Answer: For KRAS G12D colorectal cancer, current standard treatments include chemotherapy regimens (FOLFOX/FOLFIRI) and anti-VEGF therapy (bevacizumab). Emerging therapies targeting KRAS downstream signaling are in clinical development...
```

## 🤝 Contributing

The RAG system is designed to be extensible:

1. **Add New Query Types**: Extend `query_patterns` in `rag_query_processor.py`
2. **New Embedding Providers**: Implement in `vector_embeddings.py`
3. **Clinical Domains**: Add domain-specific patterns and rules
4. **Integration Points**: Add new API endpoints as needed

## 📞 Support

For issues or questions:
1. Check the troubleshooting section above
2. Run the demo script to validate setup
3. Review the logs for detailed error messages
4. Test with simple queries first

---

**Transforming Literature Search into Clinical Intelligence** 🔬✨

The RAG system represents a paradigm shift from static literature dumps to dynamic, conversational clinical decision support. By combining semantic search, clinical insight extraction, and LLM-powered generation, it provides actionable intelligence for precision medicine.
