"""
Patient Knowledge Base Agent - MVP Implementation

Autonomous agent that continuously builds knowledge base for patients based on their profiles.
Integrates Research Intelligence, RAG Agent, Structured KB, and Biomarker Intelligence.

Research Use Only - Not for Clinical Decision Making
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
import logging
from pathlib import Path
import json
import sys

from api.services.research_intelligence.orchestrator import ResearchIntelligenceOrchestrator
from api.services.biomarker_intelligence_universal.biomarker_intelligence import get_biomarker_intelligence_service

logger = logging.getLogger(__name__)

# Try to import RAG Agent components
rag_agent_path = Path(__file__).parent.parent.parent / "Pubmed-LLM-Agent-main"
if rag_agent_path.exists():
    sys.path.insert(0, str(rag_agent_path))
    try:
        from core.knowledge_base import KnowledgeBase
        from rag_agent import RAGAgent
        RAG_AVAILABLE = True
    except ImportError:
        logger.warning("⚠️ RAG Agent components not available")
        KnowledgeBase = None
        RAGAgent = None
        RAG_AVAILABLE = False
else:
    KnowledgeBase = None
    RAGAgent = None
    RAG_AVAILABLE = False


class PatientKnowledgeBaseAgent:
    """
    Autonomous agent for building patient-specific knowledge bases.
    
    Combines:
    - Research Intelligence (comprehensive research)
    - RAG Agent (conversational queries, semantic search)
    - Structured KB (entities, facts, relationships)
    - Biomarker Intelligence (resistance detection, triggers)
    """
    
    def __init__(self, patient_id: str, patient_profile: Dict[str, Any]):
        """
        Initialize agent for a specific patient.
        
        Args:
            patient_id: Patient identifier (e.g., "ayesha_11_17_25")
            patient_profile: Complete patient profile from constants
        """
        self.patient_id = patient_id
        self.patient_profile = patient_profile
        
        # Set up patient-specific KB path
        base_path = Path(__file__).parent.parent.parent
        self.kb_path = base_path / "knowledge_base" / "patients" / patient_id
        self.kb_path.mkdir(parents=True, exist_ok=True)
        
        # Initialize services
        self.research_orchestrator = ResearchIntelligenceOrchestrator()
        self.biomarker_service = get_biomarker_intelligence_service()
        
        # Initialize RAG Agent KB (patient-specific)
        if RAG_AVAILABLE and KnowledgeBase:
            rag_kb_path = self.kb_path / "rag_kb"
            rag_kb_path.mkdir(parents=True, exist_ok=True)
            try:
                self.rag_kb = KnowledgeBase(storage_path=str(rag_kb_path))
                self.rag_agent = RAGAgent(knowledge_base_path=str(rag_kb_path))
            except Exception as e:
                logger.warning(f"⚠️ RAG Agent initialization failed: {e}")
                self.rag_kb = None
                self.rag_agent = None
        else:
            self.rag_kb = None
            self.rag_agent = None
            logger.info("ℹ️ RAG Agent not available - patient KB will use Research Intelligence only")
        
        logger.info(f"✅ Patient KB Agent initialized for {patient_id}")
    
    def extract_research_context(self, patient_profile: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract research context from patient profile.
        
        Returns:
            Dict with disease, mutations, biomarkers, stage, etc.
        """
        # Extract from AYESHA_11_17_25_PROFILE structure
        disease = patient_profile.get("disease", {}).get("type", "")
        stage = patient_profile.get("disease", {}).get("stage", "")
        
        # Extract mutations
        germline_mutations = []
        for mut in patient_profile.get("germline", {}).get("mutations", []):
            germline_mutations.append({
                "gene": mut.get("gene"),
                "variant": mut.get("variant"),
                "protein_change": mut.get("protein_change"),
                "classification": mut.get("classification"),
                "zygosity": mut.get("zygosity")
            })
        
        somatic_mutations = []
        for mut in patient_profile.get("tumor_context", {}).get("somatic_mutations", []):
            somatic_mutations.append({
                "gene": mut.get("gene"),
                "variant": mut.get("variant"),
                "evidence": mut.get("evidence")
            })
        
        # Extract biomarkers
        biomarkers = patient_profile.get("tumor_context", {}).get("biomarkers", {})
        
        # Extract treatment context
        treatment_line = 0
        if "inferred_fields" in patient_profile:
            treatment_line = patient_profile.get("inferred_fields", {}).get("treatment_line", {}).get("value", 0)
        
        return {
            "disease": disease,
            "stage": stage,
            "germline_mutations": germline_mutations,
            "somatic_mutations": somatic_mutations,
            "biomarkers": biomarkers,
            "treatment_line": treatment_line,
            "germline_status": patient_profile.get("germline", {}).get("status", "unknown"),
            "tumor_context": patient_profile.get("tumor_context", {})
        }
    
    def generate_research_queries(self, context: Dict[str, Any]) -> List[str]:
        """
        Generate research queries from patient context.
        
        Uses Research Intelligence Question Formulator to generate
        diverse, high-quality queries.
        """
        queries = []
        
        disease = context.get("disease", "")
        germline_mutations = context.get("germline_mutations", [])
        somatic_mutations = context.get("somatic_mutations", [])
        biomarkers = context.get("biomarkers", {})
        
        # Query 1: Disease + primary mutation
        for mut in germline_mutations[:2]:  # Top 2 germline mutations
            gene = mut.get("gene")
            variant = mut.get("variant") or mut.get("protein_change")
            classification = mut.get("classification", "")
            
            if gene:
                if classification == "pathogenic":
                    queries.append(f"{gene} {variant} {disease} treatment")
                    queries.append(f"{gene} {variant} {disease} clinical significance")
                elif classification == "VUS":
                    queries.append(f"{gene} {variant} VUS {disease} significance")
                    queries.append(f"{gene} {variant} {disease} clinical interpretation")
        
        # Query 2: Somatic mutations
        for mut in somatic_mutations[:2]:  # Top 2 somatic mutations
            gene = mut.get("gene")
            if gene:
                queries.append(f"{gene} mutation {disease} treatment")
        
        # Query 3: Biomarker combinations
        pd_l1_status = biomarkers.get("pd_l1_status", "")
        er_status = biomarkers.get("er_status", "")
        
        if pd_l1_status == "POSITIVE":
            queries.append(f"PD-L1 positive {disease} immunotherapy")
        if er_status and er_status != "NEGATIVE":
            queries.append(f"ER {er_status} {disease} treatment")
        
        # Query 4: DNA repair pathway (if MBD4, BRCA, etc.)
        dna_repair_genes = {"MBD4", "BRCA1", "BRCA2", "TP53", "ATM", "ATR"}
        for mut in germline_mutations + somatic_mutations:
            gene = mut.get("gene", "").upper()
            if gene in dna_repair_genes:
                queries.append(f"{gene} DNA repair deficiency {disease} PARP inhibitor")
                queries.append(f"{gene} mutation {disease} synthetic lethality")
                break
        
        # Query 5: Rare mutations
        rare_genes = {"MBD4", "CHEK2", "PALB2", "BRIP1"}
        for mut in germline_mutations:
            gene = mut.get("gene", "").upper()
            if gene in rare_genes:
                queries.append(f"{gene} rare mutation {disease} registry")
                queries.append(f"{gene} {disease} precision medicine")
        
        # Deduplicate and limit
        unique_queries = list(dict.fromkeys(queries))  # Preserve order
        return unique_queries[:10]  # Limit to 10 queries
    
    async def build_knowledge_base(self, max_queries: int = 10) -> Dict[str, Any]:
        """
        Build knowledge base for patient.
        
        Args:
            max_queries: Maximum number of research queries to execute
        
        Returns:
            Dict with build statistics and results
        """
        logger.info(f"🔨 Building KB for patient {self.patient_id}")
        
        # Extract context
        context = self.extract_research_context(self.patient_profile)
        
        # Generate queries
        queries = self.generate_research_queries(context)
        queries = queries[:max_queries]
        
        logger.info(f"📋 Generated {len(queries)} research queries")
        
        # Execute Research Intelligence for each query
        papers_added = 0
        research_results = []
        
        for i, query in enumerate(queries, 1):
            try:
                logger.info(f"🔍 Query {i}/{len(queries)}: {query}")
                
                # Execute Research Intelligence
                result = await self.research_orchestrator.research_question(
                    question=query,
                    context={
                        "disease": context.get("disease"),
                        "treatment_line": f"L{context.get('treatment_line', 0)}",
                        "biomarkers": context.get("biomarkers", {})
                    }
                )
                
                # Extract papers from result
                portal_results = result.get("portal_results", {})
                pubmed_results = portal_results.get("pubmed", {})
                articles = pubmed_results.get("articles", [])
                
                # Add papers to RAG KB
                if self.rag_kb and articles:
                    for article in articles[:20]:  # Limit per query
                        paper = {
                            "pmid": article.get("pmid", ""),
                            "title": article.get("title", ""),
                            "abstract": article.get("abstract", ""),
                            "authors": article.get("authors", []),
                            "year": article.get("year"),
                            "journal": article.get("journal", ""),
                            "doi": article.get("doi", "")
                        }
                        try:
                            if self.rag_kb.add_paper(paper):
                                papers_added += 1
                        except Exception as e:
                            logger.warning(f"Failed to add paper {article.get('pmid')}: {e}")
                
                # Store research result
                research_results.append({
                    "query": query,
                    "result": result,
                    "papers_found": len(articles),
                    "timestamp": datetime.utcnow().isoformat()
                })
                
            except Exception as e:
                logger.error(f"❌ Query '{query}' failed: {e}", exc_info=True)
                continue
        
        # Store research results
        results_file = self.kb_path / "research_results.json"
        with open(results_file, 'w') as f:
            json.dump(research_results, f, indent=2)
        
        # Create patient entities in Structured KB
        entities_created = self.create_patient_entities(context)
        
        # Detect edge cases
        edge_cases = self.detect_edge_cases(self.patient_profile)
        
        # Store edge cases
        edge_cases_file = self.kb_path / "edge_cases.json"
        with open(edge_cases_file, 'w') as f:
            json.dump(edge_cases, f, indent=2)
        
        logger.info(f"✅ KB build complete: {papers_added} papers, {entities_created} entities, {len(edge_cases)} edge cases")
        
        return {
            "patient_id": self.patient_id,
            "papers_added": papers_added,
            "queries_executed": len(queries),
            "entities_created": entities_created,
            "edge_cases_detected": len(edge_cases),
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def create_patient_entities(self, context: Dict[str, Any]) -> int:
        """Create patient-specific entities in Structured KB."""
        entities_created = 0
        entities_dir = self.kb_path / "entities" / "mutations"
        entities_dir.mkdir(parents=True, exist_ok=True)
        
        # Create mutation entities
        for mut in context.get("germline_mutations", []):
            gene = mut.get("gene")
            variant = mut.get("variant")
            if gene and variant:
                entity = {
                    "id": f"{gene}_{variant}",
                    "gene": gene,
                    "variant": variant,
                    "protein_change": mut.get("protein_change"),
                    "classification": mut.get("classification"),
                    "zygosity": mut.get("zygosity"),
                    "patient_id": self.patient_id,
                    "source": "patient_profile",
                    "created_at": datetime.utcnow().isoformat()
                }
                entity_file = entities_dir / f"{gene}_{variant}.json"
                with open(entity_file, 'w') as f:
                    json.dump(entity, f, indent=2)
                entities_created += 1
        
        return entities_created
    
    def detect_edge_cases(self, patient_profile: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Detect edge cases in patient profile."""
        edge_cases = []
        
        # Check for rare mutations
        rare_genes = {"MBD4", "CHEK2", "PALB2", "BRIP1"}
        for mut in patient_profile.get("germline", {}).get("mutations", []):
            gene = mut.get("gene", "").upper()
            if gene in rare_genes:
                edge_cases.append({
                    "type": "rare_mutation",
                    "gene": gene,
                    "variant": mut.get("variant"),
                    "classification": mut.get("classification"),
                    "severity": "high",
                    "message": f"Rare mutation detected: {gene} {mut.get('variant')}"
                })
        
        # Check for VUS
        for mut in patient_profile.get("germline", {}).get("mutations", []):
            if mut.get("classification") == "VUS":
                edge_cases.append({
                    "type": "vus_requires_resolution",
                    "gene": mut.get("gene"),
                    "variant": mut.get("variant"),
                    "severity": "medium",
                    "message": f"VUS detected: {mut.get('gene')} {mut.get('variant')} - requires resolution"
                })
        
        # Check for homozygous pathogenic
        for mut in patient_profile.get("germline", {}).get("mutations", []):
            if mut.get("zygosity") == "homozygous" and mut.get("classification") == "pathogenic":
                edge_cases.append({
                    "type": "homozygous_pathogenic",
                    "gene": mut.get("gene"),
                    "variant": mut.get("variant"),
                    "severity": "high",
                    "message": f"Homozygous pathogenic mutation: {mut.get('gene')} {mut.get('variant')}"
                })
        
        return edge_cases
    
    async def query_patient_kb(self, query: str) -> Dict[str, Any]:
        """Query patient's knowledge base using RAG Agent."""
        if not self.rag_agent:
            return {
                "error": "RAG Agent not available",
                "message": "Patient KB querying requires RAG Agent. KB may still be building.",
                "suggestion": "Try building the KB first using POST /api/patient-kb/{patient_id}/build"
            }
        
        # Use RAG Agent to query patient KB
        try:
            # Get papers from knowledge base
            if not self.rag_kb:
                return {
                    "error": "Knowledge base not initialized",
                    "message": "Patient KB not yet built. Please build KB first."
                }
            
            # Get papers from KB
            papers = self.rag_kb.papers if hasattr(self.rag_kb, 'papers') else []
            
            if not papers:
                return {
                    "error": "No papers in knowledge base",
                    "message": "Patient KB is empty. Please build KB first.",
                    "papers_count": 0
                }
            
            # Use RAG query processor
            from core.rag_query_processor import RAGQueryProcessor
            from core.llm_client import LLMClient
            
            processor = RAGQueryProcessor(
                llm_client=LLMClient(),
                embeddings_service=None  # Will use default
            )
            
            variant_info = self.extract_research_context(self.patient_profile)
            result = processor.process_query(
                query=query,
                variant_info=variant_info,
                knowledge_base=papers,
                max_context_papers=10
            )
            
            return result
        except Exception as e:
            logger.error(f"Query failed: {e}", exc_info=True)
            return {
                "error": str(e),
                "message": "Failed to query patient KB",
                "query": query
            }
