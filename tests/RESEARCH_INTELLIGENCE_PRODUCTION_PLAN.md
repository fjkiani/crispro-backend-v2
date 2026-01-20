# 🚀 RESEARCH INTELLIGENCE - PRODUCTION EXECUTION PLAN

**Date**: January 2, 2026  
**Goal**: Transform Research Intelligence from "backend ready" to "patient-ready production"  
**Timeline**: 4 weeks  
**Focus**: Patient-first, then Doctor, then R&D

---

## 🎯 CORE VALUE PROPOSITION

### **What We're Building**
A **beautiful, patient-friendly research intelligence system** that:
1. **Saves everything** - No lost queries, full history
2. **Creates beautiful dossiers** - Not just JSON dumps
3. **Speaks patient language** - Not technical jargon
4. **Delivers value** - Not just data, but insights
5. **Remembers context** - Builds on previous research
6. **Shares easily** - PDFs, links, emails

### **Who Benefits**
- **Patients**: "Will this help me? Is it safe? What should I do?"
- **Doctors**: "What's the evidence? What's the mechanism? Any interactions?"
- **R&D**: "What's known? What's missing? What's trending?"

---

## 📋 PHASE 1: FOUNDATION (Week 1)

### **Goal**: Persist queries and create basic dossiers

### **Task 1.1: Database Schema**
**File**: `.cursor/SUPABASE_SCHEMA_UPDATES.sql`

```sql
-- Research Intelligence Queries
CREATE TABLE IF NOT EXISTS public.research_intelligence_queries (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    session_id UUID REFERENCES public.user_sessions(id) ON DELETE CASCADE,
    
    -- Query
    question TEXT NOT NULL,
    context JSONB NOT NULL,  -- disease, treatment_line, biomarkers
    options JSONB,  -- portals, synthesize, run_moat_analysis
    
    -- Results
    result JSONB NOT NULL,  -- Full API response
    provenance JSONB,  -- run_id, methods_used, timestamp
    
    -- Metadata
    dossier_id UUID,  -- Link to generated dossier
    persona VARCHAR(20) DEFAULT 'patient',  -- patient, doctor, r&d
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    last_accessed_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_ri_queries_user_id ON public.research_intelligence_queries(user_id);
CREATE INDEX idx_ri_queries_session_id ON public.research_intelligence_queries(session_id);
CREATE INDEX idx_ri_queries_created_at ON public.research_intelligence_queries(created_at);
CREATE INDEX idx_ri_queries_question ON public.research_intelligence_queries USING gin(to_tsvector('english', question));

-- Research Intelligence Dossiers
CREATE TABLE IF NOT EXISTS public.research_intelligence_dossiers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    query_id UUID REFERENCES public.research_intelligence_queries(id) ON DELETE CASCADE,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    
    -- Dossier Content
    persona VARCHAR(20) NOT NULL,  -- patient, doctor, r&d
    markdown TEXT NOT NULL,  -- Full markdown content
    pdf_path TEXT,  -- Path to generated PDF (if generated)
    
    -- Metadata
    shareable_link TEXT UNIQUE,  -- Unique shareable URL
    shareable_expires_at TIMESTAMPTZ,  -- Optional expiration
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_ri_dossiers_query_id ON public.research_intelligence_dossiers(query_id);
CREATE INDEX idx_ri_dossiers_user_id ON public.research_intelligence_dossiers(user_id);
CREATE INDEX idx_ri_dossiers_shareable_link ON public.research_intelligence_dossiers(shareable_link);
```

**Acceptance Criteria**:
- ✅ Tables created in Supabase
- ✅ Indexes created for performance
- ✅ RLS policies set (users can only see their own queries)

---

### **Task 1.2: Auto-Save Queries in Router**
**File**: `api/routers/research_intelligence.py`

```python
from api.services.supabase_client import get_supabase_client
import uuid
from datetime import datetime

@router.post("/api/research/intelligence")
async def research_intelligence(
    request: ResearchIntelligenceRequest,
    user: Optional[Dict] = Depends(get_optional_user)
):
    # ... existing query logic ...
    
    # NEW: Save query to database
    query_id = None
    if user:
        supabase = get_supabase_client()
        query_data = {
            "id": str(uuid.uuid4()),
            "user_id": user.get("user_id"),
            "question": request.question,
            "context": request.context.dict() if hasattr(request.context, 'dict') else request.context,
            "options": {
                "portals": request.portals,
                "synthesize": request.synthesize,
                "run_moat_analysis": request.run_moat_analysis
            },
            "result": result,
            "provenance": result.get("provenance"),
            "persona": request.persona or "patient",
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "last_accessed_at": datetime.utcnow().isoformat()
        }
        
        try:
            response = supabase.table("research_intelligence_queries").insert(query_data).execute()
            if response.data:
                query_id = response.data[0]["id"]
        except Exception as e:
            logger.warning(f"Failed to save query: {e}")
    
    return {
        **result,
        "query_id": query_id  # NEW
    }
```

