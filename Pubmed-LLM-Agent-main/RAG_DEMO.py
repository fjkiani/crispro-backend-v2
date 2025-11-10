#!/usr/bin/env python3
"""
RAG (Retrieval Augmented Generation) Demo Script
Demonstrates the enhanced PubMed LLM Agent with conversational capabilities.
"""

import os
import sys
import json
import requests
from pathlib import Path

# Add the agent directory to path
agent_dir = Path(__file__).parent
sys.path.append(str(agent_dir))

from rag_agent import RAGAgent

def demo_rag_agent():
    """Demonstrate the RAG agent capabilities."""
    print("🧬 Clinical Literature RAG Agent - Demo")
    print("=" * 50)

    # Initialize the RAG agent
    print("🚀 Initializing RAG Agent...")
    agent = RAGAgent(knowledge_base_path="demo_knowledge_base")

    # Demo queries
    demo_queries = [
        {
            'query': 'What is the functional impact of BRAF p.Val600Glu mutation?',
            'variant_info': {'gene': 'BRAF', 'hgvs_p': 'p.Val600Glu', 'disease': 'melanoma'}
        },
        {
            'query': 'How common is the KRAS G12D mutation in colorectal cancer?',
            'variant_info': {'gene': 'KRAS', 'hgvs_p': 'p.Gly12Asp', 'disease': 'colorectal cancer'}
        },
        {
            'query': 'What treatment options are available for patients with TP53 mutations?',
            'variant_info': {'gene': 'TP53', 'hgvs_p': 'p.Arg175His', 'disease': 'breast cancer'}
        },
        {
            'query': 'Are there clinical trials for EGFR variants in lung cancer?',
            'variant_info': {'gene': 'EGFR', 'hgvs_p': 'p.Leu858Arg', 'disease': 'lung cancer'}
        }
    ]

    print(f"\n📚 Processing {len(demo_queries)} demo queries...")
    print("-" * 50)

    for i, demo in enumerate(demo_queries, 1):
        print(f"\n🔍 Query {i}: {demo['query']}")
        print("🤔 Processing...")

        try:
            # Process the query
            result = agent.query(
                query=demo['query'],
                variant_info=demo['variant_info'],
                max_context_papers=3
            )

            # Display results
            print(f"\n📋 Query Type: {result.get('query_type', 'Unknown')}")
            print(f"📊 Evidence Level: {result.get('evidence_level', 'Unknown')}")
            print(f"🎯 Confidence: {result.get('confidence_score', 0):.1%}")
            print(f"📚 Papers Found: {result.get('total_papers_found', 0)}")

            print(f"\n🤖 Answer:")
            print(f"{result.get('answer', 'No answer generated')}")

            # Show supporting papers
            papers = result.get('supporting_papers', [])
            if papers:
                print(f"\n📚 Supporting Evidence:")
                for j, paper in enumerate(papers, 1):
                    title = paper.get('title', 'Unknown title')[:60]
                    relevance = paper.get('similarity_score', 0)
                    print(f"  {j}. {title}... (Relevance: {relevance:.2f})")

            print("\n" + "-" * 50)

        except Exception as e:
            print(f"❌ Error processing query {i}: {e}")
            print("-" * 50)

    # Show knowledge base statistics
    print("\n📊 Knowledge Base Statistics:")
    stats = agent.get_knowledge_base_stats()
    print(f"Total Papers: {stats.get('total_papers', 0)}")
    print(f"Last Updated: {stats.get('last_updated', 'Never')}")
    print(f"Embedding Provider: {stats.get('embedding_provider', 'Unknown')}")

    gene_stats = stats.get('gene_statistics', {})
    if gene_stats:
        print("\n🔬 Top Genes Covered:")
        for gene, count in list(gene_stats.items())[:3]:
            print(f"  • {gene}: {count} papers")

    print("\n✅ Demo completed! The RAG agent is ready for clinical queries.")

