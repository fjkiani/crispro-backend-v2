"""
MOAT Analysis Generator - Main orchestrator for comprehensive analysis.

Pulls together all sub-services to generate complete analysis documents.
"""

from typing import Dict, Any, List, Optional
import logging
import uuid
from datetime import datetime

from .genomic_analyzer import GenomicAnalyzer
from .drug_moa_explainer import DrugMoAExplainer
from .markdown_assembler import MarkdownAssembler
from .llm_explanation_enhancer import LLMExplanationEnhancer

# Import existing services
from api.services.nutrition.nutrition_agent import NutritionAgent
from api.services.safety_service import get_safety_service
from api.services.toxicity_pathway_mappings import get_drug_moa

logger = logging.getLogger(__name__)


class MOATAnalysisGenerator:
    """Generate comprehensive MOAT analysis documents."""
    
    def __init__(self):
        self.genomic_analyzer = GenomicAnalyzer()
        self.drug_moa_explainer = DrugMoAExplainer()
        self.markdown_assembler = MarkdownAssembler()
        self.llm_enhancer = LLMExplanationEnhancer()
        self.nutrition_agent = NutritionAgent()
        self.safety_service = get_safety_service()
    
    async def generate_comprehensive_analysis(
        self,
        patient_profile: Dict[str, Any],
        treatment_context: Dict[str, Any],
        use_llm: bool = True
    ) -> Dict[str, Any]:
        """
        Generate complete MOAT analysis like AK_CYCLE_2_MOAT_ANALYSIS.md
        
        Args:
            patient_profile: Full patient profile (demographics, disease, biomarkers, etc.)
            treatment_context: Treatment context (current_drugs, treatment_line, cycle_number, etc.)
            use_llm: Whether to use LLM for enhanced explanations (default: True)
        
        Returns:
            {
                'analysis_id': str,
                'markdown': str,  # Full markdown document
                'sections': Dict[str, Any],  # Structured data
                'metadata': Dict[str, Any]  # Generation metadata
            }
        """
        analysis_id = f"moat_analysis_{uuid.uuid4().hex[:12]}"
        
        try:
            # Step 1: Analyze genomics
            logger.info(f"[{analysis_id}] Analyzing genomics...")
            genomic_findings = self._analyze_genomics(patient_profile)
            
            # Step 2: Analyze drugs and toxicity
            logger.info(f"[{analysis_id}] Analyzing drugs and toxicity...")
            toxicity_assessment = await self._analyze_toxicity(
                patient_profile, treatment_context, genomic_findings
            )
            
            # Step 3: Generate nutrition protocol
            logger.info(f"[{analysis_id}] Generating nutrition protocol...")
            nutrition_protocol = await self._generate_nutrition_protocol(
                patient_profile, treatment_context, genomic_findings
            )
            
            # Step 4: Generate timing protocol
            logger.info(f"[{analysis_id}] Generating timing protocol...")
            timing_protocol = self._generate_timing_protocol(
                treatment_context, nutrition_protocol
            )
            
            # Step 5: Generate avoid list
            logger.info(f"[{analysis_id}] Generating avoid list...")
            avoid_list = self._generate_avoid_list(treatment_context)
            
            # Step 6: Generate treatment optimization
            logger.info(f"[{analysis_id}] Generating treatment optimization...")
            treatment_optimization = self._generate_treatment_optimization(
                genomic_findings, treatment_context
            )
            
            # Step 7: Generate action items
            logger.info(f"[{analysis_id}] Generating action items...")
            action_items = self._generate_action_items(
                nutrition_protocol, treatment_optimization, timing_protocol
            )
            
            # Step 8: Generate big picture
            logger.info(f"[{analysis_id}] Generating big picture...")
            big_picture = self._generate_big_picture(
                genomic_findings, toxicity_assessment, nutrition_protocol
            )
            
            # Assemble all sections
            sections = {
                "genomic_findings": genomic_findings,
                "toxicity_assessment": toxicity_assessment,
                "nutrition_protocol": nutrition_protocol,
                "timing_protocol": timing_protocol,
                "avoid_list": avoid_list,
                "treatment_optimization": treatment_optimization,
                "action_items": action_items,
                "big_picture": big_picture
            }
            
            # Step 9: Enhance with LLM explanations (if enabled)
            if use_llm:
                logger.info(f"[{analysis_id}] Enhancing with LLM explanations...")
                patient_context = {
                    "genomic_findings": genomic_findings,
                    "current_drugs": treatment_context.get("current_drugs", []),
                    "treatment_line": treatment_context.get("treatment_line", "first-line")
                }
                sections = await self.llm_enhancer.enhance_explanations(sections, patient_context)
            
            # Generate markdown
            logger.info(f"[{analysis_id}] Assembling markdown...")
            markdown = self.markdown_assembler.assemble_analysis(
                sections, patient_profile, treatment_context
            )
            
            metadata = {
                "analysis_id": analysis_id,
                "generated_at": datetime.now().isoformat(),
                "patient_id": patient_profile.get("demographics", {}).get("patient_id", "unknown"),
                "llm_enhanced": use_llm,
                "version": "1.0"
            }
            
            logger.info(f"[{analysis_id}] ✅ Analysis generation complete")
            
            return {
                "analysis_id": analysis_id,
                "markdown": markdown,
                "sections": sections,
                "metadata": metadata
            }
        
        except Exception as e:
            logger.error(f"[{analysis_id}] ❌ Analysis generation failed: {e}", exc_info=True)
            raise
    
    def _analyze_genomics(self, patient_profile: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze patient genomics."""
        # Extract variants from patient profile
        germline_variants = patient_profile.get("germline_variants", [])
        somatic_variants = patient_profile.get("somatic_variants", [])
        
        # If variants are in different format, try to extract
        if not germline_variants:
            biomarkers = patient_profile.get("biomarkers", {})
            mutations = patient_profile.get("mutations", [])
            
            # Try to extract from mutations
            for mut in mutations:
                if isinstance(mut, dict):
                    if mut.get("source") == "germline" or "germline" in str(mut).lower():
                        germline_variants.append(mut)
                    else:
                        somatic_variants.append(mut)
        
        return self.genomic_analyzer.analyze_critical_findings(
            germline_variants, somatic_variants
        )
    
    async def _analyze_toxicity(
        self,
        patient_profile: Dict[str, Any],
        treatment_context: Dict[str, Any],
        genomic_findings: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze toxicity risks for current drugs."""
        current_drugs = treatment_context.get("current_drugs", [])
        
        if not current_drugs:
            return {"drug_explanations": []}
        
        drug_explanations = []
        
        # Extract germline genes from genomic findings
        germline_genes = []
        for finding in genomic_findings.get("critical_findings", []):
            gene = finding.get("gene", "")
            if gene and finding.get("source") == "germline":
                germline_genes.append(gene)
        
        for drug in current_drugs:
            explanation = self.drug_moa_explainer.explain_drug_mechanism(
                drug, genomic_findings, germline_genes
            )
            drug_explanations.append(explanation)
        
        return {
            "drug_explanations": drug_explanations
        }
    
    async def _generate_nutrition_protocol(
        self,
        patient_profile: Dict[str, Any],
        treatment_context: Dict[str, Any],
        genomic_findings: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate nutrition protocol."""
        # Extract data for nutrition agent
        patient_id = patient_profile.get("demographics", {}).get("patient_id", "unknown")
        
        # Build mutations list from genomic findings
        mutations = []
        germline_genes = []
        for finding in genomic_findings.get("critical_findings", []):
            if finding.get("source") == "germline":
                gene = finding.get("gene", "")
                if gene:
                    germline_genes.append(gene)
                    mutations.append({
                        "gene": gene,
                        "hgvs_p": finding.get("variant", ""),
                        "classification": finding.get("classification", "unknown")
                    })
        
        current_drugs = treatment_context.get("current_drugs", [])
        treatment_line = treatment_context.get("treatment_line", "first-line")
        disease = patient_profile.get("disease", {}).get("name", "ovarian_cancer_hgs")
        
        # Generate nutrition plan
        nutrition_plan = await self.nutrition_agent.generate_nutrition_plan(
            patient_id=patient_id,
            mutations=mutations,
            germline_genes=germline_genes,
            current_drugs=current_drugs,
            disease=disease,
            treatment_line=treatment_line
        )
        
        # Convert to dict if it's a dataclass
        if hasattr(nutrition_plan, 'to_dict'):
            nutrition_plan_dict = nutrition_plan.to_dict()
        else:
            nutrition_plan_dict = nutrition_plan
        
        # Format supplements with mechanisms
        supplements = []
        for supp in nutrition_plan_dict.get("supplements", []):
            supplements.append({
                "compound": supp.get("name", ""),
                "score": 0.85,  # Default MOAT score (can be enhanced later)
                "mechanism": supp.get("mechanism", "Supports treatment"),
                "rationale": supp.get("llm_rationale") or supp.get("mechanism", "Recommended for your profile"),
                "dose": supp.get("dosage", ""),
                "timing": supp.get("timing", "")
            })
        
        return {
            "supplements": supplements,
            "nutrition_plan": nutrition_plan_dict
        }
    
    def _generate_timing_protocol(
        self,
        treatment_context: Dict[str, Any],
        nutrition_protocol: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate day-by-day timing protocol."""
        current_drugs = treatment_context.get("current_drugs", [])
        cycle_day = treatment_context.get("cycle_number", 1)
        
        pre_infusion = {
            "Day -3 to -1": [
                "Start Ginger 1g with each meal (anti-emetic)",
                "Start Vitamin B6 25mg TID (anti-emetic synergy)",
                "Continue Vitamin D 5000 IU daily (DNA repair support)",
                "Hydration: 2-3L water daily"
            ],
            "Day 0 (Infusion Day)": [
                "Continue all above EXCEPT NAC",
                "⚠️ STOP NAC 24h before infusion (antioxidant interference)",
                "Light meal before treatment",
                "No grapefruit (CYP3A4 interaction)"
            ]
        }
        
        post_infusion = {
            "Days 1-3 (Acute Phase)": [
                "RESUME NAC 600mg BID (wait 24h post-infusion)",
                "Continue antiemetics as prescribed",
                "High hydration: 3L daily minimum",
                "Monitor: Temperature, urine output"
            ],
            "Days 4-10 (Recovery Phase)": [
                "Continue NAC, Vitamin D, Omega-3",
                "Add L-glutamine 10g TID (gut/immune support)",
                "Add Zinc 30mg daily (immune support)",
                "Alpha-lipoic acid 600mg daily (neuropathy prevention)",
                "Monitor: CBC at day 7-10 (nadir period)"
            ],
            "Days 11-21 (Between Cycles)": [
                "Continue all supplements",
                "Focus on nutrition, protein intake",
                "Gentle activity as tolerated",
                "Report any numbness/tingling immediately"
            ]
        }
        
        return {
            "pre_infusion": pre_infusion,
            "post_infusion": post_infusion
        }
    
    def _generate_avoid_list(self, treatment_context: Dict[str, Any]) -> Dict[str, Any]:
        """Generate avoid list."""
        current_drugs = treatment_context.get("current_drugs", [])
        
        absolute_avoid = [
            {
                "item": "Grapefruit/pomelo",
                "reason": "inhibits CYP3A4 → paclitaxel toxicity"
            },
            {
                "item": "St. John's Wort",
                "reason": "induces CYP3A4 → reduces drug efficacy"
            },
            {
                "item": "High-dose Vitamin C DURING infusion",
                "reason": "may protect tumor cells"
            }
        ]
        
        timing_critical = [
            {
                "item": "NAC",
                "rationale": "Stop 24h before, resume 24h after infusion"
            },
            {
                "item": "Antioxidants (high-dose)",
                "rationale": "Avoid on infusion day only"
            }
        ]
        
        return {
            "absolute_avoid": absolute_avoid,
            "timing_critical": timing_critical
        }
    
    def _generate_treatment_optimization(
        self,
        genomic_findings: Dict[str, Any],
        treatment_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate treatment optimization recommendations."""
        tests_to_request = []
        
        # Check for MBD4 or other hypermutator genes
        critical_findings = genomic_findings.get("critical_findings", [])
        for finding in critical_findings:
            gene = finding.get("gene", "")
            implications = genomic_findings.get("clinical_implications", {}).get(gene, "")
            
            if "hypermutator" in implications.lower() or gene == "MBD4":
                tests_to_request.append({
                    "name": "Tumor Mutational Burden (TMB)",
                    "how": "Counts mutations in tumor DNA per million bases",
                    "why": f"{gene} loss → hypermutator → likely high TMB",
                    "action": "Pembrolizumab eligible if ≥10 mut/Mb"
                })
                
                tests_to_request.append({
                    "name": "Microsatellite Instability (MSI)",
                    "how": "Tests if DNA repeats are unstable",
                    "why": f"{gene} deficiency may cause MSI-like phenotype",
                    "action": "Pembrolizumab if MSI-H"
                })
            
            if "ber_deficiency" in implications.lower() or "hrd" in implications.lower():
                tests_to_request.append({
                    "name": "HRD Score",
                    "how": "Measures if tumor can't repair double-strand breaks",
                    "why": f"{gene} loss may create HRD-like state",
                    "action": "PARP inhibitor maintenance if HRD+"
                })
        
        return {
            "tests_to_request": tests_to_request
        }
    
    def _generate_action_items(
        self,
        nutrition_protocol: Dict[str, Any],
        treatment_optimization: Dict[str, Any],
        timing_protocol: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate action items checklist."""
        immediate = [
            "Start Vitamin D 5000 IU daily",
            "Start Omega-3 2g daily",
            "Ensure high hydration (3L/day)"
        ]
        
        post_cycle = [
            "Resume NAC 600mg BID (24h after infusion)",
            "Add L-glutamine 10g TID",
            "Add Alpha-lipoic acid 600mg daily"
        ]
        
        testing = []
        for test in treatment_optimization.get("tests_to_request", []):
            testing.append(f"Request {test.get('name', '')}")
        
        return {
            "immediate": immediate,
            "post_cycle": post_cycle,
            "testing": testing
        }
    
    def _generate_big_picture(
        self,
        genomic_findings: Dict[str, Any],
        toxicity_assessment: Dict[str, Any],
        nutrition_protocol: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate big picture explanation."""
        steps = [
            {
                "title": "Step 1: Your Genomics",
                "explanation": "Critical genomic findings affect how you respond to treatment"
            },
            {
                "title": "Step 2: How Drugs Work (For You)",
                "explanation": "Drug mechanisms interact with your genomic profile → specific risks"
            },
            {
                "title": "Step 3: Why Toxicity Happens",
                "explanation": "Your pathway deficiencies overlap with drug toxicity pathways"
            },
            {
                "title": "Step 4: Why Nutrition Matters",
                "explanation": "Supplements compensate for your specific pathway gaps"
            }
        ]
        
        bottom_line = (
            "This isn't random numbers - it's YOUR genomics → YOUR drug mechanism → "
            "YOUR pathway overlap → YOUR targeted mitigation. This is personalized precision oncology."
        )
        
        return {
            "steps": steps,
            "bottom_line": bottom_line
        }


# Singleton instance
_moat_generator = None

def get_moat_analysis_generator() -> MOATAnalysisGenerator:
    """Get singleton MOAT analysis generator instance."""
    global _moat_generator
    if _moat_generator is None:
        _moat_generator = MOATAnalysisGenerator()
    return _moat_generator

