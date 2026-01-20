"""
LLM Router for AI-Powered Explanations
Wraps src/tools/llm_api.py to provide LLM endpoints for synthetic lethality analysis
"""
from fastapi import APIRouter, HTTPException
from typing import Dict, Any, Optional
import sys
import os
from pathlib import Path

# Add project root to path to import llm_api
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent
LLM_API_PATH = PROJECT_ROOT / "src" / "tools" / "llm_api.py"

# Add to path if not already there
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

router = APIRouter(prefix="/api/llm", tags=["llm"])

def _get_llm_function():
    """Lazy import of query_llm to handle import errors gracefully"""
    try:
        # Import from the tools directory
        sys.path.insert(0, str(PROJECT_ROOT / "src" / "tools"))
        from llm_api import query_llm
        return query_llm
    except ImportError as e:
        raise HTTPException(
            status_code=503,
            detail=f"LLM API not available: {str(e)}. Ensure src/tools/llm_api.py exists and dependencies are installed."
        )

@router.post("/explain")
async def explain_results(request: Dict[str, Any]):
    """
    Generate LLM explanation for synthetic lethality analysis results.
    
    Request body:
    {
        "prompt": "Full prompt string",
        "provider": "gemini" | "openai" | "anthropic" (default: "gemini"),
        "context": "synthetic_lethality" (optional)
    }
    
    Returns:
    {
        "explanation": "Generated explanation text",
        "provider": "gemini"
    }
    """
    try:
        query_llm = _get_llm_function()
        
        prompt = request.get("prompt", "")
        provider = request.get("provider", "gemini")
        context = request.get("context", "synthetic_lethality")
        
        if not prompt:
            raise HTTPException(status_code=400, detail="prompt required")
        
        # Call LLM API
        response = query_llm(prompt, provider=provider)
        
        return {
            "explanation": response,
            "provider": provider,
            "context": context
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"LLM error: {str(e)}"
        )

@router.post("/chat")
async def chat_with_llm(request: Dict[str, Any]):
    """
    Chat endpoint for follow-up questions about analysis.
    
    Request body:
    {
        "prompt": "User question with context",
        "provider": "gemini" | "openai" | "anthropic" (default: "gemini")
    }
    
    Returns:
    {
        "response": "LLM response text"
    }
    """
    try:
        query_llm = _get_llm_function()
        
        prompt = request.get("prompt", "")
        provider = request.get("provider", "gemini")
        
        if not prompt:
            raise HTTPException(status_code=400, detail="prompt required")
        
        response = query_llm(prompt, provider=provider)
        
        return {"response": response}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"LLM chat error: {str(e)}"
        )

@router.get("/health")
async def llm_health():
    """
    Check if LLM API is available and configured.
    
    Returns:
    {
        "available": true/false,
        "provider": "gemini" | null,
        "error": "error message if not available"
    }
    """
    try:
        query_llm = _get_llm_function()
        
        # Try a simple test query
        test_response = query_llm("Test", provider="gemini")
        
        return {
            "available": True,
            "provider": "gemini",
            "message": "LLM API is operational"
        }
    except Exception as e:
        return {
            "available": False,
            "provider": None,
            "error": str(e),
            "message": "LLM API not available. Check API keys in .env file."
        }




