"""
Resistance Prediction Router - Disease-Agnostic API

Endpoint: POST /api/resistance/predict

Supports:
- Multiple Myeloma (MM): DIS3, TP53, cytogenetics, treatment line
- Ovarian Cancer (OV): MAPK, PI3K, DDR/HRD

Uses shared ResistancePlaybookService for DRY architecture.

Created: January 28, 2025
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
import logging

from api.services.disease_normalization import validate_disease_type as validate_and_normalize_disease
from api.services.resistance_evidence_tiers import map_resistance_evidence_to_manager_tier
from api.contracts.resistance_contract import ResistanceContract
from api.contracts.resistance_builders import contract_from_playbook_result
from api.services.input_completeness import compute_input_completeness

from api.services.resistance_prophet_service import (
    get_resistance_prophet_service,
    ResistanceProphetService,
    ResistanceRiskLevel,
    UrgencyLevel
)
from api.services.resistance_playbook_service import (
    get_resistance_playbook_service,
    ResistancePlaybookService,
    EvidenceLevel
)
from api.services.resistance.biomarkers.diagnostic.ddr_bin_scoring import assign_ddr_status
from api.services.resistance.biomarkers.therapeutic.timing_chemo_features import build_timing_chemo_features

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/resistance", tags=["Resistance Prediction"])


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class MutationInput(BaseModel):
    """Single mutation input"""
    gene: str = Field(..., description="Gene symbol (e.g., 'DIS3', 'TP53', 'NF1')")
    hgvs_p: Optional[str] = Field(None, description="Protein change (e.g., 'p.R175H')")
    hgvs_c: Optional[str] = Field(None, description="Coding change")
    consequence: Optional[str] = Field(None, description="Variant consequence")
    vaf: Optional[float] = Field(None, description="Variant allele frequency")


class ResistancePredictRequest(BaseModel):
    """Request for resistance prediction - disease-agnostic"""
    # Required
    disease: str = Field(
        ..., 
        description="Disease type: 'myeloma', 'ovarian', 'mm', 'ov'"
    )
    mutations: List[MutationInput] = Field(
        default=[],
        description="List of patient mutations"
    )
    
    # Optional - Patient context
    patient_id: Optional[str] = Field(None, description="Patient identifier")
    
    # Optional - Treatment context
    current_drug_class: Optional[str] = Field(
        None, 
        description="Current drug class (e.g., 'proteasome_inhibitor', 'platinum')"
    )
    current_regimen: Optional[str] = Field(
        None, 
        description="Current treatment regimen (e.g., 'VRd', 'carboplatin/paclitaxel')"
    )
    treatment_line: int = Field(
        1, 
        description="Treatment line (1, 2, 3+)"
    )
    prior_therapies: Optional[List[str]] = Field(
        None, 
        description="List of prior drug classes"
    )
    
    # Optional - MM-specific: Cytogenetics
    cytogenetics: Optional[Dict[str, bool]] = Field(
        None,
        description="MM cytogenetics: {'del_17p': True, 't_4_14': False, '1q_gain': True}"
    )
    
    # Optional - OV-specific: SAE features for mechanism-based prediction
    sae_features: Optional[Dict[str, Any]] = Field(
        None,
        description="SAE mechanism features for OV pathway analysis"
    )
    baseline_sae_features: Optional[Dict[str, Any]] = Field(
        None,
        description="Baseline SAE features for comparison"
    )


class DrugAlternativeResponse(BaseModel):
    """Single drug alternative in response"""
    drug: str
    drug_class: str
    rationale: str
    evidence_level: str
    evidence_tier: str
    priority: int
    source_gene: str
    requires: Optional[List[str]] = None


class RegimenChangeResponse(BaseModel):
    """Regimen change recommendation"""
    from_regimen: str
    to_regimen: str
    rationale: str
    evidence_level: str
    evidence_tier: str


class MonitoringChangesResponse(BaseModel):
    """Updated monitoring recommendations"""
    mrd_frequency: Optional[str] = None
    ctdna_targets: Optional[List[str]] = None
    imaging_frequency: Optional[str] = None
    biomarker_frequency: Optional[str] = None
    bone_marrow_frequency: Optional[str] = None


class DownstreamHandoffResponse(BaseModel):
    """Structured handoff for downstream agent"""
    agent: str
    action: str
    payload: Dict[str, Any]


class SignalResponse(BaseModel):
    """Single resistance signal"""
    signal_type: str
    detected: bool
    probability: float
    confidence: float
    rationale: str


class ResistancePredictResponse(BaseModel):
    """Full resistance prediction response"""
    # Patient context
    patient_id: Optional[str] = None
    disease: str
    
    # Risk assessment
    risk_level: str  # HIGH, MEDIUM, LOW
    probability: float
    confidence: float
    urgency: str  # CRITICAL, ELEVATED, ROUTINE
    
    # Signals detected
    signals_detected: List[SignalResponse]
    signal_count: int
    
    # Actionable recommendations (the "what's next")
    alternatives: List[DrugAlternativeResponse]
    regimen_changes: List[RegimenChangeResponse]
    monitoring_changes: MonitoringChangesResponse
    escalation_triggers: List[str]
    
    # Downstream agent handoffs
    downstream_handoffs: Dict[str, DownstreamHandoffResponse]
    
    # Explanation
    rationale: List[str]
    recommended_actions: List[Dict[str, Any]]
    
    # Provenance
    provenance: Dict[str, Any]
    warnings: List[str]
    contract: Optional[ResistanceContract] = None


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.post("/predict", response_model=ResistancePredictResponse)
async def predict_resistance(request: ResistancePredictRequest):
    """
    Predict treatment resistance and provide actionable next steps.
    
    Disease-agnostic endpoint supporting:
    - **Multiple Myeloma (MM)**: DIS3, TP53, cytogenetics (del(17p), t(4;14), 1q gain)
    - **Ovarian Cancer (OV)**: MAPK (NF1, KRAS), PI3K (PIK3CA, PTEN)
    
    Returns:
    - Risk level with probability and confidence
    - Alternative drugs (ranked by priority and evidence)
    - Regimen change suggestions
    - Monitoring updates
    - Downstream agent handoffs (Drug Efficacy, Care Plan, Monitoring)
    """
    logger.info(f"🔮 Resistance prediction request: disease={request.disease}, mutations={len(request.mutations)}")
    
    try:
        # Get service instances
        playbook_service = get_resistance_playbook_service()
        prophet_service = get_resistance_prophet_service(
            resistance_playbook_service=playbook_service
        )
        
        # Convert mutations to dict format
        mutations_list = [
            {
                "gene": m.gene,
                "hgvs_p": m.hgvs_p,
                "hgvs_c": m.hgvs_c,
                "consequence": m.consequence,
                "vaf": m.vaf
            }
            for m in request.mutations
        ]
        
        # Route based on disease
        is_valid, normalized_disease = validate_and_normalize_disease(request.disease)
        if not is_valid:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Unsupported disease: {request.disease}. Supported: "
                    "ovarian_cancer_hgs, multiple_myeloma, melanoma, breast_cancer, colorectal_cancer, pancreatic_cancer, lung_cancer, prostate_cancer"
                )
            )

        # Canonical disease id (returned in response)
        request.disease = normalized_disease

        # Internal routing keys expected by playbook/prophet
        playbook_disease = "myeloma" if normalized_disease == "multiple_myeloma" else "ovarian"
        disease_lower = normalized_disease
        
        if disease_lower == "multiple_myeloma":
            # MM-specific prediction
            prediction = await prophet_service.predict_mm_resistance(
                mutations=mutations_list,
                drug_class=request.current_drug_class,
                treatment_line=request.treatment_line,
                prior_therapies=request.prior_therapies,
                cytogenetics=request.cytogenetics
            )
        elif disease_lower == "ovarian_cancer_hgs":
            # OV-specific prediction (uses full mechanism-based prediction)
            if request.sae_features:
                prediction = await prophet_service.predict_resistance(
                    current_sae_features=request.sae_features,
                    baseline_sae_features=request.baseline_sae_features,
                    current_drug_class=request.current_drug_class
                )
            else:
                # Fallback: use gene-level for OV too
                # Extract genes from mutations for playbook lookup
                detected_genes = [m.gene.upper() for m in request.mutations]
                playbook_result = await playbook_service.get_next_line_options(
                    disease=playbook_disease,
                    detected_resistance=detected_genes,
                    current_regimen=request.current_regimen,
                    current_drug_class=request.current_drug_class,
                    treatment_line=request.treatment_line,
                    prior_therapies=request.prior_therapies,
                    patient_id=request.patient_id
                )
                
                # Build simplified response for OV without full prediction
                return _build_ov_simple_response(
                    request=request,
                    detected_genes=detected_genes,
                    playbook_result=playbook_result
                )
        else:
            raise HTTPException(
                status_code=422,
                detail=f"Unsupported disease: {request.disease}. Supported: ovarian_cancer_hgs, multiple_myeloma"
            )
        
        # Get playbook recommendations
        detected_genes = []
        for sig in prediction.signals_detected:
            if sig.provenance.get("detected_genes"):
                detected_genes.extend([g["gene"] for g in sig.provenance["detected_genes"]])
            if sig.provenance.get("detected_abnormalities"):
                detected_genes.extend([a["abnormality"] for a in sig.provenance["detected_abnormalities"]])
        
        playbook_result = await playbook_service.get_next_line_options(
            disease=playbook_disease,
            detected_resistance=detected_genes,
            current_regimen=request.current_regimen,
            current_drug_class=request.current_drug_class,
            treatment_line=request.treatment_line,
            prior_therapies=request.prior_therapies,
            cytogenetics=request.cytogenetics,
            patient_id=request.patient_id
        )
        
        # Build response
        response = ResistancePredictResponse(
            patient_id=request.patient_id,
            disease=playbook_disease,
            risk_level=prediction.risk_level.value,
            probability=prediction.probability,
            confidence=prediction.confidence,
            urgency=prediction.urgency.value,
            signals_detected=[
                SignalResponse(
                    signal_type=sig.signal_type.value,
                    detected=sig.detected,
                    probability=sig.probability,
                    confidence=sig.confidence,
                    rationale=sig.rationale
                )
                for sig in prediction.signals_detected
            ],
            signal_count=prediction.signal_count,
            alternatives=[
                DrugAlternativeResponse(
                    drug=alt.drug,
                    drug_class=alt.drug_class,
                    rationale=alt.rationale,
                    evidence_level=alt.evidence_level.value if hasattr(alt.evidence_level, 'value') else str(alt.evidence_level),
                    evidence_tier=map_resistance_evidence_to_manager_tier(alt.evidence_level).value,
                    priority=alt.priority,
                    source_gene=alt.source_gene,
                    requires=alt.requires
                )
                for alt in playbook_result.alternatives
            ],
            regimen_changes=[
                RegimenChangeResponse(
                    from_regimen=rc.from_regimen,
                    to_regimen=rc.to_regimen,
                    rationale=rc.rationale,
                    evidence_level=rc.evidence_level.value if hasattr(rc.evidence_level, 'value') else str(rc.evidence_level),
                    evidence_tier=map_resistance_evidence_to_manager_tier(rc.evidence_level).value
                )
                for rc in playbook_result.regimen_changes
            ],
            monitoring_changes=MonitoringChangesResponse(
                mrd_frequency=playbook_result.monitoring_changes.mrd_frequency,
                ctdna_targets=playbook_result.monitoring_changes.ctdna_targets,
                imaging_frequency=playbook_result.monitoring_changes.imaging_frequency,
                biomarker_frequency=playbook_result.monitoring_changes.biomarker_frequency,
                bone_marrow_frequency=playbook_result.monitoring_changes.bone_marrow_frequency
            ),
            escalation_triggers=playbook_result.escalation_triggers,
            downstream_handoffs={
                agent: DownstreamHandoffResponse(
                    agent=handoff.agent,
                    action=handoff.action,
                    payload=handoff.payload
                )
                for agent, handoff in playbook_result.downstream_handoffs.items()
            },
            rationale=prediction.rationale,
            recommended_actions=prediction.recommended_actions,
            provenance={
                **prediction.provenance,
                **playbook_result.provenance
            },
            warnings=prediction.warnings
        )
        
        # Canonical contract (non-breaking additive field)
        try:
            response.contract = contract_from_playbook_result(
                endpoint='resistance_predict',
                disease_canonical=request.disease,
                tumor_context={'somatic_mutations': mutations_list},
                playbook_disease_key=playbook_disease,
                playbook_result=playbook_result,
                warnings=list(response.warnings or []),
            )
        except Exception as _e:
            # Never fail the endpoint due to contract emission
            pass

        logger.info(f"✅ Resistance prediction complete: risk={response.risk_level}, alternatives={len(response.alternatives)}")

        # Sprint 2: enforce L0/L1/L2 confidence caps + surface missing-input warnings
        try:
            completeness = compute_input_completeness(
                tumor_context={"somatic_mutations": mutations_list},
                ca125_history=None,
            )

            if response.confidence is not None:
                response.confidence = float(min(float(response.confidence), float(completeness.confidence_cap)))

            existing_warnings = list(response.warnings or [])
            merged: List[str] = []
            for w in existing_warnings + list(completeness.warnings or []):
                if w and w not in merged:
                    merged.append(w)
            response.warnings = merged
        except Exception:
            # Never fail due to caps/warnings logic
            pass

        return response
        
    except Exception as e:
        logger.error(f"❌ Resistance prediction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _build_ov_simple_response(
    request: ResistancePredictRequest,
    detected_genes: List[str],
    playbook_result
) -> ResistancePredictResponse:
    """Build simplified response for OV when SAE features not provided"""
    
    # Determine risk level based on detected genes
    if any(g in ["NF1", "KRAS", "NRAS", "BRAF"] for g in detected_genes):
        risk_level = "MEDIUM"
        probability = 0.60
        urgency = "ELEVATED"
    elif any(g in ["PIK3CA", "PTEN", "AKT1"] for g in detected_genes):
        risk_level = "MEDIUM"
        probability = 0.55
        urgency = "ELEVATED"
    else:
        risk_level = "LOW"
        probability = 0.30
        urgency = "ROUTINE"
    
    return ResistancePredictResponse(
        patient_id=request.patient_id,
        disease=request.disease,
        risk_level=risk_level,
        probability=probability,
        confidence=0.70,  # Gene-level only
        urgency=urgency,
        signals_detected=[
            SignalResponse(
                signal_type="OV_PATHWAY_GENE",
                detected=len(detected_genes) > 0,
                probability=probability,
                confidence=0.70,
                rationale=f"Detected resistance genes: {', '.join(detected_genes) if detected_genes else 'none'}"
            )
        ],
        signal_count=1 if detected_genes else 0,
        alternatives=[
            DrugAlternativeResponse(
                drug=alt.drug,
                drug_class=alt.drug_class,
                rationale=alt.rationale,
                evidence_level=alt.evidence_level.value if hasattr(alt.evidence_level, 'value') else str(alt.evidence_level),
                    evidence_tier=map_resistance_evidence_to_manager_tier(alt.evidence_level).value,
                priority=alt.priority,
                source_gene=alt.source_gene,
                requires=alt.requires
            )
            for alt in playbook_result.alternatives
        ],
        regimen_changes=[
            RegimenChangeResponse(
                from_regimen=rc.from_regimen,
                to_regimen=rc.to_regimen,
                rationale=rc.rationale,
                evidence_level=rc.evidence_level.value if hasattr(rc.evidence_level, 'value') else str(rc.evidence_level),
                    evidence_tier=map_resistance_evidence_to_manager_tier(rc.evidence_level).value
            )
            for rc in playbook_result.regimen_changes
        ],
        monitoring_changes=MonitoringChangesResponse(
            mrd_frequency=playbook_result.monitoring_changes.mrd_frequency,
            ctdna_targets=playbook_result.monitoring_changes.ctdna_targets,
            imaging_frequency=playbook_result.monitoring_changes.imaging_frequency,
            biomarker_frequency=playbook_result.monitoring_changes.biomarker_frequency
        ),
        escalation_triggers=playbook_result.escalation_triggers,
        downstream_handoffs={
            agent: DownstreamHandoffResponse(
                agent=handoff.agent,
                action=handoff.action,
                payload=handoff.payload
            )
            for agent, handoff in playbook_result.downstream_handoffs.items()
        },
        rationale=[
            f"OV resistance assessment based on gene-level analysis",
            f"Detected genes: {', '.join(detected_genes) if detected_genes else 'none'}",
            "Note: For full mechanism-based prediction, provide SAE features"
        ],
        recommended_actions=[
            {
                "action": "MONITOR_CA125" if risk_level == "MEDIUM" else "ROUTINE_MONITORING",
                "timeframe": "per standard of care",
                "rationale": f"Risk level: {risk_level}"
            }
        ],
        provenance={
            **playbook_result.provenance,
            "method": "gene_level_simple",
            "note": "SAE features not provided - using simplified gene-level assessment"
        },
        warnings=["SAE_FEATURES_NOT_PROVIDED"]
    )


# ============================================================================
# DDR_bin STATUS ENDPOINT
# ============================================================================

class MutationInputDDR(BaseModel):
    """Mutation input for DDR_bin scoring"""
    gene_symbol: str = Field(..., description="Gene symbol (e.g., 'BRCA1', 'BRCA2', 'ATM')")
    variant_classification: str = Field(..., description="Variant classification: 'pathogenic', 'likely_pathogenic', 'VUS', 'benign', etc.")
    variant_type: Optional[str] = Field(None, description="Variant type: 'SNV', 'indel', 'rearrangement'")


class CNAInputDDR(BaseModel):
    """Copy-number alteration input for DDR_bin scoring"""
    gene_symbol: str = Field(..., description="Gene symbol")
    copy_number_state: str = Field(..., description="Copy number state: 'deletion', 'loss', 'neutral', 'gain', 'amplification'")
    copy_number: Optional[float] = Field(None, description="Optional numeric copy number value")


class HRDAssayInputDDR(BaseModel):
    """HRD assay input for DDR_bin scoring"""
    hrd_score: Optional[float] = Field(None, description="Continuous HRD score (e.g., 45.0)")
    hrd_status: Optional[str] = Field(None, description="HRD status: 'HRD_positive', 'HRD_negative', 'equivocal', 'unknown'")
    assay_name: Optional[str] = Field(None, description="Assay name: 'Myriad', 'Leuven', 'Geneva', 'other'")


class DDRStatusRequest(BaseModel):
    """Request for DDR_bin status scoring"""
    patient_id: str = Field(..., description="Patient identifier")
    disease_site: str = Field(..., description="Disease site: 'ovary', 'breast', 'pancreas', 'prostate', 'other'")
    tumor_subtype: Optional[str] = Field(None, description="Tumor subtype (e.g., 'HGSOC', 'TNBC', 'PDAC')")
    mutations: List[MutationInputDDR] = Field(default=[], description="List of mutations")
    cna: Optional[List[CNAInputDDR]] = Field(None, description="Optional copy-number alterations")
    hrd_assay: Optional[HRDAssayInputDDR] = Field(None, description="Optional HRD assay results")


class DDRStatusResponse(BaseModel):
    """Response for DDR_bin status scoring"""
    patient_id: str
    disease_site: str
    tumor_subtype: Optional[str]
    
    # Primary classification
    DDR_bin_status: str  # 'DDR_defective' | 'DDR_proficient' | 'unknown'
    
    # HRD information
    HRD_status_inferred: str  # 'HRD_positive' | 'HRD_negative' | 'unknown'
    HRD_score_raw: Optional[float]
    
    # Flags
    BRCA_pathogenic: bool
    core_HRR_pathogenic: bool
    extended_DDR_pathogenic: bool
    
    # Scoring
    DDR_score: float
    DDR_features_used: Optional[List[str]]
    
    # Metadata
    config_used: Dict[str, Any]
    provenance: Optional[Dict[str, Any]] = None


@router.post("/ddr-status", response_model=DDRStatusResponse)
async def get_ddr_status(request: DDRStatusRequest):
    """
    Compute DDR_bin status for a patient.
    
    DDR_bin is a pan-solid-tumor DDR deficiency classifier that determines whether
    a patient has DDR_defective, DDR_proficient, or unknown DDR status based on
    genomic variants and optional HRD assay results.
    
    **Priority Order:**
    1. BRCA pathogenic variants (highest priority)
    2. HRD score/status (genomic scar)
    3. Core HRR gene pathogenic variants
    4. Extended DDR gene pathogenic variants
    
    **Research Use Only - Not for Clinical Diagnosis**
    """
    logger.info(f"🧬 DDR_bin status request: patient_id={request.patient_id}, disease_site={request.disease_site}, mutations={len(request.mutations)}")
    
    try:
        # Convert request to internal format
        mutations_table = [
            {
                "patient_id": request.patient_id,
                "gene_symbol": m.gene_symbol,
                "variant_classification": m.variant_classification,
                "variant_type": m.variant_type
            }
            for m in request.mutations
        ]
        
        clinical_table = [{
            "patient_id": request.patient_id,
            "disease_site": request.disease_site,
            "tumor_subtype": request.tumor_subtype
        }]
        
        cna_table = None
        if request.cna:
            cna_table = [
                {
                    "patient_id": request.patient_id,
                    "gene_symbol": c.gene_symbol,
                    "copy_number_state": c.copy_number_state,
                    "copy_number": c.copy_number
                }
                for c in request.cna
            ]
        
        hrd_assay_table = None
        if request.hrd_assay:
            hrd_assay_table = [{
                "patient_id": request.patient_id,
                "hrd_score": request.hrd_assay.hrd_score,
                "hrd_status": request.hrd_assay.hrd_status,
                "assay_name": request.hrd_assay.assay_name
            }]
        
        # Call DDR_bin engine
        results = assign_ddr_status(
            mutations_table=mutations_table,
            clinical_table=clinical_table,
            cna_table=cna_table,
            hrd_assay_table=hrd_assay_table,
            config=None  # Use disease-specific config from clinical_table
        )
        
        if not results:
            raise HTTPException(
                status_code=500,
                detail=f"DDR_bin engine returned no results for patient {request.patient_id}"
            )
        
        result = results[0]  # Should be single patient result
        
        # Build response
        response = DDRStatusResponse(
            patient_id=result.get("patient_id", request.patient_id),
            disease_site=result.get("disease_site", request.disease_site),
            tumor_subtype=result.get("tumor_subtype", request.tumor_subtype),
            DDR_bin_status=result.get("DDR_bin_status", "unknown"),
            HRD_status_inferred=result.get("HRD_status_inferred", "unknown"),
            HRD_score_raw=result.get("HRD_score_raw"),
            BRCA_pathogenic=result.get("BRCA_pathogenic", False),
            core_HRR_pathogenic=result.get("core_HRR_pathogenic", False),
            extended_DDR_pathogenic=result.get("extended_DDR_pathogenic", False),
            DDR_score=result.get("DDR_score", 0.0),
            DDR_features_used=result.get("DDR_features_used"),
            config_used=result.get("config_used", {}),
            provenance={
                "timestamp": result.get("timestamp"),
                "method": "ddr_bin_scoring_engine",
                "disease_site": request.disease_site
            }
        )
        
        logger.info(f"✅ DDR_bin status computed: patient_id={request.patient_id}, status={response.DDR_bin_status}")
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ DDR_bin status computation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"DDR_bin computation failed: {str(e)}")


# ============================================================================
# TIMING & CHEMOSENSITIVITY FEATURES ENDPOINT
# ============================================================================

class RegimenRecord(BaseModel):
    """Single regimen record"""
    patient_id: Union[str, int] = Field(..., description="Patient identifier")
    regimen_id: Union[str, int] = Field(..., description="Regimen identifier")
    regimen_start_date: Union[str, datetime] = Field(..., description="Regimen start date (ISO format or Date)")
    regimen_end_date: Optional[Union[str, datetime]] = Field(None, description="Regimen end date (optional if ongoing)")
    regimen_type: str = Field(..., description="Regimen type: 'platinum', 'PARPi', 'ATRi', etc.")
    line_of_therapy: int = Field(..., description="Treatment line (1, 2, 3+)")
    setting: str = Field(..., description="Setting: 'frontline', 'first_recurrence', etc.")
    last_platinum_dose_date: Optional[Union[str, datetime]] = Field(None, description="Last platinum dose date (for platinum regimens)")
    progression_date: Optional[Union[str, datetime]] = Field(None, description="Progression date")
    best_response: Optional[str] = Field(None, description="Best response: 'CR', 'PR', 'SD', 'PD'")


class SurvivalRecord(BaseModel):
    """Single survival record"""
    patient_id: Union[str, int] = Field(..., description="Patient identifier")
    vital_status: str = Field(..., description="Vital status: 'Alive', 'Dead', 'Unknown'")
    death_date: Optional[Union[str, datetime]] = Field(None, description="Death date (if applicable)")
    last_followup_date: Union[str, datetime] = Field(..., description="Last follow-up date (ISO format or Date)")


class ClinicalRecord(BaseModel):
    """Single clinical record"""
    patient_id: Union[str, int] = Field(..., description="Patient identifier")
    disease_site: str = Field(..., description="Disease site: 'ovary', 'endometrium', 'breast', etc.")
    tumor_subtype: Optional[str] = Field(None, description="Tumor subtype: 'HGSOC', 'TNBC', etc.")


class CA125FeaturesRecord(BaseModel):
    """Pre-computed CA-125 features record"""
    patient_id: Union[str, int] = Field(..., description="Patient identifier")
    regimen_id: Union[str, int] = Field(..., description="Regimen identifier")
    kelim_k_value: Optional[float] = Field(None, description="KELIM k-value")
    kelim_category: Optional[str] = Field(None, description="KELIM category: 'favorable', 'intermediate', 'unfavorable'")
    ca125_percent_change_day21: Optional[float] = Field(None, description="CA-125 % change at day 21")
    ca125_percent_change_day42: Optional[float] = Field(None, description="CA-125 % change at day 42")
    ca125_time_to_50pct_reduction_days: Optional[int] = Field(None, description="Time to 50% CA-125 reduction (days)")
    ca125_normalized_by_cycle3: Optional[bool] = Field(None, description="CA-125 normalized by cycle 3")


class CA125MeasurementRecord(BaseModel):
    """Raw CA-125 measurement record"""
    patient_id: Union[str, int] = Field(..., description="Patient identifier")
    regimen_id: Union[str, int] = Field(..., description="Regimen identifier")
    date: Union[str, datetime] = Field(..., description="Measurement date (ISO format or Date)")
    value: float = Field(..., description="CA-125 value in U/mL")


class TimingChemoFeaturesRequest(BaseModel):
    """Request for timing & chemosensitivity features"""
    regimen_table: List[RegimenRecord] = Field(..., description="List of regimen records")
    survival_table: List[SurvivalRecord] = Field(..., description="List of survival records")
    clinical_table: List[ClinicalRecord] = Field(..., description="List of clinical records")
    ca125_features_table: Optional[List[CA125FeaturesRecord]] = Field(None, description="Pre-computed CA-125 features (optional)")
    ca125_measurements_table: Optional[List[CA125MeasurementRecord]] = Field(None, description="Raw CA-125 measurements for on-the-fly KELIM (optional)")
    config: Optional[Dict[str, Any]] = Field(None, description="Custom timing configuration (optional)")


class TimingChemoFeaturesResponse(BaseModel):
    """Response with timing features"""
    timing_features_table: List[Dict[str, Any]] = Field(..., description="List of timing feature records")
    provenance: Optional[Dict[str, Any]] = Field(None, description="Provenance metadata")


@router.post("/timing-chemo-features", response_model=TimingChemoFeaturesResponse)
async def get_timing_chemo_features(request: TimingChemoFeaturesRequest):
    """
    Compute timing and chemosensitivity features for treatment history.
    
    This endpoint computes:
    - **PFI (Platinum-Free Interval)** and platinum sensitivity categories for platinum regimens
    - **PTPI (Platinum-to-PARPi Interval)** for DDR-targeted regimens
    - **TFI (Treatment-Free Interval)** between treatment lines
    - **PFS/OS** from regimen start
    - **KELIM/CA-125 features** (on-the-fly from raw measurements or pre-computed)
    
    **Research Use Only - Not for Clinical Decision Making**
    """
    logger.info(f"⏱️ Timing & chemosensitivity features request: {len(request.regimen_table)} regimens, {len(request.clinical_table)} patients")
    
    try:
        # Convert Pydantic models to dicts for engine
        regimen_table = [r.dict() for r in request.regimen_table]
        survival_table = [s.dict() for s in request.survival_table]
        clinical_table = [c.dict() for c in request.clinical_table]
        
        ca125_features_table = None
        if request.ca125_features_table:
            ca125_features_table = [f.dict() for f in request.ca125_features_table]
        
        ca125_measurements_table = None
        if request.ca125_measurements_table:
            ca125_measurements_table = [m.dict() for m in request.ca125_measurements_table]
        
        # Call timing engine
        results = build_timing_chemo_features(
            regimen_table=regimen_table,
            survival_table=survival_table,
            clinical_table=clinical_table,
            ca125_features_table=ca125_features_table,
            ca125_measurements_table=ca125_measurements_table,
            config=request.config
        )
        
        logger.info(f"✅ Timing features computed: {len(results)} regimen records processed")
        
        return TimingChemoFeaturesResponse(
            timing_features_table=results,
            provenance={
                "method": "timing_chemo_features_engine",
                "version": "1.0",
                "ruo": "Research Use Only",
                "regimens_processed": len(results),
                "disease_sites": list(set(r.get("disease_site") for r in results if r.get("disease_site")))
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Timing features computation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Timing features computation failed: {str(e)}")


@router.get("/health")
async def health_check():
    """Health check endpoint for resistance prediction service"""
    return {
        "status": "healthy",
        "service": "resistance_prediction",
        "version": "v1.0_dry",
        "supported_diseases": ["myeloma", "ovarian"]
    }

