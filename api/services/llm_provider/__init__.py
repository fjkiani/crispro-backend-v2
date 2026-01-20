"""
LLM Provider Abstraction Layer

Unified interface for switching between LLM providers (Cohere, Gemini, OpenAI, etc.)
without refactoring code.

Usage:
    from api.services.llm_provider import get_llm_provider, llm_chat, LLMProvider
    
    # Auto-detect provider
    provider = get_llm_provider()
    response = await provider.chat(message="Your prompt", max_tokens=500)
    
    # Explicitly use Cohere
    provider = get_llm_provider(LLMProvider.COHERE)
    response = await provider.chat(message="Your prompt", max_tokens=500)
    
    # Convenience function
    response = await llm_chat(message="Your prompt", max_tokens=500)
"""

from .llm_abstract import (
    LLMProvider,
    LLMResponse,
    LLMProviderBase,
    CohereProvider,
    GeminiProvider,
    OpenAIProvider,
    AnthropicProvider,
    get_llm_provider,
    llm_chat,
)

__all__ = [
    "LLMProvider",
    "LLMResponse",
    "LLMProviderBase",
    "CohereProvider",
    "GeminiProvider",
    "OpenAIProvider",
    "AnthropicProvider",
    "get_llm_provider",
    "llm_chat",
]

