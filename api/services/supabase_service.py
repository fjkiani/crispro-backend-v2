"""
Supabase service for database operations.
"""
import json
import time
import httpx
from httpx import Timeout
from typing import Dict, Any, List
import logging
from ..config import SUPABASE_URL, SUPABASE_KEY

logger = logging.getLogger(__name__)

class SupabaseService:
    """Service for handling Supabase database operations."""
    
    def __init__(self):
        self.url = SUPABASE_URL
        self.key = SUPABASE_KEY
        self.enabled = bool(self.url and self.key)
    
    async def insert(self, table: str, rows: List[Dict[str, Any]], timeout_s: float = 5.0) -> None:
        """Insert rows into a Supabase table."""
        if not self.enabled or not table or not rows:
            return
            
        url = f"{self.url.rstrip('/')}/rest/v1/{table}"
        headers = {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }
        
        async with httpx.AsyncClient(timeout=Timeout(timeout_s)) as client:
            try:
                await client.post(url, headers=headers, content=json.dumps(rows))
            except Exception:
                # Never fail the request due to analytics
                return
    
    async def select(self, table: str, eq: Dict[str, Any], order: str = "", limit: int = 1000, timeout_s: float = 5.0):
        """Select rows from a Supabase table."""
        if not self.enabled:
            return []
            
        url = f"{self.url.rstrip('/')}/rest/v1/{table}"
        headers = {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
        }
        
        params = {"select": "*", "limit": str(limit)}
        # equality filters
        for k, v in (eq or {}).items():
            params[f"{k}"] = f"eq.{v}"
        if order:
            params["order"] = order
            
        async with httpx.AsyncClient(timeout=Timeout(timeout_s)) as client:
            try:
                r = await client.get(url, headers=headers, params=params)
                r.raise_for_status()
                return r.json()
            except Exception:
                return []
    
    async def log_event(self, run_signature: str, stage: str, message: str = "", table: str = "mdt_events") -> None:
        """Log an event to the events table."""
        try:
            if not self.enabled:
                return
            ts = int(time.time())
            await self.insert(table, [{
                "run_signature": run_signature,
                "stage": stage,
                "message": message[:2000],
                "t": ts,
            }])
        except Exception:
            return
    
    async def log_run(self, run_data: Dict[str, Any], table: str = "mdt_runs") -> None:
        """Log a run to the runs table."""
        try:
            if not self.enabled:
                return
            await self.insert(table, [run_data])
        except Exception:
            return
    
    async def log_variants(self, variant_data: List[Dict[str, Any]], table: str = "mdt_run_variants") -> None:
        """Log variant data to the variants table."""
        try:
            if not self.enabled or not variant_data:
                return
            await self.insert(table, variant_data)
        except Exception:
            return
    
    async def log_evidence_run(self, run_data: Dict[str, Any], table: str = "mdt_evidence_runs") -> None:
        """Log complete evidence prediction run with metadata."""
        try:
            if not self.enabled or not run_data:
                return
            
            # Ensure we have required fields
            run_entry = {
                "run_signature": run_data.get("run_signature", "unknown"),
                "request_payload": json.dumps(run_data.get("request", {})),
                "sequence_details": json.dumps(run_data.get("sequence_details", [])),
                "pathway_scores": json.dumps(run_data.get("pathway_scores", {})),
                "scoring_strategy": json.dumps(run_data.get("scoring_strategy", {})),
                "confidence_tier": run_data.get("confidence_tier", "insufficient"),
                "drug_count": run_data.get("drug_count", 0),
                "created_at": run_data.get("created_at", time.time())
            }
            
            await self.insert(table, [run_entry])
        except Exception:
            return
    
    async def log_evidence_items(self, evidence_data: List[Dict[str, Any]], table: str = "mdt_evidence_items") -> None:
        """Log individual evidence items (citations, ClinVar, etc.) for a run."""
        try:
            if not self.enabled or not evidence_data:
                return
            
            # Ensure each evidence item has required fields
            evidence_entries = []
            for item in evidence_data:
                entry = {
                    "run_signature": item.get("run_signature", "unknown"),
                    "drug_name": item.get("drug_name", ""),
                    "evidence_type": item.get("evidence_type", "unknown"),  # citation, clinvar, prior
                    "evidence_content": json.dumps(item.get("content", {})),
                    "strength_score": item.get("strength_score", 0.0),
                    "pubmed_id": item.get("pubmed_id"),
                    "created_at": item.get("created_at", time.time())
                }
                evidence_entries.append(entry)
            
            await self.insert(table, evidence_entries)
        except Exception:
            return
    
    async def update(self, table: str, data: Dict[str, Any], eq: Dict[str, Any], timeout_s: float = 5.0) -> bool:
        """
        Update rows in a Supabase table.
        
        Args:
            table: Table name
            data: Data to update
            eq: Equality filters for WHERE clause
            timeout_s: Request timeout
            
        Returns:
            True if update successful, False otherwise
        """
        if not self.enabled or not table or not data or not eq:
            return False
            
        url = f"{self.url.rstrip('/')}/rest/v1/{table}"
        headers = {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }
        
        # Build query parameters for WHERE clause
        params = {}
        for k, v in eq.items():
            params[f"{k}"] = f"eq.{v}"
        
        async with httpx.AsyncClient(timeout=Timeout(timeout_s)) as client:
            try:
                response = await client.patch(url, headers=headers, params=params, content=json.dumps(data))
                response.raise_for_status()
                return True
            except Exception as e:
                logger.error(f"Supabase update failed: {e}")
                return False

# Global instance
supabase = SupabaseService()

# Legacy helper functions for backward compatibility
async def _supabase_select(table: str, columns: list = None, eq: dict = None, limit: int = 1000):
    """Legacy helper function for select operations."""
    return await supabase.select(table, eq or {}, limit=limit)

async def _supabase_event(stage: str, data: dict, run_signature: str = "default"):
    """Legacy helper function for event logging."""
    await supabase.log_event(run_signature, stage, str(data))

async def _supabase_insert(table: str, rows: list):
    """Legacy helper function for insert operations."""
    await supabase.insert(table, rows)

async def _supabase_update(table: str, data: dict, eq: dict):
    """Legacy helper function for update operations."""
    if not supabase.enabled or not table or not data or not eq:
        return
        
    url = f"{supabase.url.rstrip('/')}/rest/v1/{table}"
    headers = {
        "apikey": supabase.key,
        "Authorization": f"Bearer {supabase.key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }
    
    # Build query parameters for WHERE clause
    params = {}
    for k, v in eq.items():
        params[f"{k}"] = f"eq.{v}"
    
    async with httpx.AsyncClient(timeout=Timeout(5.0)) as client:
        try:
            await client.patch(url, headers=headers, params=params, content=json.dumps(data))
        except Exception:
            # Never fail the request due to analytics
            return
