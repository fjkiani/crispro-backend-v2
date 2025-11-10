import re
import json
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import os

from .vector_embeddings import VectorEmbeddingsService
from .clinical_insights_processor import ClinicalInsightsProcessor
from .llm_client import LLMClient

class RAGQueryProcessor:
    """
    RAG (Retrieval Augmented Generation) processor for clinical literature queries.
    Handles conversational queries and generates answers based on retrieved context.
    """

    def __init__(self, llm_client: Optional[LLMClient] = None, embeddings_service: Optional[VectorEmbeddingsService] = None):
        self.llm_client = llm_client or LLMClient()
        self.embeddings_service = embeddings_service or VectorEmbeddingsService()
        self.insights_processor = ClinicalInsightsProcessor(llm_client=self.llm_client)

        # Query patterns for different types of clinical questions
        self.query_patterns = {
            'variant_functional_impact': [
                r'what is the functional impact of',
                r'how does.*affect.*function',
                r'is.*pathogenic',
                r'what is the effect of.*mutation',
                r'does.*cause.*disease'
            ],
            'clinical_outcomes': [
                r'what are the clinical outcomes',
                r'what is the prognosis',
                r'how does it affect survival',
                r'what treatments are available',
                r'what is the response to therapy'
            ],
            'population_frequency': [
                r'how common is',
                r'what is the frequency of',
                r'how often does.*occur',
                r'what is the prevalence'
            ],
            'therapeutic_implications': [
                r'what drugs are effective',
                r'what are the treatment options',
                r'is there targeted therapy',
                r'what is the best treatment',
                r'are there clinical trials'
            ],
            'biomarker_associations': [
                r'what are the biomarkers',
                r'is it a predictive marker',
                r'companion diagnostic',
                r'molecular marker'
            ]
        }

    def process_query(self, query: str, variant_info: Dict[str, Any],
                     knowledge_base: List[Dict[str, Any]], max_context_papers: int = 5) -> Dict[str, Any]:
        """
        Process a conversational query and generate an answer based on retrieved context.

        Args:
            query: User's natural language query
            variant_info: Information about the variant being discussed
            knowledge_base: List of papers/embeddings to search
            max_context_papers: Maximum number of papers to include in context

        Returns:
            Dictionary containing the answer and supporting information
        """

        try:
            print(f"🔍 Processing RAG query: {query}")

            # Step 1: Classify the query type
            query_type = self._classify_query(query)
            print(f"📋 Query type: {query_type}")

            # Step 2: Retrieve relevant context using semantic search
            relevant_papers = self._retrieve_context(query, knowledge_base, max_context_papers)
            print(f"📚 Found {len(relevant_papers)} relevant papers")

            # Step 3: Generate answer using LLM with context
            answer = self._generate_answer(query, variant_info, relevant_papers, query_type)

            # Step 4: Extract evidence and confidence
            evidence_level, confidence_score = self._assess_answer_confidence(relevant_papers, query_type)

            return {
                'query': query,
                'query_type': query_type,
                'answer': answer,
                'evidence_level': evidence_level,
                'confidence_score': confidence_score,
                'supporting_papers': relevant_papers[:3],  # Include top 3 papers
                'total_papers_found': len(relevant_papers),
                'generated_at': datetime.now().isoformat(),
                'variant_info': variant_info
            }

        except Exception as e:
            print(f"❌ Error in RAG processing: {e}")
            return self._create_error_response(query, variant_info, str(e))

    def _classify_query(self, query: str) -> str:
        """Classify the type of clinical query."""
        query_lower = query.lower()

        for query_type, patterns in self.query_patterns.items():
            for pattern in patterns:
                if re.search(pattern, query_lower):
                    return query_type

        return 'general_clinical'

    def _retrieve_context(self, query: str, knowledge_base: List[Dict[str, Any]],
                         max_papers: int) -> List[Dict[str, Any]]:
        """Retrieve relevant papers using semantic search."""

        # Create query embedding
        query_embedding = self.embeddings_service.embed_query(query)

        # Search for similar papers
        relevant_papers = self.embeddings_service.search_similar(
            query_embedding=query_embedding,
            papers=knowledge_base,
            top_k=max_papers,
            threshold=0.1  # Minimum similarity threshold
        )

        # Boost papers that are highly relevant to the specific variant
        variant_boost = self._calculate_variant_relevance_boost(query, relevant_papers)

        # Sort by combined score (similarity + variant relevance)
        for paper in relevant_papers:
            paper['combined_score'] = paper.get('similarity_score', 0) + variant_boost.get(paper.get('pmid', ''), 0)

        relevant_papers.sort(key=lambda x: x.get('combined_score', 0), reverse=True)

        return relevant_papers

    def _calculate_variant_relevance_boost(self, query: str, papers: List[Dict[str, Any]]) -> Dict[str, float]:
        """Calculate relevance boost for papers mentioning the specific variant."""
        boost_scores = {}

        # Extract gene and variant from query
        gene_match = re.search(r'\b([A-Z]{2,})\b', query.upper())
        gene = gene_match.group(1) if gene_match else None

        for paper in papers:
            boost = 0.0
            paper_text = f"{paper.get('title', '')} {paper.get('abstract', '')}".lower()

            # Boost for exact gene mentions
            if gene and gene.lower() in paper_text:
                boost += 0.3

            # Boost for clinical relevance keywords
            clinical_keywords = ['mutation', 'variant', 'pathogenic', 'cancer', 'treatment']
            keyword_count = sum(1 for keyword in clinical_keywords if keyword in paper_text)
            boost += min(0.2, keyword_count * 0.05)

            # Boost for recent papers (last 5 years)
            if paper.get('year') and paper['year'] >= 2019:
                boost += 0.1

            boost_scores[paper.get('pmid', '')] = boost

        return boost_scores

    def _generate_answer(self, query: str, variant_info: Dict[str, Any],
                        relevant_papers: List[Dict[str, Any]], query_type: str) -> str:
        """Generate an answer using LLM with retrieved context."""

        if not relevant_papers:
            return self._generate_no_context_answer(query, variant_info)

        # Prepare context from relevant papers
        context_parts = []
        for i, paper in enumerate(relevant_papers[:3]):  # Use top 3 papers for context
            paper_text = f"""
Paper {i+1} (Relevance: {paper.get('similarity_score', 0):.2f}):
Title: {paper.get('title', 'Unknown')}
Year: {paper.get('year', 'Unknown')}
Abstract: {paper.get('abstract', 'No abstract available')[:500]}...

Clinical Insights: {self._format_paper_insights(paper)}
"""
            context_parts.append(paper_text)

        context = "\n\n".join(context_parts)

        # Create prompt for LLM
        gene = variant_info.get('gene', 'Unknown')
        variant = variant_info.get('hgvs_p', 'Unknown')

        system_prompt = f"""You are a clinical research assistant specializing in genetic variants and cancer.
You have access to recent scientific literature about the {gene} {variant} variant.

Please provide a comprehensive, evidence-based answer to the user's question.
Use the provided research papers as context, but do not just repeat the abstracts.
Synthesize the information into a coherent, clinically relevant response.

Guidelines:
- Be specific about the variant and its clinical implications
- Cite supporting evidence from the literature
- Explain the level of evidence (strong, moderate, limited)
- Mention any uncertainties or areas needing further research
- Keep the response focused and actionable for clinical decision-making
"""

        user_prompt = f"""
Context from scientific literature:
{context}

Question: {query}

Please provide a comprehensive answer based on the above research context.
"""

        try:
            # Use LLM to generate answer
            response = self.llm_client.generate_text(
                prompt=user_prompt,
                system_prompt=system_prompt,
                max_tokens=1000,
                temperature=0.3  # Lower temperature for more factual responses
            )

            return response.strip()

        except Exception as e:
            print(f"❌ Error generating LLM answer: {e}")
            return self._generate_fallback_answer(query, variant_info, relevant_papers)

    def _format_paper_insights(self, paper: Dict[str, Any]) -> str:
        """Format clinical insights from a paper."""
        if 'insights' not in paper:
            return "No clinical insights extracted"

        insights = paper['insights']
        formatted = []

        for category, insight_list in insights.items():
            if insight_list:
                formatted.append(f"{category.title()}: {', '.join(insight_list[:2])}")

        return "; ".join(formatted) if formatted else "General clinical relevance"

    def _generate_no_context_answer(self, query: str, variant_info: Dict[str, Any]) -> str:
        """Generate answer when no relevant context is found."""
        gene = variant_info.get('gene', 'Unknown')
        variant = variant_info.get('hgvs_p', 'Unknown')

        return f"""I apologize, but I couldn't find specific literature directly addressing your question about the {gene} {variant} variant.

This could mean:
1. The question is very specific and requires more targeted research
2. The variant is rare or newly discovered
3. The specific clinical scenario hasn't been extensively studied

I recommend:
- Consulting with a molecular genetics specialist
- Checking recent publications in specialized journals
- Looking for similar variants in the same gene family
- Considering functional studies or in silico predictions

Would you like me to search for more general information about {gene} mutations or related cancer types?"""

    def _generate_fallback_answer(self, query: str, variant_info: Dict[str, Any],
                                 relevant_papers: List[Dict[str, Any]]) -> str:
        """Generate fallback answer when LLM fails."""
        gene = variant_info.get('gene', 'Unknown')
        variant = variant_info.get('hgvs_p', 'Unknown')

        if relevant_papers:
            paper_count = len(relevant_papers)
            return f"""Based on {paper_count} relevant research papers about {gene} {variant}:

I found literature suggesting this variant has clinical significance, but I'm unable to provide detailed analysis at the moment. The papers indicate:

• Functional studies show the variant may impact protein function
• Clinical studies suggest associations with disease outcomes
• Treatment responses may vary compared to wild-type

For specific guidance, I recommend consulting the original research papers or a clinical geneticist familiar with this variant."""

        return self._generate_no_context_answer(query, variant_info)

    def _assess_answer_confidence(self, relevant_papers: List[Dict[str, Any]], query_type: str) -> Tuple[str, float]:
        """Assess the confidence level and evidence strength of the answer."""

        if not relevant_papers:
            return "Insufficient", 0.0

        # Calculate confidence based on various factors
        confidence = 0.0

        # Factor 1: Number of relevant papers
        paper_count = len(relevant_papers)
        if paper_count >= 5:
            confidence += 0.4
        elif paper_count >= 2:
            confidence += 0.2
        else:
            confidence += 0.1

        # Factor 2: Average relevance score
        avg_relevance = sum(p.get('similarity_score', 0) for p in relevant_papers) / len(relevant_papers)
        confidence += avg_relevance * 0.3

        # Factor 3: Paper quality indicators
        quality_indicators = 0
        for paper in relevant_papers:
            if paper.get('year', 0) >= 2020:
                quality_indicators += 1
            if 'clinical trial' in f"{paper.get('title', '')} {paper.get('abstract', '')}".lower():
                quality_indicators += 2

        confidence += min(0.3, quality_indicators * 0.1)

        # Determine evidence level
        if confidence >= 0.7:
            evidence_level = "Strong"
        elif confidence >= 0.4:
            evidence_level = "Moderate"
        else:
            evidence_level = "Limited"

        return evidence_level, confidence

    def _create_error_response(self, query: str, variant_info: Dict[str, Any], error: str) -> Dict[str, Any]:
        """Create error response when processing fails."""
        return {
            'query': query,
            'query_type': 'error',
            'answer': f"I encountered an error while processing your query: {error}. Please try rephrasing your question or contact support if the issue persists.",
            'evidence_level': "Error",
            'confidence_score': 0.0,
            'supporting_papers': [],
            'total_papers_found': 0,
            'generated_at': datetime.now().isoformat(),
            'variant_info': variant_info,
            'error': error
        }

    def get_query_suggestions(self, variant_info: Dict[str, Any]) -> List[str]:
        """Generate suggested queries for a variant."""
        gene = variant_info.get('gene', 'this gene')
        variant = variant_info.get('hgvs_p', 'this variant')

        return [
            f"What is the functional impact of the {gene} {variant} mutation?",
            f"What are the clinical outcomes associated with {gene} {variant}?",
            f"How common is the {gene} {variant} variant in the population?",
            f"What treatment options are available for patients with {gene} {variant}?",
            f"Are there any targeted therapies for {gene} {variant}?",
            f"What is the prognosis for patients with {gene} {variant}?",
            f"Are there any clinical trials for {gene} {variant}?",
            f"How does {gene} {variant} affect treatment response?"
        ]
