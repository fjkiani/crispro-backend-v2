"""
MOAT Integrator

Connects research findings to MOAT framework for mechanism analysis.
"""

import logging
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class MOATIntegrator:
    """
    Connects research findings to MOAT framework.
    """
    
    def __init__(self):
        pass
    
    async def integrate_with_moat(
        self,
        synthesized_findings: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Map research findings to MOAT capabilities.
        
        Args:
            synthesized_findings: LLM-synthesized findings
            context: Patient context (disease, treatment_line, biomarkers)
        
        Returns:
        {
            "pathways": [...],
            "mechanisms": [...],
            "treatment_line_analysis": {...},
            "biomarker_analysis": {...},
            "pathway_alignment": {...}
        }
        """
        mechanisms = synthesized_findings.get("mechanisms", [])
        
        # Map mechanisms to pathways
        pathways = []
        pathway_scores = {}
        
        for mech in mechanisms:
            mechanism_name = mech.get("mechanism", "").lower()
            pathway = self._map_mechanism_to_pathway(mechanism_name)
            
            if pathway:
                pathways.append(pathway)
                # Score based on confidence
                confidence = mech.get("confidence", 0.5)
                pathway_scores[pathway] = max(
                    pathway_scores.get(pathway, 0),
                    confidence
                )
        
        # Get treatment line analysis
        treatment_line_analysis = self._analyze_treatment_line(
            mechanisms,
            context.get("treatment_line")
        )
        
        # Get biomarker analysis
        biomarker_analysis = self._analyze_biomarkers(
            mechanisms,
            context.get("biomarkers", {})
        )
        
        # [NEW] Cross-resistance analysis
        cross_resistance = await self._analyze_cross_resistance(
            mechanisms,
            synthesized_findings,
            context
        )
        
        # [NEW] Toxicity mitigation analysis
        toxicity_mitigation = self._analyze_toxicity_mitigation(
            mechanisms,
            synthesized_findings,
            context
        )
        
        # [NEW] SAE feature extraction
        sae_features = self._extract_sae_features(
            mechanisms,
            pathway_scores,
            context
        )
        
        # [NEW] S/P/E Framework Integration (mechanism vector + insight chips)
        spe_framework = self._integrate_spe_framework(
            mechanisms,
            pathway_scores,
            sae_features,
            context
        )
        
        # [NEW] Toxicity Risk Assessment Integration
        toxicity_risk = await self._assess_toxicity_risk(
            mechanisms,
            synthesized_findings,
            context
        )
        
        # [NEW] Dosing Guidance Integration
        dosing_guidance = await self._compute_dosing_guidance(
            mechanisms,
            synthesized_findings,
            context
        )
        
        return {
            "pathways": list(set(pathways)),  # Deduplicate
            "mechanisms": mechanisms,
            "pathway_scores": pathway_scores,
            "treatment_line_analysis": treatment_line_analysis,
            "biomarker_analysis": biomarker_analysis,
            "cross_resistance": cross_resistance,  # NEW
            "toxicity_mitigation": toxicity_mitigation,  # NEW
            "sae_features": sae_features,  # NEW
            "mechanism_vector": spe_framework.get("mechanism_vector"),  # NEW: 7D vector
            "insight_chips": spe_framework.get("insight_chips"),  # NEW
            "pathway_aggregation": spe_framework.get("pathway_aggregation"),  # NEW
            "toxicity_risk": toxicity_risk,  # NEW
            "dosing_guidance": dosing_guidance,  # NEW
            "overall_confidence": synthesized_findings.get("overall_confidence", 0.5)
        }
    
    def _map_mechanism_to_pathway(self, mechanism: str) -> Optional[str]:
        """Map mechanism name to cancer pathway."""
        mechanism_lower = mechanism.lower()
        
        pathway_map = {
            "angiogenesis": "angiogenesis",
            "vegf": "angiogenesis",
            "vascular": "angiogenesis",
            "inflammation": "inflammation",
            "nf-κb": "inflammation",
            "nfkb": "inflammation",
            "cox": "inflammation",
            "il-6": "inflammation",
            "tnf": "inflammation",
            "dna repair": "dna_repair",
            "dna_repair": "dna_repair",
            "brca": "dna_repair",
            "parp": "dna_repair",
            "homologous recombination": "dna_repair",
            "apoptosis": "apoptosis",
            "cell death": "apoptosis",
            "caspase": "apoptosis",
            "bcl": "apoptosis",
            "cell cycle": "cell_cycle",
            "cdk": "cell_cycle",
            "cyclin": "cell_cycle",
            "metabolism": "metabolism",
            "mtor": "metabolism",
            "pi3k": "metabolism",
            "akt": "metabolism",
            "glycolysis": "metabolism",
            "oxidative stress": "oxidative_stress",
            "antioxidant": "oxidative_stress",
            "ros": "oxidative_stress"
        }
        
        for key, pathway in pathway_map.items():
            if key in mechanism_lower:
                return pathway
        
        return None
    
    def _analyze_treatment_line(
        self,
        mechanisms: List[Dict[str, Any]],
        treatment_line: Optional[str]
    ) -> Dict[str, Any]:
        """Analyze treatment line appropriateness."""
        if not treatment_line:
            return {"score": 0.5, "status": "unknown"}
        
        # Recovery mechanisms are better for L2/L3
        recovery_keywords = ["dna repair", "antioxidant", "recovery", "support"]
        has_recovery = any(
            any(kw in mech.get("mechanism", "").lower() for kw in recovery_keywords)
            for mech in mechanisms
        )
        
        line_num = self._parse_treatment_line(treatment_line)
        
        if has_recovery and line_num >= 2:
            return {"score": 0.9, "status": "highly_appropriate", "reason": "Recovery mechanisms match post-treatment context"}
        elif has_recovery and line_num == 1:
            return {"score": 0.6, "status": "moderate", "reason": "Recovery mechanisms less relevant for first-line"}
        else:
            return {"score": 0.7, "status": "appropriate", "reason": "General mechanisms applicable"}
    
    def _analyze_biomarkers(
        self,
        mechanisms: List[Dict[str, Any]],
        biomarkers: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze biomarker matches."""
        matches = []
        
        # HRD+ → DNA repair mechanisms
        if biomarkers.get("HRD") == "POSITIVE":
            dna_repair_mechs = [
                mech for mech in mechanisms
                if "dna" in mech.get("mechanism", "").lower() or "repair" in mech.get("mechanism", "").lower()
            ]
            if dna_repair_mechs:
                matches.append({
                    "biomarker": "HRD+",
                    "matched_mechanisms": [m.get("mechanism") for m in dna_repair_mechs],
                    "score": 0.9
                })
        
        # TMB-H → Immune mechanisms
        if biomarkers.get("TMB", 0) >= 10:
            immune_mechs = [
                mech for mech in mechanisms
                if "immune" in mech.get("mechanism", "").lower() or "inflammation" in mech.get("mechanism", "").lower()
            ]
            if immune_mechs:
                matches.append({
                    "biomarker": "TMB-H",
                    "matched_mechanisms": [m.get("mechanism") for m in immune_mechs],
                    "score": 0.8
                })
        
        return {
            "matches": matches,
            "total_matches": len(matches)
        }
    
    def _parse_treatment_line(self, treatment_line: str) -> int:
        """Parse treatment line to number."""
        line_lower = treatment_line.lower()
        if "l1" in line_lower or "first" in line_lower:
            return 1
        elif "l2" in line_lower or "second" in line_lower:
            return 2
        elif "l3" in line_lower or "third" in line_lower:
            return 3
        else:
            return 1  # Default
    
    async def _analyze_cross_resistance(
        self,
        mechanisms: List[Dict[str, Any]],
        synthesized_findings: Dict[str, Any],
        context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Analyze cross-resistance patterns using ResistancePlaybookService.
        
        Returns:
        [
            {
                "current_drug": "platinum_agent",
                "potential_drug": "alternative_drug",
                "drug_class": "drug_class",
                "resistance_risk": 0.4,
                "mechanism": "TP53",
                "evidence": "...",
                "evidence_level": "VALIDATED"
            },
            ...
        ]
        """
        try:
            from api.services.resistance_playbook_service import ResistancePlaybookService
            playbook = ResistancePlaybookService()
        except ImportError:
            logger.debug("ResistancePlaybookService not available")
            return []
        
        current_drug_class = context.get("current_drug_class")
        treatment_line = context.get("treatment_line", 1)
        disease = context.get("disease", "ovarian")  # Default to ovarian
        
        if not current_drug_class or not mechanisms:
            return []
        
        # Map mechanisms to detected resistance genes
        detected_resistance = self._extract_resistance_genes_from_mechanisms(mechanisms)
        
        if not detected_resistance:
            return []
        
        try:
            # Get next-line options (includes cross-resistance analysis)
            playbook_result = await playbook.get_next_line_options(
                disease=disease,
                detected_resistance=detected_resistance,
                current_drug_class=current_drug_class,
                treatment_line=treatment_line,
                prior_therapies=context.get("prior_therapies", [])
            )
            
            # Extract cross-resistance patterns from playbook result
            cross_resistance = []
            for alt in playbook_result.alternatives:
                # Check if this alternative has cross-resistance risk (lower priority suggests cross-resistance)
                if alt.priority > 3:  # Lower priority = higher number
                    cross_resistance.append({
                        "current_drug": current_drug_class,
                        "potential_drug": alt.drug,
                        "drug_class": alt.drug_class,
                        "resistance_risk": 0.4,  # Derived from priority (would be more sophisticated)
                        "mechanism": alt.source_gene,
                        "evidence": alt.rationale,
                        "evidence_level": alt.evidence_level.value if hasattr(alt.evidence_level, 'value') else str(alt.evidence_level)
                    })
            
            return cross_resistance
        except Exception as e:
            logger.warning(f"Cross-resistance analysis failed: {e}")
            return []
    
    def _extract_resistance_genes_from_mechanisms(self, mechanisms: List[Dict[str, Any]]) -> List[str]:
        """Extract resistance gene names from mechanisms."""
        # Common resistance genes that appear in mechanisms
        resistance_genes = []
        known_resistance_genes = ["TP53", "BRCA1", "BRCA2", "DIS3", "NF1", "PIK3CA", "ABCB1", "SLFN11"]
        
        for mech in mechanisms:
            mechanism_name = mech.get("mechanism", "").upper()
            target = mech.get("target", "").upper()
            
            # Check if mechanism or target matches known resistance genes
            for gene in known_resistance_genes:
                if gene in mechanism_name or gene in target:
                    if gene not in resistance_genes:
                        resistance_genes.append(gene)
        
        return resistance_genes
    
    def _analyze_toxicity_mitigation(
        self,
        mechanisms: List[Dict[str, Any]],
        synthesized_findings: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Analyze toxicity mitigation using pathway overlap and mitigating foods.
        
        Returns:
        {
            "pathway_overlap": {...},
            "mitigating_foods": [...],
            "risk_level": "HIGH" | "MODERATE" | "LOW",
            "max_overlap_score": 0.9
        }
        """
        try:
            from api.services.toxicity_pathway_mappings import (
                compute_pathway_overlap,
                get_mitigating_foods
            )
        except ImportError:
            logger.debug("toxicity_pathway_mappings not available")
            return {}
        
        germline_genes = context.get("germline_genes", [])
        drug_moa = context.get("drug_moa")  # From research findings or context
        
        # Extract drug MoA from mechanisms if not provided
        if not drug_moa and mechanisms:
            # Use first mechanism as proxy for drug MoA
            first_mech = mechanisms[0].get("mechanism", "")
            drug_moa = first_mech.lower().replace("_", " ")
        
        if not germline_genes or not drug_moa:
            return {}
        
        try:
            # Compute pathway overlap
            pathway_overlaps = compute_pathway_overlap(germline_genes, drug_moa)
            
            # Get mitigating foods
            mitigating_foods = get_mitigating_foods(pathway_overlaps)
            
            # Compute risk level from pathway overlap scores
            max_overlap = max(pathway_overlaps.values()) if pathway_overlaps else 0.0
            risk_level = "HIGH" if max_overlap > 0.7 else "MODERATE" if max_overlap > 0.4 else "LOW"
            
            return {
                "pathway_overlap": pathway_overlaps,
                "mitigating_foods": mitigating_foods,
                "risk_level": risk_level,
                "max_overlap_score": max_overlap
            }
        except Exception as e:
            logger.warning(f"Toxicity mitigation analysis failed: {e}")
            return {}
    
    def _extract_sae_features(
        self,
        mechanisms: List[Dict[str, Any]],
        pathway_scores: Dict[str, float],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Extract SAE features (DNA repair capacity, 7D mechanism vector).
        
        Returns:
        {
            "dna_repair_capacity": 0.74,
            "mechanism_vector": [0.8, 0.2, 0.3, 0.5, 0.0, 0.0, 0.3],
            "resistance_signals": ["HRD_DROP"],
            "pathway_burdens": {...}
        }
        """
        try:
            from api.services.sae_feature_service import SAEFeatureService
        except ImportError:
            logger.debug("SAEFeatureService not available")
            return {}
        
        tumor_context = context.get("tumor_context", {})
        insights_bundle = context.get("insights_bundle", {})
        
        # Fix: Handle string inputs (convert to dict if needed)
        if isinstance(tumor_context, str):
            try:
                import json
                tumor_context = json.loads(tumor_context)
            except:
                tumor_context = {}
        if not isinstance(tumor_context, dict):
            tumor_context = {}
        
        if isinstance(insights_bundle, str):
            try:
                import json
                insights_bundle = json.loads(insights_bundle)
            except:
                insights_bundle = {}
        if not isinstance(insights_bundle, dict):
            insights_bundle = {}
        
        if not mechanisms or not pathway_scores:
            return {}
        
        try:
            sae_service = SAEFeatureService()
            
            # Convert pathway_scores to format expected by SAEFeatureService
            # SAE service expects pathway_scores with keys like "ddr", "mapk", etc.
            sae_pathway_scores = self._convert_to_sae_pathway_scores(pathway_scores)
            
            # Extract SAE features from mechanisms
            sae_features = sae_service.compute_sae_features(
                insights_bundle=insights_bundle,
                pathway_scores=sae_pathway_scores,
                tumor_context=tumor_context,
                treatment_history=context.get("treatment_history", []),
                ca125_intelligence=context.get("ca125_intelligence")
            )
            
            return {
                "dna_repair_capacity": sae_features.dna_repair_capacity,
                "mechanism_vector": sae_features.mechanism_vector,
                "resistance_signals": sae_features.resistance_signals,
                "pathway_burdens": {
                    "ddr": sae_features.pathway_burdens.get("ddr", 0.0),
                    "mapk": sae_features.pathway_burdens.get("mapk", 0.0),
                    "pi3k": sae_features.pathway_burdens.get("pi3k", 0.0),
                    "vegf": sae_features.pathway_burdens.get("vegf", 0.0),
                    "her2": sae_features.pathway_burdens.get("her2", 0.0)
                }
            }
        except Exception as e:
            logger.warning(f"SAE feature extraction failed: {e}")
            return {}
    
    def _convert_to_sae_pathway_scores(self, pathway_scores: Dict[str, float]) -> Dict[str, float]:
        """Convert pathway scores to SAE format (ddr, mapk, pi3k, vegf, her2)."""
        sae_scores = {
            "ddr": 0.0,
            "mapk": 0.0,
            "pi3k": 0.0,
            "vegf": 0.0,
            "her2": 0.0
        }
        
        # Map pathway names to SAE pathway keys
        pathway_mapping = {
            "dna_repair": "ddr",
            "dna repair": "ddr",
            "angiogenesis": "vegf",
            "metabolism": "pi3k",
            "pi3k": "pi3k",
            "akt": "pi3k",
            "mtor": "pi3k"
        }
        
        for pathway, score in pathway_scores.items():
            pathway_lower = pathway.lower()
            for key, sae_key in pathway_mapping.items():
                if key in pathway_lower:
                    sae_scores[sae_key] = max(sae_scores[sae_key], score)
                    break
        
        return sae_scores
    
    def _integrate_spe_framework(
        self,
        mechanisms: List[Dict[str, Any]],
        pathway_scores: Dict[str, float],
        sae_features: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Integrate S/P/E Framework (Sequence/Pathway/Evidence).
        
        Returns:
        {
            "mechanism_vector": [0.8, 0.2, 0.3, 0.5, 0.0, 0.0, 0.3],  # 7D vector
            "insight_chips": {
                "functionality": 0.60,
                "regulatory": 0.12,
                "essentiality": 0.35,
                "chromatin": 0.58
            },
            "pathway_aggregation": {
                "ddr": 0.8,
                "mapk": 0.2,
                "pi3k": 0.3,
                "vegf": 0.5,
                "her2": 0.0
            }
        }
        """
        try:
            from api.services.pathway_to_mechanism_vector import convert_pathway_scores_to_mechanism_vector
        except ImportError:
            logger.debug("pathway_to_mechanism_vector not available")
            return {}
        
        tumor_context = context.get("tumor_context", {})
        insights_bundle = context.get("insights_bundle", {})
        
        # Use SAE mechanism vector if available, otherwise compute from pathway scores
        mechanism_vector = None
        if sae_features.get("mechanism_vector"):
            mechanism_vector = sae_features["mechanism_vector"]
        else:
            # Convert pathway scores to 7D mechanism vector
            sae_pathway_scores = self._convert_to_sae_pathway_scores(pathway_scores)
            
            if sae_pathway_scores:
                try:
                    mechanism_vector, dimension_used = convert_pathway_scores_to_mechanism_vector(
                        sae_pathway_scores,
                        tumor_context=tumor_context,
                        tmb=tumor_context.get("tmb_score", 0.0),
                        msi_status=tumor_context.get("msi_status", "Unknown"),
                        use_7d=True
                    )
                except Exception as e:
                    logger.debug(f"Failed to convert pathway scores to mechanism vector: {e}")
                    mechanism_vector = None
        
        # Extract insight chips from insights_bundle
        insight_chips = {
            "functionality": insights_bundle.get("functionality", 0.0),
            "regulatory": insights_bundle.get("regulatory", 0.0),
            "essentiality": insights_bundle.get("essentiality", 0.0),
            "chromatin": insights_bundle.get("chromatin", 0.0)
        }
        
        # Pathway aggregation (from pathway_scores)
        pathway_aggregation = self._convert_to_sae_pathway_scores(pathway_scores)
        
        return {
            "mechanism_vector": mechanism_vector,
            "insight_chips": insight_chips,
            "pathway_aggregation": pathway_aggregation
        }
    
    async def rank_trials_by_mechanism_fit(
        self,
        mechanisms: List[Dict[str, Any]],
        trials: List[Dict[str, Any]],
        sae_mechanism_vector: Optional[List[float]] = None
    ) -> List[Dict[str, Any]]:
        """
        Rank trials by mechanism fit using SAE mechanism vectors.
        
        Uses mechanism_fit_ranker service for cosine similarity.
        
        Args:
            mechanisms: List of mechanism dicts from synthesized_findings
            trials: List of trial dicts (from ClinicalTrials.gov or other sources)
            sae_mechanism_vector: Optional 7D mechanism vector (if already computed)
        
        Returns:
            Ranked trials with mechanism_fit_score and mechanism_alignment
        """
        try:
            from api.services.mechanism_fit_ranker import MechanismFitRanker
            ranker = MechanismFitRanker(alpha=0.7, beta=0.3)  # Manager's P4 formula
        except ImportError:
            logger.warning("MechanismFitRanker not available, returning unranked trials")
            return trials
        
        # Extract or compute mechanism vector
        if not sae_mechanism_vector:
            # Compute from mechanisms (fallback)
            pathway_scores = {}
            for mech in mechanisms:
                mechanism_name = mech.get("mechanism", "").lower()
                pathway = self._map_mechanism_to_pathway(mechanism_name)
                if pathway:
                    confidence = mech.get("confidence", 0.5)
                    pathway_scores[pathway] = max(pathway_scores.get(pathway, 0), confidence)
            
            sae_pathway_scores = self._convert_to_sae_pathway_scores(pathway_scores)
            # Convert to 7D vector (simplified - would need full SAE service for accurate conversion)
            sae_mechanism_vector = [
                sae_pathway_scores.get("ddr", 0.0),
                sae_pathway_scores.get("mapk", 0.0),
                sae_pathway_scores.get("pi3k", 0.0),
                sae_pathway_scores.get("vegf", 0.0),
                sae_pathway_scores.get("her2", 0.0),
                0.0,  # IO (would need TMB/MSI from tumor context)
                0.0   # Efflux (would need treatment history analysis)
            ]
        
        # Ensure trials have eligibility_score (required by ranker)
        for trial in trials:
            if "eligibility_score" not in trial:
                trial["eligibility_score"] = 0.7  # Default eligibility
        
        # Rank trials
        try:
            ranked_scores = ranker.rank_trials(
                trials=trials,
                sae_mechanism_vector=sae_mechanism_vector,
                min_eligibility=0.60,
                min_mechanism_fit=0.50
            )
            
            # Convert TrialMechanismScore back to trial dicts
            ranked_trials = []
            for score in ranked_scores:
                # Find matching trial
                trial = next((t for t in trials if t.get("nct_id") == score.nct_id), None)
                if trial:
                    trial["mechanism_fit_score"] = score.mechanism_fit_score
                    trial["combined_score"] = score.combined_score
                    trial["mechanism_alignment"] = score.mechanism_alignment
                    trial["mechanism_alignment_level"] = "HIGH" if score.mechanism_fit_score > 0.7 else "MODERATE" if score.mechanism_fit_score > 0.5 else "LOW"
                    trial["boost_applied"] = score.boost_applied
                    ranked_trials.append(trial)
            
            return ranked_trials
        except Exception as e:
            logger.warning(f"Trial ranking failed: {e}")
            return trials
    
    async def _assess_toxicity_risk(
        self,
        mechanisms: List[Dict[str, Any]],
        synthesized_findings: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Assess toxicity risk using SafetyService.
        
        Returns:
        {
            "risk_score": 0.4,
            "risk_level": "MODERATE",
            "confidence": 0.85,
            "reason": "...",
            "contributing_factors": [...],
            "mitigating_foods": [...]
        }
        """
        try:
            from api.services.safety_service import get_safety_service
            from api.schemas.safety import ToxicityRiskRequest, PatientContext, TherapeuticCandidate, ClinicalContext
        except ImportError:
            logger.debug("SafetyService not available")
            return {}
        
        germline_variants = context.get("germline_variants", [])
        drug_moa = context.get("drug_moa")  # From research findings or context
        disease = context.get("disease", "")
        
        # Extract drug MoA from mechanisms if not provided
        if not drug_moa and mechanisms:
            first_mech = mechanisms[0].get("mechanism", "")
            drug_moa = first_mech.lower().replace("_", " ")
        
        if not germline_variants or not drug_moa:
            return {}
        
        try:
            safety_service = get_safety_service()
            
            # Build ToxicityRiskRequest
            patient_context = PatientContext(
                germlineVariants=[
                    {"gene": v.get("gene"), "hgvs": v.get("hgvs", "")}
                    for v in germline_variants
                ]
            )
            
            therapeutic_candidate = TherapeuticCandidate(
                type="drug",
                moa=drug_moa
            )
            
            clinical_context = ClinicalContext(
                disease=disease,
                tissue=context.get("tissue")
            )
            
            toxicity_request = ToxicityRiskRequest(
                patient=patient_context,
                candidate=therapeutic_candidate,
                context=clinical_context,
                options={"profile": context.get("profile", "baseline")}
            )
            
            # Compute toxicity risk
            toxicity_response = await safety_service.compute_toxicity_risk(toxicity_request)
            
            # Derive risk level from risk score
            risk_level = "HIGH" if toxicity_response.risk_score >= 0.5 else \
                       "MODERATE" if toxicity_response.risk_score >= 0.3 else "LOW"
            
            return {
                "risk_score": toxicity_response.risk_score,
                "risk_level": risk_level,
                "confidence": toxicity_response.confidence,
                "reason": toxicity_response.reason,
                "contributing_factors": [
                    {
                        "type": f.type,
                        "detail": f.detail,
                        "weight": f.weight,
                        "confidence": f.confidence
                    }
                    for f in toxicity_response.factors
                ],
                "mitigating_foods": toxicity_response.mitigating_foods
            }
        except Exception as e:
            logger.warning(f"Toxicity risk assessment failed: {e}")
            return {}
    
    async def _compute_dosing_guidance(
        self,
        mechanisms: List[Dict[str, Any]],
        synthesized_findings: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Compute dosing guidance using DosingGuidanceService.
        
        Returns:
        {
            "recommendations": [...],
            "cumulative_toxicity_alert": {...}
        }
        """
        try:
            from api.services.dosing_guidance_service import DosingGuidanceService
            from api.schemas.dosing import DosingGuidanceRequest
        except ImportError:
            logger.debug("DosingGuidanceService not available")
            return {}
        
        germline_variants = context.get("germline_variants", [])
        drug_name = context.get("drug_name")  # From research findings or context
        treatment_history = context.get("treatment_history", [])
        
        if not germline_variants or not drug_name:
            return {}
        
        try:
            dosing_service = DosingGuidanceService()
            
            # Extract pharmacogene variants
            dosing_recommendations = []
            cumulative_alert = None
            
            for variant in germline_variants:
                gene = variant.get("gene")
                hgvs = variant.get("hgvs", "")
                
                # Check if this is a known pharmacogene
                pharmacogenes = ["DPYD", "UGT1A1", "TPMT", "CYP2D6", "CYP2C19"]
                if gene in pharmacogenes:
                    # Build DosingGuidanceRequest
                    dosing_request = DosingGuidanceRequest(
                        gene=gene,
                        variant=hgvs,
                        drug=drug_name,
                        standard_dose=context.get("standard_dose"),
                        treatment_line=context.get("treatment_line"),
                        prior_therapies=treatment_history,
                        disease=context.get("disease")
                    )
                    
                    # Get dosing guidance
                    dosing_response = await dosing_service.get_dosing_guidance(dosing_request)
                    
                    # Extract recommendations (FIXED: Using actual DosingRecommendation schema)
                    for rec in dosing_response.recommendations:
                        dosing_recommendations.append({
                            "gene": rec.gene,
                            "drug": rec.drug,  # ADDED: Was missing
                            "phenotype": rec.phenotype,
                            "cpic_level": rec.cpic_level.value if rec.cpic_level else None,  # FIXED: Handle None
                            "adjustment_type": rec.adjustment_type.value,  # Order fixed
                            "adjustment_factor": rec.adjustment_factor,
                            "recommendation": rec.recommendation,  # FIXED: This is the plain English recommendation
                            "rationale": rec.rationale,
                            "monitoring": rec.monitoring,
                            "alternatives": rec.alternatives
                        })
                    
                    # Extract cumulative toxicity alert (FIXED: It's a string, not Dict!)
                    if dosing_response.cumulative_toxicity_alert:
                        cumulative_alert = {
                            "alert_message": dosing_response.cumulative_toxicity_alert,  # String, not Dict
                            "type": "cumulative_toxicity_warning"
                        }
            
            if dosing_recommendations:
                return {
                    "recommendations": dosing_recommendations,
                    "cumulative_toxicity_alert": cumulative_alert
                }
            else:
                return {}
        except Exception as e:
            logger.warning(f"Dosing guidance integration failed: {e}")
            return {}