**Acceptance Criteria**:
- ✅ Queries auto-saved on completion
- ✅ User ID linked correctly
- ✅ Full result stored in JSONB
- ✅ Error handling if save fails (query still returns)

---

### **Task 1.3: Basic Dossier Generator**
**File**: `api/services/research_intelligence/dossier_generator.py`

```python
class ResearchIntelligenceDossierGenerator:
    """
    Generates beautiful dossiers from Research Intelligence results.
    """
    
    async def generate_dossier(
        self,
        query_result: Dict[str, Any],
        persona: str = "patient",
        query_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate dossier in markdown format.
        
        Returns:
        {
            "markdown": "...",
            "sections": {...},
            "metadata": {...}
        }
        """
        research_plan = query_result.get("research_plan", {})
        synthesized = query_result.get("synthesized_findings", {})
        moat = query_result.get("moat_analysis", {})
        
        # Build markdown
        markdown_parts = []
        
        # Title
        question = research_plan.get("primary_question", "Research Query")
        markdown_parts.append(f"# Research Intelligence Report\n\n")
        markdown_parts.append(f"**Question**: {question}\n\n")
        markdown_parts.append(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        markdown_parts.append("---\n\n")
        
        # Executive Summary (persona-specific)
        if persona == "patient":
            markdown_parts.append(self._generate_patient_summary(synthesized, moat))
        elif persona == "doctor":
            markdown_parts.append(self._generate_doctor_summary(synthesized, moat))
        else:
            markdown_parts.append(self._generate_rnd_summary(synthesized, moat))
        
        # Mechanisms
        markdown_parts.append(self._generate_mechanisms_section(synthesized, persona))
        
        # Evidence
        markdown_parts.append(self._generate_evidence_section(synthesized, persona))
        
        # Clinical Implications (if MOAT analysis)
        if moat:
            markdown_parts.append(self._generate_clinical_implications(moat, persona))
        
        # Citations
        markdown_parts.append(self._generate_citations_section(query_result))
        
        markdown = "\n".join(markdown_parts)
        
        return {
            "markdown": markdown,
            "persona": persona,
            "query_id": query_id
        }
    
    def _generate_patient_summary(self, synthesized, moat) -> str:
        """Generate patient-friendly executive summary."""
        mechanisms = synthesized.get("mechanisms", [])
        evidence_tier = synthesized.get("evidence_tier", "Unknown")
        confidence = synthesized.get("overall_confidence", 0.5)
        
        summary = "## Executive Summary\n\n"
        summary += f"Based on analysis of **{len(mechanisms)} key mechanisms**, "
        summary += f"the evidence strength is **{evidence_tier}** "
        summary += f"(confidence: {confidence:.0%}).\n\n"
        
        # Safety (if available)
        if moat.get("toxicity_mitigation"):
            toxicity = moat["toxicity_mitigation"]
            risk_level = toxicity.get("risk_level", "UNKNOWN")
            summary += f"**Safety**: {risk_level} risk level.\n\n"
        
        return summary
    
    # ... more section generators ...
```

**Acceptance Criteria**:
- ✅ Markdown generated for all personas
- ✅ Patient-friendly language for patient persona
- ✅ Technical details for doctor/R&D personas
- ✅ All sections included (summary, mechanisms, evidence, citations)

---

### **Task 1.4: Query History UI**
**File**: `oncology-coPilot/oncology-frontend/src/components/research/QueryHistorySidebar.jsx`

```javascript
export default function QueryHistorySidebar({ onSelectQuery }) {
  const [queries, setQueries] = useState([]);
  const [loading, setLoading] = useState(true);
  
  useEffect(() => {
    loadQueryHistory();
  }, []);
  
  const loadQueryHistory = async () => {
    try {
      const response = await fetch('/api/research/intelligence/history');
      const data = await response.json();
      setQueries(data.queries || []);
    } catch (err) {
      console.error('Failed to load query history:', err);
    } finally {
      setLoading(false);
    }
  };
  
  return (
    <Box sx={{ width: 300, p: 2 }}>
      <Typography variant="h6">Recent Research</Typography>
      {queries.map(query => (
        <Card key={query.id} sx={{ mb: 1, cursor: 'pointer' }} onClick={() => onSelectQuery(query)}>
          <CardContent>
            <Typography variant="body2" noWrap>{query.question}</Typography>
            <Typography variant="caption" color="text.secondary">
              {new Date(query.created_at).toLocaleDateString()}
            </Typography>
          </CardContent>
        </Card>
      ))}
    </Box>
  );
}
```

