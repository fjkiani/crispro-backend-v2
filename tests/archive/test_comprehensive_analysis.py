"""
Test script for MOAT Comprehensive Analysis generation.

Tests the complete pipeline with AK profile data.
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / "oncology-coPilot" / "oncology-backend-minimal"))

from api.services.comprehensive_analysis.moat_analysis_generator import get_moat_analysis_generator


async def test_ak_analysis():
    """Test comprehensive analysis generation for AK profile."""
    
    print("=" * 80)
    print("🧪 TESTING MOAT COMPREHENSIVE ANALYSIS GENERATION")
    print("=" * 80)
    print()
    
    generator = get_moat_analysis_generator()
    
    # AK profile data
    patient_profile = {
        "demographics": {
            "name": "AK",
            "patient_id": "AK001",
            "age": 40,
            "sex": "F"
        },
        "disease": {
            "name": "ovarian_cancer_hgs",
            "stage": "Advanced (carcinomatosis, bilateral pleural effusions, nodal mets)"
        },
        "germline_variants": [
            {
                "gene": "MBD4",
                "hgvs_p": "p.K431Nfs*54",
                "hgvs_c": "c.1293delA",
                "zygosity": "homozygous",
                "classification": "pathogenic",
                "source": "germline"
            }
        ],
        "somatic_variants": [
            {
                "gene": "TP53",
                "classification": "pathogenic",
                "source": "somatic"
            }
        ],
        "biomarkers": {
            "HRD": "NEGATIVE",
            "MBD4": "DEFICIENT"
        }
    }
    
    treatment_context = {
        "current_drugs": ["carboplatin", "paclitaxel"],
        "treatment_line": "first-line",
        "cycle_number": 2,
        "treatment_goal": "pre-cycle-2",
        "status": "About to start SECOND CYCLE"
    }
    
    print("📋 Patient Profile:")
    print(f"   Name: {patient_profile['demographics']['name']}")
    print(f"   Diagnosis: {patient_profile['disease']['name']}")
    print(f"   Critical Finding: MBD4 homozygous")
    print()
    
    print("💊 Treatment Context:")
    print(f"   Drugs: {', '.join(treatment_context['current_drugs'])}")
    print(f"   Line: {treatment_context['treatment_line']}")
    print(f"   Cycle: {treatment_context['cycle_number']}")
    print()
    
    print("🔄 Generating comprehensive analysis...")
    print("   (This may take 30-60 seconds with LLM, or 5-10 seconds without)")
    print()
    
    try:
        # Test without LLM first (faster)
        print("   [1/2] Testing without LLM...")
        result_no_llm = await generator.generate_comprehensive_analysis(
            patient_profile=patient_profile,
            treatment_context=treatment_context,
            use_llm=False
        )
        
        print(f"   ✅ Generated analysis ID: {result_no_llm['analysis_id']}")
        print(f"   📄 Markdown length: {len(result_no_llm['markdown']):,} characters")
        print(f"   📊 Sections: {', '.join(result_no_llm['sections'].keys())}")
        print()
        
        # Check sections
        genomic = result_no_llm['sections'].get('genomic_findings', {})
        critical_findings = genomic.get('critical_findings', [])
        print(f"   🧬 Critical Findings: {len(critical_findings)}")
        for finding in critical_findings:
            print(f"      - {finding.get('gene', '')} ({finding.get('zygosity', '')})")
        print()
        
        toxicity = result_no_llm['sections'].get('toxicity_assessment', {})
        drug_explanations = toxicity.get('drug_explanations', [])
        print(f"   💊 Drug Explanations: {len(drug_explanations)}")
        for drug in drug_explanations:
            print(f"      - {drug.get('drug_name', '').upper()}: {drug.get('moa', '')}")
        print()
        
        nutrition = result_no_llm['sections'].get('nutrition_protocol', {})
        supplements = nutrition.get('supplements', [])
        print(f"   🥗 Supplements: {len(supplements)}")
        for supp in supplements[:5]:
            print(f"      - {supp.get('compound', '')}: {supp.get('score', 0):.2f}")
        print()
        
        # Save to file
        output_file = Path(".cursor/ayesha/analysis/test_moat_analysis.md")
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(result_no_llm['markdown'])
        
        print(f"   💾 Saved to: {output_file}")
        print()
        
        # Test with LLM if available
        print("   [2/2] Testing with LLM enhancement...")
        try:
            result_with_llm = await generator.generate_comprehensive_analysis(
                patient_profile=patient_profile,
                treatment_context=treatment_context,
                use_llm=True
            )
            
            # Check if LLM enhanced anything
            enhanced_count = 0
            for finding in result_with_llm['sections'].get('genomic_findings', {}).get('critical_findings', []):
                if finding.get('llm_enhanced_explanation'):
                    enhanced_count += 1
            
            print(f"   ✅ LLM-enhanced analysis generated")
            print(f"   🎨 LLM enhancements: {enhanced_count} genomic findings")
            print()
            
            # Save LLM version
            output_file_llm = Path(".cursor/ayesha/analysis/test_moat_analysis_llm.md")
            output_file_llm.write_text(result_with_llm['markdown'])
            print(f"   💾 Saved LLM version to: {output_file_llm}")
            
        except Exception as e:
            print(f"   ⚠️ LLM enhancement failed (this is okay if LLM not configured): {e}")
            print()
        
        print("=" * 80)
        print("✅ TEST COMPLETE")
        print("=" * 80)
        print()
        print("📝 Next Steps:")
        print("   1. Review generated analysis in: .cursor/ayesha/analysis/test_moat_analysis.md")
        print("   2. Compare structure to: .cursor/ayesha/analysis/AK_CYCLE_2_MOAT_ANALYSIS.md")
        print("   3. Test API endpoint: POST /api/dossiers/intelligence/comprehensive-analysis")
        print()
        
        return result_no_llm
    
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    asyncio.run(test_ak_analysis())













