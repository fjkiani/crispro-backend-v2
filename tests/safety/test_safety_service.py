"""
Unit tests for safety service (toxicity risk + off-target preview).

Tests cover:
- Pharmacogene detection
- MoA → toxicity pathway overlap
- Off-target heuristic scoring
- Edge cases and error handling
"""

import pytest
from api.services.safety_service import SafetyService
from api.services.toxicity_pathway_mappings import (
    is_pharmacogene, get_pharmacogene_risk_weight,
    compute_pathway_overlap, get_moa_toxicity_weights
)
from api.schemas.safety import (
    ToxicityRiskRequest, PatientContext, GermlineVariant,
    TherapeuticCandidate, ClinicalContext,
    OffTargetPreviewRequest, GuideRNA
)


# ============================================================================
# TOXICITY PATHWAY MAPPINGS TESTS
# ============================================================================

class TestToxicityPathwayMappings:
    """Test toxicity pathway mapping utilities."""
    
    def test_is_pharmacogene_positive(self):
        """Test pharmacogene detection (positive cases)."""
        assert is_pharmacogene("DPYD") is True
        assert is_pharmacogene("CYP2D6") is True
        assert is_pharmacogene("UGT1A1") is True
        assert is_pharmacogene("TPMT") is True
        assert is_pharmacogene("G6PD") is True
    
    def test_is_pharmacogene_negative(self):
        """Test pharmacogene detection (negative cases)."""
        assert is_pharmacogene("BRAF") is False
        assert is_pharmacogene("TP53") is False
        assert is_pharmacogene("KRAS") is False
    
    def test_is_pharmacogene_case_insensitive(self):
        """Test pharmacogene detection is case-insensitive."""
        assert is_pharmacogene("dpyd") is True
        assert is_pharmacogene("Dpyd") is True
        assert is_pharmacogene("DPYD") is True
    
    def test_get_pharmacogene_risk_weight_high_impact(self):
        """Test risk weights for high-impact pharmacogenes."""
        assert get_pharmacogene_risk_weight("DPYD") == 0.4
        assert get_pharmacogene_risk_weight("TPMT") == 0.4
        assert get_pharmacogene_risk_weight("G6PD") == 0.4
    
    def test_get_pharmacogene_risk_weight_cyp(self):
        """Test risk weights for CYP enzymes."""
        assert get_pharmacogene_risk_weight("CYP2D6") == 0.3
        assert get_pharmacogene_risk_weight("CYP2C19") == 0.3
    
    def test_get_pharmacogene_risk_weight_other(self):
        """Test risk weights for other pharmacogenes."""
        assert get_pharmacogene_risk_weight("UGT1A1") == 0.4  # High impact
        assert get_pharmacogene_risk_weight("ABCB1") == 0.2  # Other
    
    def test_get_moa_toxicity_weights_braf(self):
        """Test MoA weights for BRAF inhibitor."""
        weights = get_moa_toxicity_weights("BRAF_inhibitor")
        assert "dna_repair" in weights
        assert weights["dna_repair"] == 0.3
        assert weights["inflammation"] == 0.2
    
    def test_get_moa_toxicity_weights_platinum(self):
        """Test MoA weights for platinum agents (high DNA damage)."""
        weights = get_moa_toxicity_weights("platinum_agent")
        assert weights["dna_repair"] == 0.9  # Very high
    
    def test_get_moa_toxicity_weights_unknown(self):
        """Test MoA weights for unknown drug (conservative baseline)."""
        weights = get_moa_toxicity_weights("unknown_drug")
        assert weights["dna_repair"] == 0.1
        assert weights["inflammation"] == 0.1
        assert weights["cardiometabolic"] == 0.1
    
    def test_compute_pathway_overlap_no_overlap(self):
        """Test pathway overlap with no germline hits."""
        patient_genes = ["BRAF", "KRAS"]  # Not in DNA repair pathways
        overlaps = compute_pathway_overlap(patient_genes, "platinum_agent")
        assert all(score == 0.0 for score in overlaps.values())
    
    def test_compute_pathway_overlap_with_hits(self):
        """Test pathway overlap with germline DNA repair hits."""
        patient_genes = ["BRCA1", "BRCA2", "ATM"]  # DNA repair genes
        overlaps = compute_pathway_overlap(patient_genes, "platinum_agent")
        assert overlaps["dna_repair"] > 0.5  # Should have significant overlap


