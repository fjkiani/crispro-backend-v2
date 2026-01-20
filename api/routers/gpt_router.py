"""
GPT Router - Reusable API endpoint for GPT-4o access

This router provides a clean API interface to GPT that can be used by:
- Any agent needing LLM capabilities
- Benchmark comparisons
- General text generation tasks

Endpoints:
- POST /api/gpt/chat - Simple chat interface
- POST /api/gpt/chat-with-context - Chat with full message history
- POST /api/gpt/benchmark - Generate benchmark response for comparison
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Optional
import logging

from api.services.gpt_service import get_gpt_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/gpt", tags=["GPT"])


class ChatRequest(BaseModel):
    """Request for simple chat."""
    prompt: str
    system_message: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 2000


class ChatWithContextRequest(BaseModel):
    """Request for chat with full message history."""
    messages: List[Dict[str, str]]  # [{"role": "user", "content": "..."}]
    temperature: float = 0.7
    max_tokens: int = 2000


class BenchmarkRequest(BaseModel):
    """Request for benchmark response."""
    question: str
    context: Optional[str] = None


@router.post("/chat")
async def chat_endpoint(request: ChatRequest):
    """
    Simple chat interface to GPT-4o.
    
    Returns:
        {
            "response": str,
            "model": str
        }
    """
    try:
        gpt_service = get_gpt_service()
        response = await gpt_service.chat(
            prompt=request.prompt,
            system_message=request.system_message,
            temperature=request.temperature,
            max_tokens=request.max_tokens
        )
        
        return {
            "response": response,
            "model": gpt_service.model
        }
    
    except Exception as e:
        logger.error(f"❌ GPT chat failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat-with-context")
async def chat_with_context_endpoint(request: ChatWithContextRequest):
    """
    Chat with full message history.
    
    Returns:
        {
            "response": str,
            "model": str
        }
    """
    try:
        gpt_service = get_gpt_service()
        response = await gpt_service.chat_with_context(
            messages=request.messages,
            temperature=request.temperature,
            max_tokens=request.max_tokens
        )
        
        return {
            "response": response,
            "model": gpt_service.model
        }
    
    except Exception as e:
        logger.error(f"❌ GPT chat with context failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/benchmark")
async def benchmark_endpoint(request: BenchmarkRequest):
    """
    Generate benchmark response for comparison with MOAT.
    
    Returns:
        {
            "response": str,
            "model": str,
            "question": str,
            "has_context": bool
        }
    """
    try:
        gpt_service = get_gpt_service()
        result = await gpt_service.benchmark_response(
            question=request.question,
            context=request.context
        )
        
        return result
    
    except Exception as e:
        logger.error(f"❌ GPT benchmark failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))










