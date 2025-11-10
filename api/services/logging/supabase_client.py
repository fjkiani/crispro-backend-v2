"""
Supabase Client: Core Supabase connection and operations for logging.
"""
from typing import Optional


class LoggingService:
    """Service for logging efficacy runs and evidence to Supabase."""
    
    def __init__(self):
        self.supabase = None
        self._initialize_supabase()
    
    def _initialize_supabase(self):
        """Initialize Supabase connection."""
        try:
            from api.services.supabase_service import supabase
            self.supabase = supabase
        except Exception:
            # Supabase not available
            self.supabase = None
    
    def is_available(self) -> bool:
        """Check if logging service is available."""
        return self.supabase is not None and self.supabase.enabled
    
    async def log_evidence_run(self, data: dict) -> bool:
        """Log evidence run to Supabase."""
        if not self.is_available():
            return False
        
        try:
            await self.supabase.log_evidence_run(data)
            return True
        except Exception:
            return False
    
    async def log_evidence_items(self, items: list[dict]) -> bool:
        """Log evidence items to Supabase."""
        if not self.is_available() or not items:
            return False
        
        try:
            await self.supabase.log_evidence_items(items)
            return True
        except Exception:
            return False
    
    async def get_evidence_run(self, run_signature: str) -> Optional[dict]:
        """Retrieve evidence run by signature."""
        if not self.is_available():
            return None
        
        try:
            # Get main run data
            run_data = await self.supabase.select("mdt_evidence_runs", {"run_signature": run_signature}, limit=1)
            if not run_data:
                return None
            
            # Get associated evidence items
            evidence_items = await self.supabase.select("mdt_evidence_items", {"run_signature": run_signature}, limit=100)
            
            # Parse JSON fields back
            run = run_data[0]
            run["evidence_items"] = evidence_items
            
            return run
            
        except Exception:
            return None



