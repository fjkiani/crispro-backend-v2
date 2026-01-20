"""
LLM Trial Fit Analyzer

Deep analysis of WHY this trial is a good fit for the patient.

Covers:
1. Drug mechanism vs patient's disease characteristics
2. Location logistics (NYC sites, distance from home)
3. Risk-benefit for patient specifically (comorbidities, performance status)
4. Comparison to standard of care
"""

import sys
from pathlib import Path
from typing import Dict, Any

# Import LLM API
# From: oncology-coPilot/oncology-backend-minimal/api/services/trial_intelligence/stage5_llm_analysis/trial_fit_analyzer.py
# To: crispr-assistant-main/src/tools/llm_api.py
# Path count: trial_fit_analyzer (0) -> stage5_llm_analysis (1) -> trial_intelligence (2) -> services (3) -> api (4) -> oncology-backend-minimal (5) -> oncology-coPilot (6) -> crispr-assistant-main (7)
PROJECT_ROOT = Path(__file__).resolve()
for _ in range(7):  # Go up 7 levels to reach crispr-assistant-main
    PROJECT_ROOT = PROJECT_ROOT.parent
sys.path.insert(0, str(PROJECT_ROOT / "src" / "tools"))

try:
    from llm_api import get_llm_chat_response
    LLM_AVAILABLE = True
    GEMINI_MODEL = "gemini-2.5-pro"
except ImportError as e:
    LLM_AVAILABLE = False
    GEMINI_MODEL = None
    print(f"❌ LLM import failed: {e}")

async def analyze(trial: Dict[str, Any], ayesha: Dict[str, Any]) -> str:
    """
    Generate deep LLM analysis of trial fit.
    
    Returns:
        Markdown-formatted analysis (~800 words)
    """
    if not LLM_AVAILABLE:
        print(f"⚠️ LLM NOT AVAILABLE - using fallback for {trial.get('nct_id')}")
        return _generate_fallback_analysis(trial, ayesha)
    
    # Build comprehensive prompt
    trial_title = trial.get('title', 'N/A')
    trial_description = trial.get('description_text', 'No description available.')[:1000]
    eligibility = trial.get('eligibility_text', 'No eligibility data.')[:1000]
    
    # Patient context
    disease = ayesha['disease']
    biomarkers = ayesha['biomarkers']
    treatment = ayesha['treatment']
    eligibility_factors = ayesha['eligibility']
    
    # NYC locations
    nyc_locations = [
        loc for loc in trial.get('locations_data', [])
        if loc.get('city', '').lower() in ['new york', 'brooklyn', 'bronx', 'queens', 'manhattan']
           or 'mount sinai' in loc.get('facility', '').lower()
           or 'msk' in loc.get('facility', '').lower()
           or 'sloan kettering' in loc.get('facility', '').lower()
           or 'nyu' in loc.get('facility', '').lower()
    ]
    
    nyc_sites_text = "\n".join([
        f"- {loc.get('facility', 'Unknown')} ({loc.get('city', 'Unknown')}, {loc.get('state', 'Unknown')})"
        for loc in nyc_locations[:5]
    ]) if nyc_locations else "No NYC locations found in metadata"
    
    prompt = f"""You are a clinical oncology expert analyzing a clinical trial for a specific patient.

**PATIENT PROFILE:**
- Name: AK (40F, ZIP 10029 - East Harlem, NYC)
- Disease: {disease['primary_diagnosis']}
- Stage: {disease['figo_stage']}
- Tumor Burden: {disease['tumor_burden']} (CA-125: {biomarkers['ca125']['value']} U/mL)
- Treatment Line: {treatment['line']} ({treatment['status']})
- Performance Status: ECOG {disease['performance_status']}
- BRCA: {biomarkers['germline_status']}
- HER2: {biomarkers['her2_status']}
- HRD: {biomarkers['hrd_status']}
- Pulmonary Status: {eligibility_factors['organ_function']['pulmonary']} (large bilateral pleural effusions)
- Planned SOC: Carboplatin + Paclitaxel + Bevacizumab (first-line)

**TRIAL:**
- Title: {trial_title}
- NCT ID: {trial.get('nct_id', 'N/A')}

**TRIAL DESCRIPTION:**
{trial_description}

**ELIGIBILITY CRITERIA (excerpt):**
{eligibility[:500]}

**NYC METRO LOCATIONS:**
{nyc_sites_text}

**YOUR TASK:**
Analyze WHY this trial is a good fit (or not) for Ayesha. Write a ~500-word clinical analysis covering:

1. **Drug Mechanism Fit**: How does the trial's drug/intervention address Ayesha's specific disease characteristics? Consider her Stage IVB HGSOC, high tumor burden, pleural metastases, and biomarker status (BRCA wildtype, HER2/HRD unknown).

2. **Location Logistics**: Which NYC sites are available? Estimate travel time from ZIP 10029 (East Harlem) to these sites. Are they at her preferred centers (Mount Sinai, MSK, NYU)?

3. **Risk-Benefit for Ayesha**: Given her pulmonary compromise (large bilateral pleural effusions) and ECOG 1, what are the specific risks and benefits? Would the trial intervention be safe for her? Any concerns about toxicity given her comorbidities?

4. **Comparison to Standard of Care**: How does this trial compare to her planned SOC (Carboplatin + Paclitaxel + Bevacizumab)? Is it better, worse, or complementary? Should she pursue this trial or stick with SOC?

5. **Critical Considerations**: What are the most important factors for Ayesha's care team to consider when deciding about this trial?

Write in clear, concise clinical language. Be honest about limitations and uncertainties. Format as markdown with section headers.
"""

    try:
        conversation_history = [
            {"role": "system", "content": "You are a clinical oncology expert analyzing clinical trials for specific patients. Provide evidence-based, nuanced analysis."},
            {"role": "user", "content": prompt}
        ]
        
        response = get_llm_chat_response(
            conversation_history=conversation_history,
            provider="gemini",
            model_name=GEMINI_MODEL
        )
        
        # Clean up response
        if response.startswith("```"):
            lines = response.split('\n')
            response = '\n'.join(lines[1:-1]) if len(lines) > 2 else response
        
        return response
    
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"❌ LLM analysis failed for {trial.get('nct_id')}: {type(e).__name__}: {e}")
        print(f"❌ LLM Error: {type(e).__name__}: {e}")  # Also print to console
        return _generate_fallback_analysis(trial, ayesha)