**Acceptance Criteria**:
- ✅ Sidebar displays recent queries
- ✅ Click to load previous query
- ✅ Shows date and question preview
- ✅ Loading state handled

---

## 📋 PHASE 2: PATIENT EXPERIENCE (Week 2)

### **Goal**: Patient-friendly language and value synthesis

### **Task 2.1: Language Translation Service**
**File**: `api/services/research_intelligence/language_translator.py`

```python
class PatientLanguageTranslator:
    """
    Translates technical terms to patient-friendly language.
    """
    
    TRANSLATIONS = {
        "NF-kB inhibition": "Reduces inflammation",
        "DDR pathway": "DNA repair system",
        "Apoptosis": "Programmed cell death (cancer cell elimination)",
        "Mechanism of action": "How it works",
        "Evidence tier": "How strong is the evidence",
        "Pathway": "Biological process",
        "Biomarker": "Biological indicator",
        "Toxicity": "Side effects",
        "Efficacy": "How well it works",
        "Pharmacogenomics": "How your genes affect drug response"
    }
    
    def translate_mechanism(self, mechanism: str) -> str:
        """Translate mechanism to patient-friendly language."""
        # Check direct translation
        if mechanism in self.TRANSLATIONS:
            return self.TRANSLATIONS[mechanism]
        
        # Pattern-based translation
        if "inhibition" in mechanism.lower():
            return f"Blocks {mechanism.replace('inhibition', '').strip()}"
        if "pathway" in mechanism.lower():
            return f"Affects {mechanism.replace('pathway', 'process').strip()}"
        
        # Fallback: return as-is with explanation
        return f"{mechanism} (biological process)"
    
    def translate_evidence_tier(self, tier: str) -> str:
        """Translate evidence tier to patient-friendly language."""
        translations = {
            "Supported": "Strong evidence - multiple studies support this",
            "Consider": "Moderate evidence - some studies support this",
            "Insufficient": "Limited evidence - more research needed"
        }
        return translations.get(tier, tier)
```

**Acceptance Criteria**:
- ✅ Common terms translated
- ✅ Pattern-based translation for unknown terms
- ✅ Fallback with explanation
- ✅ Configurable translations

---

### **Task 2.2: Value Synthesis Service**
**File**: `api/services/research_intelligence/value_synthesizer.py`

```python
class ValueSynthesizer:
    """
    Synthesizes research data into actionable insights.
    """
    
    def __init__(self):
        from api.services.llm_provider.llm_abstract import get_llm_provider, LLMProvider
        self.llm = get_llm_provider(provider=LLMProvider.COHERE)
    
    async def synthesize_insights(
        self,
        query_result: Dict[str, Any],
        persona: str = "patient"
    ) -> Dict[str, Any]:
        """
        Generate "What This Means" insights.
        
        Returns:
        {
            "executive_summary": "...",
            "what_this_means": "...",
            "action_items": [...],
            "confidence": 0.85,
            "recommendations": [...]
        }
        """
        synthesized = query_result.get("synthesized_findings", {})
        moat = query_result.get("moat_analysis", {})
        research_plan = query_result.get("research_plan", {})
        
        # Build prompt for LLM
        prompt = self._build_synthesis_prompt(
            synthesized, moat, research_plan, persona
        )
        
        # Call LLM
        response = await self.llm.chat(
            message=prompt,
            temperature=0.3,
            max_tokens=1000
        )
        
        # Parse response
        insights = self._parse_llm_response(response.text)
        
        return insights
    
    def _build_synthesis_prompt(self, synthesized, moat, research_plan, persona):
        """Build LLM prompt for value synthesis."""
        mechanisms = synthesized.get("mechanisms", [])
        evidence_tier = synthesized.get("evidence_tier", "Unknown")
        confidence = synthesized.get("overall_confidence", 0.5)
        
        if persona == "patient":
            prompt = f"""
            Based on this research analysis:
            - Mechanisms found: {len(mechanisms)}
            - Evidence strength: {evidence_tier}
            - Confidence: {confidence:.0%}
            
            Generate a patient-friendly summary that answers:
            1. Will this help me? (Yes/No/Maybe with explanation)
            2. Is it safe? (Safety assessment)
            3. What should I do? (Action items)
            
            Use simple language, avoid jargon.
            """
        # ... doctor and R&D prompts ...
        
        return prompt
```

**Acceptance Criteria**:
- ✅ LLM generates insights for all personas
- ✅ Patient-friendly language for patients
- ✅ Action items extracted
- ✅ Confidence scores included

---

### **Task 2.3: Persona Selector in UI**
**File**: `oncology-coPilot/oncology-frontend/src/pages/ResearchIntelligence.jsx`