# ============================================================================
# SAFETY SERVICE TESTS
# ============================================================================

class TestSafetyService:
    """Test SafetyService toxicity risk assessment."""
    
    @pytest.fixture
    def safety_service(self):
        """Create SafetyService instance."""
        return SafetyService()
    
    @pytest.mark.asyncio
    async def test_toxicity_risk_no_germline(self, safety_service):
        """Test toxicity risk with no germline variants."""
        request = ToxicityRiskRequest(
            patient=PatientContext(germlineVariants=[]),
            candidate=TherapeuticCandidate(type="drug", moa="BRAF_inhibitor"),
            context=ClinicalContext(disease="melanoma")
        )
        
        response = await safety_service.compute_toxicity_risk(request)
        
        assert response.risk_score >= 0.0
        assert response.risk_score <= 1.0
        assert response.confidence > 0.0
        assert len(response.factors) == 0  # No germline factors
        assert "run_id" in response.provenance
    
    @pytest.mark.asyncio
    async def test_toxicity_risk_with_pharmacogene(self, safety_service):
        """Test toxicity risk with pharmacogene variant."""
        request = ToxicityRiskRequest(
            patient=PatientContext(germlineVariants=[
                GermlineVariant(chrom="1", pos=97450058, ref="C", alt="T", gene="DPYD")
            ]),
            candidate=TherapeuticCandidate(type="drug", moa="platinum_agent"),
            context=ClinicalContext(disease="ovarian")
        )
        
        response = await safety_service.compute_toxicity_risk(request)
        
        assert response.risk_score > 0.3  # Should flag pharmacogene risk
        assert len(response.factors) >= 1
        assert any(f.type == "germline" for f in response.factors)
        assert "DPYD" in response.reason or any("DPYD" in f.detail for f in response.factors)
    
    @pytest.mark.asyncio
    async def test_toxicity_risk_pathway_overlap(self, safety_service):
        """Test toxicity risk with MoA pathway overlap."""
        request = ToxicityRiskRequest(
            patient=PatientContext(germlineVariants=[
                GermlineVariant(chrom="17", pos=43044295, ref="G", alt="A", gene="BRCA1"),
                GermlineVariant(chrom="13", pos=32379913, ref="C", alt="T", gene="BRCA2")
            ]),
            candidate=TherapeuticCandidate(type="drug", moa="platinum_agent"),
            context=ClinicalContext(disease="ovarian")
        )
        
        response = await safety_service.compute_toxicity_risk(request)
        
        assert response.risk_score > 0.0
        assert any(f.type == "pathway" for f in response.factors)
        assert any("dna" in f.detail.lower() for f in response.factors if f.type == "pathway")
    
    @pytest.mark.asyncio
    async def test_toxicity_risk_confidence_calibration(self, safety_service):
        """Test confidence is calibrated conservatively for high risk."""
        request = ToxicityRiskRequest(
            patient=PatientContext(germlineVariants=[
                GermlineVariant(chrom="1", pos=97450058, ref="C", alt="T", gene="DPYD"),
                GermlineVariant(chrom="17", pos=43044295, ref="G", alt="A", gene="BRCA1")
            ]),
            candidate=TherapeuticCandidate(type="drug", moa="platinum_agent"),
            context=ClinicalContext(disease="ovarian")
        )
        
        response = await safety_service.compute_toxicity_risk(request)
        
        # High risk should have lower confidence (conservative)
        if response.risk_score > 0.5:
            assert response.confidence < 0.8
    
    @pytest.mark.asyncio
    async def test_off_target_preview_optimal_guide(self, safety_service):
        """Test off-target preview with optimal guide (GC 50%, no homopolymers)."""
        request = OffTargetPreviewRequest(
            guides=[GuideRNA(seq="AGCTGCTAGCTGCTAGCTGC", pam="NGG")]  # GC=50%, balanced
        )
        
        response = await safety_service.preview_off_targets(request)
        
        assert len(response.guides) == 1
        guide = response.guides[0]
        assert guide.gc_content == 0.5
        assert guide.heuristic_score > 0.6  # Should score well
        assert guide.risk_level in ["low", "medium"]
    
    @pytest.mark.asyncio
    async def test_off_target_preview_low_gc(self, safety_service):
        """Test off-target preview with low GC content."""
        request = OffTargetPreviewRequest(
            guides=[GuideRNA(seq="AAAATTTAAATTTAAATTAA", pam="NGG")]  # GC=0%
        )
        
        response = await safety_service.preview_off_targets(request)
        
        guide = response.guides[0]
        assert guide.gc_content < 0.3
        assert guide.heuristic_score < 0.5  # Should score poorly
        assert guide.risk_level in ["medium", "high"]
        assert any("low GC" in w.lower() for w in guide.warnings)
    
    @pytest.mark.asyncio
    async def test_off_target_preview_homopolymer(self, safety_service):
        """Test off-target preview detects homopolymer runs."""
        request = OffTargetPreviewRequest(
            guides=[GuideRNA(seq="AGCTGCAAAAAAAAGCTGCT", pam="NGG")]  # Has AAAAAAAA
        )
        
        response = await safety_service.preview_off_targets(request)
        
        guide = response.guides[0]
        assert guide.homopolymer is True
        assert guide.homopolymer_penalty < 1.0
        assert any("homopolymer" in w.lower() for w in guide.warnings)
    
    @pytest.mark.asyncio
    async def test_off_target_preview_multiple_guides(self, safety_service):
        """Test off-target preview with multiple guides."""
        request = OffTargetPreviewRequest(
            guides=[
                GuideRNA(seq="AGCTGCTAGCTGCTAGCTGC", pam="NGG"),  # Good
                GuideRNA(seq="AAAATTTAAATTTAAATTAA", pam="NGG"),  # Bad (low GC)
                GuideRNA(seq="GGGGCCCGGGGCCCGGGGCC", pam="NGG"),  # Bad (high GC)
            ]
        )
        
        response = await safety_service.preview_off_targets(request)
        
        assert len(response.guides) == 3
        assert response.summary["total_guides"] == 3
        assert "avg_heuristic_score" in response.summary
        # Should have mix of risk levels
        risk_levels = [g.risk_level for g in response.guides]
        assert len(set(risk_levels)) > 1  # Not all same risk level


