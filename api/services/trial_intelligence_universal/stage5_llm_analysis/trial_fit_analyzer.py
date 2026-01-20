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

async def analyze(trial: Dict[str, Any], patient: Dict[str, Any]) -> str:
    """
    Generate deep LLM analysis of trial fit.
    
    Returns:
        Markdown-formatted analysis (~800 words)
    """
    if not LLM_AVAILABLE:
        print(f"⚠️ LLM NOT AVAILABLE - using fallback for {trial.get('nct_id')}")
        return _generate_fallback_analysis(trial, patient)
    
    # Build comprehensive prompt
    trial_title = trial.get('title', 'N/A')
    trial_description = trial.get('description_text', 'No description available.')[:1000]
    eligibility = trial.get('eligibility_text', 'No eligibility data.')[:1000]
    
    # Patient context
    demographics = patient.get('demographics', {})
    disease = patient.get('disease', {})
    biomarkers = patient.get('biomarkers', {})
    treatment = patient.get('treatment', {})
    eligibility_factors = patient.get('eligibility', {})
    logistics = patient.get('logistics', {})
    
    # Extract patient details
    patient_name = demographics.get('name', 'Patient')
    patient_age = demographics.get('age', 'N/A')
    patient_sex = demographics.get('sex', '')
    patient_zip = logistics.get('zip_code') or logistics.get('home_zip', 'Unknown')
    patient_location = logistics.get('location', 'Unknown')
    
    # Get matching locations (based on config, not hardcoded NYC)
    matching_locations = [
        loc for loc in trial.get('locations_data', [])
        if loc.get('state', '').upper() in ['NY', 'NJ', 'CT']  # Default to NYC metro, but can be overridden
    ]
    
    locations_text = "\n".join([
        f"- {loc.get('facility', 'Unknown')} ({loc.get('city', 'Unknown')}, {loc.get('state', 'Unknown')})"
        for loc in matching_locations[:5]
    ]) if matching_locations else "No matching locations found in metadata"
    
    # Get CA-125 if available
    ca125_value = biomarkers.get('ca125', {}).get('value') if isinstance(biomarkers.get('ca125'), dict) else biomarkers.get('ca125')
    ca125_text = f" (CA-125: {ca125_value} U/mL)" if ca125_value else ""
    
    # Get planned SOC if available
    planned_soc = treatment.get('planned_frontline', {}).get('regimen') if isinstance(treatment.get('planned_frontline'), dict) else None
    soc_text = f"Planned SOC: {planned_soc}" if planned_soc else "Standard of care not specified"
    
    prompt = f"""You are a clinical oncology expert analyzing a clinical trial for a specific patient.

**PATIENT PROFILE:**
- Name: {patient_name} ({patient_age}{patient_sex}, ZIP {patient_zip} - {patient_location})
- Disease: {disease.get('primary_diagnosis', 'Unknown')}
- Stage: {disease.get('figo_stage', disease.get('stage', 'Unknown'))}
- Tumor Burden: {disease.get('tumor_burden', 'Unknown')}{ca125_text}
- Treatment Line: {treatment.get('line', 'Unknown')} ({treatment.get('status', 'Unknown')})
- Performance Status: ECOG {disease.get('performance_status', 'Unknown')}
- BRCA: {biomarkers.get('germline_status', 'Unknown')}
- HER2: {biomarkers.get('her2_status', 'Unknown')}
- HRD: {biomarkers.get('hrd_status', 'Unknown')}
- Pulmonary Status: {eligibility_factors.get('organ_function', {}).get('pulmonary', 'Unknown')}
- {soc_text}

**TRIAL:**
- Title: {trial_title}
- NCT ID: {trial.get('nct_id', 'N/A')}

**TRIAL DESCRIPTION:**
{trial_description}

**ELIGIBILITY CRITERIA (excerpt):**
{eligibility[:500]}

**MATCHING LOCATIONS:**
{locations_text}

**YOUR TASK:**
Analyze WHY this trial is a good fit (or not) for this patient. Write a ~500-word clinical analysis covering:

1. **Drug Mechanism Fit**: How does the trial's drug/intervention address the patient's specific disease characteristics? Consider their stage, tumor burden, metastases, and biomarker status.

2. **Location Logistics**: Which sites are available near the patient? Estimate travel time from ZIP {patient_zip} ({patient_location}) to these sites. Are they at preferred centers?

3. **Risk-Benefit Analysis**: Given the patient's comorbidities and performance status, what are the specific risks and benefits? Would the trial intervention be safe? Any concerns about toxicity?

4. **Comparison to Standard of Care**: How does this trial compare to the patient's planned or current standard of care? Is it better, worse, or complementary? Should they pursue this trial or stick with SOC?

5. **Critical Considerations**: What are the most important factors for the patient's care team to consider when deciding about this trial?

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
        return _generate_fallback_analysis(trial, patient)

def _generate_fallback_analysis(trial: Dict[str, Any], patient: Dict[str, Any]) -> str:
    """Generate structured fallback analysis if LLM fails"""
    
    title = trial.get('title', 'N/A')
    nct_id = trial.get('nct_id', 'N/A')
    
    return f"""### **Clinical Trial Analysis: {nct_id}**

**Note**: This is a structured fallback analysis (LLM unavailable).

#### **1. Drug Mechanism Fit**
The trial "{title}" requires detailed mechanism analysis. Review the trial protocol to understand how the investigational drug addresses the patient's disease characteristics, stage, and tumor burden.

#### **2. Location Logistics**
Review trial locations to identify sites accessible from the patient's location. Consider travel distance, preferred centers, and logistics.

#### **3. Risk-Benefit Analysis**
**Key Considerations**:
- Comorbidities: Review patient's organ function and performance status
- Performance status: Acceptable for most trials, but toxicity profile is critical
- Tumor burden: Consider disease extent and may require aggressive initial treatment

#### **4. Comparison to Standard of Care**
Compare this trial to the patient's planned or current standard of care. Assess:
- Is it a replacement for SOC (frontline trial)?
- Is it additional to SOC (maintenance trial)?
- Is it an alternative if SOC fails?

#### **5. Critical Considerations**
1. **Biomarker testing**: Review required biomarkers - may need testing before enrollment
2. **Timing**: When should the patient enroll? Before SOC, during SOC, or after response?
3. **Clinical team review**: Discuss with the patient's oncologist before enrollment decisions

**Recommendation**: Full protocol review with clinical team required.
"""


