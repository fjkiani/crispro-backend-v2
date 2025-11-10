import json
import os
import threading
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from pathlib import Path

from .vector_embeddings import VectorEmbeddingsService
from .clinical_insights_processor import ClinicalInsightsProcessor
from .pubmed_client_enhanced import PubMedClientEnhanced

class KnowledgeBase:
    """
    Manages the clinical literature knowledge base with vector embeddings.
    Handles storage, retrieval, and updating of clinical papers and insights.
    """

    def __init__(self, storage_path: str = "knowledge_base", max_papers: int = 1000):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(exist_ok=True)

        self.max_papers = max_papers
        self.papers_file = self.storage_path / "papers.json"
        self.metadata_file = self.storage_path / "metadata.json"

        # Initialize services
        self.embeddings_service = VectorEmbeddingsService()
        self.insights_processor = ClinicalInsightsProcessor()

        # Thread safety
        self.lock = threading.Lock()

        # Load existing knowledge base
        self.papers = []
        self.metadata = {}
        self._load_knowledge_base()

    def _load_knowledge_base(self):
        """Load existing knowledge base from disk."""
        try:
            if self.papers_file.exists():
                with open(self.papers_file, 'r', encoding='utf-8') as f:
                    self.papers = json.load(f)
                print(f"📚 Loaded {len(self.papers)} papers from knowledge base")

            if self.metadata_file.exists():
                with open(self.metadata_file, 'r', encoding='utf-8') as f:
                    self.metadata = json.load(f)

        except Exception as e:
            print(f"Warning: Could not load knowledge base: {e}")
            self.papers = []
            self.metadata = {}

    def _save_knowledge_base(self):
        """Save knowledge base to disk."""
        try:
            with open(self.papers_file, 'w', encoding='utf-8') as f:
                json.dump(self.papers, f, indent=2, ensure_ascii=False)

            with open(self.metadata_file, 'w', encoding='utf-8') as f:
                json.dump(self.metadata, f, indent=2, ensure_ascii=False)

        except Exception as e:
            print(f"Error saving knowledge base: {e}")

    def add_paper(self, paper: Dict[str, Any], force_recompute: bool = False) -> bool:
        """
        Add a paper to the knowledge base with embeddings and insights.

        Args:
            paper: Paper data (should include title, abstract, etc.)
            force_recompute: Whether to force recompute embeddings even if cached

        Returns:
            True if paper was added successfully
        """
        with self.lock:
            try:
                # Check if paper already exists
                existing_paper = self._find_paper(paper.get('pmid', ''))
                if existing_paper and not force_recompute:
                    print(f"⏭️ Paper {paper.get('pmid', '')} already exists, skipping")
                    return False

                print(f"🔬 Processing paper: {paper.get('pmid', '')}")

                # Generate clinical insights
                variant_info = self._extract_variant_from_paper(paper)
                if not variant_info.get('gene'):
                    print(f"⚠️ Could not extract gene information from paper {paper.get('pmid', '')}")
                    return False

                # Create clinical insights
                insights = self.insights_processor._extract_insights_from_text(
                    f"{paper.get('title', '')} {paper.get('abstract', '')}",
                    variant_info
                )

                # Generate embeddings
                paper_with_embeddings = self.embeddings_service.embed_clinical_paper({
                    **paper,
                    'insights': insights
                })

                # Add metadata
                paper_with_embeddings['added_to_kb'] = datetime.now().isoformat()
                paper_with_embeddings['insights'] = insights

                # Remove existing paper if present
                if existing_paper:
                    self.papers = [p for p in self.papers if p.get('pmid') != paper.get('pmid')]

                # Add new paper
                self.papers.append(paper_with_embeddings)

                # Maintain size limit (keep most recent)
                if len(self.papers) > self.max_papers:
                    self.papers.sort(key=lambda x: x.get('added_to_kb', ''), reverse=True)
                    self.papers = self.papers[:self.max_papers]

                # Update metadata
                self._update_metadata()

                # Save to disk
                self._save_knowledge_base()

                print(f"✅ Added paper {paper.get('pmid', '')} to knowledge base")
                return True

            except Exception as e:
                print(f"❌ Error adding paper to knowledge base: {e}")
                return False

    def add_papers_batch(self, papers: List[Dict[str, Any]], batch_size: int = 10) -> Dict[str, int]:
        """
        Add multiple papers to the knowledge base in batches.

        Args:
            papers: List of paper data
            batch_size: Number of papers to process at once

        Returns:
            Dictionary with success/failure counts
        """
        results = {'added': 0, 'skipped': 0, 'failed': 0}

        for i in range(0, len(papers), batch_size):
            batch = papers[i:i + batch_size]
            print(f"📦 Processing batch {i//batch_size + 1}/{(len(papers) + batch_size - 1)//batch_size}")

            for paper in batch:
                if self.add_paper(paper):
                    results['added'] += 1
                else:
                    # Check if it was skipped or failed
                    existing = self._find_paper(paper.get('pmid', ''))
                    if existing:
                        results['skipped'] += 1
                    else:
                        results['failed'] += 1

        print(f"📊 Batch processing complete: {results}")
        return results

    def _find_paper(self, pmid: str) -> Optional[Dict[str, Any]]:
        """Find a paper by PMID."""
        return next((p for p in self.papers if p.get('pmid') == pmid), None)

    def _extract_variant_from_paper(self, paper: Dict[str, Any]) -> Dict[str, Any]:
        """Extract variant information from paper title and abstract."""
        text = f"{paper.get('title', '')} {paper.get('abstract', '')}"

        # Simple regex patterns to extract gene and variant information
        import re

        # Look for gene names (typically all caps, 2-10 characters)
        gene_match = re.search(r'\b([A-Z]{2,10})\b(?!\s*\()', text)
        gene = gene_match.group(1) if gene_match else None

        # Look for HGVS notation (p.Val600Glu, c.123A>G, etc.)
        hgvs_patterns = [
            r'p\.\w+\d+\w+',  # Protein changes (p.Val600Glu)
            r'c\.\d+[A-Z]>[A-Z]',  # DNA changes (c.123A>G)
            r'g\.\d+[A-Z]>[A-Z]'   # Genomic changes (g.123A>G)
        ]

        hgvs_p = None
        for pattern in hgvs_patterns:
            match = re.search(pattern, text)
            if match:
                hgvs_p = match.group(0)
                break

        # Extract disease context
        disease_keywords = [
            'melanoma', 'lung cancer', 'breast cancer', 'colorectal cancer',
            'leukemia', 'lymphoma', 'myeloma', 'glioblastoma', 'pancreatic cancer'
        ]

        disease = None
        text_lower = text.lower()
        for keyword in disease_keywords:
            if keyword in text_lower:
                disease = keyword
                break

        return {
            'gene': gene,
            'hgvs_p': hgvs_p,
            'disease': disease,
            'variant_info': f"{gene or 'Unknown'} {hgvs_p or 'Unknown'}"
        }

    def _update_metadata(self):
        """Update knowledge base metadata."""
        self.metadata.update({
            'total_papers': len(self.papers),
            'last_updated': datetime.now().isoformat(),
            'embedding_provider': self.embeddings_service.provider,
            'genes_covered': list(set(p.get('gene') for p in self.papers if p.get('gene'))),
            'diseases_covered': list(set(p.get('disease') for p in self.papers if p.get('disease'))),
            'year_range': {
                'min': min((p.get('year', 2024) for p in self.papers if p.get('year')), default=2024),
                'max': max((p.get('year', 2024) for p in self.papers if p.get('year')), default=2024)
            }
        })

    def search_papers(self, query: str, top_k: int = 10, threshold: float = 0.1) -> List[Dict[str, Any]]:
        """
        Search the knowledge base for papers relevant to a query.

        Args:
            query: Search query
            top_k: Number of top results to return
            threshold: Minimum similarity threshold

        Returns:
            List of relevant papers with similarity scores
        """
        if not self.papers:
            return []

        query_embedding = self.embeddings_service.embed_query(query)
        return self.embeddings_service.search_similar(
            query_embedding=query_embedding,
            papers=self.papers,
            top_k=top_k,
            threshold=threshold
        )

    def get_papers_by_gene(self, gene: str, max_papers: int = 50) -> List[Dict[str, Any]]:
        """Get all papers related to a specific gene."""
        gene_lower = gene.lower()
        relevant_papers = [
            p for p in self.papers
            if p.get('gene', '').lower() == gene_lower or
               gene_lower in p.get('title', '').lower() or
               gene_lower in p.get('abstract', '').lower()
        ]

        # Sort by year (newest first)
        relevant_papers.sort(key=lambda x: x.get('year', 0), reverse=True)
        return relevant_papers[:max_papers]

    def get_papers_by_variant(self, gene: str, variant: str, max_papers: int = 20) -> List[Dict[str, Any]]:
        """Get papers specifically about a gene-variant combination."""
        gene_lower = gene.lower()
        variant_clean = variant.replace('p.', '').replace('c.', '').replace('g.', '')

        relevant_papers = []
        for p in self.papers:
            if (p.get('gene', '').lower() == gene_lower and
                (variant in p.get('title', '') or variant in p.get('abstract', '') or
                 variant_clean in p.get('title', '') or variant_clean in p.get('abstract', ''))):
                relevant_papers.append(p)

        # Sort by relevance and year
        relevant_papers.sort(key=lambda x: (x.get('year', 0)), reverse=True)
        return relevant_papers[:max_papers]

    def get_statistics(self) -> Dict[str, Any]:
        """Get knowledge base statistics."""
        if not self.papers:
            return {'total_papers': 0, 'message': 'Knowledge base is empty'}

        # Gene statistics
        genes = [p.get('gene') for p in self.papers if p.get('gene')]
        gene_counts = {}
        for gene in genes:
            gene_counts[gene] = gene_counts.get(gene, 0) + 1

        # Year distribution
        years = [p.get('year') for p in self.papers if p.get('year')]
        year_counts = {}
        for year in years:
            year_counts[year] = year_counts.get(year, 0) + 1

        return {
            **self.metadata,
            'gene_statistics': dict(sorted(gene_counts.items(), key=lambda x: x[1], reverse=True)),
            'year_distribution': dict(sorted(year_counts.items())),
            'papers_with_embeddings': sum(1 for p in self.papers if p.get('embedding')),
            'average_relevance_score': sum(p.get('relevance_score', 0) for p in self.papers) / len(self.papers)
        }

    def clear_knowledge_base(self):
        """Clear all papers from the knowledge base."""
        with self.lock:
            self.papers = []
            self.metadata = {}
            self._save_knowledge_base()
            print("🧹 Knowledge base cleared")

    def export_knowledge_base(self, export_path: str) -> bool:
        """
        Export the knowledge base to a file.

        Args:
            export_path: Path to export file

        Returns:
            True if export was successful
        """
        try:
            export_data = {
                'metadata': self.metadata,
                'papers': self.papers,
                'exported_at': datetime.now().isoformat()
            }

            with open(export_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)

            print(f"📤 Knowledge base exported to {export_path}")
            return True

        except Exception as e:
            print(f"❌ Error exporting knowledge base: {e}")
            return False

    def import_knowledge_base(self, import_path: str) -> bool:
        """
        Import knowledge base from a file.

        Args:
            import_path: Path to import file

        Returns:
            True if import was successful
        """
        try:
            with open(import_path, 'r', encoding='utf-8') as f:
                import_data = json.load(f)

            with self.lock:
                self.metadata = import_data.get('metadata', {})
                self.papers = import_data.get('papers', [])
                self._save_knowledge_base()

            print(f"📥 Knowledge base imported from {import_path}")
            return True

        except Exception as e:
            print(f"❌ Error importing knowledge base: {e}")
            return False

    def refresh_embeddings(self, provider: str = None):
        """
        Refresh embeddings using a different provider.

        Args:
            provider: New embedding provider to use
        """
        if provider:
            self.embeddings_service = VectorEmbeddingsService(provider=provider)

        print("🔄 Refreshing embeddings for all papers...")

        refreshed_count = 0
        for i, paper in enumerate(self.papers):
            try:
                print(f"🔄 Refreshing paper {i+1}/{len(self.papers)}: {paper.get('pmid', '')}")

                # Remove old embeddings
                paper_copy = {k: v for k, v in paper.items()
                            if not k.endswith('_embedding') and k != 'embedding'}

                # Generate new embeddings
                refreshed_paper = self.embeddings_service.embed_clinical_paper(paper_copy)

                # Update paper in place
                paper.update(refreshed_paper)
                refreshed_count += 1

            except Exception as e:
                print(f"❌ Error refreshing embeddings for paper {paper.get('pmid', '')}: {e}")

        # Save updated knowledge base
        self._save_knowledge_base()
        print(f"✅ Refreshed embeddings for {refreshed_count} papers")
