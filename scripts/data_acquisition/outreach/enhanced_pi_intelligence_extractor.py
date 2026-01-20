#!/usr/bin/env python3
"""
Enhanced PI Intelligence Extractor
Uses ALL our capabilities to extract maximum intelligence for personalized outreach
"""

import json
import requests
from pathlib import Path
from datetime import datetime
import time
import sys

# Add pubmearch to path
base_path = Path('/Users/fahadkiani/Desktop/development/crispr-assistant-main')
pubmearch_path = base_path / '.github' / 'frameworks' / 'pubmearch-main'
if pubmearch_path.exists() and str(pubmearch_path) not in sys.path:
    sys.path.insert(0, str(pubmearch_path))

output_dir = Path('/Users/fahadkiani/Desktop/development/crispr-assistant-main/oncology-coPilot/oncology-backend-minimal/data/kelim_resurrection/s4_deliverables')

print("=" * 80)
print("Enhanced PI Intelligence Extraction")
print("Using ALL Capabilities for Maximum Personalization")
print("=" * 80)

# Load PI contacts
with open(output_dir / 'ctgov_pi_contacts.json', 'r') as f:
    pi_data = json.load(f)

pi_contacts = pi_data.get('pi_contacts', [])

print(f"\n📋 Processing {len(pi_contacts)} PIs with enhanced intelligence extraction...")

enhanced_profiles = []

