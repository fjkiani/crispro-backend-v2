"""
Disease Module Loader Service

Loads disease-specific configuration YAML files and provides:
- Mechanism axis definitions (7D vector)
- Evidence gates
- Dominance policies
- Query templates
- Subtype discrimination
"""

import yaml
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Path to disease module configs
DISEASE_MODULES_DIR = Path(__file__).parent.parent / "resources" / "disease_modules"


@dataclass
class MechanismAxis:
    """Represents a mechanism axis in the 7D vector"""
    name: str
    vector_index: int
    biomarkers: List[str]
    pathways: List[str]
    interventions: List[str]
    priority: str
    description: str
    dominance_condition: Optional[str] = None


@dataclass
class EvidenceGate:
    """Represents an evidence gate that boosts mechanism axes"""
    name: str
    condition: str
    boosts: Dict[str, float]
    rationale: str


@dataclass
class DominancePolicy:
    """Represents a dominance policy for trial ranking"""
    name: str
    condition: str
    prioritize_axis: str
    deprioritize_axis: Optional[str] = None
    layer_axes: Optional[List[str]] = None
    rationale: str = ""


@dataclass
class QueryTemplate:
    """Represents a query template for CT.gov searches"""
    name: str
    query: str
    condition: str
    status: List[str]
    target_axis: str
    priority: int


@dataclass
class DiseaseModule:
    """Complete disease module configuration"""
    disease: str
    aliases: List[str]
    mechanism_axes: Dict[str, MechanismAxis]
    evidence_gates: List[EvidenceGate]
    dominance_policies: List[DominancePolicy]
    query_templates: List[QueryTemplate]
    subtypes: List[Dict[str, Any]]
    eligibility_patterns: Dict[str, List[str]]
    contraindications: List[Dict[str, Any]]
    explainability_fields: List[str]


