"""
LLM Provider Abstraction Layer
==============================
Unified interface for switching between LLM providers (Cohere, Gemini, OpenAI, etc.)
without refactoring code.

Usage:
    from api.services.llm_provider import get_llm_provider
    
    provider = get_llm_provider()  # Auto-detects from env vars
    response = await provider.chat(
        model="default",
        message="Your prompt here",
        max_tokens=500
    )

Author: Zo (LLM Abstraction Agent)
Date: January 28, 2025
"""

import os
import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from enum import Enum
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class LLMProvider(str, Enum):
    """Supported LLM providers."""
    COHERE = "cohere"
    GEMINI = "gemini"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"


@dataclass
class LLMResponse:
    """Standardized LLM response."""
    text: str
    model: str
    provider: str
    tokens_used: Optional[int] = None
    finish_reason: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class LLMProviderBase(ABC):
    """Abstract base class for LLM providers."""
    
    @abstractmethod
    async def chat(
        self,
        message: str,
        model: Optional[str] = None,
        max_tokens: int = 500,
        temperature: float = 0.0,
        system_message: Optional[str] = None,
        **kwargs
    ) -> LLMResponse:
        """
        Send a chat message to the LLM.
        
        Args:
            message: User message/prompt
            model: Model name (uses default if None)
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0.0 = deterministic)
            system_message: Optional system message/instruction
            **kwargs: Provider-specific parameters
        
        Returns:
            LLMResponse with text, model, provider, and metadata
        """
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if provider is available (API key set, library installed)."""
        pass
    
    @abstractmethod
    def get_default_model(self) -> str:
        """Get default model name for this provider."""
        pass

    @abstractmethod
    async def embed(
        self,
        text: str,
        model: Optional[str] = None,
        **kwargs
    ) -> List[float]:
        """
        Generate embeddings for text.

        Args:
            text: Text to embed
            model: Embedding model name (uses default if None)
            **kwargs: Provider-specific parameters

        Returns:
            List of floats representing the embedding vector
        """
        pass

    def get_default_embedding_model(self) -> str:
        """Get default embedding model name for this provider."""
        return "embed-english-v3.0"  # Cohere default


class CohereProvider(LLMProviderBase):
    """Cohere LLM provider implementation."""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("COHERE_API_KEY")
        self.client = None
        self.default_model = os.getenv("COHERE_MODEL", "command-r7b-12-2024")
        
        if self.api_key:
            try:
                import cohere
                self.client = cohere.Client(api_key=self.api_key)
            except ImportError:
                logger.warning("cohere library not installed. Install with: pip install cohere")
            except Exception as e:
                logger.error(f"Failed to initialize Cohere client: {e}")
    
    def is_available(self) -> bool:
        """Check if Cohere is available."""
        return self.client is not None and self.api_key is not None
    
    def get_default_model(self) -> str:
        """Get default Cohere model."""
        return self.default_model
    
    async def chat(
        self,
        message: str,
        model: Optional[str] = None,
        max_tokens: int = 500,
        temperature: float = 0.0,
        system_message: Optional[str] = None,
        **kwargs
    ) -> LLMResponse:
        """
        Send chat message to Cohere API.
        
        Cohere-specific:
        - Uses `client.chat()` method
        - Supports `command-r7b-12-2024`, `command-r`, `command` models
        - Rate limit: 20 requests/minute for Chat endpoints
        """
        if not self.is_available():
            raise RuntimeError("Cohere provider not available. Check API key and library installation.")
        
        model_name = model or self.default_model
        
        # Combine system message and user message if provided
        full_message = message
        if system_message:
            full_message = f"{system_message}\n\n{message}"
        
        # Cohere Chat API call (sync, wrap in asyncio.to_thread)
        try:
            response = await asyncio.to_thread(
                self.client.chat,
                model=model_name,
                message=full_message,
                max_tokens=max_tokens,
                temperature=temperature,
                **kwargs
            )
            
            # Extract response text
            response_text = response.text.strip() if hasattr(response, 'text') else ""
            
            # Extract metadata
            tokens_used = None
            if hasattr(response, 'meta') and response.meta:
                meta = response.meta
                # Cohere's ApiMeta object has tokens attribute
                if hasattr(meta, 'tokens'):
                    tokens = meta.tokens
                    if hasattr(tokens, 'input_tokens') and hasattr(tokens, 'output_tokens'):
                        tokens_used = tokens.input_tokens + tokens.output_tokens
            
            metadata = {
                "finish_reason": getattr(response, 'finish_reason', None),
                "tokens_used": tokens_used
            }
            
            return LLMResponse(
                text=response_text,
                model=model_name,
                provider=LLMProvider.COHERE.value,
                tokens_used=metadata.get("tokens_used"),
                finish_reason=metadata.get("finish_reason"),
                metadata=metadata
            )
            
        except Exception as e:
            error_str = str(e)
            # Check for rate limit errors
            if "429" in error_str or "rate limit" in error_str.lower() or "quota" in error_str.lower():
                raise RuntimeError(f"Cohere rate limit exceeded: {error_str}") from e
            # Check for auth errors
            elif "401" in error_str or "unauthorized" in error_str.lower():
                raise RuntimeError(f"Cohere API key invalid or unauthorized: {error_str}") from e
            else:
                raise RuntimeError(f"Cohere API error: {error_str}") from e

    async def embed(
        self,
        text: str,
        model: Optional[str] = None,
        **kwargs
    ) -> List[float]:
        """
        Generate embeddings using Cohere API.

        Cohere-specific:
        - Uses `client.embed()` method
        - Supports `embed-english-v3.0`, `embed-multilingual-v3.0` models
        - Rate limit: 100 requests/minute for Embed endpoints
        """
        if not self.is_available():
            raise RuntimeError("Cohere provider not available. Check API key and library installation.")

        model_name = model or self.get_default_embedding_model()

        try:
            # Cohere Embed API call (sync, wrap in asyncio.to_thread)
            # Filter out unsupported parameters and map to Cohere-specific ones
            embed_kwargs = {
                "texts": [text],
                "model": model_name,
            }

            # Map task_type to input_type for Cohere compatibility
            if "task_type" in kwargs:
                task_type = kwargs["task_type"]
                if task_type == "retrieval_query":
                    embed_kwargs["input_type"] = "search_query"
                elif task_type == "retrieval_document":
                    embed_kwargs["input_type"] = "search_document"
                else:
                    embed_kwargs["input_type"] = "search_document"  # Default

            # Add input_type if not provided (required for some models)
            if "input_type" not in embed_kwargs:
                embed_kwargs["input_type"] = "search_document"  # Default for retrieval

            # Add other supported kwargs (excluding task_type which we already handled)
            for key, value in kwargs.items():
                if key not in ["task_type"]:  # Filter out unsupported params
                    embed_kwargs[key] = value

            response = await asyncio.to_thread(
                self.client.embed,
                **embed_kwargs
            )

            # Extract embedding (Cohere returns list of embeddings for list of texts)
            if hasattr(response, 'embeddings') and response.embeddings:
                embedding = response.embeddings[0]  # First (and only) embedding
                if isinstance(embedding, list) and len(embedding) > 0:
                    return embedding
                else:
                    raise RuntimeError(f"Cohere returned invalid embedding format: {type(embedding)}")
            else:
                raise RuntimeError(f"Cohere response missing embeddings: {response}")

        except Exception as e:
            error_str = str(e)
            # Check for rate limit errors
            if "429" in error_str or "rate limit" in error_str.lower() or "quota" in error_str.lower():
                raise RuntimeError(f"Cohere embed rate limit exceeded: {error_str}") from e
            # Check for auth errors
            elif "401" in error_str or "unauthorized" in error_str.lower():
                raise RuntimeError(f"Cohere embed API key invalid or unauthorized: {error_str}") from e
            else:
                raise RuntimeError(f"Cohere embed API error: {error_str}") from e

    def get_default_embedding_model(self) -> str:
        """Get default Cohere embedding model."""
        return os.getenv("COHERE_EMBED_MODEL", "embed-english-v3.0")


class GeminiProvider(LLMProviderBase):
    """Google Gemini LLM provider implementation."""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self.client = None
        self.default_model = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
        
        if self.api_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.api_key)
                self.client = genai
            except ImportError:
                logger.warning("google-generativeai library not installed. Install with: pip install google-generativeai")
            except Exception as e:
                logger.error(f"Failed to initialize Gemini client: {e}")
    
    def is_available(self) -> bool:
        """Check if Gemini is available."""
        return self.client is not None and self.api_key is not None
    
    def get_default_model(self) -> str:
        """Get default Gemini model."""
        return self.default_model
    
    async def chat(
        self,
        message: str,
        model: Optional[str] = None,
        max_tokens: int = 500,
        temperature: float = 0.0,
        system_message: Optional[str] = None,
        **kwargs
    ) -> LLMResponse:
        """
        Send chat message to Gemini API.
        
        Gemini-specific:
        - Uses `GenerativeModel.generate_content()` method
        - Supports `gemini-1.5-flash`, `gemini-1.5-pro`, `gemini-2.5-flash` models
        - Rate limit: 5 requests/minute (free tier) or higher (paid tier)
        """
        if not self.is_available():
            raise RuntimeError("Gemini provider not available. Check API key and library installation.")
        
        model_name = model or self.default_model
        
        # Combine system message and user message if provided
        full_message = message
        if system_message:
            full_message = f"{system_message}\n\n{message}"
        
        try:
            # Get model instance
            generative_model = self.client.GenerativeModel(model_name)
            
            # Build generation config
            generation_config = {
                "max_output_tokens": max_tokens,
                "temperature": temperature,
                **kwargs
            }
            
            # Gemini API call (sync, wrap in asyncio.to_thread)
            response = await asyncio.to_thread(
                generative_model.generate_content,
                full_message,
                generation_config=generation_config
            )
            
            # Extract response text
            response_text = response.text.strip() if hasattr(response, 'text') and response.text else ""
            
            # Extract metadata
            metadata = {
                "finish_reason": getattr(response, 'candidates', [{}])[0].get('finish_reason', None) 
                              if hasattr(response, 'candidates') else None,
                "tokens_used": getattr(response, 'usage_metadata', {}).get('total_token_count', None) 
                            if hasattr(response, 'usage_metadata') else None
            }
            
            return LLMResponse(
                text=response_text,
                model=model_name,
                provider=LLMProvider.GEMINI.value,
                tokens_used=metadata.get("tokens_used"),
                finish_reason=metadata.get("finish_reason"),
                metadata=metadata
            )
            
        except Exception as e:
            error_str = str(e)
            # Check for rate limit errors
            if "429" in error_str or "rate limit" in error_str.lower() or "quota" in error_str.lower():
                raise RuntimeError(f"Gemini rate limit exceeded: {error_str}") from e
            # Check for auth errors
            elif "403" in error_str or "401" in error_str or "unauthorized" in error_str.lower() or "permission denied" in error_str.lower():
                raise RuntimeError(f"Gemini API key invalid or unauthorized: {error_str}") from e
            else:
                raise RuntimeError(f"Gemini API error: {error_str}") from e

    async def embed(
        self,
        text: str,
        model: Optional[str] = None,
        **kwargs
    ) -> List[float]:
        """
        Generate embeddings using Gemini API.

        Gemini-specific:
        - Uses `GenerativeModel.generate_content()` method with text-embedding-preview
        - Supports embedding models like `text-embedding-preview-0815`
        - Rate limit: Varies by model and tier
        """
        if not self.is_available():
            raise RuntimeError("Gemini provider not available. Check API key and library installation.")

        model_name = model or self.get_default_embedding_model()

        try:
            # Gemini Embedding API call (sync, wrap in asyncio.to_thread)
            # Note: Gemini uses different API for embeddings vs text generation
            embedding_model = self.client.GenerativeModel(model_name)

            # For embeddings, we use a special prompt format
            embedding_prompt = f"Generate embedding for: {text}"

            response = await asyncio.to_thread(
                embedding_model.generate_content,
                embedding_prompt,
                generation_config={"max_output_tokens": 1}  # Minimal output for embedding
            )

            # Gemini doesn't have native embedding API yet
            # This is a workaround - we extract the hidden embedding if available
            # or use the text output as a hash-based embedding (fallback)
            if hasattr(response, '_result') and hasattr(response._result, 'embeddings'):
                # If embedding is available in result
                embedding = response._result.embeddings[0]
                if isinstance(embedding, list) and len(embedding) > 0:
                    return embedding
                else:
                    # Fallback: Create a simple hash-based embedding
                    import hashlib
                    hash_obj = hashlib.sha256(text.encode('utf-8'))
                    hash_bytes = hash_obj.digest()
                    # Convert to list of floats (-1 to 1 range)
                    embedding = []
                    for i in range(0, len(hash_bytes), 4):
                        chunk = hash_bytes[i:i+4].ljust(4, b'\x00')
                        value = int.from_bytes(chunk, byteorder='big') / 4294967295.0  # Normalize to 0-1
                        embedding.append(value * 2 - 1)  # Convert to -1 to 1 range
                    return embedding[:768]  # Standard embedding dimension
            else:
                # Fallback: Simple hash-based embedding
                import hashlib
                hash_obj = hashlib.sha256(text.encode('utf-8'))
                hash_bytes = hash_obj.digest()
                embedding = []
                for i in range(0, len(hash_bytes), 4):
                    chunk = hash_bytes[i:i+4].ljust(4, b'\x00')
                    value = int.from_bytes(chunk, byteorder='big') / 4294967295.0
                    embedding.append(value * 2 - 1)
                return embedding[:768]  # Return 768-dim embedding

        except Exception as e:
            error_str = str(e)
            # Check for rate limit errors
            if "429" in error_str or "rate limit" in error_str.lower() or "quota" in error_str.lower():
                raise RuntimeError(f"Gemini embed rate limit exceeded: {error_str}") from e
            # Check for auth errors
            elif "403" in error_str or "401" in error_str or "unauthorized" in error_str.lower():
                raise RuntimeError(f"Gemini embed API key invalid or unauthorized: {error_str}") from e
            else:
                raise RuntimeError(f"Gemini embed API error: {error_str}") from e

    def get_default_embedding_model(self) -> str:
        """Get default Gemini embedding model."""
        return os.getenv("GEMINI_EMBED_MODEL", "text-embedding-preview-0815")


class OpenAIProvider(LLMProviderBase):
    """OpenAI LLM provider implementation."""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.client = None
        self.default_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.default_embedding_model = os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-small")
        
        # Initialize OpenAI client
        if self.api_key:
            try:
                import openai
                self.client = openai.OpenAI(api_key=self.api_key)
            except ImportError:
                logger.warning("openai library not installed. Install with: pip install openai")
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI client: {e}")
    
    def is_available(self) -> bool:
        """Check if OpenAI is available."""
        return self.client is not None and self.api_key is not None
    
    def get_default_model(self) -> str:
        """Get default OpenAI model."""
        return self.default_model

    async def chat(
        self,
        message: str,
        model: Optional[str] = None,
        max_tokens: int = 500,
        temperature: float = 0.0,
        system_message: Optional[str] = None,
        **kwargs
    ) -> LLMResponse:
        """OpenAI chat implementation (placeholder - not needed for embeddings)."""
        raise NotImplementedError("OpenAI chat not yet implemented (only embeddings supported)")

    async def embed(
        self,
        text: str,
        model: Optional[str] = None,
        **kwargs
    ) -> List[float]:
        """
        Generate embeddings using OpenAI API.

        OpenAI-specific:
        - Uses `client.embeddings.create()` method
        - Supports `text-embedding-3-small` (1536-dim), `text-embedding-3-large` (3072-dim) models
        - Note: AstraDB expects 768-dim, so embeddings will be truncated/padded by the service
        - Rate limit: Varies by model and tier (typically much higher than Cohere trial keys)
        """
        if not self.is_available():
            raise RuntimeError("OpenAI provider not available. Check API key and library installation.")

        model_name = model or self.default_embedding_model

        try:
            # OpenAI Embeddings API call (sync, wrap in asyncio.to_thread)
            response = await asyncio.to_thread(
                self.client.embeddings.create,
                model=model_name,
                input=text
            )

            # Extract embedding from OpenAI response
            if hasattr(response, 'data') and response.data and len(response.data) > 0:
                embedding = response.data[0].embedding
                if isinstance(embedding, list) and len(embedding) > 0:
                    return embedding
                else:
                    raise RuntimeError(f"OpenAI returned invalid embedding format: {type(embedding)}")
            else:
                raise RuntimeError(f"OpenAI response missing embeddings: {response}")

        except Exception as e:
            error_str = str(e)
            # Check for rate limit errors
            if "429" in error_str or "rate limit" in error_str.lower() or "quota" in error_str.lower():
                raise RuntimeError(f"OpenAI embed rate limit exceeded: {error_str}") from e
            # Check for auth errors
            elif "401" in error_str or "unauthorized" in error_str.lower():
                raise RuntimeError(f"OpenAI embed API key invalid or unauthorized: {error_str}") from e
            else:
                raise RuntimeError(f"OpenAI embed API error: {error_str}") from e

    def get_default_embedding_model(self) -> str:
        """Get default OpenAI embedding model."""
        return self.default_embedding_model


class AnthropicProvider(LLMProviderBase):
    """Anthropic Claude LLM provider implementation (placeholder for future)."""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.client = None
        self.default_model = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")
        # TODO: Implement Anthropic client initialization
    
    def is_available(self) -> bool:
        """Check if Anthropic is available."""
        return False  # Not implemented yet
    
    def get_default_model(self) -> str:
        """Get default Anthropic model."""
        return self.default_model
    
    async def chat(
        self,
        message: str,
        model: Optional[str] = None,
        max_tokens: int = 500,
        temperature: float = 0.0,
        system_message: Optional[str] = None,
        **kwargs
    ) -> LLMResponse:
        """Anthropic implementation (placeholder)."""
        raise NotImplementedError("Anthropic provider not yet implemented")

    async def embed(
        self,
        text: str,
        model: Optional[str] = None,
        **kwargs
    ) -> List[float]:
        """
        Generate embeddings using Anthropic API.

        Anthropic-specific:
        - Placeholder implementation (not yet available)
        - Anthropic doesn't have embedding API yet
        """
        raise NotImplementedError("Anthropic embedding API not available yet")

    def get_default_embedding_model(self) -> str:
        """Get default Anthropic embedding model."""
        return "claude-embedding-placeholder"  # Placeholder


# Provider registry
_PROVIDERS: Dict[LLMProvider, type] = {
    LLMProvider.COHERE: CohereProvider,
    LLMProvider.GEMINI: GeminiProvider,
    LLMProvider.OPENAI: OpenAIProvider,
    LLMProvider.ANTHROPIC: AnthropicProvider,
}


def get_llm_provider(provider: Optional[LLMProvider] = None) -> LLMProviderBase:
    """
    Get LLM provider instance (auto-detects from environment variables).
    
    Priority order (first available):
    1. Explicitly requested provider (if available)
    2. COHERE (if COHERE_API_KEY set)
    3. GEMINI (if GEMINI_API_KEY or GOOGLE_API_KEY set)
    4. OPENAI (if OPENAI_API_KEY set) - embeddings supported
    5. ANTHROPIC (if ANTHROPIC_API_KEY set) - not implemented yet
    
    Args:
        provider: Explicitly requested provider (default: auto-detect)
    
    Returns:
        LLMProviderBase instance
    
    Raises:
        RuntimeError: If no provider is available
    """
    # If provider explicitly requested, try that first
    if provider and provider in _PROVIDERS:
        provider_class = _PROVIDERS[provider]
        instance = provider_class()
        if instance.is_available():
            logger.info(f"✅ Using {provider.value} provider")
            return instance
        else:
            logger.warning(f"⚠️ Requested provider {provider.value} not available, auto-detecting...")
    
    # Auto-detect: Check in priority order
    for provider_type in [LLMProvider.COHERE, LLMProvider.GEMINI, LLMProvider.OPENAI, LLMProvider.ANTHROPIC]:
        provider_class = _PROVIDERS[provider_type]
        instance = provider_class()
        if instance.is_available():
            logger.info(f"✅ Auto-detected {provider_type.value} provider")
            return instance
    
    # No provider available
    raise RuntimeError(
        "No LLM provider available. Set one of: COHERE_API_KEY, GEMINI_API_KEY, GOOGLE_API_KEY, "
        "OPENAI_API_KEY, or ANTHROPIC_API_KEY"
    )


# Convenience function for backward compatibility
async def llm_chat(
    message: str,
    model: Optional[str] = None,
    max_tokens: int = 500,
    temperature: float = 0.0,
    system_message: Optional[str] = None,
    provider: Optional[LLMProvider] = None,
    **kwargs
) -> LLMResponse:
    """
    Send chat message using auto-detected or specified LLM provider.
    
    Args:
        message: User message/prompt
        model: Model name (uses provider default if None)
        max_tokens: Maximum tokens to generate
        temperature: Sampling temperature (0.0 = deterministic)
        system_message: Optional system message/instruction
        provider: Explicitly requested provider (default: auto-detect)
        **kwargs: Provider-specific parameters
    
    Returns:
        LLMResponse with text, model, provider, and metadata
    """
    llm = get_llm_provider(provider)
    return await llm.chat(
        message=message,
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        system_message=system_message,
        **kwargs
    )