def demo_api_integration():
    """Demonstrate API integration with the backend."""
    print("\n🔗 API Integration Demo")
    print("=" * 30)

    # Example API calls
    base_url = "http://localhost:8000"  # Adjust as needed

    demo_requests = [
        {
            'endpoint': '/api/evidence/rag-query',
            'payload': {
                'query': 'What is the functional impact of BRAF p.Val600Glu?',
                'gene': 'BRAF',
                'hgvs_p': 'p.Val600Glu',
                'disease': 'melanoma',
                'max_context_papers': 3
            }
        },
        {
            'endpoint': '/api/evidence/rag-add-variant',
            'payload': {
                'gene': 'KRAS',
                'hgvs_p': 'p.Gly12Asp',
                'disease': 'colorectal cancer',
                'max_papers': 20
            }
        },
        {
            'endpoint': '/api/evidence/rag-stats',
            'payload': {}
        }
    ]

    for demo in demo_requests:
        print(f"\n📡 Testing {demo['endpoint']}:")
        print(f"Payload: {json.dumps(demo['payload'], indent=2)}")

        if demo['endpoint'] == '/api/evidence/rag-stats':
            # GET request for stats
            try:
                response = requests.get(f"{base_url}{demo['endpoint']}", timeout=30)
                print(f"Status: {response.status_code}")
                if response.status_code == 200:
                    print(f"Response: {json.dumps(response.json(), indent=2)[:300]}...")
                else:
                    print(f"Error: {response.text}")
            except Exception as e:
                print(f"Request failed: {e}")
        else:
            # POST request
            try:
                response = requests.post(
                    f"{base_url}{demo['endpoint']}",
                    json=demo['payload'],
                    timeout=60
                )
                print(f"Status: {response.status_code}")
                if response.status_code == 200:
                    result = response.json()
                    print(f"Response keys: {list(result.keys())}")
                    if 'answer' in result:
                        print(f"Answer preview: {result['answer'][:100]}...")
                else:
                    print(f"Error: {response.text}")
            except Exception as e:
                print(f"Request failed: {e}")

        print("-" * 30)

def demo_interactive_chat():
    """Demonstrate the interactive chat mode."""
    print("\n🗣️  Interactive Chat Demo")
    print("=" * 30)
    print("This would start an interactive chat session.")
    print("In a real scenario, you would run:")
    print("python rag_agent.py --chat")
    print("\nExample interaction:")
    print("❓ Your question: What is the functional impact of BRAF p.Val600Glu?")
    print("🤔 Thinking...")
    print("🤖 Answer (Evidence: Strong): [Detailed answer with citations]")
    print("📚 Supporting Evidence: [List of relevant papers]")

if __name__ == "__main__":
    print("🧬 Clinical Literature RAG System Demo")
    print("This demo shows the enhanced PubMed LLM Agent with RAG capabilities.\n")

    # Check for required environment variables
    required_env_vars = ['GEMINI_API_KEY']
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]

    if missing_vars:
        print(f"⚠️  Missing environment variables: {', '.join(missing_vars)}")
        print("Please set these before running the full demo.")
        print("You can still see the API integration demo.\n")
        demo_api_integration()
        demo_interactive_chat()
    else:
        # Run the full demo
        demo_rag_agent()
        demo_api_integration()
        demo_interactive_chat()

    print("\n📚 RAG System Documentation:")
    print("• Vector Embeddings: Converts papers to semantic vectors")
    print("• Knowledge Base: Stores processed clinical literature")
    print("• Query Processor: Handles natural language queries")
    print("• LLM Integration: Generates answers with context")
    print("• API Endpoints: RESTful interface for applications")
    print("\n🎯 Use Cases:")
    print("• Clinical decision support for genetic variants")
    print("• Research question answering")
    print("• Evidence-based medicine queries")
    print("• Literature review automation")

    print("\n✨ The RAG system transforms static literature searches")
    print("   into dynamic, conversational clinical intelligence!")
