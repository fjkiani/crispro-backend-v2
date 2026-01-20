"""
Safety Validator Service

Validates therapeutic sequences for biological safety before generation/optimization.

Safety Checks:
1. Viral Content Blocking: Prevents generation of human pathogenic virus sequences
2. GC Extreme Filtering: Blocks sequences with extreme GC content (<20% or >80%)
3. Homopolymer Filtering: Blocks sequences with long homopolymer runs (>6bp)
4. Known Toxic Sequences: Database of problematic sequences to avoid

Usage:
    from api.services.safety_validator import get_safety_validator
    
    validator = get_safety_validator()
    result = validator.validate_sequence(sequence, context)
    if not result.is_safe:
        print(f"Unsafe: {result.reason}")
"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from enum import Enum


class SafetyLevel(str, Enum):
    """Safety assessment levels."""
    SAFE = "safe"
    WARNING = "warning"
    BLOCKED = "blocked"


class SafetyCheckResult(BaseModel):
    """Result of a single safety check."""
    check_name: str
    passed: bool
    level: SafetyLevel
    reason: str = ""
    details: Dict[str, Any] = Field(default_factory=dict)


class SafetyValidationResult(BaseModel):
    """Complete safety validation result."""
    is_safe: bool
    level: SafetyLevel
    checks: List[SafetyCheckResult]
    reason: str = ""
    recommendations: List[str] = Field(default_factory=list)


# Viral content blocklist
# These are partial sequences known to be associated with human pathogenic viruses
VIRAL_BLOCKLIST = {
    "hiv": [
        "ATGGGTGCGAGAGCGTC",  # HIV-1 gag gene start
        "TGGAAGGGCTAATTCAC",  # HIV-1 LTR region
        "CCTCAGGTCACTCTTTG",  # HIV-1 pol region
    ],
    "sars_cov": [
        "ATGTTTGTTTTTCTTGT",  # SARS-CoV-2 ORF1a start
        "ATTAAAGGTTTATACCT",  # SARS-CoV-2 spike region
        "ATGTCTGATAATGGACC",  # SARS-CoV S protein
    ],
    "ebola": [
        "ATGGGAATTACACTTTT",  # Ebola VP35 start
        "ATGAGTACTCGAAAATA",  # Ebola GP start
    ],
    "influenza": [
        "ATGGAGAGAATAAAGGA",  # Influenza A HA start
        "ATGGATTGGACCTTTGA",  # Influenza A NA start
    ],
}

# Known toxic sequences (placeholder - expand with real data)
TOXIC_SEQUENCES = [
    "GGGGGGGGGGGGGG",  # Excessive G runs (aggregation prone)
    "CCCCCCCCCCCCCC",  # Excessive C runs (aggregation prone)
]


class SafetyValidator:
    """
    Validates therapeutic sequences for biological safety.
    
    Implements multiple layers of safety checks:
    - Viral content detection
    - GC content validation
    - Homopolymer detection
    - Toxic sequence blocking
    """
    
    def __init__(
        self,
        gc_min: float = 0.20,
        gc_max: float = 0.80,
        max_homopolymer: int = 6,
        enable_viral_check: bool = True,
        enable_toxic_check: bool = True,
        gc_warning_threshold_low: float = 0.30,
        gc_warning_threshold_high: float = 0.70
    ):
        self.gc_min = gc_min
        self.gc_max = gc_max
        self.max_homopolymer = max_homopolymer
        self.enable_viral_check = enable_viral_check
        self.enable_toxic_check = enable_toxic_check
        self.gc_warning_threshold_low = gc_warning_threshold_low
        self.gc_warning_threshold_high = gc_warning_threshold_high
        
        # Build viral blocklist lookup
        self.viral_patterns = []
        for virus_type, patterns in VIRAL_BLOCKLIST.items():
            self.viral_patterns.extend([(p, virus_type) for p in patterns])
    
    def validate_sequence(
        self,
        sequence: str,
        context: Optional[Dict[str, Any]] = None
    ) -> SafetyValidationResult:
        """
        Validates a therapeutic sequence for safety.
        
        Args:
            sequence: DNA sequence to validate
            context: Optional context (target_gene, disease, therapeutic_type)
        
        Returns:
            SafetyValidationResult with is_safe flag and detailed checks
        """
        if not sequence:
            return SafetyValidationResult(
                is_safe=False,
                level=SafetyLevel.BLOCKED,
                checks=[],
                reason="Empty sequence provided"
            )
        
        sequence = sequence.upper().strip()
        checks: List[SafetyCheckResult] = []
        
        # 1. Viral content check
        if self.enable_viral_check:
            viral_check = self._check_viral_content(sequence)
            checks.append(viral_check)
        
        # 2. GC content check
        gc_check = self._check_gc_content(sequence)
        checks.append(gc_check)
        
        # 3. Homopolymer check
        homopolymer_check = self._check_homopolymers(sequence)
        checks.append(homopolymer_check)
        
        # 4. Toxic sequences check
        if self.enable_toxic_check:
            toxic_check = self._check_toxic_sequences(sequence)
            checks.append(toxic_check)
        
        # 5. Determine overall safety
        blocked_checks = [c for c in checks if c.level == SafetyLevel.BLOCKED]
        warning_checks = [c for c in checks if c.level == SafetyLevel.WARNING]
        
        if blocked_checks:
            is_safe = False
            level = SafetyLevel.BLOCKED
            reason = f"Blocked by: {', '.join([c.check_name for c in blocked_checks])}"
            recommendations = self._generate_recommendations(checks, context)
        elif warning_checks:
            is_safe = True  # Warnings don't block, but flag issues
            level = SafetyLevel.WARNING
            reason = f"Warnings: {', '.join([c.check_name for c in warning_checks])}"
            recommendations = self._generate_recommendations(checks, context)
        else:
            is_safe = True
            level = SafetyLevel.SAFE
            reason = "All safety checks passed"
            recommendations = []
        
        return SafetyValidationResult(
            is_safe=is_safe,
            level=level,
            checks=checks,
            reason=reason,
            recommendations=recommendations
        )
    
    def _check_viral_content(self, sequence: str) -> SafetyCheckResult:
        """Check for viral sequence patterns."""
        for pattern, virus_type in self.viral_patterns:
            if pattern in sequence:
                return SafetyCheckResult(
                    check_name="viral_content",
                    passed=False,
                    level=SafetyLevel.BLOCKED,
                    reason=f"Contains {virus_type.upper()} sequence pattern",
                    details={"virus_type": virus_type, "pattern": pattern}
                )
        
        return SafetyCheckResult(
            check_name="viral_content",
            passed=True,
            level=SafetyLevel.SAFE,
            reason="No viral content detected"
        )
    
    def _check_gc_content(self, sequence: str) -> SafetyCheckResult:
        """Check GC content is within acceptable range."""
        gc_count = sequence.count('G') + sequence.count('C')
        gc_content = gc_count / len(sequence) if len(sequence) > 0 else 0.0
        
        if gc_content < self.gc_min:
            return SafetyCheckResult(
                check_name="gc_content",
                passed=False,
                level=SafetyLevel.BLOCKED,
                reason=f"GC content too low: {gc_content:.2%} (min: {self.gc_min:.2%})",
                details={"gc_content": gc_content, "gc_min": self.gc_min}
            )
        elif gc_content > self.gc_max:
            return SafetyCheckResult(
                check_name="gc_content",
                passed=False,
                level=SafetyLevel.BLOCKED,
                reason=f"GC content too high: {gc_content:.2%} (max: {self.gc_max:.2%})",
                details={"gc_content": gc_content, "gc_max": self.gc_max}
            )
        elif gc_content < self.gc_warning_threshold_low or gc_content > self.gc_warning_threshold_high:
            # Warning zone (configurable thresholds)
            return SafetyCheckResult(
                check_name="gc_content",
                passed=True,
                level=SafetyLevel.WARNING,
                reason=f"GC content in warning zone: {gc_content:.2%}",
                details={"gc_content": gc_content}
            )
        else:
            return SafetyCheckResult(
                check_name="gc_content",
                passed=True,
                level=SafetyLevel.SAFE,
                reason=f"GC content optimal: {gc_content:.2%}",
                details={"gc_content": gc_content}
            )
    
    def _check_homopolymers(self, sequence: str) -> SafetyCheckResult:
        """Check for long homopolymer runs."""
        max_run = 0
        max_run_base = ""
        
        for base in "ATCG":
            current_run = 0
            for char in sequence:
                if char == base:
                    current_run += 1
                    if current_run > max_run:
                        max_run = current_run
                        max_run_base = base
                else:
                    current_run = 0
        
        if max_run > self.max_homopolymer:
            return SafetyCheckResult(
                check_name="homopolymer",
                passed=False,
                level=SafetyLevel.BLOCKED,
                reason=f"Homopolymer run too long: {max_run_base}x{max_run} (max: {self.max_homopolymer})",
                details={"max_run": max_run, "base": max_run_base, "max_allowed": self.max_homopolymer}
            )
        elif max_run > 4:
            # Warning zone (5-6bp)
            return SafetyCheckResult(
                check_name="homopolymer",
                passed=True,
                level=SafetyLevel.WARNING,
                reason=f"Homopolymer run in warning zone: {max_run_base}x{max_run}",
                details={"max_run": max_run, "base": max_run_base}
            )
        else:
            return SafetyCheckResult(
                check_name="homopolymer",
                passed=True,
                level=SafetyLevel.SAFE,
                reason=f"Homopolymer runs acceptable: max {max_run}bp",
                details={"max_run": max_run}
            )
    
    def _check_toxic_sequences(self, sequence: str) -> SafetyCheckResult:
        """Check for known toxic sequences."""
        for toxic_seq in TOXIC_SEQUENCES:
            if toxic_seq in sequence:
                return SafetyCheckResult(
                    check_name="toxic_sequences",
                    passed=False,
                    level=SafetyLevel.BLOCKED,
                    reason=f"Contains known toxic sequence: {toxic_seq[:20]}...",
                    details={"toxic_sequence": toxic_seq}
                )
        
        return SafetyCheckResult(
            check_name="toxic_sequences",
            passed=True,
            level=SafetyLevel.SAFE,
            reason="No known toxic sequences detected"
        )
    
    def _generate_recommendations(
        self,
        checks: List[SafetyCheckResult],
        context: Optional[Dict[str, Any]]
    ) -> List[str]:
        """Generate actionable recommendations based on failed checks."""
        recommendations = []
        
        for check in checks:
            if not check.passed:
                if check.check_name == "viral_content":
                    recommendations.append("Regenerate sequence avoiding viral patterns")
                elif check.check_name == "gc_content":
                    gc = check.details.get("gc_content", 0)
                    if gc < self.gc_min:
                        recommendations.append(f"Increase GC content to at least {self.gc_min:.0%}")
                    else:
                        recommendations.append(f"Decrease GC content to at most {self.gc_max:.0%}")
                elif check.check_name == "homopolymer":
                    recommendations.append(f"Break up homopolymer runs to max {self.max_homopolymer}bp")
                elif check.check_name == "toxic_sequences":
                    recommendations.append("Regenerate sequence avoiding toxic patterns")
        
        return recommendations


def get_safety_validator(
    gc_min: float = 0.20,
    gc_max: float = 0.80,
    max_homopolymer: int = 6,
    enable_viral_check: bool = True,
    enable_toxic_check: bool = True
) -> SafetyValidator:
    """
    Factory function to get a configured SafetyValidator.
    
    Args:
        gc_min: Minimum acceptable GC content (default: 0.20)
        gc_max: Maximum acceptable GC content (default: 0.80)
        max_homopolymer: Maximum homopolymer run length (default: 6)
        enable_viral_check: Enable viral content checking (default: True)
        enable_toxic_check: Enable toxic sequence checking (default: True)
    
    Returns:
        Configured SafetyValidator instance
    """
    return SafetyValidator(
        gc_min=gc_min,
        gc_max=gc_max,
        max_homopolymer=max_homopolymer,
        enable_viral_check=enable_viral_check,
        enable_toxic_check=enable_toxic_check
    )

