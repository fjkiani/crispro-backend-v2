"""
Reusable GPT Service for MOAT Benchmark and General Use

This service provides a clean interface to OpenAI GPT-4o that can be used by:
- Benchmark comparisons (MOAT vs GPT)
- Any agent that needs LLM capabilities
- General text generation tasks

Usage:
    from api.services.gpt_service import get_gpt_service
    
    service = get_gpt_service()
    response = await service.chat(prompt="Your question here")
"""

import os
import logging
from typing import Optional, Dict, Any, List
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

# Global client instance
_gpt_client: Optional[AsyncOpenAI] = None


def get_gpt_service(api_key: Optional[str] = None) -> 'GPTService':
    """Get singleton GPT service instance."""
    return GPTService(api_key=api_key)


class GPTService:
    """Reusable GPT service for OpenAI API calls."""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o"):
        """
        Initialize GPT service.
        
        Args:
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
            model: Model to use (default: gpt-4o)
        """
        global _gpt_client
        
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model
        
        if not self.api_key:
            raise ValueError(
                "OPENAI_API_KEY not found. Set it in environment or pass as argument."
            )
        
        if _gpt_client is None or _gpt_client.api_key != self.api_key:
            _gpt_client = AsyncOpenAI(api_key=self.api_key)
        
        self.client = _gpt_client
        logger.info(f"✅ GPT Service initialized (model: {self.model})")
    
    async def chat(
        self,
        prompt: str,
        system_message: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        **kwargs
    ) -> str:
        """
        Send a chat message to GPT and get response.
        
        Args:
            prompt: User prompt
            system_message: Optional system message (default: helpful assistant)
            temperature: Sampling temperature (0-2)
            max_tokens: Maximum tokens in response
            **kwargs: Additional OpenAI API parameters
        
        Returns:
            Response text
        """
        messages = []
        
        if system_message:
            messages.append({"role": "system", "content": system_message})
        else:
            messages.append({
                "role": "system",
                "content": "You are a helpful AI assistant specializing in oncology and precision medicine."
            })
        
        messages.append({"role": "user", "content": prompt})
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs
            )
            
            return response.choices[0].message.content.strip()
        
        except Exception as e:
            logger.error(f"❌ GPT API error: {e}")
            raise
    
    async def chat_with_context(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2000,
        **kwargs
    ) -> str:
        """
        Send a conversation with full message history.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature
            max_tokens: Maximum tokens
            **kwargs: Additional parameters
        
        Returns:
            Response text
        """
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs
            )
            
            return response.choices[0].message.content.strip()
        
        except Exception as e:
            logger.error(f"❌ GPT API error: {e}")
            raise
    
    async def benchmark_response(
        self,
        question: str,
        context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate a benchmark response for comparison with MOAT.
        
        Args:
            question: User question
            context: Optional patient context (for personalized questions)
        
        Returns:
            Dict with response and metadata
        """
        system_message = """You are a medical AI assistant. Answer questions about oncology, 
nutrition, and drug interactions. Be helpful but always recommend consulting with healthcare providers.
Do not provide specific medical diagnoses or treatment recommendations without proper context."""
        
        if context:
            prompt = f"""Context: {context}

Question: {question}

Please provide a helpful answer."""
        else:
            prompt = question
        
        try:
            response_text = await self.chat(
                prompt=prompt,
                system_message=system_message,
                temperature=0.7,
                max_tokens=2000
            )
            
            return {
                "response": response_text,
                "model": self.model,
                "question": question,
                "has_context": context is not None
            }
        
        except Exception as e:
            logger.error(f"❌ Benchmark response failed: {e}")
            return {
                "response": f"Error: {str(e)}",
                "model": self.model,
                "question": question,
                "error": str(e)
            }

