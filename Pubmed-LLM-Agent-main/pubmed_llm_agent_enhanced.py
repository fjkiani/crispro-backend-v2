#!/usr/bin/env python3
"""
Enhanced PubMed LLM Agent with:
- Intelligent rate limiting and caching
- Clinical insights extraction
- Variant-specific relevance scoring
- Robust error handling and fallbacks
"""

import os
import sys
import json
import argparse
import tqdm
from typing import Optional, Dict, Any, List

from core.pubmed_client_enhanced import PubMedClientEnhanced
from core.clinical_insights_processor import ClinicalInsightsProcessor
from core.llm_client import LLMClient
from core.query_builder import build_pubmed_query


def run_enhanced_pubmed_search(
    variant_info: Dict[str, Any],
    max_results: int = 50,
    time_window: str = "since 2015",
    disease_context: str = "",
    llm_rerank: bool = True,
    include_abstracts: bool = True,
    llm_model: str = "gemini-2.5-pro",
    pubmed_email: Optional[str] = None,
    pubmed_api_key: Optional[str] = None,
    llm_api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Enhanced PubMed search with clinical insights extraction.

    Args:
        variant_info: Dictionary containing gene, hgvs_p, and other variant details
        max_results: Maximum number of papers to retrieve
        time_window: Time window for search (e.g., "since 2015")
        disease_context: Additional disease context for search
        llm_rerank: Whether to use LLM for reranking
        include_abstracts: Whether to fetch abstracts
        llm_model: LLM model to use
        pubmed_email: NCBI email for rate limiting
        pubmed_api_key: NCBI API key for higher limits
        llm_api_key: API key for LLM

    Returns:
        Enhanced results with clinical insights and relevance scoring
    """

    try:
        # Initialize components
        print("🔬 Initializing Enhanced PubMed Agent...")

        # Enhanced PubMed client with rate limiting
        pubmed_client = PubMedClientEnhanced(
            email=pubmed_email,
            api_key=pubmed_api_key
        )

        # LLM client for query building and optional reranking
        llm_client = LLMClient(model=llm_model)
        llm_client.api_key = llm_api_key

        # Clinical insights processor
        insights_processor = ClinicalInsightsProcessor(llm_client=llm_client)

        # Build intelligent search query
        gene = variant_info.get('gene', '')
        hgvs_p = variant_info.get('hgvs_p', '')
        disease = disease_context or variant_info.get('disease', '')

        # Construct comprehensive query
        query_parts = []
        if gene:
            query_parts.append(f'"{gene}"[Gene]')
        if hgvs_p:
            query_parts.append(f'"{hgvs_p}"')
        if disease:
            query_parts.append(f'"{disease}"')

        # Add variant-specific terms
        variant_terms = []
        if 'missense' in hgvs_p.lower():
            variant_terms.append('missense mutation')
        elif 'nonsense' in hgvs_p.lower():
            variant_terms.append('nonsense mutation')
        elif 'frameshift' in hgvs_p.lower():
            variant_terms.append('frameshift mutation')

        if variant_terms:
            query_parts.extend(variant_terms)

        # Add clinical relevance terms
        clinical_terms = [
            'pathogenic', 'deleterious', 'functional impact',
            'clinical significance', 'variant interpretation',
            'cancer', 'tumor', 'neoplasm'
        ]
        query_parts.extend(clinical_terms)

        base_query = ' AND '.join(query_parts)

        # Add time window
        if time_window.startswith('since'):
            try:
                year = int(time_window.split()[-1])
                base_query += f" AND {year}:2025[pdat]"
            except:
                pass

        print(f"🔍 Search Query: {base_query}")
        print(f"📊 Target Results: {max_results}")

        # Execute search with enhanced client
        print("🔍 Searching PubMed with enhanced rate limiting...")

        # Step 1: Search for PMIDs
        search_results = pubmed_client.esearch(
            query=base_query,
            retmax=max_results,
            sort="relevance"
        )

        total_found = int(search_results.get('count', 0))
        pmids = search_results.get('idlist', [])

        print(f"📚 Found {total_found} total papers, retrieved {len(pmids)} PMIDs")

        if not pmids:
            return insights_processor._create_empty_response(variant_info)

        # Step 2: Get paper summaries
        print("📖 Fetching paper summaries...")
        summaries = pubmed_client.esummary(pmids)

        # Step 3: Get abstracts if requested
        abstracts = {}
        if include_abstracts:
            print("📄 Fetching abstracts...")
            try:
                abstracts = pubmed_client.efetch_abstracts(pmids)
            except Exception as e:
                print(f"⚠️ Abstract fetching failed: {e}")
                # Continue without abstracts

        # Step 4: Assemble raw results
        print("🔧 Processing and assembling results...")
        raw_results = []

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
                'pmcid': abstract_data.get('pmcid', ''),
                'relevance_score': 0.5  # Default score
            }

            raw_results.append(paper)

        print(f"✅ Processed {len(raw_results)} papers")

        # Step 5: Extract clinical insights
        print("🧠 Extracting clinical insights...")

        # Prepare PubMed results format for insights processor
        pubmed_results = {
            'results': raw_results,
            'total_found': total_found,
            'retrieved_count': len(raw_results)
        }

        # Process with clinical insights processor
        enhanced_results = insights_processor.process_literature_results(
            pubmed_results=pubmed_results,
            variant_info=variant_info
        )

        # Add metadata
        enhanced_results['search_metadata'].update({
            'base_query': base_query,
            'enhanced_features': {
                'rate_limiting': True,
                'caching': True,
                'clinical_insights': True,
                'relevance_scoring': True
            },
            'performance_metrics': {
                'total_api_calls': getattr(pubmed_client, 'request_history', []),
                'cache_hits': len([r for r in getattr(pubmed_client, 'request_history', []) if hasattr(pubmed_client, '_get_cache')])
            }
        })

        print(f"🎯 Enhanced analysis complete!")
        print(f"📊 Evidence Level: {enhanced_results.get('evidence_level', 'Unknown')}")
        print(f"📚 Papers Analyzed: {enhanced_results['search_metadata']['papers_analyzed']}")

        return enhanced_results

    except Exception as e:
        print(f"❌ Error in enhanced PubMed search: {e}")
        import traceback
        traceback.print_exc()

        # Fallback to basic PubMed search without LLM features
        print("🔄 Falling back to basic PubMed search...")
        try:
            # Basic PubMed client without LLM dependencies
            pubmed_client = PubMedClientEnhanced(
                email=pubmed_email,
                api_key=pubmed_api_key
            )

            # Build simple query
            gene = variant_info.get('gene', '')
            hgvs_p = variant_info.get('hgvs_p', '')
            disease = disease_context or variant_info.get('disease', '')

            query_parts = []
            if gene:
                query_parts.append(f'"{gene}"[Gene]')
            if hgvs_p:
                # Extract variant from HGVS notation (e.g., "p.Val600E" -> "V600E")
                if hgvs_p.startswith('p.'):
                    variant_part = hgvs_p[2:]  # Remove "p." prefix
                    query_parts.append(f'"{variant_part}"')
                else:
                    query_parts.append(f'"{hgvs_p}"')
            if disease:
                query_parts.append(f'"{disease}"')

            if query_parts:
                base_query = ' AND '.join(query_parts)
                print(f"🔍 Basic Query: {base_query}")

                # Execute basic search (synchronous)
                try:
                    search_results = pubmed_client.esearch(
                        query=base_query,
                        retmax=max_results,
                        sort="relevance"
                    )
                except Exception as search_error:
                    print(f"❌ Basic search failed: {search_error}")
                    # Create empty search results
                    search_results = {"count": "0", "idlist": []}

                total_found = int(search_results.get('count', 0))
                pmids = search_results.get('idlist', [])

                # If no results with the specific combination, try a broader search
                if not pmids and disease:
                    print("📭 No results with specific disease, trying broader search...")
                    broad_query_parts = query_parts.copy()
                    broad_query_parts.remove(f'"{disease}"')  # Remove disease term
                    broad_query = ' AND '.join(broad_query_parts)
                    print(f"🔍 Broad Query: {broad_query}")

                    broad_search_results = pubmed_client.esearch(
                        query=broad_query,
                        retmax=max_results,
                        sort="relevance"
                    )

                    broad_total_found = int(broad_search_results.get('count', 0))
                    broad_pmids = broad_search_results.get('idlist', [])

                    if broad_pmids:
                        print(f"📚 Found {len(broad_pmids)} results in broad search")
                        total_found = broad_total_found
                        pmids = broad_pmids
                        base_query = broad_query

                if pmids:
                    # Get article details using esummary (available method)
                    try:
                        details_results = pubmed_client.esummary(pmids=pmids)
                    except Exception as summary_error:
                        print(f"❌ Article summary failed: {summary_error}")
                        # Create empty details results
                        details_results = {}
                    # Convert esummary format to paper format
                    papers = []
                    for pmid, paper_data in details_results.items():
                        papers.append({
                            'pmid': paper_data.get('uid', ''),
                            'title': paper_data.get('title', ''),
                            'abstract': paper_data.get('abstract', '') if include_abstracts else None,
                            'authors': paper_data.get('authors', []),
                            'journal': paper_data.get('source', ''),
                            'year': paper_data.get('pubdate', '').split(' ')[0] if paper_data.get('pubdate') else '',
                            'doi': paper_data.get('doi', ''),
                        })

                    # Convert to enhanced format
                    results = []
                    for paper in papers:
                        results.append({
                            'pmid': paper.get('pmid', ''),
                            'title': paper.get('title', ''),
                            'abstract': paper.get('abstract', '') if include_abstracts else None,
                            'authors': paper.get('authors', []),
                            'journal': paper.get('journal', ''),
                            'year': paper.get('year', ''),
                            'doi': paper.get('doi', ''),
                            'relevance': 0.5,  # Default relevance without LLM
                            'relevance_reason': 'Basic keyword matching',
                            'evidence_level': 'Limited',
                            'confidence': 0.5,
                            'insights': [],
                            'recommendations': []
                        })

                    return {
                        'results': results,
                        'search_metadata': {
                            'total_found': total_found,
                            'returned_count': len(results),
                            'papers_analyzed': len(results),
                            'search_strategy': 'basic_fallback',
                            'llm_used': False,
                            'llm_error': str(e)
                        },
                        'variant_info': variant_info,
                        'evidence_level': 'Limited',
                        'confidence': 0.5,
                        'natural_query': f"{gene} {hgvs_p} {disease}",
                        'pubmed_query': base_query
                    }
                else:
                    print("📭 No results found in basic search")
            else:
                print("📭 No valid query terms")

        except Exception as fallback_error:
            print(f"❌ Basic fallback also failed: {fallback_error}")

        # Return empty response as final fallback
        return ClinicalInsightsProcessor()._create_empty_response(variant_info)


async def run_enhanced_pubmed_search_async(
    variant_info: Dict[str, Any],
    max_results: int = 50,
    time_window: str = "since 2015",
    disease_context: str = "",
    llm_rerank: bool = True,
    include_abstracts: bool = True,
    llm_model: str = "gemini-2.5-pro",
    pubmed_email: Optional[str] = None,
    pubmed_api_key: Optional[str] = None,
    llm_api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Async version of enhanced PubMed search that properly handles the async PubMed client.
    """
    # For now, just call the sync version since the PubMed client is the main async component
    # In a full implementation, this would be properly async throughout
    return run_enhanced_pubmed_search(
        variant_info=variant_info,
        max_results=max_results,
        time_window=time_window,
        disease_context=disease_context,
        llm_rerank=llm_rerank,
        include_abstracts=include_abstracts,
        llm_model=llm_model,
        pubmed_email=pubmed_email,
        pubmed_api_key=pubmed_api_key,
        llm_api_key=llm_api_key
    )


def format_clinical_insights(results: Dict[str, Any]) -> str:
    """Format clinical insights into a readable card format."""
    if not results or results.get('evidence_level') == 'Insufficient':
        return "No significant literature found for this variant."

    output = []

    # Evidence level header
    evidence_level = results.get('evidence_level', 'Unknown')
    paper_count = results['search_metadata'].get('papers_analyzed', 0)

    output.append(f"📊 **Evidence Level: {evidence_level}** ({paper_count} papers analyzed)")

    # Clinical summary
    summary = results.get('summary', {})
    if summary.get('functional_impact'):
        output.append(f"🔬 **Functional Impact:** {summary['functional_impact']}")

    if summary.get('clinical_evidence'):
        output.append(f"🏥 **Clinical Evidence:** {summary['clinical_evidence']}")

    if summary.get('therapeutic_implications'):
        output.append(f"💊 **Therapeutic Implications:** {summary['therapeutic_implications']}")

    # Clinical insights breakdown
    insights = results.get('clinical_insights', {})

    if insights.get('functional_impact'):
        output.append(f"\n🔍 **Functional Impact Insights:**")
        for insight in insights['functional_impact'][:3]:
            output.append(f"  • {insight.title()}")

    if insights.get('clinical_evidence'):
        output.append(f"\n📈 **Clinical Evidence:**")
        for insight in insights['clinical_evidence'][:3]:
            output.append(f"  • {insight.title()}")

    if insights.get('therapeutic_implications'):
        output.append(f"\n🎯 **Therapeutic Implications:**")
        for insight in insights['therapeutic_implications'][:2]:
            output.append(f"  • {insight.title()}")

    # Clinical recommendations
    recommendations = results.get('clinical_recommendations', [])
    if recommendations:
        output.append(f"\n💡 **Clinical Recommendations:**")
        for rec in recommendations[:3]:
            output.append(f"  • {rec}")

    # Key papers
    papers = results.get('processed_papers', [])
    if papers:
        output.append(f"\n📚 **Key Papers:**")
        # Sort by relevance and show top 3
        top_papers = sorted(papers, key=lambda x: x.get('relevance_score', 0), reverse=True)[:3]
        for paper in top_papers:
            year = paper.get('year', 'Unknown')
            title = paper.get('title', '')[:80] + "..." if len(paper.get('title', '')) > 80 else paper.get('title', '')
            relevance = paper.get('relevance_score', 0)
            output.append(f"  • {year}: {title} (Relevance: {relevance:.1f})")

    return "\n".join(output)


def parse_cli_args():
    """Parse command line arguments for the enhanced agent."""
    parser = argparse.ArgumentParser(
        description="Enhanced PubMed LLM Agent with Clinical Insights",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python pubmed_llm_agent_enhanced.py --gene BRAF --hgvs_p p.Val600Glu
  python pubmed_llm_agent_enhanced.py --gene TP53 --hgvs_p p.Arg175His --disease "breast cancer"
  python pubmed_llm_agent_enhanced.py --gene KRAS --hgvs_p p.Gly12Val --time-window "since 2020"
        """
    )

    parser.add_argument("--gene", required=True, help="Gene name (e.g., BRAF)")
    parser.add_argument("--hgvs_p", required=True, help="HGVS protein notation (e.g., p.Val600Glu)")
    parser.add_argument("--disease", help="Disease context (e.g., 'melanoma')")
    parser.add_argument("--max-results", type=int, default=50, help="Maximum results to retrieve")
    parser.add_argument("--time-window", default="since 2015", help="Time window (e.g., 'since 2015')")
    parser.add_argument("--no-abstracts", action="store_true", help="Skip abstract fetching")
    parser.add_argument("--llm-model", default="gemini-2.5-pro", help="LLM model for query building")
    parser.add_argument("--output", help="Output file path")
    parser.add_argument("--format", choices=["json", "text"], default="text", help="Output format")

    # API keys
    parser.add_argument("--pubmed-email", help="NCBI email for rate limiting")
    parser.add_argument("--pubmed-api-key", help="NCBI API key for higher rate limits")
    parser.add_argument("--llm-api-key", help="Gemini API key")

    return parser.parse_args()


def cli_main():
    """Command line interface for the enhanced agent."""
    args = parse_cli_args()

    # Build variant info
    variant_info = {
        'gene': args.gene,
        'hgvs_p': args.hgvs_p,
        'disease': args.disease,
        'variant_info': f"{args.gene} {args.hgvs_p}"
    }

    # Get API keys from environment or arguments
    pubmed_email = args.pubmed_email or os.getenv("NCBI_EMAIL")
    pubmed_api_key = args.pubmed_api_key or os.getenv("NCBI_API_KEY")
    llm_api_key = args.llm_api_key or os.getenv("GEMINI_API_KEY")

    print("🚀 Enhanced PubMed LLM Agent")
    print(f"🔬 Analyzing: {args.gene} {args.hgvs_p}")
    if args.disease:
        print(f"🎯 Disease Context: {args.disease}")
    print(f"📅 Time Window: {args.time_window}")
    print(f"📊 Max Results: {args.max_results}")
    print("-" * 50)

    # Run enhanced search
    results = run_enhanced_pubmed_search(
        variant_info=variant_info,
        max_results=args.max_results,
        time_window=args.time_window,
        disease_context=args.disease,
        include_abstracts=not args.no_abstracts,
        llm_model=args.llm_model,
        pubmed_email=pubmed_email,
        pubmed_api_key=pubmed_api_key,
        llm_api_key=llm_api_key
    )

    # Format and output results
    if args.format == "json":
        output = json.dumps(results, indent=2, ensure_ascii=False)
    else:
        output = format_clinical_insights(results)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"✅ Results saved to {args.output}")
    else:
        print(output)


if __name__ == "__main__":
    cli_main()
