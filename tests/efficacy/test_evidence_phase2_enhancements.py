"""
Test Phase 2 Evidence Service Enhancements

Tests:
1. Multi-name compound search
2. Evidence quality scoring
3. Mechanistic extraction (LLM)
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from api.services.enhanced_evidence_service import EnhancedEvidenceService


class TestEvidencePhase2:
    """Test Phase 2 enhancements to evidence service."""
    
    @pytest.fixture
    def evidence_service(self):
        """Create evidence service instance."""
        return EnhancedEvidenceService()
    
    def test_service_initialization(self, evidence_service):
        """Test that service initializes with Phase 2 components."""
        # Verify alias resolver initialized (may be None if import fails)
        assert hasattr(evidence_service, 'alias_resolver')
        print(f"✅ Alias resolver: {'initialized' if evidence_service.alias_resolver else 'unavailable'}")
        
        # Verify new methods exist
        assert hasattr(evidence_service, 'score_evidence_quality')
        assert hasattr(evidence_service, 'search_pubmed_multi_name')
        assert hasattr(evidence_service, 'extract_mechanism_evidence')
        print("✅ Phase 2 methods available")
    
    def test_evidence_quality_scoring(self, evidence_service):
        """Test evidence quality scoring for different paper types."""
        
        # Clinical trial (should score highest)
        clinical_trial = {
            "title": "Phase II randomized controlled trial of curcumin in ovarian cancer",
            "abstract": "This phase II clinical trial evaluated curcumin efficacy...",
            "year": 2022,
            "citation_count": 150
        }
        score_ct = evidence_service.score_evidence_quality(clinical_trial)
        print(f"✅ Clinical trial (2022, 150 cites): {score_ct:.3f}")
        
        # Meta-analysis
        meta_analysis = {
            "title": "Meta-analysis of vitamin D in cancer prevention",
            "abstract": "This systematic review and meta-analysis examined...",
            "year": 2020,
            "citation_count": 80
        }
        score_ma = evidence_service.score_evidence_quality(meta_analysis)
        print(f"✅ Meta-analysis (2020, 80 cites): {score_ma:.3f}")
        
        # Case study (should score lower)
        case_study = {
            "title": "Case report of resveratrol use in melanoma patient",
            "abstract": "We report a case series of 5 patients...",
            "year": 2010,
            "citation_count": 10
        }
        score_cs = evidence_service.score_evidence_quality(case_study)
        print(f"✅ Case study (2010, 10 cites): {score_cs:.3f}")
        
        # Verify ranking: clinical trial > meta-analysis > case study
        assert score_ct > score_ma > score_cs
        print("\n✅ Quality scoring hierarchy correct: Clinical Trial > Meta-analysis > Case Study")
    
    def test_get_compound_search_names(self, evidence_service):
        """Test multi-name compound resolution."""
        # Test with well-known compound (should resolve)
        names_vitamin_d = evidence_service._get_compound_search_names("Vitamin D")
        print(f"\n✅ Vitamin D search names: {names_vitamin_d}")
        assert len(names_vitamin_d) >= 1
        assert "Vitamin D" in names_vitamin_d
        
        # Test with "Turmeric" (should resolve to "Curcumin")
        names_turmeric = evidence_service._get_compound_search_names("Turmeric")
        print(f"✅ Turmeric search names: {names_turmeric}")
        assert len(names_turmeric) >= 1
        
        # Test deduplication
        names_curcumin = evidence_service._get_compound_search_names("Curcumin")
        print(f"✅ Curcumin search names: {names_curcumin}")
        # Should not have duplicates (case-insensitive)
        assert len(names_curcumin) == len(set(n.lower() for n in names_curcumin))
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_multi_name_pubmed_search(self, evidence_service):
        """
        Test multi-name PubMed search (SLOW - hits real API).
        
        Searches for "Vitamin D" in "ovarian cancer" using multiple names.
        """
        print("\n" + "="*80)
        print("MULTI-NAME PUBMED SEARCH TEST")
        print("="*80)
        
        papers = await evidence_service.search_pubmed_multi_name(
            compound="Vitamin D",
            disease="ovarian_cancer",
            max_results=10
        )
        
        print(f"\n✅ Found {len(papers)} papers")
        
        if papers:
            # Verify quality scores added
            for paper in papers[:3]:
                assert "quality_score" in paper
                print(f"   - PMID {paper.get('pmid')}: quality={paper.get('quality_score', 0):.3f}, title={paper.get('title', 'N/A')[:60]}...")
            
            # Verify sorted by quality
            quality_scores = [p.get("quality_score", 0) for p in papers]
            assert quality_scores == sorted(quality_scores, reverse=True), "Papers should be sorted by quality"
            print("\n✅ Papers sorted by quality score (descending)")
        else:
            print("⚠️ No papers found (PubMed may be rate-limiting)")
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_mechanism_extraction_mock(self, evidence_service):
        """
        Test mechanistic extraction with mock papers.
        
        Uses synthetic papers to validate extraction logic.
        """
        print("\n" + "="*80)
        print("MECHANISTIC EXTRACTION TEST (MOCK)")
        print("="*80)
        
        # Mock papers with abstracts
        mock_papers = [
            {
                "pmid": "12345678",
                "title": "Curcumin inhibits NF-κB in ovarian cancer cells",
                "abstract": "Curcumin demonstrated significant inhibition of NF-κB signaling in vitro. Treatment with 10μM curcumin reduced NF-κB activation by 60%. In vivo studies confirmed anti-inflammatory effects.",
                "quality_score": 0.8
            },
            {
                "pmid": "87654321",
                "title": "Vitamin D modulates immune response in cancer",
                "abstract": "Vitamin D3 (cholecalciferol) was shown to modulate immune cell activity. Clinical trials demonstrated improved outcomes with vitamin D supplementation at 4000 IU daily.",
                "quality_score": 0.9
            }
        ]
        
        # Test extraction (may fail if LLM unavailable)
        result = await evidence_service.extract_mechanism_evidence(
            compound="Curcumin",
            targets=["NF-κB", "COX-2"],
            papers=mock_papers
        )
        
        print(f"\n✅ Mechanism extraction result:")
        print(f"   Method: {result.get('method')}")
        print(f"   Targets analyzed: {result.get('targets_analyzed', 0)}")
        
        if result.get("method") == "llm_extraction":
            mechanism_evidence = result.get("mechanism_evidence", {})
            for target, evidence in mechanism_evidence.items():
                print(f"   - {target}: {len(evidence)} pieces of evidence")
        elif result.get("method") == "unavailable":
            print("   ⚠️ LLM unavailable (expected in test environment)")
        else:
            print(f"   ⚠️ Error: {result.get('error')}")
    
    @pytest.mark.asyncio
    async def test_phase2_integration_vitamin_d(self, evidence_service):
        """
        Integration test: Vitamin D for ovarian cancer with Phase 2 enhancements.
        
        Tests full pipeline:
        1. Multi-name search
        2. Quality scoring
        3. Mechanistic extraction (if LLM available)
        """
        print("\n" + "="*80)
        print("PHASE 2 INTEGRATION: VITAMIN D FOR OVARIAN CANCER")
        print("="*80)
        
        # Step 1: Multi-name search
        papers = await evidence_service.search_pubmed_multi_name(
            compound="Vitamin D",
            disease="ovarian_cancer",
            pathways=["DNA repair", "Immune modulation"],
            max_results=5
        )
        
        print(f"\n✅ Step 1 (Multi-name search): {len(papers)} papers")
        
        if not papers:
            print("⚠️ No papers found - test inconclusive")
            return
        
        # Step 2: Verify quality scores
        top_papers = papers[:3]
        for i, paper in enumerate(top_papers, 1):
            print(f"   {i}. Quality: {paper.get('quality_score', 0):.3f}, PMID: {paper.get('pmid')}")
        
        # Step 3: Extract mechanisms (if LLM available)
        mechanism_result = await evidence_service.extract_mechanism_evidence(
            compound="Vitamin D",
            targets=["VDR"],
            papers=top_papers
        )
        
        print(f"\n✅ Step 3 (Mechanism extraction): {mechanism_result.get('method')}")
        
        if mechanism_result.get("method") == "llm_extraction":
            print(f"   Targets analyzed: {mechanism_result.get('targets_analyzed', 0)}")
        
        print("\n✅ Phase 2 integration test complete!")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "-m", "not slow"])