# ============================================================================
# EDGE CASES AND ERROR HANDLING
# ============================================================================

class TestSafetyServiceEdgeCases:
    """Test edge cases and error handling."""
    
    @pytest.fixture
    def safety_service(self):
        return SafetyService()
    
    @pytest.mark.asyncio
    async def test_toxicity_risk_empty_moa(self, safety_service):
        """Test toxicity risk with no MoA specified."""
        request = ToxicityRiskRequest(
            patient=PatientContext(germlineVariants=[
                GermlineVariant(chrom="17", pos=43044295, ref="G", alt="A", gene="BRCA1")
            ]),
            candidate=TherapeuticCandidate(type="drug"),  # No MoA
            context=ClinicalContext(disease="breast")
        )
        
        response = await safety_service.compute_toxicity_risk(request)
        
        # Should still work, but no pathway factors
        assert response.risk_score >= 0.0
        assert not any(f.type == "pathway" for f in response.factors)
    
    @pytest.mark.asyncio
    async def test_off_target_preview_non_standard_length(self, safety_service):
        """Test off-target preview with non-standard guide length."""
        request = OffTargetPreviewRequest(
            guides=[GuideRNA(seq="AGCTGCTAGCTGCT", pam="NGG")]  # 14bp, not 20bp
        )
        
        response = await safety_service.preview_off_targets(request)
        
        guide = response.guides[0]
        assert any("Non-standard length" in w for w in guide.warnings)
    
    @pytest.mark.asyncio
    async def test_toxicity_provenance_tracking(self, safety_service):
        """Test provenance tracking is complete."""
        request = ToxicityRiskRequest(
            patient=PatientContext(germlineVariants=[]),
            candidate=TherapeuticCandidate(type="drug", moa="BRAF_inhibitor"),
            context=ClinicalContext(disease="melanoma"),
            options={"profile": "richer", "evidence": True}
        )
        
        response = await safety_service.compute_toxicity_risk(request)
        
        assert "run_id" in response.provenance
        assert response.provenance["profile"] == "richer"
        assert "methods" in response.provenance
        assert "timestamp" in response.provenance
        assert "germline_genes_analyzed" in response.provenance

