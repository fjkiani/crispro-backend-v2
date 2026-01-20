"""
⚔️ TRIAL INTELLIGENCE PIPELINE - MAIN ORCHESTRATOR ⚔️

Modular pipeline that progressively filters and analyzes trials.
Each stage is independent, testable, and upgradeable.

Author: Zo (Lead Commander)
Date: November 15, 2025
"""

import asyncio
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime
from .config import FilterConfig, get_nyc_metro_config

@dataclass
class FilterResult:
    """Result from a filter stage"""
    passed: bool
    stage: str
    score: float
    reasons: List[str]
    rejection_reason: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

class TrialIntelligencePipeline:
    """
    Modular trial intelligence pipeline.
    
    Each stage:
    - Is independently testable
    - Can be upgraded without touching other stages
    - Records pass/fail with reasoning
    - Contributes to composite score
    
    Usage:
        pipeline = TrialIntelligencePipeline(ayesha_profile, use_llm=True)
        results = await pipeline.execute(candidates)
    """
    
    def __init__(self, ayesha_profile: Dict[str, Any], config: Optional[FilterConfig] = None, use_llm: bool = True, verbose: bool = True):
        """
        Initialize pipeline with patient profile.
        
        Args:
            ayesha_profile: Complete patient profile from ayesha_patient_profile.py
            config: FilterConfig instance (default: NYC metro config)
            use_llm: Enable LLM classification and analysis (costs API credits)
            verbose: Print progress messages
        """
        self.ayesha = ayesha_profile
        self.config = config if config is not None else get_nyc_metro_config()
        self.use_llm = use_llm if use_llm else self.config.USE_LLM
        self.verbose = verbose
        self.audit_trail = []
    
    def log(self, message: str):
        """Log message if verbose mode enabled"""
        if self.verbose:
            print(message)
    
    async def execute(self, candidates: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Execute complete pipeline with progressive filtering.
        
        Returns:
            {
                'top_tier': List[Dict],  # Trials with score ≥0.8
                'good_tier': List[Dict], # Trials with score ≥0.6
                'rejected': List[Dict],  # All rejected trials
                'audit_trail': List[Dict],  # Rejection reasons
                'statistics': Dict  # Pipeline statistics
            }
        """
        self.log(f"\n⚔️ EXECUTING TRIAL INTELLIGENCE PIPELINE")
        self.log(f"   Patient: {self.ayesha['demographics']['name']}")
        self.log(f"   Disease: {self.ayesha['disease']['primary_diagnosis']}")
        self.log(f"   Input: {len(candidates)} candidates")
        
        results = {
            'top_tier': [],
            'good_tier': [],
            'rejected': [],
            'audit_trail': [],
            'statistics': {
                'input_count': len(candidates),
                'stage1_survivors': 0,
                'stage2_survivors': 0,
                'stage3_survivors': 0,
                'stage4_survivors': 0,
                'stage5_analyzed': 0,
                'rejection_breakdown': {}
            }
        }
        
        for trial in candidates:
            nct_id = trial.get('nct_id', 'UNKNOWN')
            
            # STAGE 1: Hard Filters
            stage1 = await self.run_stage1(trial)
            if not stage1.passed:
                self._record_rejection(results, trial, stage1, nct_id)
                continue
            results['statistics']['stage1_survivors'] += 1
            
            # STAGE 2: Trial Type Classification
            stage2 = await self.run_stage2(trial)
            if not stage2.passed:
                self._record_rejection(results, trial, stage2, nct_id)
                continue
            results['statistics']['stage2_survivors'] += 1
            
            # STAGE 3: Location Validation
            stage3 = await self.run_stage3(trial)
            if not stage3.passed:
                self._record_rejection(results, trial, stage3, nct_id)
                continue
            results['statistics']['stage3_survivors'] += 1
            
            # STAGE 4: Eligibility Scoring
            stage4 = await self.run_stage4(trial)
            results['statistics']['stage4_survivors'] += 1
            
            # Calculate composite score (without LLM)
            composite_score = self._calculate_composite_score(stage1, stage2, stage3, stage4)
            
            # Store metadata (stage5 will be added later)
            trial['_filter_metadata'] = {
                'stage1': stage1,
                'stage2': stage2,
                'stage3': stage3,
                'stage4': stage4,
                'stage5': None,  # Will be populated in Stage 5
                'composite_score': composite_score,
                'pipeline_version': 'v2.0'
            }
            trial['_composite_score'] = composite_score  # For sorting
            
            # Classify tier (preliminary)
            if composite_score >= self.config.TOP_TIER_THRESHOLD:
                results['top_tier'].append(trial)
            elif composite_score >= self.config.GOOD_TIER_THRESHOLD:
                results['good_tier'].append(trial)
        
        # Sort tiers by composite score
        results['top_tier'].sort(key=lambda t: t['_composite_score'], reverse=True)
        results['good_tier'].sort(key=lambda t: t['_composite_score'], reverse=True)
        
        # STAGE 5: LLM Analysis (AFTER sorting, on top N trials)
        if self.use_llm:
            self.log(f"\n🤖 STAGE 5: LLM DEEP ANALYSIS (Top {self.config.MAX_LLM_ANALYSES} trials)")
            self.log(f"   ⏱️ Rate limiting enabled: 15s delay between calls (Gemini free tier: 2/min)\n")
            
            # Get top N trials across both tiers
            all_survivors = results['top_tier'] + results['good_tier']
            top_n = all_survivors[:self.config.MAX_LLM_ANALYSES]
            
            for i, trial in enumerate(top_n, 1):
                nct_id = trial.get('nct_id', 'UNKNOWN')
                title = trial.get('title', 'N/A')[:60]
                self.log(f"   {i}. {nct_id}: {title}...")
                self.log(f"      🤖 Analyzing with Gemini...")
                
                stage5 = await self.run_stage5(trial)
                trial['_filter_metadata']['stage5'] = stage5
                results['statistics']['stage5_analyzed'] += 1
                
                # Log result
                if stage5 and stage5.metadata.get('llm_analysis'):
                    analysis_length = len(stage5.metadata['llm_analysis'])
                    # Check if it's an error message (starts with "Error calling")
                    if stage5.metadata['llm_analysis'].startswith("Error calling"):
                        self.log(f"      ❌ API error (quota exceeded)\n")
                    else:
                        self.log(f"      ✅ Analysis complete ({analysis_length} chars)")
                else:
                    self.log(f"      ⚠️ Analysis failed (using fallback)")
                
                # RATE LIMITING: Wait 30s between calls (Gemini free tier = 2/min = 30s interval)
                if i < len(top_n):  # Don't wait after last call
                    self.log(f"      ⏱️ Rate limiting... (30s)\n")
                    await asyncio.sleep(30)
                else:
                    self.log("")  # Newline after last trial
        
        self._print_statistics(results['statistics'])
        
        return results
    
    def _record_rejection(self, results, trial, stage_result, nct_id):
        """Record rejected trial with reason"""
        results['rejected'].append(trial)
        results['audit_trail'].append({
            'nct_id': nct_id,
            'title': trial.get('title', 'N/A')[:80],
            'rejected_at': stage_result.stage,
            'reason': stage_result.rejection_reason,
            'details': stage_result.reasons
        })
        
        # Update rejection breakdown
        stage_key = stage_result.stage
        results['statistics']['rejection_breakdown'][stage_key] = \
            results['statistics']['rejection_breakdown'].get(stage_key, 0) + 1
    
    def _calculate_composite_score(self, stage1, stage2, stage3, stage4) -> float:
        """Calculate weighted composite score"""
        weights = self.config.COMPOSITE_WEIGHTS
        return (
            stage1.score * weights['stage1'] +
            stage2.score * weights['stage2'] +
            stage3.score * weights['stage3'] +
            stage4.score * weights['stage4']
        )
    
    def _print_statistics(self, stats):
        """Print pipeline statistics"""
        self.log(f"\n📊 PIPELINE STATISTICS:")
        self.log(f"   Input: {stats['input_count']}")
        self.log(f"   After Stage 1 (Hard Filters): {stats['stage1_survivors']} ({stats['stage1_survivors']/stats['input_count']*100:.0f}%)")
        self.log(f"   After Stage 2 (Trial Type): {stats['stage2_survivors']} ({stats['stage2_survivors']/stats['input_count']*100:.0f}%)")
        self.log(f"   After Stage 3 (Location): {stats['stage3_survivors']} ({stats['stage3_survivors']/stats['input_count']*100:.0f}%)")
        self.log(f"   Final Survivors: {stats['stage4_survivors']}")
        
        if stats['rejection_breakdown']:
            self.log(f"\n   Rejection Breakdown:")
            for stage, count in sorted(stats['rejection_breakdown'].items(), key=lambda x: x[1], reverse=True):
                self.log(f"      {stage}: {count}")
    
    async def run_stage1(self, trial) -> FilterResult:
        """STAGE 1: Hard Filters (status, disease, basic stage)"""
        from .stage1_hard_filters import status_filter, disease_filter, basic_stage_filter
        
        reasons = []
        
        # Check status
        status_pass, status_reason = status_filter.check(trial, self.config)
        if not status_pass:
            return FilterResult(False, 'STAGE_1_STATUS', 0.0, [], status_reason)
        reasons.append(status_reason)
        
        # Check disease
        disease_pass, disease_reason = disease_filter.check(trial, self.ayesha, self.config)
        if not disease_pass:
            return FilterResult(False, 'STAGE_1_DISEASE', 0.0, [], disease_reason)
        reasons.append(disease_reason)
        
        # Check basic stage
        stage_pass, stage_reason = basic_stage_filter.check(trial, self.ayesha, self.config)
        if not stage_pass:
            return FilterResult(False, 'STAGE_1_STAGE', 0.0, [], stage_reason)
        reasons.append(stage_reason)
        
        return FilterResult(True, 'STAGE_1', 0.9, reasons)
    
    async def run_stage2(self, trial) -> FilterResult:
        """STAGE 2: Trial Type Classification"""
        from .stage2_trial_type import keyword_classifier, llm_classifier
        
        # First try keyword-based (fast)
        trial_type, confidence, reasoning = keyword_classifier.classify(trial)
        
        if trial_type == 'OBSERVATIONAL':
            return FilterResult(False, 'STAGE_2_OBSERVATIONAL', 0.0, [], 
                              f"❌ Observational study: {reasoning}")
        
        # If uncertain, use LLM (slow but accurate)
        if trial_type == 'UNKNOWN' and self.use_llm:
            llm_type, llm_confidence, llm_reasoning = await llm_classifier.classify(trial)
            if llm_type == 'OBSERVATIONAL':
                return FilterResult(False, 'STAGE_2_LLM_OBSERVATIONAL', 0.0, [],
                                  f"❌ LLM: Observational - {llm_reasoning}")
            trial_type = llm_type
            confidence = llm_confidence
            reasoning = llm_reasoning
        
        return FilterResult(True, 'STAGE_2', confidence, 
                          [f'✅ {trial_type} ({confidence:.0%})'],
                          metadata={'trial_type': trial_type})
    
    async def run_stage3(self, trial) -> FilterResult:
        """STAGE 3: Location Validation (NYC metro)"""
        from .stage3_location import nyc_metro_detector
        
        has_nyc, nyc_locs, reasoning = nyc_metro_detector.check(trial)
        
        if not has_nyc:
            return FilterResult(False, 'STAGE_3_NO_NYC', 0.0, [],
                              f"❌ No NYC metro locations: {reasoning}")
        
        score = min(1.0, len(nyc_locs) * 0.3)  # More sites = higher score
        return FilterResult(True, 'STAGE_3', score,
                          [f'✅ {len(nyc_locs)} NYC metro location(s)'],
                          metadata={'nyc_locations': nyc_locs})
    
    async def run_stage4(self, trial) -> FilterResult:
        """STAGE 4: Eligibility Scoring (probability)"""
        from .stage4_eligibility import probability_calculator
        
        prob, breakdown = probability_calculator.calculate(trial, self.ayesha)
        
        return FilterResult(True, 'STAGE_4', prob, breakdown,
                          metadata={'eligibility_probability': prob})
    
    async def run_stage5(self, trial) -> FilterResult:
        """STAGE 5: LLM Deep Analysis"""
        from .stage5_llm_analysis import trial_fit_analyzer
        
        analysis = await trial_fit_analyzer.analyze(trial, self.ayesha)
        
        return FilterResult(True, 'STAGE_5', 1.0, [],
                          metadata={'llm_analysis': analysis})

