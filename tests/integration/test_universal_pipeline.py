"""
Test Universal Pipeline

Validates that universal pipeline produces same results as Ayesha pipeline
when given Ayesha profile, and works with different patient profiles.
"""
import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from api.services.trial_intelligence_universal.pipeline import TrialIntelligencePipeline
from api.services.trial_intelligence.pipeline import TrialIntelligencePipeline as AyeshaPipeline
from api.services.trial_intelligence_universal.profile_adapter import adapt_simple_to_full_profile, is_simple_profile
import ayesha_patient_profile


async def test_universal_matches_ayesha():
    """Test that universal pipeline produces same results as Ayesha pipeline."""
    print("🧪 Testing: Universal pipeline matches Ayesha pipeline\n")
    
    # Load Ayesha profile
    ayesha = ayesha_patient_profile.get_ayesha_complete_profile()
    
    # Create test trials (simplified for testing)
    test_trials = [
        {
            'nct_id': 'NCT12345678',
            'title': 'Test Ovarian Cancer Trial',
            'status': 'RECRUITING',
            'disease_category': 'ovarian cancer',
            'description_text': 'A trial for ovarian cancer patients',
            'eligibility_text': 'Stage IV ovarian cancer, first-line treatment',
            'locations_data': [
                {'facility': 'Mount Sinai', 'city': 'New York', 'state': 'NY', 'country': 'United States'}
            ]
        }
    ]
    
    # Run Ayesha pipeline
    print("Running Ayesha pipeline...")
    ayesha_pipeline = AyeshaPipeline(ayesha, use_llm=False, verbose=False)
    ayesha_results = await ayesha_pipeline.execute(test_trials)
    
    # Run universal pipeline
    print("Running universal pipeline...")
    universal_pipeline = TrialIntelligencePipeline(ayesha, use_llm=False, verbose=False)
    universal_results = await universal_pipeline.execute(test_trials)
    
    # Compare results
    print(f"\n📊 Results Comparison:")
    print(f"   Ayesha - Top Tier: {len(ayesha_results['top_tier'])}, Good Tier: {len(ayesha_results['good_tier'])}")
    print(f"   Universal - Top Tier: {len(universal_results['top_tier'])}, Good Tier: {len(universal_results['good_tier'])}")
    
    # Basic validation
    assert len(ayesha_results['top_tier']) == len(universal_results['top_tier']), "Top tier counts don't match"
    assert len(ayesha_results['good_tier']) == len(universal_results['good_tier']), "Good tier counts don't match"
    
    print("✅ Universal pipeline matches Ayesha pipeline!\n")


async def test_profile_adapter():
    """Test profile adapter converts simple to full profile."""
    print("🧪 Testing: Profile adapter\n")
    
    simple_profile = {
        'patient_id': 'test_001',
        'disease': 'ovarian cancer',
        'treatment_line': 'first-line',
        'location': 'NYC',
        'biomarkers': {'her2_status': 'UNKNOWN'},
        'zip_code': '10029',
        'age': 45,
        'sex': 'F',
        'stage': 'IVB'
    }
    
    full_profile = adapt_simple_to_full_profile(simple_profile)
    
    # Validate structure
    assert 'demographics' in full_profile
    assert 'disease' in full_profile
    assert 'treatment' in full_profile
    assert 'biomarkers' in full_profile
    assert full_profile['demographics']['patient_id'] == 'test_001'
    assert full_profile['disease']['primary_diagnosis'] == 'ovarian cancer'
    
    print("✅ Profile adapter works correctly!\n")


async def test_different_patient():
    """Test universal pipeline with different patient profile."""
    print("🧪 Testing: Universal pipeline with different patient\n")
    
    # Create different patient (breast cancer, California)
    different_patient = {
        'demographics': {
            'patient_id': 'patient_002',
            'name': 'Test Patient',
            'age': 55,
            'sex': 'F',
            'location': 'Los Angeles'
        },
        'disease': {
            'primary_diagnosis': 'Breast Cancer',
            'stage': 'III',
            'figo_stage': 'III',
            'tumor_burden': 'MODERATE',
            'performance_status': 1
        },
        'treatment': {
            'line': 'first-line',
            'line_number': 1,
            'status': 'treatment_naive',
            'prior_therapies': []
        },
        'biomarkers': {
            'her2_status': 'POSITIVE',
            'hrd_status': 'UNKNOWN',
            'germline_status': 'NEGATIVE'
        },
        'eligibility': {
            'age_eligible': True,
            'performance_status': 'ECOG 0-2',
            'organ_function': {
                'hepatic': 'normal',
                'renal': 'normal',
                'cardiac': 'normal',
                'pulmonary': 'normal'
            },
            'exclusions': {
                'bowel_obstruction': False,
                'active_infection': False,
                'brain_metastases': False,
                'other_malignancy': False
            }
        },
        'logistics': {
            'location': 'Los Angeles',
            'zip_code': '90024',
            'home_zip': '90024',
            'travel_radius_miles': 50,
            'willing_to_travel': True
        },
        'labs': {},
        'screening': {
            'recist_measurable_disease': True,
            'target_lesions_present': True
        },
        'critical_gates': {},
        'probability_estimates': {}
    }
    
    test_trials = [
        {
            'nct_id': 'NCT87654321',
            'title': 'Test Breast Cancer Trial',
            'status': 'RECRUITING',
            'disease_category': 'breast cancer',
            'description_text': 'A trial for breast cancer patients',
            'eligibility_text': 'Stage III breast cancer, HER2 positive',
            'locations_data': [
                {'facility': 'UCLA Medical Center', 'city': 'Los Angeles', 'state': 'CA', 'country': 'United States'}
            ]
        }
    ]
    
    # Run universal pipeline
    universal_pipeline = TrialIntelligencePipeline(different_patient, use_llm=False, verbose=False)
    results = await universal_pipeline.execute(test_trials)
    
    print(f"📊 Results for different patient:")
    print(f"   Top Tier: {len(results['top_tier'])}, Good Tier: {len(results['good_tier'])}")
    
    # Should process without errors
    assert results is not None
    print("✅ Universal pipeline works with different patient!\n")


async def main():
    """Run all tests."""
    print("=" * 60)
    print("🧪 UNIVERSAL PIPELINE TESTS")
    print("=" * 60 + "\n")
    
    try:
        await test_profile_adapter()
        await test_universal_matches_ayesha()
        await test_different_patient()
        
        print("=" * 60)
        print("✅ ALL TESTS PASSED")
        print("=" * 60)
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())