for i, contact in enumerate(pi_contacts[:15], 1):
    pi_name = contact.get('pi_name', '')
    nct_id = contact.get('nct_id', '')
    institution = contact.get('pi_institution', '')
    
    print(f"\n[{i}/15] 🔍 Deep Intelligence: {pi_name}")
    print(f"   Institution: {institution}")
    
    profile = {
        'pi_name': pi_name,
        'institution': institution,
        'nct_id': nct_id,
        'extraction_date': datetime.now().isoformat(),
        'trial_intelligence': {},
        'research_intelligence': {},
        'biomarker_intelligence': {},
        'collaboration_intelligence': {},
        'personalized_insights': {},
        'targeted_value_prop': '',
        'personalized_email': ''
    }
    
    # ============================================================
    # 1. TRIAL INTELLIGENCE (ClinicalTrials.gov API)
    # ============================================================
    print(f"   📊 Extracting trial intelligence...")
    try:
        trial_url = f"https://clinicaltrials.gov/api/v2/studies/{nct_id}"
        resp = requests.get(trial_url, params={'format': 'json'}, timeout=20)
        
        if resp.status_code == 200:
            trial = resp.json()
            protocol = trial.get('protocolSection', {})
            
            # Extract comprehensive trial data
            ident = protocol.get('identificationModule', {})
            design = protocol.get('designModule', {})
            arms = protocol.get('armsInterventionsModule', {})
            conditions = protocol.get('conditionsModule', {})
            eligibility = protocol.get('eligibilityModule', {})
            outcomes = protocol.get('outcomesModule', {})
            status = protocol.get('statusModule', {})
            contacts = protocol.get('contactsLocationsModule', {})
            
            profile['trial_intelligence'] = {
                'title': ident.get('briefTitle', ''),
                'official_title': ident.get('officialTitle', ''),
                'phase': design.get('phases', []),
                'study_type': design.get('studyType', ''),
                'allocation': design.get('allocation', ''),
                'intervention_model': design.get('interventionModel', ''),
                'primary_purpose': design.get('primaryPurpose', ''),
                'enrollment': design.get('enrollment', {}),
                'enrollment_count': design.get('enrollment', {}).get('value', 0),
                'interventions': [i.get('name', '') for i in arms.get('interventions', [])],
                'intervention_types': [i.get('type', '') for i in arms.get('interventions', [])],
                'conditions': conditions.get('conditions', []),
                'eligibility_criteria': eligibility.get('eligibilityCriteria', ''),
                'inclusion_criteria': eligibility.get('eligibilityCriteria', '').split('Exclusion Criteria')[0] if 'Exclusion Criteria' in eligibility.get('eligibilityCriteria', '') else '',
                'exclusion_criteria': eligibility.get('eligibilityCriteria', '').split('Exclusion Criteria')[1] if 'Exclusion Criteria' in eligibility.get('eligibilityCriteria', '') else '',
                'primary_outcomes': [o.get('measure', '') for o in outcomes.get('primaryOutcomeMeasures', [])],
                'secondary_outcomes': [o.get('measure', '') for o in outcomes.get('secondaryOutcomeMeasures', [])],
                'status': status.get('overallStatus', ''),
                'start_date': status.get('startDateStruct', {}).get('date', ''),
                'completion_date': status.get('completionDateStruct', {}).get('date', ''),
                'sponsors': [s.get('name', '') for s in protocol.get('sponsorCollaboratorsModule', {}).get('leadSponsor', {}).get('name', '')] if protocol.get('sponsorCollaboratorsModule', {}).get('leadSponsor') else [],
                'collaborators': [c.get('name', '') for c in protocol.get('sponsorCollaboratorsModule', {}).get('collaborators', [])]
            }
            
            print(f"      ✅ Trial: {profile['trial_intelligence']['title'][:50]}...")
            print(f"      Phase: {profile['trial_intelligence']['phase']}")
            print(f"      Enrollment: {profile['trial_intelligence']['enrollment_count']}")
            print(f"      Interventions: {', '.join(profile['trial_intelligence']['interventions'][:2])}")
            
    except Exception as e:
        print(f"      ⚠️  Error: {e}")
    
    # ============================================================
    # 2. RESEARCH INTELLIGENCE (PubMed API)
    # ============================================================
    print(f"   📚 Extracting research intelligence...")
    try:
        # Extract name parts for search
        name_parts = pi_name.split(',')
        if len(name_parts) >= 2:
            last_name = name_parts[0].strip()
            first_part = name_parts[1].strip().split()[0] if name_parts[1].strip() else ''
            first_initial = first_part[0] if first_part else ''
            search_name = f"{last_name} {first_initial}[Author]"
        else:
            name_words = pi_name.split()
            if len(name_words) >= 2:
                last_name = name_words[-1]
                first_initial = name_words[0][0]
                search_name = f"{last_name} {first_initial}[Author]"
            else:
                search_name = f'"{pi_name}"[Author]'
        
        # Search for publications
        search_queries = [
            f'{search_name} AND (ovarian[Title/Abstract] OR "ovarian cancer"[Title/Abstract])',
            f'{search_name} AND ("CA-125"[Title/Abstract] OR "CA125"[Title/Abstract] OR "cancer antigen 125"[Title/Abstract])',
            f'{search_name} AND (platinum[Title/Abstract] OR "platinum resistance"[Title/Abstract])',
            f'{search_name} AND (biomarker[Title/Abstract] OR "predictive marker"[Title/Abstract])'
        ]
        
        all_pmids = set()
        publications = []
        
        for query in search_queries:
            try:
                search_url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term={query}&retmax=10&retmode=json"
                resp = requests.get(search_url, timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    pmids = data.get('esearchresult', {}).get('idlist', [])
                    all_pmids.update(pmids)
            except:
                pass
        
        # Get details for publications
        if all_pmids:
            pmids_list = list(all_pmids)[:10]  # Top 10
            fetch_url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=pubmed&id={','.join(pmids_list)}&retmode=json"
            resp = requests.get(fetch_url, timeout=15)
            
            if resp.status_code == 200:
                pub_data = resp.json()
                results = pub_data.get('result', {})
                
                for pmid in pmids_list:
                    if pmid in results:
                        result = results[pmid]
                        pub_info = {
                            'pmid': pmid,
                            'title': result.get('title', ''),
                            'journal': result.get('source', ''),
                            'year': result.get('pubdate', '').split()[0] if result.get('pubdate') else '',
                            'authors': result.get('authors', []),
                            'doi': result.get('elocationid', '')
                        }
                        publications.append(pub_info)
            
            print(f"      ✅ Found {len(publications)} publications")
            
            # Analyze research focus
            research_keywords = []
            research_focus = []
            
            for pub in publications:
                title_lower = pub.get('title', '').lower()
                if 'resistance' in title_lower or 'resistant' in title_lower:
                    research_focus.append('Platinum resistance research')
                if 'biomarker' in title_lower or 'marker' in title_lower:
                    research_focus.append('Biomarker development')
                if 'ca-125' in title_lower or 'ca125' in title_lower:
                    research_focus.append('CA-125 research')
                if 'predict' in title_lower or 'prediction' in title_lower:
                    research_focus.append('Predictive modeling')
                if 'survival' in title_lower or 'outcome' in title_lower:
                    research_focus.append('Outcome research')
            
            profile['research_intelligence'] = {
                'publication_count': len(publications),
                'publications': publications[:5],  # Top 5
                'research_focus': list(set(research_focus)),
                'recent_publications': [p for p in publications if p.get('year', '').isdigit() and int(p.get('year', '0')) >= 2020],
                'expertise_areas': list(set(research_focus))
            }
            
            if research_focus:
                print(f"      Research focus: {', '.join(list(set(research_focus))[:3])}")
    
    except Exception as e:
        print(f"      ⚠️  Error: {e}")
    
    # ============================================================
    # 3. BIOMARKER INTELLIGENCE (Trial Analysis)
    # ============================================================
    print(f"   🧬 Analyzing biomarker intelligence...")
    
    trial_intel = profile.get('trial_intelligence', {})
    interventions = trial_intel.get('interventions', [])
    outcomes = trial_intel.get('primary_outcomes', []) + trial_intel.get('secondary_outcomes', [])
    title = trial_intel.get('title', '').lower()
    eligibility = trial_intel.get('eligibility_criteria', '').lower()
    
    biomarker_insights = {
        'uses_platinum': any('platinum' in str(i).lower() or 'carboplatin' in str(i).lower() or 'cisplatin' in str(i).lower() for i in interventions),
        'monitors_ca125': any('ca-125' in str(o).lower() or 'ca125' in str(o).lower() or 'cancer antigen 125' in str(o).lower() for o in outcomes) or 'ca-125' in title or 'ca125' in title,
        'focuses_resistance': 'resistance' in title or 'resistant' in title or 'resistance' in eligibility,
        'biomarker_trial': 'biomarker' in title or 'marker' in title or 'predict' in title,
        'outcome_focus': any('survival' in str(o).lower() or 'pfs' in str(o).lower() or 'os' in str(o).lower() or 'response' in str(o).lower() for o in outcomes),
        'recurrent_disease': 'recurrent' in title or 'relapsed' in title or 'recurrent' in eligibility,
        'first_line': 'first-line' in title or 'primary' in title or 'first line' in eligibility
    }
    
    profile['biomarker_intelligence'] = biomarker_insights
    
    kelim_fit_reasons = []
    if biomarker_insights['uses_platinum']:
        kelim_fit_reasons.append("Uses platinum-based therapy (KELIM's target)")
    if biomarker_insights['monitors_ca125']:
        kelim_fit_reasons.append("Monitors CA-125 as outcome (KELIM's input)")
    if biomarker_insights['focuses_resistance']:
        kelim_fit_reasons.append("Focuses on resistance (KELIM's prediction)")
    if biomarker_insights['recurrent_disease']:
        kelim_fit_reasons.append("Recurrent disease (KELIM predicts resistance in this population)")
    if biomarker_insights['first_line']:
        kelim_fit_reasons.append("First-line treatment (KELIM can guide initial therapy)")
    
    profile['kelim_fit'] = {
        'fit_score': len(kelim_fit_reasons),
        'fit_reasons': kelim_fit_reasons,
        'is_high_fit': len(kelim_fit_reasons) >= 2
    }
    
    if kelim_fit_reasons:
        print(f"      ✅ KELIM fit: {len(kelim_fit_reasons)} reasons")
        print(f"      Reasons: {', '.join(kelim_fit_reasons[:2])}")
    
    # ============================================================
    # 4. UNDERSTAND WHAT THEY'RE TRYING TO DO
    # ============================================================
    print(f"   🎯 Understanding their goals...")
    
    research_focus = profile.get('research_intelligence', {}).get('research_focus', [])
    trial_title = trial_intel.get('title', '').lower()
    
    what_they_do = []
    
    # From research focus
    if 'Platinum resistance research' in research_focus:
        what_they_do.append("Studying platinum resistance mechanisms and predictors")
    if 'Biomarker development' in research_focus:
        what_they_do.append("Developing predictive biomarkers for treatment response")
    if 'CA-125 research' in research_focus:
        what_they_do.append("Researching CA-125 as a biomarker")
    if 'Predictive modeling' in research_focus:
        what_they_do.append("Building predictive models for treatment outcomes")
    if 'Outcome research' in research_focus:
        what_they_do.append("Improving patient outcomes through better prediction")
    
    # From trial design
    if biomarker_insights['focuses_resistance']:
        what_they_do.append("Identifying patients at risk for platinum resistance")
    if biomarker_insights['biomarker_trial']:
        what_they_do.append("Validating biomarkers for clinical use")
    if trial_intel.get('primary_purpose') == 'Treatment':
        what_they_do.append("Testing new treatment strategies")
    if trial_intel.get('primary_purpose') == 'Diagnostic':
        what_they_do.append("Improving diagnostic and predictive capabilities")
    
    # Default if nothing specific
    if not what_they_do:
        what_they_do.append("Advancing ovarian cancer treatment through research")
    
    profile['what_they_do'] = list(set(what_they_do))
    
    if what_they_do:
        print(f"      Goals: {', '.join(what_they_do[:2])}")
    
    # ============================================================
    # 5. HOW WE CAN HELP THEM (Specific to Their Goals)
    # ============================================================
    print(f"   💡 Determining how we can help...")
    
    how_we_help = []
    
    # If they're studying resistance
    if any('resistance' in goal.lower() for goal in what_they_do):
        how_we_help.append("KELIM provides early prediction of platinum resistance (before treatment failure)")
        how_we_help.append("Validates resistance prediction methods you're developing")
        how_we_help.append("Enhances your trial's resistance biomarker analysis")
    
    # If they're developing biomarkers
    if any('biomarker' in goal.lower() for goal in what_they_do):
        how_we_help.append("KELIM validation strengthens the biomarker evidence base you're building")
        how_we_help.append("Your data contributes to establishing KELIM as a standard biomarker")
        how_we_help.append("Co-authorship adds to your biomarker validation portfolio")
    
    # If they're researching CA-125
    if any('ca-125' in goal.lower() or 'ca125' in goal.lower() for goal in what_they_do):
        how_we_help.append("KELIM uses CA-125 kinetics you're already collecting")
        how_we_help.append("Validates CA-125 as a predictive biomarker")
        how_we_help.append("Enhances your CA-125 research with validated methodology")
    
    # If they're improving outcomes
    if any('outcome' in goal.lower() or 'improving' in goal.lower() for goal in what_they_do):
        how_we_help.append("KELIM enables better patient selection for treatment strategies")
        how_we_help.append("Early prediction helps optimize patient management")
        how_we_help.append("Validated biomarker supports personalized treatment approaches")
    
    # If they're testing treatments
    if any('treatment' in goal.lower() or 'testing' in goal.lower() for goal in what_they_do):
        how_we_help.append("KELIM can stratify patients for your treatment trials")
        how_we_help.append("Identifies patients who may benefit from alternative treatments")
        how_we_help.append("Enhances trial design by predicting treatment response")
    
    # General help
    if not how_we_help:
        how_we_help.append("KELIM validation contributes to the evidence base for ovarian cancer biomarkers")
        how_we_help.append("Your expertise and data strengthen the validation study")
    
    profile['how_we_help'] = list(set(how_we_help))
    
    if how_we_help:
        print(f"      Help points: {len(how_we_help)}")
    
    # ============================================================
    # 6. TARGETED VALUE PROPOSITION
    # ============================================================
    print(f"   💎 Creating targeted value proposition...")
    
    value_props = []
    
    # Based on research focus
    if 'Platinum resistance research' in research_focus:
        value_props.append("KELIM directly addresses your research focus on platinum resistance")
    if 'Biomarker development' in research_focus:
        value_props.append("KELIM validation strengthens your biomarker development work")
    if 'CA-125 research' in research_focus:
        value_props.append("KELIM builds on your CA-125 research expertise")
    
    # Based on trial
    if biomarker_insights['focuses_resistance']:
        value_props.append("Your resistance-focused trial is ideal for KELIM validation")
    if trial_intel.get('phase') and any('3' in str(p) for p in trial_intel.get('phase', [])):
        value_props.append("Your Phase 3 data would provide the most robust validation evidence")
    if trial_intel.get('enrollment_count', 0) >= 100:
        value_props.append(f"Your large trial ({trial_intel.get('enrollment_count')} patients) ensures statistical power")
    
    # Based on data availability
    if trial_intel.get('completion_date'):
        value_props.append("Your completed trial likely has mature data ready for analysis")
    
    profile['targeted_value_props'] = value_props
    
    # ============================================================
    # 7. PERSONALIZED INSIGHTS
    # ============================================================
    profile['personalized_insights'] = {
        'trial_stage': 'Completed' if trial_intel.get('completion_date') else 'Active',
        'data_readiness': 'High' if trial_intel.get('completion_date') and trial_intel.get('enrollment_count', 0) >= 50 else 'Medium',
        'collaboration_likelihood': 'High' if 'academic' in institution.lower() or 'university' in institution.lower() else 'Medium',
        'research_alignment': 'High' if len(research_focus) > 0 and any('resistance' in f.lower() or 'biomarker' in f.lower() for f in research_focus) else 'Medium',
        'kelim_relevance': 'High' if profile.get('kelim_fit', {}).get('fit_score', 0) >= 2 else 'Medium'
    }
    
    # ============================================================
    # 8. GENERATE HIGHLY PERSONALIZED EMAIL
    # ============================================================
    print(f"   📧 Generating personalized email...")
    
    # Extract first name for greeting
    if ',' in pi_name:
        first_name = pi_name.split(',')[1].strip().split()[0] if len(pi_name.split(',')) > 1 else pi_name.split()[0]
    else:
        first_name = pi_name.split()[0] if pi_name.split() else 'Dr.'
    
    trial_title = trial_intel.get('title', 'N/A')
    research_summary = ', '.join(what_they_do[:2]) if what_they_do else 'ovarian cancer research'
    help_summary = how_we_help[0] if how_we_help else 'KELIM validation'
    fit_summary = ', '.join(kelim_fit_reasons[:3]) if kelim_fit_reasons else 'involves CA-125 monitoring'
    value_summary = value_props[0] if value_props else 'Your trial is ideal for KELIM validation'
    
    personalized_email = f"""Subject: KELIM Biomarker Validation - Aligned with Your Research on {research_summary}

Dear Dr. {first_name},

I hope this email finds you well. I am reaching out because your research on {research_summary} aligns perfectly with our KELIM biomarker validation study.

**Why This Collaboration Makes Sense:**

Your trial "{trial_title}" (NCT{nct_id}) focuses on {research_summary}. KELIM (CA-125 elimination rate) directly supports this goal by:
{chr(10).join(['- ' + point for point in how_we_help[:3]])}

**What Makes Your Trial Ideal for KELIM Validation:**
{chr(10).join(['- ' + reason for reason in kelim_fit_reasons[:3]])}

**How KELIM Helps Your Research:**
{value_summary}. Specifically:
{chr(10).join(['- ' + prop for prop in value_props[:2]]) if len(value_props) >= 2 else '- KELIM validation strengthens the biomarker evidence base'}

**What We Need:**
- Serial CA-125 measurements (≥2 per patient) during first 100 days of platinum therapy
- Platinum-free interval (PFI) outcomes or progression dates
- Treatment information (platinum agent, dates)
- Minimum of 50-100 patients for statistical validation

**What You Get:**
- Co-authorship on validation publication (assuming successful validation)
- Access to validated KELIM biomarker for your research
- Enhanced biomarker analysis for your trial
- Contribution to establishing KELIM as a standard tool for {research_summary.split()[0] if research_summary else 'ovarian cancer treatment'}

**Why This Helps Your Research:**
{chr(10).join(['- ' + prop for prop in value_props[:3]]) if len(value_props) >= 3 else '- KELIM validation contributes to advancing ovarian cancer treatment'}

We would be happy to discuss:
- How KELIM can enhance your trial's biomarker analysis
- Data sharing agreements and IRB considerations
- Co-authorship and collaboration details
- Any questions you may have

Thank you for your consideration. I look forward to discussing how we can advance ovarian cancer treatment together.

Best regards,
[Your Name]
[Your Affiliation]
[Your Contact Information]
"""
    
    profile['personalized_email'] = personalized_email
    
    enhanced_profiles.append(profile)
    time.sleep(0.5)  # Rate limiting

# Save enhanced profiles
output_file = output_dir / 'enhanced_pi_intelligence_profiles.json'
with open(output_file, 'w') as f:
    json.dump({
        'metadata': {
            'extraction_date': datetime.now().isoformat(),
            'total_profiles': len(enhanced_profiles),
            'capabilities_used': [
                'ClinicalTrials.gov API (trial details, endpoints, eligibility)',
                'PubMed API (publications, research focus)',
                'Trial analysis (biomarker intelligence)',
                'Goal understanding (what they are trying to do)',
                'Value proposition (how we can help)'
            ]
        },
        'profiles': enhanced_profiles
    }, f, indent=2, default=str)

print(f"\n{'='*80}")
print("✅ ENHANCED INTELLIGENCE EXTRACTION COMPLETE")
print(f"{'='*80}")

# Summary
high_fit = [p for p in enhanced_profiles if p.get('kelim_fit', {}).get('is_high_fit')]
with_publications = [p for p in enhanced_profiles if p.get('research_intelligence', {}).get('publication_count', 0) > 0]
high_data_readiness = [p for p in enhanced_profiles if p.get('personalized_insights', {}).get('data_readiness') == 'High']

print(f"\n📊 Summary:")
print(f"   - Profiles created: {len(enhanced_profiles)}")
print(f"   - High KELIM fit: {len(high_fit)}")
print(f"   - With publications: {len(with_publications)}")
print(f"   - High data readiness: {len(high_data_readiness)}")
print(f"\n💾 Saved to: {output_file}")

# Show sample
if enhanced_profiles:
    sample = enhanced_profiles[0]
    print(f"\n📋 Sample Enhanced Profile:")
    print(f"   PI: {sample.get('pi_name', 'N/A')}")
    print(f"   What they do: {', '.join(sample.get('what_they_do', [])[:2])}")
    print(f"   How we help: {len(sample.get('how_we_help', []))} specific points")
    print(f"   KELIM fit: {sample.get('kelim_fit', {}).get('fit_score', 0)}/5")
    print(f"   Personalized email: {len(sample.get('personalized_email', ''))} chars")