Unit tests for safety service (toxicity risk + off-target preview).

Tests cover:
- Pharmacogene detection
- MoA → toxicity pathway overlap
- Off-target heuristic scoring
- Edge cases and error handling
"""

import pytest
from api.services.safety_service import SafetyService
from api.services.toxicity_pathway_mappings import (
    is_pharmacogene, get_pharmacogene_risk_weight,
    compute_pathway_overlap, get_moa_toxicity_weights
)
from api.schemas.safety import (
    ToxicityRiskRequest, PatientContext, GermlineVariant,
    TherapeuticCandidate, ClinicalContext,
    OffTargetPreviewRequest, GuideRNA
)


# ============================================================================
# TOXICITY PATHWAY MAPPINGS TESTS
# ============================================================================

class TestToxicityPathwayMappings:
    """Test toxicity pathway mapping utilities."""
    
    def test_is_pharmacogene_positive(self):
        """Test pharmacogene detection (positive cases)."""
        assert is_pharmacogene("DPYD") is True
        assert is_pharmacogene("CYP2D6") is True
        assert is_pharmacogene("UGT1A1") is True
        assert is_pharmacogene("TPMT") is True
        assert is_pharmacogene("G6PD") is True
    
    def test_is_pharmacogene_negative(self):
        """Test pharmacogene detection (negative cases)."""
        assert is_pharmacogene("BRAF") is False
        assert is_pharmacogene("TP53") is False
        assert is_pharmacogene("KRAS") is False
    
    def test_is_pharmacogene_case_insensitive(self):
        """Test pharmacogene detection is case-insensitive."""
        assert is_pharmacogene("dpyd") is True
        assert is_pharmacogene("Dpyd") is True
        assert is_pharmacogene("DPYD") is True
    
    def test_get_pharmacogene_risk_weight_high_impact(self):
        """Test risk weights for high-impact pharmacogenes."""
        assert get_pharmacogene_risk_weight("DPYD") == 0.4
        assert get_pharmacogene_risk_weight("TPMT") == 0.4
        assert get_pharmacogene_risk_weight("G6PD") == 0.4
    
    def test_get_pharmacogene_risk_weight_cyp(self):
        """Test risk weights for CYP enzymes."""
        assert get_pharmacogene_risk_weight("CYP2D6") == 0.3
        assert get_pharmacogene_risk_weight("CYP2C19") == 0.3
    
    def test_get_pharmacogene_risk_weight_other(self):
        """Test risk weights for other pharmacogenes."""
        assert get_pharmacogene_risk_weight("UGT1A1") == 0.4  # High impact
        assert get_pharmacogene_risk_weight("ABCB1") == 0.2  # Other
    
    def test_get_moa_toxicity_weights_braf(self):
        """Test MoA weights for BRAF inhibitor."""
        weights = get_moa_toxicity_weights("BRAF_inhibitor")
        assert "dna_repair" in weights
        assert weights["dna_repair"] == 0.3
        assert weights["inflammation"] == 0.2
    
    def test_get_moa_toxicity_weights_platinum(self):
        """Test MoA weights for platinum agents (high DNA damage)."""
        weights = get_moa_toxicity_weights("platinum_agent")
        assert weights["dna_repair"] == 0.9  # Very high
    
    def test_get_moa_toxicity_weights_unknown(self):
        """Test MoA weights for unknown drug (conservative baseline)."""
        weights = get_moa_toxicity_weights("unknown_drug")
        assert weights["dna_repair"] == 0.1
        assert weights["inflammation"] == 0.1
        assert weights["cardiometabolic"] == 0.1
    
    def test_compute_pathway_overlap_no_overlap(self):
        """Test pathway overlap with no germline hits."""
        patient_genes = ["BRAF", "KRAS"]  # Not in DNA repair pathways
        overlaps = compute_pathway_overlap(patient_genes, "platinum_agent")
        assert all(score == 0.0 for score in overlaps.values())
    
    def test_compute_pathway_overlap_with_hits(self):
        """Test pathway overlap with germline DNA repair hits."""
        patient_genes = ["BRCA1", "BRCA2", "ATM"]  # DNA repair genes
        overlaps = compute_pathway_overlap(patient_genes, "platinum_agent")
        assert overlaps["dna_repair"] > 0.5  # Should have significant overlap


# ============================================================================
# SAFETY SERVICE TESTS
# ============================================================================

class TestSafetyService:
    """Test SafetyService toxicity risk assessment."""
    
    @pytest.fixture
    def safety_service(self):
        """Create SafetyService instance."""
        return SafetyService()
    
    @pytest.mark.asyncio
    async def test_toxicity_risk_no_germline(self, safety_service):
        """Test toxicity risk with no germline variants."""
        request = ToxicityRiskRequest(
            patient=PatientContext(germlineVariants=[]),
            candidate=TherapeuticCandidate(type="drug", moa="BRAF_inhibitor"),
            context=ClinicalContext(disease="melanoma")
        )
        
        response = await safety_service.compute_toxicity_risk(request)
        
        assert response.risk_score >= 0.0
        assert response.risk_score <= 1.0
        assert response.confidence > 0.0
        assert len(response.factors) == 0  # No germline factors
        assert "run_id" in response.provenance
    
    @pytest.mark.asyncio
    async def test_toxicity_risk_with_pharmacogene(self, safety_service):
        """Test toxicity risk with pharmacogene variant."""
        request = ToxicityRiskRequest(
            patient=PatientContext(germlineVariants=[
                GermlineVariant(chrom="1", pos=97450058, ref="C", alt="T", gene="DPYD")
            ]),
            candidate=TherapeuticCandidate(type="drug", moa="platinum_agent"),
            context=ClinicalContext(disease="ovarian")
        )
        
        response = await safety_service.compute_toxicity_risk(request)
        
        assert response.risk_score > 0.3  # Should flag pharmacogene risk
        assert len(response.factors) >= 1
        assert any(f.type == "germline" for f in response.factors)
        assert "DPYD" in response.reason or any("DPYD" in f.detail for f in response.factors)
    
    @pytest.mark.asyncio
    async def test_toxicity_risk_pathway_overlap(self, safety_service):
        """Test toxicity risk with MoA pathway overlap."""
        request = ToxicityRiskRequest(
            patient=PatientContext(germlineVariants=[
                GermlineVariant(chrom="17", pos=43044295, ref="G", alt="A", gene="BRCA1"),
                GermlineVariant(chrom="13", pos=32379913, ref="C", alt="T", gene="BRCA2")
            ]),
            candidate=TherapeuticCandidate(type="drug", moa="platinum_agent"),
            context=ClinicalContext(disease="ovarian")
        )
        
        response = await safety_service.compute_toxicity_risk(request)
        
        assert response.risk_score > 0.0
        assert any(f.type == "pathway" for f in response.factors)
        assert any("dna" in f.detail.lower() for f in response.factors if f.type == "pathway")
    
    @pytest.mark.asyncio
    async def test_toxicity_risk_confidence_calibration(self, safety_service):
        """Test confidence is calibrated conservatively for high risk."""
        request = ToxicityRiskRequest(
            patient=PatientContext(germlineVariants=[
                GermlineVariant(chrom="1", pos=97450058, ref="C", alt="T", gene="DPYD"),
                GermlineVariant(chrom="17", pos=43044295, ref="G", alt="A", gene="BRCA1")
            ]),
            candidate=TherapeuticCandidate(type="drug", moa="platinum_agent"),
            context=ClinicalContext(disease="ovarian")
        )
        
        response = await safety_service.compute_toxicity_risk(request)
        
        # High risk should have lower confidence (conservative)
        if response.risk_score > 0.5:
            assert response.confidence < 0.8
    
    @pytest.mark.asyncio
    async def test_off_target_preview_optimal_guide(self, safety_service):
        """Test off-target preview with optimal guide (GC 50%, no homopolymers)."""
        request = OffTargetPreviewRequest(
            guides=[GuideRNA(seq="AGCTGCTAGCTGCTAGCTGC", pam="NGG")]  # GC=50%, balanced
        )
        
        response = await safety_service.preview_off_targets(request)
        
        assert len(response.guides) == 1
        guide = response.guides[0]
        assert guide.gc_content == 0.5
        assert guide.heuristic_score > 0.6  # Should score well
        assert guide.risk_level in ["low", "medium"]
    
    @pytest.mark.asyncio
    async def test_off_target_preview_low_gc(self, safety_service):
        """Test off-target preview with low GC content."""
        request = OffTargetPreviewRequest(
            guides=[GuideRNA(seq="AAAATTTAAATTTAAATTAA", pam="NGG")]  # GC=0%
        )
        
        response = await safety_service.preview_off_targets(request)
        
        guide = response.guides[0]
        assert guide.gc_content < 0.3
        assert guide.heuristic_score < 0.5  # Should score poorly
        assert guide.risk_level in ["medium", "high"]
        assert any("low GC" in w.lower() for w in guide.warnings)
    
    @pytest.mark.asyncio
    async def test_off_target_preview_homopolymer(self, safety_service):
        """Test off-target preview detects homopolymer runs."""
        request = OffTargetPreviewRequest(
            guides=[GuideRNA(seq="AGCTGCAAAAAAAAGCTGCT", pam="NGG")]  # Has AAAAAAAA
        )
        
        response = await safety_service.preview_off_targets(request)
        
        guide = response.guides[0]
        assert guide.homopolymer is True
        assert guide.homopolymer_penalty < 1.0
        assert any("homopolymer" in w.lower() for w in guide.warnings)
    
    @pytest.mark.asyncio
    async def test_off_target_preview_multiple_guides(self, safety_service):
        """Test off-target preview with multiple guides."""
        request = OffTargetPreviewRequest(
            guides=[
                GuideRNA(seq="AGCTGCTAGCTGCTAGCTGC", pam="NGG"),  # Good
                GuideRNA(seq="AAAATTTAAATTTAAATTAA", pam="NGG"),  # Bad (low GC)
                GuideRNA(seq="GGGGCCCGGGGCCCGGGGCC", pam="NGG"),  # Bad (high GC)
            ]
        )
        
        response = await safety_service.preview_off_targets(request)
        
        assert len(response.guides) == 3
        assert response.summary["total_guides"] == 3
        assert "avg_heuristic_score" in response.summary
        # Should have mix of risk levels
        risk_levels = [g.risk_level for g in response.guides]
        assert len(set(risk_levels)) > 1  # Not all same risk level


# ============================================================================
# EDGE CASES AND ERROR HANDLING
# ============================================================================

class TestSafetyServiceEdgeCases:
    """Test edge cases and error handling."""
    
    @pytest.fixture
    def safety_service(self):
        return SafetyService()
    
    @pytest.mark.asyncio
    async def test_toxicity_risk_empty_moa(self, safety_service):
        """Test toxicity risk with no MoA specified."""
        request = ToxicityRiskRequest(
            patient=PatientContext(germlineVariants=[
                GermlineVariant(chrom="17", pos=43044295, ref="G", alt="A", gene="BRCA1")
            ]),
            candidate=TherapeuticCandidate(type="drug"),  # No MoA
            context=ClinicalContext(disease="breast")
        )
        
        response = await safety_service.compute_toxicity_risk(request)
        
        # Should still work, but no pathway factors
        assert response.risk_score >= 0.0
        assert not any(f.type == "pathway" for f in response.factors)
    
    @pytest.mark.asyncio
    async def test_off_target_preview_non_standard_length(self, safety_service):
        """Test off-target preview with non-standard guide length."""
        request = OffTargetPreviewRequest(
            guides=[GuideRNA(seq="AGCTGCTAGCTGCT", pam="NGG")]  # 14bp, not 20bp
        )
        
        response = await safety_service.preview_off_targets(request)
        
        guide = response.guides[0]
        assert any("Non-standard length" in w for w in guide.warnings)
    
    @pytest.mark.asyncio
    async def test_toxicity_provenance_tracking(self, safety_service):
        """Test provenance tracking is complete."""
        request = ToxicityRiskRequest(
            patient=PatientContext(germlineVariants=[]),
            candidate=TherapeuticCandidate(type="drug", moa="BRAF_inhibitor"),
            context=ClinicalContext(disease="melanoma"),
            options={"profile": "richer", "evidence": True}
        )
        
        response = await safety_service.compute_toxicity_risk(request)
        
        assert "run_id" in response.provenance
        assert response.provenance["profile"] == "richer"
        assert "methods" in response.provenance
        assert "timestamp" in response.provenance
        assert "germline_genes_analyzed" in response.provenance

