def _generate_fallback_analysis(trial: Dict[str, Any], ayesha: Dict[str, Any]) -> str:
    """Generate structured fallback analysis if LLM fails"""
    
    title = trial.get('title', 'N/A')
    nct_id = trial.get('nct_id', 'N/A')
    
    return f"""### **Clinical Trial Analysis: {nct_id}**

**Note**: This is a structured fallback analysis (LLM unavailable).

#### **1. Drug Mechanism Fit**
The trial "{title}" requires detailed mechanism analysis. Review the trial protocol to understand how the investigational drug addresses Ayesha's Stage IVB High-Grade Serous Ovarian Carcinoma with extensive tumor burden and pleural metastases.

#### **2. Location Logistics**
Review trial locations to identify NYC metro sites accessible from ZIP 10029 (East Harlem). Preferred centers: Mount Sinai (local), MSK (2 miles), NYU Langone (3-4 miles).

#### **3. Risk-Benefit for Ayesha**
**Key Considerations**:
- Pulmonary compromise: Large bilateral pleural effusions require careful monitoring
- ECOG 1: Acceptable for most trials, but toxicity profile is critical
- Tumor burden: Extensive disease (CA-125 >2800) may require aggressive initial treatment

#### **4. Comparison to Standard of Care**
Ayesha's planned SOC is Carboplatin + Paclitaxel + Bevacizumab (NCCN-guideline first-line therapy for Stage IVB HGSOC, BRCA wildtype). This trial should be compared to this regimen to assess:
- Is it a replacement for SOC (frontline trial)?
- Is it additional to SOC (maintenance trial)?
- Is it an alternative if SOC fails?

#### **5. Critical Considerations**
1. **Biomarker testing**: HER2 and HRD status are unknown - may be required for enrollment
2. **Timing**: When should Ayesha enroll? Before SOC, during SOC, or after response?
3. **Clinical team review**: Discuss with Ayesha's oncologist before enrollment decisions

**Recommendation**: Full protocol review with clinical team required.
"""


