#!/usr/bin/env python3
"""
RAG (Retrieval Augmented Generation) Agent for Clinical Literature
Provides conversational querying capabilities for genetic variants and cancer research.
"""

import os
import json
import argparse
from typing import Dict, Any, List, Optional
from datetime import datetime

from core.knowledge_base import KnowledgeBase
from core.rag_query_processor import RAGQueryProcessor
from core.pubmed_client_enhanced import PubMedClientEnhanced
from core.clinical_insights_processor import ClinicalInsightsProcessor

class RAGAgent:
    """
    Main RAG Agent that provides conversational access to clinical literature.
    Combines knowledge base management, query processing, and answer generation.
    """

    def __init__(self, knowledge_base_path: str = "knowledge_base"):
        print("🚀 Initializing RAG Agent...")

        # Initialize components
        self.knowledge_base = KnowledgeBase(storage_path=knowledge_base_path)
        self.query_processor = RAGQueryProcessor()
        self.pubmed_client = PubMedClientEnhanced(
            email=os.getenv("NCBI_EMAIL"),
            api_key=os.getenv("NCBI_API_KEY")
        )
        self.insights_processor = ClinicalInsightsProcessor()

        print(f"📚 Knowledge base loaded with {len(self.knowledge_base.papers)} papers")
        print(f"🔬 Embedding provider: {self.knowledge_base.embeddings_service.provider}")

    def query(self, query: str, variant_info: Optional[Dict[str, Any]] = None,
              max_context_papers: int = 5) -> Dict[str, Any]:
        """
        Process a natural language query about clinical literature.

        Args:
            query: User's natural language query
            variant_info: Optional variant information for context
            max_context_papers: Maximum papers to include in context

        Returns:
            Dictionary containing the answer and supporting information
        """
        try:
            print(f"🔍 Processing query: {query}")

            # Extract variant information from query if not provided
            if not variant_info:
                variant_info = self._extract_variant_from_query(query)

            # Get knowledge base for retrieval
            knowledge_base = self.knowledge_base.papers

            # If knowledge base is empty, try to build it from recent literature
            if not knowledge_base:
                print("📚 Knowledge base is empty, building from recent literature...")
                self._build_initial_knowledge_base(variant_info)
                knowledge_base = self.knowledge_base.papers

            # Process the query using RAG
            result = self.query_processor.process_query(
                query=query,
                variant_info=variant_info,
                knowledge_base=knowledge_base,
                max_context_papers=max_context_papers
            )

            return result

        except Exception as e:
            print(f"❌ Error processing query: {e}")
            return {
                'query': query,
                'answer': f"I encountered an error while processing your query: {str(e)}",
                'evidence_level': 'Error',
                'confidence_score': 0.0,
                'supporting_papers': [],
                'total_papers_found': 0
            }

    def _extract_variant_from_query(self, query: str) -> Dict[str, Any]:
        """Extract variant information from the query text."""
        import re

        # Look for gene names (typically all caps)
        gene_match = re.search(r'\b([A-Z]{2,10})\b(?!\s*\()', query.upper())
        gene = gene_match.group(1) if gene_match else None

        # Look for HGVS notation
        hgvs_patterns = [
            r'p\.\w+\d+\w+',  # Protein changes (p.Val600Glu)
            r'c\.\d+[A-Z]>[A-Z]',  # DNA changes (c.123A>G)
            r'g\.\d+[A-Z]>[A-Z]'   # Genomic changes (g.123A>G)
        ]

        hgvs_p = None
        for pattern in hgvs_patterns:
            match = re.search(pattern, query)
            if match:
                hgvs_p = match.group(0)
                break

        # Look for disease context
        disease_keywords = [
            'melanoma', 'lung cancer', 'breast cancer', 'colorectal cancer',
            'leukemia', 'lymphoma', 'myeloma', 'glioblastoma', 'pancreatic cancer'
        ]

        disease = None
        query_lower = query.lower()
        for keyword in disease_keywords:
            if keyword in query_lower:
                disease = keyword
                break

        return {
            'gene': gene,
            'hgvs_p': hgvs_p,
            'disease': disease,
            'variant_info': f"{gene or 'Unknown'} {hgvs_p or 'Unknown'}"
        }

    def _build_initial_knowledge_base(self, variant_info: Dict[str, Any], max_papers: int = 20):
        """Build initial knowledge base from PubMed search."""
        try:
            gene = variant_info.get('gene')
            hgvs_p = variant_info.get('hgvs_p')
            disease = variant_info.get('disease')

            if not gene:
                print("⚠️ No gene information found, cannot build knowledge base")
                return

            # Construct search query
            query_parts = [f'"{gene}"[Gene]']
            if hgvs_p:
                query_parts.append(f'"{hgvs_p}"')
            if disease:
                query_parts.append(f'"{disease}"')

            # Add clinical relevance terms
            query_parts.extend(['mutation', 'variant', 'cancer', 'clinical'])

            search_query = ' AND '.join(query_parts)
            print(f"🔍 Building knowledge base with query: {search_query}")

            # Search PubMed
            search_results = self.pubmed_client.esearch(
                query=search_query,
                retmax=max_papers,
                sort="relevance"
            )

            pmids = search_results.get('idlist', [])
            if not pmids:
                print("⚠️ No papers found for initial knowledge base")
                return

            print(f"📄 Found {len(pmids)} papers for knowledge base")

            # Get paper summaries and abstracts
            summaries = self.pubmed_client.esummary(pmids)
            abstracts = self.pubmed_client.efetch_abstracts(pmids)

            # Process papers and add to knowledge base
            papers_added = 0
            for pmid in pmids:
                summary = summaries.get(pmid, {})
                abstract_data = abstracts.get(pmid, {})

                paper = {
                    'pmid': pmid,
                    'title': summary.get('title', ''),
                    'authors': summary.get('authors', []),
                    'source': summary.get('source', ''),
                    'pubdate': summary.get('pubdate', ''),
                    'year': summary.get('year'),
                    'abstract': abstract_data.get('abstract', ''),
                    'publication_types': abstract_data.get('publication_types', []),
                    'mesh_headings': abstract_data.get('mesh_headings', []),
                    'doi': summary.get('doi', ''),
                    'pmcid': abstract_data.get('pmcid', '')
                }

                if self.knowledge_base.add_paper(paper):
                    papers_added += 1

            print(f"✅ Added {papers_added} papers to knowledge base")

        except Exception as e:
            print(f"❌ Error building initial knowledge base: {e}")

    def add_variant_to_knowledge_base(self, variant_info: Dict[str, Any], max_papers: int = 50) -> Dict[str, Any]:
        """Add papers about a specific variant to the knowledge base."""
        try:
            print(f"🔬 Adding papers for {variant_info.get('gene')} {variant_info.get('hgvs_p', '')}")

            gene = variant_info.get('gene')
            hgvs_p = variant_info.get('hgvs_p')
            disease = variant_info.get('disease')

            # Construct focused search query
            query_parts = []
            if gene:
                query_parts.append(f'"{gene}"[Gene]')
            if hgvs_p:
                query_parts.append(f'"{hgvs_p}"')
            if disease:
                query_parts.append(f'"{disease}"')

            # Add specific variant terms
            query_parts.extend(['mutation', 'variant', 'pathogenic', 'clinical significance'])

            search_query = ' AND '.join(query_parts)

            # Search PubMed
            search_results = self.pubmed_client.esearch(
                query=search_query,
                retmax=max_papers,
                sort="relevance"
            )

            pmids = search_results.get('idlist', [])
            new_pmids = [pmid for pmid in pmids if not self.knowledge_base._find_paper(pmid)]

            if not new_pmids:
                return {'added': 0, 'message': 'No new papers found'}

            print(f"📄 Found {len(new_pmids)} new papers")

            # Get paper details
            summaries = self.pubmed_client.esummary(new_pmids)
            abstracts = self.pubmed_client.efetch_abstracts(new_pmids)

            # Create paper objects
            papers = []
            for pmid in new_pmids:
                summary = summaries.get(pmid, {})
                abstract_data = abstracts.get(pmid, {})

                paper = {
                    'pmid': pmid,
                    'title': summary.get('title', ''),
                    'authors': summary.get('authors', []),
                    'source': summary.get('source', ''),
                    'pubdate': summary.get('pubdate', ''),
                    'year': summary.get('year'),
                    'abstract': abstract_data.get('abstract', ''),
                    'publication_types': abstract_data.get('publication_types', []),
                    'mesh_headings': abstract_data.get('mesh_headings', []),
                    'doi': summary.get('doi', ''),
                    'pmcid': abstract_data.get('pmcid', '')
                }
                papers.append(paper)

            # Add to knowledge base
            results = self.knowledge_base.add_papers_batch(papers, batch_size=5)

            return {
                'added': results.get('added', 0),
                'skipped': results.get('skipped', 0),
                'failed': results.get('failed', 0),
                'total_found': len(pmids),
                'new_found': len(new_pmids)
            }

        except Exception as e:
            print(f"❌ Error adding variant to knowledge base: {e}")
            return {'error': str(e)}

    def get_knowledge_base_stats(self) -> Dict[str, Any]:
        """Get statistics about the current knowledge base."""
        return self.knowledge_base.get_statistics()

    def get_query_suggestions(self, variant_info: Dict[str, Any]) -> List[str]:
        """Get suggested queries for a variant."""
        return self.query_processor.get_query_suggestions(variant_info)

    def search_similar_papers(self, query: str, top_k: int = 10) -> List[Dict[str, Any]]:
        """Search for papers similar to a query."""
        return self.knowledge_base.search_papers(query, top_k=top_k)

    def export_knowledge_base(self, export_path: str) -> bool:
        """Export the knowledge base to a file."""
        return self.knowledge_base.export_knowledge_base(export_path)

    def import_knowledge_base(self, import_path: str) -> bool:
        """Import knowledge base from a file."""
        return self.knowledge_base.import_knowledge_base(import_path)

    def clear_knowledge_base(self):
        """Clear all papers from the knowledge base."""
        self.knowledge_base.clear_knowledge_base()

    def chat_loop(self):
        """Interactive chat loop for querying the clinical literature."""
        print("\n🗣️  Clinical Literature RAG Agent")
        print("=" * 50)
        print("Ask me questions about genetic variants and clinical research!")
        print("Type 'help' for suggestions, 'stats' for knowledge base info, or 'quit' to exit.")
        print()

        while True:
            try:
                user_input = input("❓ Your question: ").strip()

                if not user_input:
                    continue

                if user_input.lower() in ['quit', 'exit', 'bye']:
                    print("👋 Goodbye!")
                    break

                if user_input.lower() == 'help':
                    self._show_help()
                    continue

                if user_input.lower() == 'stats':
                    self._show_stats()
                    continue

                if user_input.lower().startswith('add'):
                    # Handle adding variants to knowledge base
                    parts = user_input.split()
                    if len(parts) >= 3:
                        gene = parts[1]
                        variant = parts[2] if len(parts) > 2 else None
                        disease = ' '.join(parts[3:]) if len(parts) > 3 else None

                        variant_info = {
                            'gene': gene,
                            'hgvs_p': variant,
                            'disease': disease
                        }

                        result = self.add_variant_to_knowledge_base(variant_info)
                        print(f"📊 Added {result.get('added', 0)} new papers to knowledge base")
                        continue

                # Process the query
                print("🤔 Thinking...")
                result = self.query(user_input)

                # Display the answer
                print(f"\n🤖 Answer (Evidence: {result.get('evidence_level', 'Unknown')}):")
                print(f"{result.get('answer', 'No answer generated')}")
                print()

                # Show supporting papers
                papers = result.get('supporting_papers', [])
                if papers:
                    print("📚 Supporting Evidence:")
                    for i, paper in enumerate(papers, 1):
                        title = paper.get('title', 'Unknown title')[:60]
                        year = paper.get('year', 'Unknown year')
                        relevance = paper.get('similarity_score', 0)
                        print(f"  {i}. {year}: {title}... (Relevance: {relevance:.2f})")
                    print()

                # Show confidence
                confidence = result.get('confidence_score', 0)
                print(f"📊 Confidence: {confidence:.1%}")
                print("-" * 50)

            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"❌ Error: {e}")
                print("Please try again or type 'help' for suggestions.")

    def _show_help(self):
        """Show help information."""
        print("\n💡 Help - Clinical Literature RAG Agent")
        print("=" * 40)
        print("Ask questions like:")
        print("• What is the functional impact of BRAF p.Val600Glu?")
        print("• How common is the KRAS G12D mutation?")
        print("• What treatments are available for TP53 mutations?")
        print("• Are there clinical trials for EGFR variants?")
        print()
        print("Commands:")
        print("• 'stats' - Show knowledge base statistics")
        print("• 'add GENE VARIANT [DISEASE]' - Add papers about a variant")
        print("• 'help' - Show this help message")
        print("• 'quit' - Exit the chat")
        print()

    def _show_stats(self):
        """Show knowledge base statistics."""
        stats = self.get_knowledge_base_stats()

        print("\n📊 Knowledge Base Statistics")
        print("=" * 30)
        print(f"Total Papers: {stats.get('total_papers', 0)}")
        print(f"Last Updated: {stats.get('last_updated', 'Never')}")
        print(f"Embedding Provider: {stats.get('embedding_provider', 'Unknown')}")

        # Show top genes
        gene_stats = stats.get('gene_statistics', {})
        if gene_stats:
            print("\n🔬 Top Genes Covered:")
            for gene, count in list(gene_stats.items())[:5]:
                print(f"  • {gene}: {count} papers")

        # Show year distribution
        year_dist = stats.get('year_distribution', {})
        if year_dist:
            years = sorted(year_dist.keys())
            if years:
                print(f"\n📅 Year Range: {min(years)} - {max(years)}")

        print()


