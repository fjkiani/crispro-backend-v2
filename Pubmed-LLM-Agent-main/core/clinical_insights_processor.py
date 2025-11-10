import re
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
import os

class ClinicalInsightsProcessor:
    """
    Processes PubMed literature results and extracts clinical insights
    specifically relevant to genetic variants and cancer.
    """

    def __init__(self, llm_client=None):
        self.llm_client = llm_client

        # Clinical relevance patterns
        self.clinical_patterns = {
            'variant_functional_impact': [
                r'pathogenic|pathogenic variant|deleterious|damaging|loss of function',
                r'gain of function|activating mutation|oncogenic|driver mutation',
                r'benign|neutral|passenger mutation|polymorphism',
                r'splicing|exon skipping|frameshift|nonsense|missense'
            ],
            'clinical_outcomes': [
                r'survival|prognosis|outcome|response|resistance',
                r'treatment|therapy|drug response|efficacy|toxicity',
                r'clinical trial|phase [1-3] trial|randomized controlled',
                r'overall survival|progression free|disease free'
            ],
            'population_frequency': [
                r'prevalence|frequency|incidence|population|cohort',
                r'rare variant|common variant|polymorphism',
                r'ethnic|population specific|geographic variation'
            ],
            'biomarkers': [
                r'biomarker|predictive|prognostic|diagnostic',
                r'companion diagnostic|targeted therapy|precision medicine',
                r'molecular marker|genetic marker|expression marker'
            ]
        }

        # Cancer-specific terms
        self.cancer_terms = {
            'solid_tumors': [
                'breast cancer', 'lung cancer', 'colorectal cancer', 'prostate cancer',
                'pancreatic cancer', 'ovarian cancer', 'melanoma', 'glioblastoma'
            ],
            'hematological': [
                'leukemia', 'lymphoma', 'multiple myeloma', 'myelodysplastic syndrome',
                'acute myeloid leukemia', 'chronic lymphocytic leukemia'
            ],
            'variant_types': [
                'missense', 'nonsense', 'frameshift', 'splice site', 'insertion', 'deletion',
                'copy number variation', 'structural variant', 'fusion gene'
            ]
        }

    def process_literature_results(self, pubmed_results: Dict[str, Any], variant_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process raw PubMed results and extract clinical insights for a specific variant.

        Args:
            pubmed_results: Raw PubMed search results
            variant_info: Information about the variant being analyzed

        Returns:
            Dict containing processed clinical insights
        """
        if not pubmed_results or 'results' not in pubmed_results:
            return self._create_empty_response(variant_info)

        results = pubmed_results['results']
        if not results:
            return self._create_empty_response(variant_info)

        # Extract clinical insights from each paper
        processed_papers = []
        clinical_insights = {
            'functional_impact': [],
            'clinical_evidence': [],
            'population_data': [],
            'therapeutic_implications': [],
            'biomarker_associations': []
        }

        for paper in results:
            processed_paper = self._process_single_paper(paper, variant_info)
            if processed_paper:
                processed_papers.append(processed_paper)

                # Categorize insights
                for category, insights in processed_paper.get('insights', {}).items():
                    if category in clinical_insights:
                        clinical_insights[category].extend(insights)

        # Generate summary and recommendations
        summary = self._generate_clinical_summary(clinical_insights, variant_info, len(processed_papers))
        recommendations = self._generate_clinical_recommendations(clinical_insights, variant_info)

        return {
            'variant_info': variant_info,
            'search_metadata': {
                'total_papers_found': pubmed_results.get('total_found', 0),
                'papers_analyzed': len(processed_papers),
                'search_timestamp': datetime.now().isoformat()
            },
            'clinical_insights': clinical_insights,
            'processed_papers': processed_papers,
            'summary': summary,
            'clinical_recommendations': recommendations,
            'evidence_level': self._assess_evidence_level(clinical_insights, len(processed_papers))
        }

    def _process_single_paper(self, paper: Dict[str, Any], variant_info: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Process a single paper and extract clinical insights."""
        try:
            # Combine title and abstract for analysis
            text_content = f"{paper.get('title', '')} {paper.get('abstract', '')}"
            if not text_content.strip():
                return None

            # Extract insights using pattern matching
            insights = self._extract_insights_from_text(text_content, variant_info)

            # Assess relevance to the specific variant
            relevance_score = self._calculate_relevance_score(text_content, variant_info)

            if relevance_score < 0.3:  # Low relevance threshold
                return None

            return {
                'paper_id': paper.get('pmid', ''),
                'title': paper.get('title', ''),
                'authors': paper.get('authors', ''),
                'journal': paper.get('source', ''),
                'year': paper.get('year', ''),
                'doi': paper.get('doi', ''),
                'relevance_score': relevance_score,
                'insights': insights,
                'key_findings': self._extract_key_findings(text_content, variant_info),
                'confidence': self._assess_paper_confidence(paper)
            }

        except Exception as e:
            print(f"Error processing paper {paper.get('pmid', 'unknown')}: {e}")
            return None

    def _extract_insights_from_text(self, text: str, variant_info: Dict[str, Any]) -> Dict[str, List[str]]:
        """Extract clinical insights from paper text using pattern matching."""
        insights = {
            'functional_impact': [],
            'clinical_evidence': [],
            'population_data': [],
            'therapeutic_implications': [],
            'biomarker_associations': []
        }

        text_lower = text.lower()

        # Extract functional impact insights
        for pattern in self.clinical_patterns['variant_functional_impact']:
            matches = re.findall(pattern, text_lower)
            if matches:
                insights['functional_impact'].extend([m.strip() for m in matches])

        # Extract clinical outcomes insights
        for pattern in self.clinical_patterns['clinical_outcomes']:
            matches = re.findall(pattern, text_lower)
            if matches:
                insights['clinical_evidence'].extend([m.strip() for m in matches])

        # Extract population data insights
        for pattern in self.clinical_patterns['population_frequency']:
            matches = re.findall(pattern, text_lower)
            if matches:
                insights['population_data'].extend([m.strip() for m in matches])

        # Extract therapeutic implications
        for pattern in self.clinical_patterns['biomarkers']:
            matches = re.findall(pattern, text_lower)
            if matches:
                insights['therapeutic_implications'].extend([m.strip() for m in matches])

        # Remove duplicates and clean
        for category in insights:
            insights[category] = list(set([self._clean_insight_text(i) for i in insights[category]]))

        return insights

    def _calculate_relevance_score(self, text: str, variant_info: Dict[str, Any]) -> float:
        """Calculate how relevant this paper is to the specific variant."""
        score = 0.0
        text_lower = text.lower()

        # Gene name matching (high weight)
        gene = variant_info.get('gene', '').lower()
        if gene and gene in text_lower:
            score += 0.4

        # Variant notation matching (high weight)
        hgvs_p = variant_info.get('hgvs_p', '').lower()
        if hgvs_p and hgvs_p in text_lower:
            score += 0.3

        # Disease/cancer type matching (medium weight)
        disease = variant_info.get('disease', '').lower()
        if disease and disease in text_lower:
            score += 0.2

        # Clinical relevance keywords (low weight)
        clinical_keywords = ['mutation', 'variant', 'pathogenic', 'cancer', 'tumor', 'treatment']
        keyword_matches = sum(1 for keyword in clinical_keywords if keyword in text_lower)
        score += min(0.1, keyword_matches * 0.02)

        return min(1.0, score)

    def _extract_key_findings(self, text: str, variant_info: Dict[str, Any]) -> List[str]:
        """Extract key findings related to the variant."""
        findings = []
        sentences = re.split(r'[.!?]+', text)

        for sentence in sentences:
            sentence_lower = sentence.lower()
            if (variant_info.get('gene', '').lower() in sentence_lower and
                any(keyword in sentence_lower for keyword in ['mutation', 'variant', 'associated', 'linked', 'found'])):
                findings.append(sentence.strip())

        return findings[:3]  # Limit to top 3 findings

    def _assess_paper_confidence(self, paper: Dict[str, Any]) -> str:
        """Assess the confidence level of the paper."""
        confidence = "low"

        # High confidence indicators
        if 'clinical trial' in ' '.join(paper.get('publication_types', [])).lower():
            confidence = "high"
        elif paper.get('year', 0) >= 2020:
            confidence = "medium"
        elif 'meta-analysis' in ' '.join(paper.get('publication_types', [])).lower():
            confidence = "high"

        return confidence

    def _generate_clinical_summary(self, clinical_insights: Dict[str, List], variant_info: Dict[str, Any], paper_count: int) -> Dict[str, Any]:
        """Generate a clinical summary of the findings."""
        gene = variant_info.get('gene', 'Unknown')
        variant = variant_info.get('hgvs_p', 'Unknown')

        # Functional impact summary
        functional_impacts = clinical_insights.get('functional_impact', [])
        if functional_impacts:
            if any('pathogenic' in impact.lower() for impact in functional_impacts):
                functional_summary = f"The {gene} {variant} variant is predominantly reported as pathogenic/deleterious."
            elif any('benign' in impact.lower() for impact in functional_impacts):
                functional_summary = f"The {gene} {variant} variant is predominantly reported as benign/neutral."
            else:
                functional_summary = f"The {gene} {variant} variant shows mixed functional impacts in the literature."
        else:
            functional_summary = f"Functional impact of {gene} {variant} is not well characterized in the current literature."

        # Clinical evidence summary
        clinical_evidence = clinical_insights.get('clinical_evidence', [])
        if clinical_evidence:
            clinical_summary = f"Found {len(clinical_evidence)} clinical associations including: {', '.join(clinical_evidence[:3])}"
        else:
            clinical_summary = "Limited clinical evidence available for this variant."

        # Therapeutic implications
        therapeutic = clinical_insights.get('therapeutic_implications', [])
        if therapeutic:
            therapeutic_summary = f"Therapeutic implications identified: {', '.join(therapeutic[:2])}"
        else:
            therapeutic_summary = "No specific therapeutic implications reported."

        return {
            'functional_impact': functional_summary,
            'clinical_evidence': clinical_summary,
            'therapeutic_implications': therapeutic_summary,
            'total_papers_analyzed': paper_count,
            'evidence_strength': self._assess_evidence_strength(functional_impacts, paper_count)
        }

    def _generate_clinical_recommendations(self, clinical_insights: Dict[str, List], variant_info: Dict[str, Any]) -> List[str]:
        """Generate clinical recommendations based on the insights."""
        recommendations = []

        functional_impacts = clinical_insights.get('functional_impact', [])
        clinical_evidence = clinical_insights.get('clinical_evidence', [])
        therapeutic = clinical_insights.get('therapeutic_implications', [])

        # Functional impact recommendations
        if any('pathogenic' in impact.lower() for impact in functional_impacts):
            recommendations.append("Consider clinical correlation and family history evaluation for potential hereditary cancer risk.")

        # Clinical evidence recommendations
        if clinical_evidence:
            if any('survival' in evidence.lower() for evidence in clinical_evidence):
                recommendations.append("Monitor for potential impact on clinical outcomes and treatment planning.")
            if any('treatment' in evidence.lower() for evidence in clinical_evidence):
                recommendations.append("Consider variant status in treatment selection and clinical trial eligibility.")

        # Therapeutic recommendations
        if therapeutic:
            recommendations.append("Evaluate for potential targeted therapy options and clinical trial opportunities.")

        # General recommendations
        if not recommendations:
            recommendations.append("Further functional studies and clinical correlation recommended.")
            recommendations.append("Consider periodic literature review for emerging evidence.")

        return recommendations

    def _assess_evidence_level(self, clinical_insights: Dict[str, List], paper_count: int) -> str:
        """Assess the overall evidence level."""
        total_insights = sum(len(insights) for insights in clinical_insights.values())

        if paper_count >= 10 and total_insights >= 5:
            return "Strong"
        elif paper_count >= 5 and total_insights >= 3:
            return "Moderate"
        elif paper_count >= 1 or total_insights >= 1:
            return "Limited"
        else:
            return "Insufficient"

    def _assess_evidence_strength(self, functional_impacts: List[str], paper_count: int) -> str:
        """Assess the strength of functional evidence."""
        if not functional_impacts:
            return "Unknown"

        pathogenic_count = sum(1 for impact in functional_impacts if 'pathogenic' in impact.lower())
        benign_count = sum(1 for impact in functional_impacts if 'benign' in impact.lower())

        if pathogenic_count > benign_count and paper_count >= 3:
            return "Likely Pathogenic"
        elif benign_count > pathogenic_count and paper_count >= 3:
            return "Likely Benign"
        else:
            return "Uncertain"

    def _clean_insight_text(self, text: str) -> str:
        """Clean and normalize insight text."""
        # Remove extra whitespace and normalize
        text = ' '.join(text.split())
        # Remove common prefixes/suffixes that don't add meaning
        text = re.sub(r'^(the|a|an)\s+', '', text, flags=re.IGNORECASE)
        return text.capitalize()

    def _create_empty_response(self, variant_info: Dict[str, Any]) -> Dict[str, Any]:
        """Create an empty response when no results are found."""
        return {
            'variant_info': variant_info,
            'search_metadata': {
                'total_papers_found': 0,
                'papers_analyzed': 0,
                'search_timestamp': datetime.now().isoformat()
            },
            'clinical_insights': {
                'functional_impact': [],
                'clinical_evidence': [],
                'population_data': [],
                'therapeutic_implications': [],
                'biomarker_associations': []
            },
            'processed_papers': [],
            'summary': {
                'functional_impact': f"No literature found for {variant_info.get('gene', 'Unknown')} {variant_info.get('hgvs_p', 'Unknown')}",
                'clinical_evidence': "No clinical evidence available",
                'therapeutic_implications': "No therapeutic implications identified",
                'total_papers_analyzed': 0,
                'evidence_strength': "Insufficient"
            },
            'clinical_recommendations': [
                "Further research and clinical correlation recommended.",
                "Consider consulting with molecular genetics specialist.",
                "Monitor for emerging literature on this variant."
            ],
            'evidence_level': "Insufficient"
        }
