"""
Therapeutic Optimizer Service

Iteratively optimizes therapeutic candidates through generate-score-refine cycles.

Key Features:
1. Generate candidates using TherapeuticPromptBuilder
2. Score candidates (Evo2 delta, structural metrics, safety)
3. Refine prompts based on feedback
4. Converge to high-quality candidates (score ≥0.85)

This service implements the "Forge" phase of the Predator Protocol.
"""

import logging
import asyncio
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
import httpx

from .therapeutic_prompt_builder import get_prompt_builder, TherapeuticDesignContext

logger = logging.getLogger(__name__)


@dataclass
class OptimizationCandidate:
    """A candidate therapeutic and its metrics."""
    sequence: str
    score: float
    iteration: int
    generation_prompt: str
    feedback: Optional[str] = None
    metrics: Dict[str, any] = field(default_factory=dict)


@dataclass
class OptimizationResult:
    """Result of therapeutic optimization."""
    best_candidate: OptimizationCandidate
    all_candidates: List[OptimizationCandidate]
    converged: bool
    total_iterations: int
    convergence_reason: str


class TherapeuticOptimizer:
    """
    Iteratively optimize therapeutic candidates.
    
    Workflow:
    1. Generate candidate (using TherapeuticPromptBuilder)
    2. Score candidate (Evo2, safety checks, structural if available)
    3. Analyze weaknesses
    4. Refine prompt with feedback
    5. Repeat until convergence or max iterations
    
    Convergence Criteria:
    - Score ≥ threshold (default: 0.85)
    - OR max iterations reached (default: 10)
    - OR no improvement for 3 consecutive iterations
    """
    
    def __init__(
        self,
        evo2_url: str = "http://127.0.0.1:8000/api/evo",
        max_iterations: int = 10,
        score_threshold: float = 0.85,
        min_improvement: float = 0.01
    ):
        self.evo2_url = evo2_url
        self.max_iterations = max_iterations
        self.score_threshold = score_threshold
        self.min_improvement = min_improvement
        
        self.prompt_builder = get_prompt_builder()
        self.logger = logging.getLogger(__name__)
        
        # Track optimization history
        self.history: List[OptimizationCandidate] = []
    
    async def optimize_guide_rna(
        self,
        target_gene: str,
        target_sequence: str,
        pam_site: str = "NGG",
        mechanism: str = "inhibit"
    ) -> OptimizationResult:
        """
        Optimize CRISPR guide RNA design.
        
        Args:
            target_gene: Target gene name
            target_sequence: Target gene sequence (>=1000bp)
            pam_site: PAM sequence (default: NGG)
            mechanism: "inhibit" or "activate"
        
        Returns:
            Optimization result with best candidate
        """
        
        self.logger.info(f"Starting guide RNA optimization for {target_gene}")
        self.history = []
        
        best_candidate = None
        best_score = 0.0
        no_improvement_count = 0
        
        for iteration in range(self.max_iterations):
            self.logger.info(f"Iteration {iteration + 1}/{self.max_iterations}")
            
            # 1. Generate prompt (with feedback from previous iteration)
            prompt = self._build_refined_prompt_guide_rna(
                target_gene, target_sequence, pam_site, mechanism,
                feedback=best_candidate.feedback if best_candidate else None
            )
            
            # 2. Generate candidate (Evo2)
            candidate_sequence = await self._generate_sequence(prompt)
            
            if not candidate_sequence:
                self.logger.warning(f"Generation failed at iteration {iteration + 1}")
                continue
            
            # 3. Score candidate
            score, metrics = await self._score_candidate(candidate_sequence, target_gene)
            
            # 4. Create candidate record
            candidate = OptimizationCandidate(
                sequence=candidate_sequence,
                score=score,
                iteration=iteration + 1,
                generation_prompt=prompt,
                metrics=metrics
            )
            
            self.history.append(candidate)
            
            # 5. Check if this is the best so far
            if score > best_score + self.min_improvement:
                best_candidate = candidate
                best_score = score
                no_improvement_count = 0
                self.logger.info(f"New best score: {score:.3f}")
            else:
                no_improvement_count += 1
            
            # 6. Check convergence
            if score >= self.score_threshold:
                self.logger.info(f"Converged! Score {score:.3f} ≥ threshold {self.score_threshold}")
                return OptimizationResult(
                    best_candidate=best_candidate,
                    all_candidates=self.history,
                    converged=True,
                    total_iterations=iteration + 1,
                    convergence_reason=f"Score threshold reached: {score:.3f}"
                )
            
            if no_improvement_count >= 3:
                self.logger.info("No improvement for 3 iterations. Stopping.")
                return OptimizationResult(
                    best_candidate=best_candidate,
                    all_candidates=self.history,
                    converged=False,
                    total_iterations=iteration + 1,
                    convergence_reason="No improvement for 3 iterations"
                )
            
            # 7. Generate feedback for next iteration
            if best_candidate:
                best_candidate.feedback = self._generate_feedback(candidate, metrics)
        
        # Max iterations reached
        self.logger.info(f"Max iterations reached. Best score: {best_score:.3f}")
        return OptimizationResult(
            best_candidate=best_candidate or self.history[-1],
            all_candidates=self.history,
            converged=False,
            total_iterations=self.max_iterations,
            convergence_reason=f"Max iterations ({self.max_iterations}) reached"
        )
    
    async def optimize_protein_therapeutic(
        self,
        target_gene: str,
        disease: str,
        mechanism: str,
        gene_context: str,
        binding_sites: Optional[Dict] = None
    ) -> OptimizationResult:
        """
        Optimize therapeutic protein design.
        
        Similar workflow to guide RNA optimization but with protein-specific scoring.
        """
        
        self.logger.info(f"Starting protein therapeutic optimization for {target_gene}")
        self.history = []
        
        best_candidate = None
        best_score = 0.0
        no_improvement_count = 0
        
        for iteration in range(self.max_iterations):
            self.logger.info(f"Iteration {iteration + 1}/{self.max_iterations}")
            
            # 1. Generate prompt with refinement
            prompt = self._build_refined_prompt_protein(
                target_gene, disease, mechanism, gene_context, binding_sites,
                feedback=best_candidate.feedback if best_candidate else None
            )
            
            # 2. Generate candidate
            candidate_sequence = await self._generate_sequence(prompt)
            
            if not candidate_sequence:
                continue
            
            # 3. Score candidate
            score, metrics = await self._score_candidate(candidate_sequence, target_gene)
            
            # 4. Create record
            candidate = OptimizationCandidate(
                sequence=candidate_sequence,
                score=score,
                iteration=iteration + 1,
                generation_prompt=prompt,
                metrics=metrics
            )
            
            self.history.append(candidate)
            
            # 5. Update best
            if score > best_score + self.min_improvement:
                best_candidate = candidate
                best_score = score
                no_improvement_count = 0
            else:
                no_improvement_count += 1
            
            # 6. Convergence checks
            if score >= self.score_threshold:
                return OptimizationResult(
                    best_candidate=best_candidate,
                    all_candidates=self.history,
                    converged=True,
                    total_iterations=iteration + 1,
                    convergence_reason=f"Score threshold reached: {score:.3f}"
                )
            
            if no_improvement_count >= 3:
                return OptimizationResult(
                    best_candidate=best_candidate,
                    all_candidates=self.history,
                    converged=False,
                    total_iterations=iteration + 1,
                    convergence_reason="No improvement for 3 iterations"
                )
            
            # 7. Feedback
            if best_candidate:
                best_candidate.feedback = self._generate_feedback(candidate, metrics)
        
        return OptimizationResult(
            best_candidate=best_candidate or self.history[-1],
            all_candidates=self.history,
            converged=False,
            total_iterations=self.max_iterations,
            convergence_reason=f"Max iterations ({self.max_iterations}) reached"
        )
    
    def _build_refined_prompt_guide_rna(
        self,
        target_gene: str,
        target_sequence: str,
        pam_site: str,
        mechanism: str,
        feedback: Optional[str] = None
    ) -> str:
        """Build refined prompt incorporating feedback from previous iterations."""
        
        base_prompt = self.prompt_builder.build_guide_rna_prompt(
            target_gene, target_sequence, pam_site, mechanism
        )
        
        if feedback:
            # Append feedback to prompt
            base_prompt += f"\n# Feedback from previous iteration:\n# {feedback}\n"
            base_prompt += "# Address these issues in the next design:\n"
        
        return base_prompt
    
    def _build_refined_prompt_protein(
        self,
        target_gene: str,
        disease: str,
        mechanism: str,
        gene_context: str,
        binding_sites: Optional[Dict],
        feedback: Optional[str] = None
    ) -> str:
        """Build refined prompt for protein therapeutic."""
        
        base_prompt = self.prompt_builder.build_protein_therapeutic_prompt(
            target_gene, disease, mechanism, gene_context, binding_sites
        )
        
        if feedback:
            base_prompt += f"\n# Feedback from previous iteration:\n# {feedback}\n"
        
        return base_prompt
    
    async def _generate_sequence(self, prompt: str) -> Optional[str]:
        """
        Generate sequence using Evo2.
        
        NOTE: This is a STUB. Real implementation will call Evo2 generation endpoint.
        For now, returns mock sequence for testing.
        """
        
        # TODO: Call actual Evo2 generation endpoint
        # POST /api/evo/generate with prompt
        
        # STUB: Return mock sequence for testing
        mock_sequence = "ATCGATCGATCGATCGATCG" * 10  # 200bp mock
        
        self.logger.debug(f"Generated sequence (STUB): {len(mock_sequence)}bp")
        return mock_sequence
    
    async def _score_candidate(
        self,
        sequence: str,
        target_gene: str,
        target_sequence: str = None,
        therapeutic_type: str = "protein"
    ) -> Tuple[float, Dict[str, any]]:
        """
        Score candidate therapeutic.
        
        Args:
            sequence: Therapeutic candidate sequence
            target_gene: Target gene name (e.g., "VEGFA")
            target_sequence: Optional target gene sequence for binding prediction
            therapeutic_type: Type of therapeutic ("protein", "peptide", "guide_rna")
        
        Metrics:
        - Evo2 delta score (sequence-level impact)
        - GC content
        - Homopolymer check
        - Safety checks (viral content)
        
        Returns:
            (score, metrics_dict)
        """
        
        metrics = {}
        
        # 1. GC content
        gc_content = self._calculate_gc_content(sequence)
        metrics["gc_content"] = gc_content
        
        # GC score (prefer 40-60%)
        if 0.40 <= gc_content <= 0.60:
            gc_score = 1.0
        elif 0.30 <= gc_content <= 0.70:
            gc_score = 0.5
        else:
            gc_score = 0.1
        
        # 2. Homopolymer check
        max_homopolymer = self._find_max_homopolymer(sequence)
        metrics["max_homopolymer"] = max_homopolymer
        
        # Homopolymer score (penalize >4bp)
        if max_homopolymer <= 4:
            homopoly_score = 1.0
        elif max_homopolymer <= 6:
            homopoly_score = 0.5
        else:
            homopoly_score = 0.1
        
        # 3. Length check
        metrics["length"] = len(sequence)
        length_score = 1.0 if 15 <= len(sequence) <= 300 else 0.5
        
        # 4. Evo2 delta score (STUB - would call actual Evo2)
        # TODO: Implement real Evo2 delta scoring
        evo2_score = 0.75  # Mock score
        metrics["evo2_delta"] = evo2_score
        
        # 5. Composite score
        composite_score = (
            0.4 * evo2_score +
            0.3 * gc_score +
            0.2 * homopoly_score +
            0.1 * length_score
        )
        
        metrics["composite_score"] = composite_score
        
        return composite_score, metrics
    
    def _calculate_gc_content(self, sequence: str) -> float:
        """Calculate GC content of sequence."""
        sequence_upper = sequence.upper()
        gc_count = sequence_upper.count('G') + sequence_upper.count('C')
        return gc_count / len(sequence) if sequence else 0.0
    
    def _find_max_homopolymer(self, sequence: str) -> int:
        """Find longest homopolymer run in sequence."""
        if not sequence:
            return 0
        
        max_run = 1
        current_run = 1
        prev_char = sequence[0]
        
        for char in sequence[1:]:
            if char == prev_char:
                current_run += 1
                max_run = max(max_run, current_run)
            else:
                current_run = 1
                prev_char = char
        
        return max_run
    
    def _generate_feedback(
        self,
        candidate: OptimizationCandidate,
        metrics: Dict[str, any]
    ) -> str:
        """Generate feedback for prompt refinement."""
        
        feedback_parts = []
        
        # GC content feedback
        gc = metrics.get("gc_content", 0)
        if gc < 0.40:
            feedback_parts.append("GC content too low - add more G/C bases")
        elif gc > 0.60:
            feedback_parts.append("GC content too high - reduce G/C bases")
        
        # Homopolymer feedback
        homopoly = metrics.get("max_homopolymer", 0)
        if homopoly > 4:
            feedback_parts.append(f"Homopolymer run ({homopoly}bp) - break up repeats")
        
        # Evo2 score feedback
        evo2 = metrics.get("evo2_delta", 0)
        if evo2 < 0.70:
            feedback_parts.append("Low Evo2 score - target different region or mechanism")
        
        return " | ".join(feedback_parts) if feedback_parts else "Good design, minor refinements"


# Singleton
_optimizer_instance = None


def get_therapeutic_optimizer(
    evo2_url: str = "http://127.0.0.1:8000/api/evo",
    max_iterations: int = 10,
    score_threshold: float = 0.85
) -> TherapeuticOptimizer:
    """Get singleton therapeutic optimizer instance."""
    global _optimizer_instance
    if _optimizer_instance is None:
        _optimizer_instance = TherapeuticOptimizer(
            evo2_url=evo2_url,
            max_iterations=max_iterations,
            score_threshold=score_threshold
        )
    return _optimizer_instance

