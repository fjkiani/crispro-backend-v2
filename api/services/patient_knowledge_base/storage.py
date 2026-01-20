"""
Patient Knowledge Base Storage - MVP Implementation

Manages patient-specific KB storage structure:
- RAG KB (papers with embeddings)
- Structured KB (entities, facts, relationships)
- Research Intelligence results
- Edge cases and opportunities

Research Use Only - Not for Clinical Decision Making
"""

from pathlib import Path
from typing import Dict, List, Any, Optional
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class PatientKBStorage:
    """Manages patient-specific knowledge base storage."""
    
    def __init__(self, patient_id: str, base_path: Optional[Path] = None):
        self.patient_id = patient_id
        
        if base_path:
            self.kb_path = base_path / "patients" / patient_id
        else:
            # Default: oncology-backend-minimal/knowledge_base/patients/
            self.kb_path = Path(__file__).parent.parent.parent.parent / "knowledge_base" / "patients" / patient_id
        
        self.kb_path.mkdir(parents=True, exist_ok=True)
        
        # Create subdirectories
        (self.kb_path / "entities" / "mutations").mkdir(parents=True, exist_ok=True)
        (self.kb_path / "entities" / "biomarkers").mkdir(parents=True, exist_ok=True)
        (self.kb_path / "facts").mkdir(parents=True, exist_ok=True)
        (self.kb_path / "relationships").mkdir(parents=True, exist_ok=True)
        (self.kb_path / "research_results").mkdir(parents=True, exist_ok=True)
        (self.kb_path / "indexes").mkdir(parents=True, exist_ok=True)
    
    def save_research_result(self, query: str, result: Dict[str, Any]) -> str:
        """Save Research Intelligence result."""
        timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
        safe_query = query.replace("/", "_").replace("\\", "_")[:50]
        result_file = self.kb_path / "research_results" / f"{timestamp}_{safe_query}.json"
        
        with open(result_file, 'w') as f:
            json.dump({
                "query": query,
                "result": result,
                "timestamp": datetime.utcnow().isoformat()
            }, f, indent=2)
        
        return str(result_file)
    
    def save_edge_case(self, edge_case: Dict[str, Any]) -> str:
        """Save edge case."""
        edge_cases_file = self.kb_path / "edge_cases.json"
        
        # Load existing
        if edge_cases_file.exists():
            with open(edge_cases_file, 'r') as f:
                edge_cases = json.load(f)
        else:
            edge_cases = []
        
        # Add new
        edge_case["detected_at"] = datetime.utcnow().isoformat()
        edge_cases.append(edge_case)
        
        # Save
        with open(edge_cases_file, 'w') as f:
            json.dump(edge_cases, f, indent=2)
        
        return str(edge_cases_file)
    
    def save_opportunity(self, opportunity: Dict[str, Any]) -> str:
        """Save research opportunity."""
        opportunities_file = self.kb_path / "opportunities.json"
        
        # Load existing
        if opportunities_file.exists():
            with open(opportunities_file, 'r') as f:
                opportunities = json.load(f)
        else:
            opportunities = []
        
        # Add new
        opportunity["discovered_at"] = datetime.utcnow().isoformat()
        opportunities.append(opportunity)
        
        # Save
        with open(opportunities_file, 'w') as f:
            json.dump(opportunities, f, indent=2)
        
        return str(opportunities_file)
    
    def get_kb_stats(self) -> Dict[str, Any]:
        """Get knowledge base statistics."""
        stats = {
            "patient_id": self.patient_id,
            "kb_path": str(self.kb_path),
            "papers_count": 0,
            "entities_count": 0,
            "facts_count": 0,
            "relationships_count": 0,
            "edge_cases_count": 0,
            "opportunities_count": 0,
            "research_queries_count": 0,
            "last_updated": None
        }
        
        # Count RAG KB papers
        rag_kb_file = self.kb_path / "rag_kb" / "papers.json"
        if rag_kb_file.exists():
            try:
                with open(rag_kb_file, 'r') as f:
                    papers = json.load(f)
                    stats["papers_count"] = len(papers) if isinstance(papers, list) else 0
            except Exception as e:
                logger.warning(f"Failed to read RAG KB papers: {e}")
        
        # Count entities
        entities_dir = self.kb_path / "entities" / "mutations"
        if entities_dir.exists():
            stats["entities_count"] = len(list(entities_dir.glob("*.json")))
        
        # Count edge cases
        edge_cases_file = self.kb_path / "edge_cases.json"
        if edge_cases_file.exists():
            try:
                with open(edge_cases_file, 'r') as f:
                    edge_cases = json.load(f)
                    stats["edge_cases_count"] = len(edge_cases) if isinstance(edge_cases, list) else 0
            except Exception as e:
                logger.warning(f"Failed to read edge cases: {e}")
        
        # Count opportunities
        opportunities_file = self.kb_path / "opportunities.json"
        if opportunities_file.exists():
            try:
                with open(opportunities_file, 'r') as f:
                    opportunities = json.load(f)
                    stats["opportunities_count"] = len(opportunities) if isinstance(opportunities, list) else 0
            except Exception as e:
                logger.warning(f"Failed to read opportunities: {e}")
        
        # Count research queries
        research_results_dir = self.kb_path / "research_results"
        if research_results_dir.exists():
            stats["research_queries_count"] = len(list(research_results_dir.glob("*.json")))
        
        # Get last updated time
        research_results_file = self.kb_path / "research_results.json"
        if research_results_file.exists():
            try:
                with open(research_results_file, 'r') as f:
                    results = json.load(f)
                    if results and isinstance(results, list) and len(results) > 0:
                        stats["last_updated"] = results[-1].get("timestamp")
            except Exception as e:
                logger.warning(f"Failed to read research results: {e}")
        
        return stats
