"""
Signature Generator: Generate unique signatures for logging runs.
"""
import hashlib
from typing import Dict, Any


class SignatureGenerator:
    """Generator for unique run signatures."""
    
    def create_signature(self, request: Dict[str, Any]) -> str:
        """
        Create run signature from request.
        
        Args:
            request: Request dictionary
            
        Returns:
            Run signature string
        """
        return hashlib.md5(str(request).encode()).hexdigest()[:12]



