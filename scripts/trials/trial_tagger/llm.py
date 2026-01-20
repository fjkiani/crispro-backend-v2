"""
LLM Client for Trial Tagging
=============================
Clean, reusable LLM interface with rate limiting.
"""

import os
import json
import asyncio
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import hashlib

from .config import TaggingConfig, MOA_PATHWAYS
from .db import Trial
from .prompts import build_batch_prompt, build_single_prompt

logger = logging.getLogger(__name__)


class GeminiTagger:
    """
    Efficient Gemini-based trial tagger.
    
    Key optimizations:
    - Batch multiple trials per API call
    - Reuse model instance
    - Smart retry with exponential backoff
    """
    
    def __init__(self, config: TaggingConfig, api_key: Optional[str] = None):
        self.config = config
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        
        if not self.api_key:
            raise ValueError("GOOGLE_API_KEY or GEMINI_API_KEY required")
        
        # Initialize Gemini
        import google.generativeai as genai
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel(config.model)
        self._genai = genai
        
        # Stats
        self.api_calls = 0
        self.total_trials_tagged = 0
    
    async def tag_batch(self, trials: List[Trial]) -> Dict[str, Dict]:
        """
        Tag a batch of trials with a SINGLE API call.
        
        Returns: Dict mapping NCT ID to MoA data
        """
        if not trials:
            return {}
        
        prompt = build_batch_prompt(trials)
        
        for attempt in range(self.config.max_retries):
            try:
                # Make API call
                response = await asyncio.to_thread(
                    self.model.generate_content, 
                    prompt
                )
                self.api_calls += 1
                
                if not response or not response.text:
                    logger.warning("Empty response from Gemini")
                    continue
                
                # Parse response
                results = self._parse_batch_response(response.text, trials)
                self.total_trials_tagged += len(results)
                return results
                
            except Exception as e:
                error_str = str(e).lower()
                is_rate_limit = any(x in error_str for x in ["429", "rate limit", "quota", "resourceexhausted"])
                
                if is_rate_limit and attempt < self.config.max_retries - 1:
                    delay = self.config.delay_on_rate_limit * (2 ** attempt)
                    logger.warning(f"Rate limit hit, waiting {delay:.1f}s (attempt {attempt + 1})")
                    await asyncio.sleep(delay)
                elif attempt < self.config.max_retries - 1:
                    delay = 2.0 * (attempt + 1)
                    logger.warning(f"Error: {e}, retrying in {delay:.1f}s")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"Failed after {self.config.max_retries} attempts: {e}")
                    return {}
        
        return {}
    
    def _parse_batch_response(self, text: str, trials: List[Trial]) -> Dict[str, Dict]:
        """Parse batch response into MoA vectors."""
        results = {}
        
        # Clean JSON
        text = text.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        
        try:
            data = json.loads(text)
            if not isinstance(data, list):
                data = [data]
            
            for item in data:
                nct_id = item.get("nct_id")
                if not nct_id:
                    continue
                
                # Extract and validate MoA vector
                moa_vector = {}
                raw_vector = item.get("moa_vector", {})
                for pathway in MOA_PATHWAYS:
                    val = raw_vector.get(pathway, 0.0)
                    moa_vector[pathway] = max(0.0, min(1.0, float(val)))
                
                confidence = max(0.0, min(1.0, float(item.get("confidence", 0.0))))
                
                # Skip low confidence if below threshold
                if confidence < self.config.min_confidence:
                    logger.debug(f"Skipping {nct_id}: confidence {confidence:.2f} < {self.config.min_confidence}")
                    continue
                
                # Find original trial for checksum
                trial = next((t for t in trials if t.nct_id == nct_id), None)
                source_data = f"{trial.title}{trial.interventions}{trial.summary}" if trial else nct_id
                
                results[nct_id] = {
                    "moa_vector": moa_vector,
                    "confidence": confidence,
                    "source": "gemini_batch_v2",
                    "tagged_at": datetime.utcnow().isoformat() + "Z",
                    "reviewed_by": "TrialTaggingAgent",
                    "provenance": {
                        "model": self.config.model,
                        "version": "v2",
                        "batch_size": len(trials),
                        "primary_moa": item.get("primary_moa", "Unknown"),
                        "source_checksum": hashlib.md5(source_data.encode()).hexdigest()[:12],
                    }
                }
        
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {e}")
            logger.debug(f"Response: {text[:500]}")
        
        return results
    
    async def tag_single(self, trial: Trial) -> Optional[Dict]:
        """Tag a single trial (fallback for failed batches)."""
        results = await self.tag_batch([trial])
        return results.get(trial.nct_id)

