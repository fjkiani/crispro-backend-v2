"""
AI Explanation Generator - Generates audience-appropriate explanations.
"""
from typing import List, Optional
from datetime import datetime
import httpx
import logging

from .models import (
    GeneEssentialityScore,
    PathwayAnalysis,
    DrugRecommendation,
    AIExplanation
)

logger = logging.getLogger(__name__)


class ExplanationGenerator:
    """
    Generate AI-powered explanations for synthetic lethality results.
    
    Audiences:
    - Clinician: Medical terminology, mechanism details, citations
    - Patient: Simple language, analogies, reassuring tone
    - Researcher: Molecular mechanisms, pathway details, combination strategies
    """
    
    def __init__(self, api_base: str = "http://127.0.0.1:8000"):
        self.api_base = api_base
    
    async def generate(
        self,
        essentiality_scores: List[GeneEssentialityScore],
        broken_pathways: List[PathwayAnalysis],
        essential_pathways: List[PathwayAnalysis],
        recommended_drugs: List[DrugRecommendation],
        audience: str = "clinician"
    ) -> Optional[AIExplanation]:
        """
        Generate AI explanation for results.
        
        Args:
            essentiality_scores: Gene scores
            broken_pathways: Disrupted pathways
            essential_pathways: Essential backups
            recommended_drugs: Drug recommendations
            audience: clinician/patient/researcher
        
        Returns:
            AIExplanation or None if LLM unavailable
        """
        try:
            prompt = self._build_prompt(
                essentiality_scores=essentiality_scores,
                broken_pathways=broken_pathways,
                essential_pathways=essential_pathways,
                recommended_drugs=recommended_drugs,
                audience=audience
            )
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.api_base}/api/llm/explain",
                    json={
                        'prompt': prompt,
                        'provider': 'gemini',
                        'context': 'synthetic_lethality'
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    explanation_text = data.get('explanation', '')
                    
                    return AIExplanation(
                        audience=audience,
                        summary=self._extract_summary(explanation_text),
                        full_explanation=explanation_text,
                        key_points=self._extract_key_points(explanation_text),
                        generated_at=datetime.utcnow(),
                        provider='gemini'
                    )
                else:
                    logger.warning(f"LLM API returned {response.status_code}")
                    return None
        
        except Exception as e:
            logger.error(f"Explanation generation failed: {e}")
            return None
    
    def _build_prompt(
        self,
        essentiality_scores: List[GeneEssentialityScore],
        broken_pathways: List[PathwayAnalysis],
        essential_pathways: List[PathwayAnalysis],
        recommended_drugs: List[DrugRecommendation],
        audience: str
    ) -> str:
        """Build audience-appropriate prompt."""
        # Build context section
        context = f"""
## Synthetic Lethality Analysis Results

### Gene Essentiality Scores:
{self._format_scores(essentiality_scores)}

### Broken Pathways:
{self._format_pathways(broken_pathways)}

### Essential Backup Pathways (Cancer Dependencies):
{self._format_pathways(essential_pathways)}

### Recommended Therapies:
{self._format_drugs(recommended_drugs)}
"""
        
        # Audience-specific instructions
        instructions = {
            'clinician': """
Explain these results for a practicing oncologist. Include:
1. Clinical significance of each gene's essentiality
2. Mechanism of synthetic lethality (why targeting backups works)
3. Rationale for drug recommendations with evidence tier
4. Key monitoring considerations
Use appropriate medical terminology.
""",
            'patient': """
Explain these results for a cancer patient with no medical background. Include:
1. What the genetic mutations mean in simple terms
2. Why certain treatments might work better for them
3. What "synthetic lethality" means using everyday analogies
4. Reassuring but honest tone about treatment options
Avoid medical jargon. Use 8th-grade reading level.
""",
            'researcher': """
Provide a detailed scientific explanation including:
1. Molecular mechanisms of pathway disruption
2. Evidence from literature supporting synthetic lethality relationships
3. Potential resistance mechanisms to monitor
4. Suggestions for combination therapy rationale
Include pathway-level detail and mechanistic insights.
"""
        }
        
        return f"{context}\n\n{instructions.get(audience, instructions['clinician'])}"
    
    def _format_scores(self, scores: List[GeneEssentialityScore]) -> str:
        """Format essentiality scores for prompt."""
        lines = []
        for s in scores:
            lines.append(f"- {s.gene}: {s.essentiality_score:.2f} ({s.essentiality_level.value}) - {s.pathway_impact}")
        return '\n'.join(lines)
    
    def _format_pathways(self, pathways: List[PathwayAnalysis]) -> str:
        """Format pathways for prompt."""
        lines = []
        for p in pathways:
            lines.append(f"- {p.pathway_name}: {p.status.value} (score: {p.disruption_score:.2f})")
        return '\n'.join(lines)
    
    def _format_drugs(self, drugs: List[DrugRecommendation]) -> str:
        """Format drugs for prompt."""
        lines = []
        for i, d in enumerate(drugs[:5], 1):
            fda = "FDA ✓" if d.fda_approved else "Clinical"
            lines.append(f"{i}. {d.drug_name} ({d.drug_class}) - {d.confidence*100:.0f}% confidence [{fda}]")
        return '\n'.join(lines)
    
    def _extract_summary(self, text: str) -> str:
        """Extract first paragraph as summary."""
        paragraphs = text.strip().split('\n\n')
        return paragraphs[0] if paragraphs else text[:200]
    
    def _extract_key_points(self, text: str) -> List[str]:
        """Extract bullet points from explanation."""
        points = []
        for line in text.split('\n'):
            line = line.strip()
            if line.startswith(('- ', '• ', '* ', '1.', '2.', '3.')):
                points.append(line.lstrip('- •* 0123456789.'))
        return points[:5]