```javascript
const [persona, setPersona] = useState('patient');

// Add persona selector
<FormControl fullWidth sx={{ mb: 2 }}>
  <InputLabel>View As</InputLabel>
  <Select
    value={persona}
    label="View As"
    onChange={(e) => setPersona(e.target.value)}
  >
    <MenuItem value="patient">Patient</MenuItem>
    <MenuItem value="doctor">Doctor</MenuItem>
    <MenuItem value="r&d">R&D</MenuItem>
  </Select>
</FormControl>

// Pass persona to results
<ResearchIntelligenceResults
  result={result}
  context={context}
  persona={persona}  // NEW
/>
```

**Acceptance Criteria**:
- ✅ Persona selector in UI
- ✅ Results filtered by persona
- ✅ Language translation applied
- ✅ Value synthesis displayed

---

## 📋 PHASE 3: VALUE DELIVERY (Week 3)

### **Goal**: Beautiful PDFs, sharing, executive summaries

### **Task 3.1: PDF Generation Service**
**File**: `api/services/research_intelligence/pdf_generator.py`

```python
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
import markdown

class PDFGenerator:
    """Generate PDF from markdown dossier."""
    
    async def generate_pdf(
        self,
        markdown_content: str,
        output_path: str
    ) -> str:
        """Generate PDF from markdown."""
        # Convert markdown to HTML
        html = markdown.markdown(markdown_content)
        
        # Generate PDF using reportlab or weasyprint
        # ... PDF generation logic ...
        
        return output_path
```

**Acceptance Criteria**:
- ✅ PDF generated from markdown
- ✅ Beautiful formatting
- ✅ Patient-friendly layout
- ✅ Citations included

---

### **Task 3.2: Shareable Links**
**File**: `api/routers/research_intelligence.py`

```python
@router.get("/api/research/intelligence/share/{shareable_link}")
async def get_shared_query(shareable_link: str):
    """Get shared query by link."""
    supabase = get_supabase_client()
    
    dossier = supabase.table("research_intelligence_dossiers")\
        .select("*, research_intelligence_queries(*)")\
        .eq("shareable_link", shareable_link)\
        .single()\
        .execute()
    
    if not dossier.data:
        raise HTTPException(404, "Shared query not found")
    
    # Check expiration
    if dossier.data.get("shareable_expires_at"):
        if datetime.now() > dossier.data["shareable_expires_at"]:
            raise HTTPException(410, "Shared link has expired")
    
    return {
        "dossier": dossier.data,
        "query": dossier.data["research_intelligence_queries"]
    }
```

**Acceptance Criteria**:
- ✅ Unique shareable links generated
- ✅ Expiration support
- ✅ Password protection (optional)
- ✅ Public access without auth

---

## 📋 PHASE 4: ADVANCED FEATURES (Week 4)

### **Goal**: Query comparison, evolution tracking, templates

### **Task 4.1: Query Comparison**
**File**: `oncology-coPilot/oncology-frontend/src/components/research/QueryComparison.jsx`

```javascript
export default function QueryComparison({ query1, query2 }) {
  // Compare mechanisms
  // Compare evidence tiers
  // Show differences
  // Highlight new findings
}
```

**Acceptance Criteria**:
- ✅ Side-by-side comparison
- ✅ Differences highlighted
- ✅ New findings identified
- ✅ Evolution tracked

---

## 🎯 SUCCESS METRICS

### **Patient Experience**
- ✅ Can understand results without medical training
- ✅ Can share research with doctor
- ✅ Can save and review past queries
- ✅ Gets actionable recommendations

### **Doctor Experience**
- ✅ Gets clinical decision support
- ✅ Can add to patient record
- ✅ Can track research over time
- ✅ Gets evidence grading

### **R&D Experience**
- ✅ Gets comprehensive research landscape
- ✅ Identifies knowledge gaps
- ✅ Tracks research evolution
- ✅ Generates research reports

---

## 📝 IMPLEMENTATION CHECKLIST

### **Week 1: Foundation**
- [ ] Database schema created
- [ ] Auto-save queries implemented
- [ ] Basic dossier generator created
- [ ] Query history UI added

### **Week 2: Patient Experience**
- [ ] Language translation service created
- [ ] Value synthesis service created
- [ ] Persona selector added
- [ ] Patient-friendly view implemented

### **Week 3: Value Delivery**
- [ ] PDF generation implemented
- [ ] Shareable links created
- [ ] Email summaries added
- [ ] Executive summary generation

### **Week 4: Advanced Features**
- [ ] Query comparison implemented
- [ ] Evolution tracking added
- [ ] Templates created
- [ ] Advanced customization

---

## 🚀 READY TO SHIP

Once all phases complete, Research Intelligence will be:
- ✅ **Patient-ready** - Beautiful, understandable, shareable
- ✅ **Doctor-ready** - Clinical decision support, evidence grading
- ✅ **R&D-ready** - Comprehensive research landscape, knowledge gaps

**Value Delivered**: Transform from "data dump" to "actionable insights"

