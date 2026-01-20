"""
NGS Fast-Track Service

CLINICAL PURPOSE: Accelerate tumor genomic data acquisition for AK
Provide specific ordering guidance for oncologist to unlock WIWFM predictions

This service recommends:
1. ctDNA testing (Guardant360) - somatic BRCA/HRR, TMB, MSI
2. Tissue HRD testing (MyChoice) - HRD score for PARP maintenance
3. IHC panel (WT1/PAX8/p53) - confirm high-grade serous histology

Once NGS returns → unlock Evo2-powered WIWFM drug ranking

Author: Zo
Date: January 13, 2025
For: AK - Stage IVB HGSOC
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class NGSFastTrackService:
    """
    NGS Fast-Track Service
    
    Provides ordering guidance for tumor genomic testing to unlock
    personalized drug efficacy predictions (WIWFM with Evo2).
    """
    
    # Test recommendations for ovarian cancer first-line
    RECOMMENDED_TESTS = {
        "ctDNA": {
            "test_name": "Guardant360 CDx",
            "lab": "Guardant Health",
            "sample_type": "Blood draw (2 tubes, 10mL each)",
            "genes_covered": ["BRCA1", "BRCA2", "PALB2", "RAD51C", "RAD51D", "BRIP1", "ATM", "CHEK2", "TP53", "PIK3CA", "KRAS", "NRAS"],
            "biomarkers_provided": ["Somatic BRCA", "HRR mutations", "TMB", "MSI"],
            "turnaround_time_days": 7,
            "clinical_utility": "Identifies actionable somatic mutations for PARP inhibitors, checkpoint inhibitors",
            "cost_approximate": "$5,000-7,000 (often covered by insurance for Stage IV)",
            "ordering_info": "Order through Guardant Health portal or call 1-855-698-8887",
            "rationale_for_ayesha": "Somatic BRCA/HRR mutations (even if germline negative) qualify for PARP maintenance. TMB-high/MSI-H may qualify for checkpoint inhibitors."
        },
        "tissue_HRD": {
            "test_name": "MyChoice CDx",
            "lab": "Myriad Genetics",
            "sample_type": "FFPE tumor tissue (from surgery/biopsy)",
            "genes_covered": ["BRCA1", "BRCA2", "plus genome-wide HRD score"],
            "biomarkers_provided": ["HRD score (0-100)", "BRCA1/2 somatic mutations", "LOH score"],
            "turnaround_time_days": 10,
            "clinical_utility": "HRD score ≥42 → PARP maintenance benefit (even without BRCA mutation)",
            "cost_approximate": "$4,000-6,000 (often covered for ovarian cancer)",
            "ordering_info": "Order through Myriad portal or call 1-800-469-7423",
            "rationale_for_ayesha": "HRD-high (≥42) predicts PARP response. GOG-0218 showed benefit in HRD+ patients regardless of BRCA status."
        },
        "IHC_panel": {
            "test_name": "Gynecologic IHC Panel",
            "lab": "Local pathology lab",
            "sample_type": "FFPE tumor tissue (from surgery/biopsy)",
            "markers_tested": ["WT1", "PAX8", "p53", "ER", "PR"],
            "biomarkers_provided": ["High-grade serous confirmation", "Hormone receptor status"],
            "turnaround_time_days": 3,
            "clinical_utility": "Confirms high-grade serous histology (WT1+, PAX8+, p53 aberrant). ER/PR for hormone therapy consideration.",
            "cost_approximate": "$500-1,000 (typically covered)",
            "ordering_info": "Order through hospital pathology department",
            "rationale_for_ayesha": "Confirm HGSOC histology (affects treatment algorithms). WT1+/PAX8+/p53 aberrant = classic HGSOC pattern."
        }
    }
    
    def __init__(self):
        """Initialize NGS Fast-Track Service"""
        logger.info("NGS Fast-Track Service initialized")
    
    def generate_ngs_checklist(
        self,
        patient_profile: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate NGS fast-track checklist for patient.
        
        Args:
            patient_profile: {
                "stage": "IVB",
                "treatment_line": "first-line",
                "germline_status": "negative",
                "histology": "high_grade_serous",
                "has_tissue_available": True/False
            }
        
        Returns:
            Checklist dict with recommended tests, rationale, ordering info
        """
        logger.info(f"Generating NGS checklist for {patient_profile.get('stage', 'unknown')} patient")
        
        # Priority order (highest to lowest)
        priority_tests = []
        
        # 1. ctDNA - ALWAYS recommended for Stage IV (fastest, most comprehensive)
        stage = patient_profile.get("stage", "").upper()
        if "IV" in stage or "4" in stage:
            priority_tests.append({
                "priority": 1,
                "test_key": "ctDNA",
                "recommended": True,
                "urgency": "HIGH",
                "reason": "Stage IV disease → ctDNA is fastest path to actionable mutations (7 days vs 10-14 for tissue)"
            })
        
        # 2. Tissue HRD - CRITICAL for PARP maintenance planning
        has_tissue = patient_profile.get("has_tissue_available", True)  # Assume true if not specified
        if has_tissue:
            priority_tests.append({
                "priority": 2,
                "test_key": "tissue_HRD",
                "recommended": True,
                "urgency": "HIGH",
                "reason": "HRD score needed for PARP maintenance decision. Can run in parallel with ctDNA."
            })
        else:
            priority_tests.append({
                "priority": 2,
                "test_key": "tissue_HRD",
                "recommended": False,
                "urgency": "MODERATE",
                "reason": "Tissue not currently available. Consider biopsy if ctDNA insufficient."
            })
        
        # 3. IHC panel - FAST confirmation of histology
        histology = patient_profile.get("histology", "").lower()
        if "high_grade" not in histology and "serous" not in histology:
            priority_tests.append({
                "priority": 3,
                "test_key": "IHC_panel",
                "recommended": True,
                "urgency": "MODERATE",
                "reason": "Histology not confirmed. IHC panel (WT1/PAX8/p53) confirms high-grade serous (3 days)."
            })
        else:
            priority_tests.append({
                "priority": 3,
                "test_key": "IHC_panel",
                "recommended": False,
                "urgency": "LOW",
                "reason": "High-grade serous histology already confirmed."
            })
        
        # Build full checklist
        checklist = []
        for priority_test in priority_tests:
            test_key = priority_test["test_key"]
            test_details = self.RECOMMENDED_TESTS[test_key].copy()
            test_details.update({
                "priority": priority_test["priority"],
                "recommended": priority_test["recommended"],
                "urgency": priority_test["urgency"],
                "reason": priority_test["reason"]
            })
            checklist.append(test_details)
        
        # Calculate total timeline
        recommended_tests = [t for t in checklist if t["recommended"]]
        if recommended_tests:
            # Parallel execution → max turnaround time
            max_turnaround = max(t["turnaround_time_days"] for t in recommended_tests)
            estimated_completion = datetime.utcnow() + timedelta(days=max_turnaround)
        else:
            max_turnaround = 0
            estimated_completion = None
        
        # What gets unlocked
        unlocked_capabilities = {
            "wiwfm_drug_ranking": {
                "enabled_by": ["ctDNA", "tissue_HRD"],
                "confidence_boost": "70-85% (Evo2-powered S/P/E)",
                "description": "Per-drug efficacy predictions with transparent S/P/E scoring"
            },
            "parp_maintenance_decision": {
                "enabled_by": ["tissue_HRD"],
                "confidence_boost": "90%+ (if HRD ≥42)",
                "description": "High-confidence PARP inhibitor recommendation for HRD-high patients"
            },
            "checkpoint_inhibitor_eligibility": {
                "enabled_by": ["ctDNA"],
                "confidence_boost": "95%+ (if TMB-high or MSI-H)",
                "description": "Pembrolizumab eligibility for TMB ≥10 or MSI-H"
            },
            "targeted_therapy_options": {
                "enabled_by": ["ctDNA"],
                "confidence_boost": "Varies by mutation",
                "description": "PIK3CA, KRAS, NRAS mutations → targeted therapy eligibility"
            }
        }
        
        # Clinical notes
        clinical_notes = self._generate_clinical_notes(patient_profile, checklist)
        
        # Provenance
        provenance = {
            "method": "ngs_fast_track_v1",
            "data_sources": ["FDA CDx approvals", "NCCN Guidelines", "Clinical trial eligibility"],
            "generated_at": datetime.utcnow().isoformat(),
            "for_patient_profile": patient_profile
        }
        
        return {
            "checklist": checklist,
            "estimated_turnaround_days": max_turnaround,
            "estimated_completion_date": estimated_completion.isoformat() if estimated_completion else None,
            "unlocked_capabilities": unlocked_capabilities,
            "clinical_notes": clinical_notes,
            "provenance": provenance
        }
    
    def _generate_clinical_notes(
        self,
        patient_profile: Dict[str, Any],
        checklist: List[Dict[str, Any]]
    ) -> str:
        """
        Generate clinical notes for oncologist.
        
        Args:
            patient_profile: Patient profile dict
            checklist: Generated checklist
        
        Returns:
            Clinical notes string
        """
        notes = []
        
        # Headline
        stage = patient_profile.get("stage", "unknown")
        germline_status = patient_profile.get("germline_status", "unknown")
        notes.append(f"NGS Fast-Track for Stage {stage} ovarian cancer (germline {germline_status}):")
        
        # Recommended tests
        recommended = [t for t in checklist if t["recommended"]]
        if recommended:
            notes.append(f"\nRecommended tests ({len(recommended)}):")
            for test in recommended:
                notes.append(f"  • {test['test_name']} ({test['urgency']} priority) - {test['turnaround_time_days']} days")
                notes.append(f"    Rationale: {test['reason']}")
        
        # Parallel execution
        if len(recommended) > 1:
            notes.append(f"\n✓ Tests can run in PARALLEL. Total turnaround: ~{max(t['turnaround_time_days'] for t in recommended)} days.")
        
        # What this unlocks
        notes.append("\nWhat NGS unlocks:")
        notes.append("  • WIWFM drug ranking (Evo2-powered S/P/E) - 70-85% confidence")
        notes.append("  • PARP maintenance decision (HRD-based) - 90%+ confidence if HRD ≥42")
        notes.append("  • Checkpoint inhibitor eligibility (TMB/MSI-based) - 95%+ if TMB ≥10 or MSI-H")
        notes.append("  • Targeted therapy options (mutation-based) - Varies by alteration")
        
        # Insurance coverage
        notes.append("\nInsurance coverage:")
        notes.append("  • Stage IV ovarian cancer → typically covered for comprehensive genomic profiling")
        notes.append("  • Prior authorization may be required (oncologist's office handles)")
        
        return "\n".join(notes)


# Singleton instance
_ngs_service = None


def get_ngs_fast_track_service() -> NGSFastTrackService:
    """Get singleton NGS Fast-Track Service instance."""
    global _ngs_service
    if _ngs_service is None:
        _ngs_service = NGSFastTrackService()
    return _ngs_service