def main():
    """Main entry point for the RAG Agent."""
    parser = argparse.ArgumentParser(
        description="RAG Agent for Clinical Literature",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python rag_agent.py --query "What is the functional impact of BRAF p.Val600Glu?"
  python rag_agent.py --chat
  python rag_agent.py --add-variant BRAF p.Val600Glu melanoma
  python rag_agent.py --stats
        """
    )

    parser.add_argument("--query", help="Single query to process")
    parser.add_argument("--chat", action="store_true", help="Start interactive chat mode")
    parser.add_argument("--add-variant", nargs="*", help="Add variant to knowledge base (GENE VARIANT [DISEASE])")
    parser.add_argument("--stats", action="store_true", help="Show knowledge base statistics")
    parser.add_argument("--export", help="Export knowledge base to file")
    parser.add_argument("--import-kb", help="Import knowledge base from file")
    parser.add_argument("--clear", action="store_true", help="Clear knowledge base")
    parser.add_argument("--kb-path", default="knowledge_base", help="Knowledge base storage path")

    args = parser.parse_args()

    # Initialize RAG agent
    agent = RAGAgent(knowledge_base_path=args.kb_path)

    if args.query:
        # Process single query
        result = agent.query(args.query)
        print(json.dumps(result, indent=2))

    elif args.chat:
        # Start interactive chat
        agent.chat_loop()

    elif args.add_variant:
        # Add variant to knowledge base
        if len(args.add_variant) >= 2:
            gene = args.add_variant[0]
            variant = args.add_variant[1]
            disease = ' '.join(args.add_variant[2:]) if len(args.add_variant) > 2 else None

            variant_info = {
                'gene': gene,
                'hgvs_p': variant,
                'disease': disease
            }

            result = agent.add_variant_to_knowledge_base(variant_info)
            print(f"📊 Added {result.get('added', 0)} new papers to knowledge base")
        else:
            print("❌ Please provide at least GENE and VARIANT")

    elif args.stats:
        # Show statistics
        stats = agent.get_knowledge_base_stats()
        print(json.dumps(stats, indent=2))

    elif args.export:
        # Export knowledge base
        if agent.export_knowledge_base(args.export):
            print(f"✅ Knowledge base exported to {args.export}")
        else:
            print("❌ Export failed")

    elif args.import_kb:
        # Import knowledge base
        if agent.import_knowledge_base(args.import_kb):
            print(f"✅ Knowledge base imported from {args.import_kb}")
        else:
            print("❌ Import failed")

    elif args.clear:
        # Clear knowledge base
        agent.clear_knowledge_base()
        print("🧹 Knowledge base cleared")

    else:
        # Default to chat mode
        agent.chat_loop()


if __name__ == "__main__":
    main()