class DiseaseModuleLoader:
    """Service for loading and managing disease-specific configurations"""
    
    def __init__(self):
        self._modules: Dict[str, DiseaseModule] = {}
        self._load_all_modules()
    
    def _load_all_modules(self):
        """Load all disease module YAML files"""
        if not DISEASE_MODULES_DIR.exists():
            logger.warning(f"Disease modules directory not found: {DISEASE_MODULES_DIR}")
            return
        
        for yaml_file in DISEASE_MODULES_DIR.glob("*.yaml"):
            try:
                disease_name = yaml_file.stem
                module = self._load_module(yaml_file)
                self._modules[disease_name] = module
                logger.info(f"✅ Loaded disease module: {disease_name}")
            except Exception as e:
                logger.error(f"❌ Failed to load {yaml_file}: {e}", exc_info=True)
    
    def _load_module(self, yaml_path: Path) -> DiseaseModule:
        """Load a single disease module from YAML"""
        with open(yaml_path, 'r') as f:
            data = yaml.safe_load(f)
        
        # Parse mechanism axes
        mechanism_axes = {}
        for axis_name, axis_data in data.get("mechanism_axes", {}).items():
            mechanism_axes[axis_name] = MechanismAxis(
                name=axis_data.get("name", axis_name),
                vector_index=axis_data.get("vector_index", 0),
                biomarkers=axis_data.get("biomarkers", []),
                pathways=axis_data.get("pathways", []),
                interventions=axis_data.get("interventions", []),
                priority=axis_data.get("priority", "medium"),
                description=axis_data.get("description", ""),
                dominance_condition=axis_data.get("dominance_condition")
            )
        
        # Parse evidence gates (can be dict or list, with different formats)
        evidence_gates = []
        gates_data = data.get("evidence_gates", {})
        if isinstance(gates_data, dict):
            # Format: {gate_name: {name: ..., condition: ...}} OR {gate_name: {condition: ..., score: ...}}
            for gate_name, gate_info in gates_data.items():
                if isinstance(gate_info, dict):
                    # Handle different boost formats
                    boosts = gate_info.get("boosts", {})
                    # If score is provided instead of boosts, create a boost dict
                    if not boosts and "score" in gate_info:
                        # Try to infer axis from gate name or use a default
                        axis_name = gate_name.replace("_strong", "").replace("_moderate", "").replace("_weak", "")
                        boosts = {axis_name: gate_info.get("score", 1.0)}
                    
                    evidence_gates.append(EvidenceGate(
                        name=gate_info.get("name", gate_name),
                        condition=gate_info.get("condition", ""),
                        boosts=boosts,
                        rationale=gate_info.get("rationale") or gate_info.get("description", "")
                    ))
        elif isinstance(gates_data, list):
            # Format: [{gate_name: {name: ...}}, ...] OR [{condition: ..., score: ...}, ...]
            for gate_item in gates_data:
                if isinstance(gate_item, dict):
                    if len(gate_item) == 1:
                        # Format: {gate_name: {name: ...}}
                        gate_name = list(gate_item.keys())[0]
                        gate_info = gate_item[gate_name]
                    else:
                        # Format: {condition: ..., score: ...} (direct format)
                        gate_name = gate_item.get("name", "gate")
                        gate_info = gate_item
                    
                    if isinstance(gate_info, dict):
                        boosts = gate_info.get("boosts", {})
                        if not boosts and "score" in gate_info:
                            axis_name = gate_name.replace("_strong", "").replace("_moderate", "").replace("_weak", "")
                            boosts = {axis_name: gate_info.get("score", 1.0)}
                        
                        evidence_gates.append(EvidenceGate(
                            name=gate_info.get("name", gate_name),
                            condition=gate_info.get("condition", ""),
                            boosts=boosts,
                            rationale=gate_info.get("rationale") or gate_info.get("description", "")
                        ))
        
        # Parse dominance policies (can be dict, list, or list of direct dicts)
        dominance_policies = []
        policies_data = data.get("dominance_policies", {})
        if isinstance(policies_data, dict):
            # Format: {policy_name: {name: ..., condition: ...}}
            for policy_name, policy_info in policies_data.items():
                if isinstance(policy_info, dict):
                    dominance_policies.append(DominancePolicy(
                        name=policy_info.get("name", policy_name),
                        condition=policy_info.get("condition", ""),
                        prioritize_axis=policy_info.get("prioritize_axis") or policy_info.get("dominant_axis", ""),
                        deprioritize_axis=policy_info.get("deprioritize_axis"),
                        layer_axes=policy_info.get("layer_axes"),
                        rationale=policy_info.get("rationale") or policy_info.get("description", "")
                    ))
        elif isinstance(policies_data, list):
            # Format: [{policy_name: {name: ...}}, ...] OR [{condition: ..., dominant_axis: ...}, ...]
            for policy_item in policies_data:
                if isinstance(policy_item, dict):
                    # Check if it's nested format
                    if len(policy_item) == 1:
                        # Format: {policy_name: {name: ...}}
                        policy_name = list(policy_item.keys())[0]
                        policy_info = policy_item[policy_name]
                    else:
                        # Format: {condition: ..., dominant_axis: ...} (direct format)
                        policy_name = policy_item.get("name", "policy")
                        policy_info = policy_item
                    
                    if isinstance(policy_info, dict):
                        dominance_policies.append(DominancePolicy(
                            name=policy_info.get("name", policy_name),
                            condition=policy_info.get("condition", ""),
                            prioritize_axis=policy_info.get("prioritize_axis") or policy_info.get("dominant_axis", ""),
                            deprioritize_axis=policy_info.get("deprioritize_axis"),
                            layer_axes=policy_info.get("layer_axes"),
                            rationale=policy_info.get("rationale") or policy_info.get("description", "")
                        ))
        
        # Parse query templates (can be dict or list, with different formats)
        query_templates = []
        templates_data = data.get("query_templates", {})
        if isinstance(templates_data, dict):
            # Format: {template_name: {name: ..., query: ...}}
            for template_name, template_info in templates_data.items():
                if isinstance(template_info, dict):
                    query_templates.append(QueryTemplate(
                        name=template_info.get("name", template_name),
                        query=template_info.get("query", ""),
                        condition=template_info.get("condition", ""),
                        status=template_info.get("status", []),
                        target_axis=template_info.get("target_axis") or template_info.get("axis", ""),
                        priority=template_info.get("priority", 2) if isinstance(template_info.get("priority"), int) else 2
                    ))
        elif isinstance(templates_data, list):
            # Format: [{template_name: {name: ...}}, ...] OR [{name: ..., query: ...}, ...]
            for template_item in templates_data:
                if isinstance(template_item, dict):
                    if len(template_item) == 1:
                        # Format: {template_name: {name: ...}}
                        template_name = list(template_item.keys())[0]
                        template_info = template_item[template_name]
                    else:
                        # Format: {name: ..., query: ...} (direct format)
                        template_name = template_item.get("name", "template")
                        template_info = template_item
                    
                    if isinstance(template_info, dict):
                        # Handle priority as string or int
                        priority = template_info.get("priority", 2)
                        if isinstance(priority, str):
                            priority_map = {"high": 1, "medium": 2, "low": 3}
                            priority = priority_map.get(priority.lower(), 2)
                        
                        query_templates.append(QueryTemplate(
                            name=template_info.get("name", template_name),
                            query=template_info.get("query", ""),
                            condition=template_info.get("condition", ""),
                            status=template_info.get("status", []),
                            target_axis=template_info.get("target_axis") or template_info.get("axis", ""),
                            priority=priority
                        ))
        
        return DiseaseModule(
            disease=data.get("disease", ""),
            aliases=data.get("aliases", []),
            mechanism_axes=mechanism_axes,
            evidence_gates=evidence_gates,
            dominance_policies=dominance_policies,
            query_templates=query_templates,
            subtypes=data.get("subtypes", []),
            eligibility_patterns=data.get("eligibility_patterns", {}),
            contraindications=data.get("contraindications", []),
            explainability_fields=data.get("explainability_fields", [])
        )
    
    def get_module(self, disease_name: str) -> Optional[DiseaseModule]:
        """Get disease module by name or alias"""
        # Try exact match first
        if disease_name in self._modules:
            return self._modules[disease_name]
        
        # Try aliases
        for module_name, module in self._modules.items():
            if disease_name.lower() in [a.lower() for a in module.aliases]:
                return module
        
        return None
    
    def list_diseases(self) -> List[str]:
        """List all available disease modules"""
        return list(self._modules.keys())
    
    def build_mechanism_vector(
        self,
        disease_name: str,
        patient_profile: Dict[str, Any]
    ) -> List[float]:
        """
        Build 7D mechanism vector for a patient profile
        
        Returns:
            List of 7 floats representing mechanism axis scores
        """
        module = self.get_module(disease_name)
        if not module:
            logger.warning(f"No module found for disease: {disease_name}")
            return [0.0] * 7
        
        # Initialize vector
        vector = [0.0] * 7
        
        # Extract patient biomarkers
        tumor_context = patient_profile.get("tumor_context", {})
        somatic_mutations = tumor_context.get("somatic_mutations", [])
        germline_variants = patient_profile.get("germline_variants", [])
        biomarkers = patient_profile.get("biomarkers", {})
        
        # Build biomarker text for matching
        biomarker_text = " ".join([
            str(m.get("gene", "")) for m in somatic_mutations + germline_variants
        ]).upper()
        
        # Score each mechanism axis
        for axis_name, axis in module.mechanism_axes.items():
            score = 0.0
            
            # Check biomarker matches
            for biomarker in axis.biomarkers:
                if biomarker.upper() in biomarker_text:
                    score += 1.0
            
            # Check pathway matches
            for pathway in axis.pathways:
                if pathway.upper() in biomarker_text:
                    score += 0.5
            
            # Apply evidence gates
            for gate in module.evidence_gates:
                if self._evaluate_condition(gate.condition, patient_profile, biomarker_text):
                    if axis_name in gate.boosts:
                        score += gate.boosts[axis_name]
            
            # Normalize and store
            vector[axis.vector_index] = min(1.0, score / 3.0)  # Cap at 1.0
        
        return vector
    
    def _evaluate_condition(
        self,
        condition: str,
        patient_profile: Dict[str, Any],
        biomarker_text: str
    ) -> bool:
        """Evaluate a condition string against patient profile"""
        # Simple keyword-based evaluation
        # TODO: Implement proper expression parsing
        condition_upper = condition.upper()
        
        # Check for OR conditions
        if " OR " in condition_upper:
            parts = condition_upper.split(" OR ")
            return any(part.strip() in biomarker_text for part in parts)
        
        # Check for AND conditions
        if " AND " in condition_upper:
            parts = condition_upper.split(" AND ")
            return all(part.strip() in biomarker_text for part in parts)
        
        # Simple match
        return condition_upper in biomarker_text
    
    def get_dominance_policy(
        self,
        disease_name: str,
        patient_profile: Dict[str, Any]
    ) -> Optional[DominancePolicy]:
        """Get applicable dominance policy for patient profile"""
        module = self.get_module(disease_name)
        if not module:
            return None
        
        biomarker_text = self._get_biomarker_text(patient_profile)
        
        for policy in module.dominance_policies:
            if self._evaluate_condition(policy.condition, patient_profile, biomarker_text):
                return policy
        
        return None
    
    def _get_biomarker_text(self, patient_profile: Dict[str, Any]) -> str:
        """Extract biomarker text from patient profile"""
        tumor_context = patient_profile.get("tumor_context", {})
        somatic_mutations = tumor_context.get("somatic_mutations", [])
        germline_variants = patient_profile.get("germline_variants", [])
        
        return " ".join([
            str(m.get("gene", "")) for m in somatic_mutations + germline_variants
        ]).upper()
    
    def get_query_templates(
        self,
        disease_name: str,
        priority: Optional[int] = None
    ) -> List[QueryTemplate]:
        """Get query templates for a disease, optionally filtered by priority"""
        module = self.get_module(disease_name)
        if not module:
            return []
        
        templates = module.query_templates
        if priority is not None:
            templates = [t for t in templates if t.priority == priority]
        
        return sorted(templates, key=lambda t: t.priority)


# Singleton instance
_disease_module_loader: Optional[DiseaseModuleLoader] = None


def get_disease_module_loader() -> DiseaseModuleLoader:
    """Get singleton instance of DiseaseModuleLoader"""
    global _disease_module_loader
    if _disease_module_loader is None:
        _disease_module_loader = DiseaseModuleLoader()
    return _disease_module_loader
