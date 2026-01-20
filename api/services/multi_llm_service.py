"""
Multi-LLM Service

Supports multiple LLM providers:
- OpenAI (GPT-4, GPT-4o, etc.)
- Google (Gemini)
- Anthropic (Claude)

Configuration via environment variables:
- LLM_PROVIDER: "openai" | "google" | "claude" (default: "openai")
- OPENAI_API_KEY: OpenAI API key
- GOOGLE_API_KEY: Google API key
- ANTHROPIC_API_KEY: Anthropic API key

Usage:
    from api.services.multi_llm_service import get_llm_service
    
    service = get_llm_service()
    response = await service.chat(prompt="Your question here")
"""

import os
import logging
import asyncio
import time
import hashlib
from typing import Optional, Dict, Any, List, Literal
from enum import Enum
from datetime import datetime, timedelta
from collections import defaultdict

logger = logging.getLogger(__name__)

# Provider type
LLMProvider = Literal["openai", "google", "claude"]


class Provider(Enum):
    """LLM Provider enum."""
    OPENAI = "openai"
    GOOGLE = "google"
    CLAUDE = "claude"


class MultiLLMService:
    """
    Multi-provider LLM service supporting OpenAI, Google Gemini, and Claude.
    
    Features:
    - Rate limiting with exponential backoff for 429 errors
    - Response caching to reduce API calls
    - Daily request tracking for quota management
    """
    
    # Class-level cache and rate limit tracking
    _response_cache: Dict[str, tuple] = {}  # {cache_key: (response, timestamp)}
    _daily_request_count: Dict[str, int] = defaultdict(int)  # {date: count}
    _last_reset_date: str = datetime.now().strftime("%Y-%m-%d")
    _rate_limit_delay: float = 2.0  # Base delay for rate limiting (increased for Gemini)
    _max_retries: int = 3
    _cache_ttl_seconds: int = 3600  # 1 hour cache
    _min_delay_between_calls: float = 1.0  # Minimum delay between any LLM calls (prevent rapid-fire)
    _last_call_timestamp: float = 0.0  # Track last API call time
    
    def __init__(
        self,
        provider: Optional[LLMProvider] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        enable_caching: bool = True,
        max_daily_requests: Optional[int] = None
    ):
        """
        Initialize multi-LLM service.
        
        Args:
            provider: LLM provider ("openai", "google", "claude")
                     Defaults to LLM_PROVIDER env var or "openai"
            api_key: API key for the provider
                     Defaults to provider-specific env var
            model: Model name (provider-specific)
        """
        # Determine provider
        self.provider = provider or os.getenv("LLM_PROVIDER", "openai").lower()
        
        if self.provider not in ["openai", "google", "claude"]:
            logger.warning(f"Unknown provider '{self.provider}', defaulting to 'openai'")
            self.provider = "openai"
        
        # Rate limiting and caching settings
        self.enable_caching = enable_caching
        # Free tier for gemini-2.5-flash is 20 requests/day
        self.max_daily_requests = max_daily_requests or int(os.getenv("LLM_MAX_DAILY_REQUESTS", "20"))
        
        # Initialize provider-specific client
        if self.provider == "openai":
            self._init_openai(api_key, model)
        elif self.provider == "google":
            self._init_google(api_key, model)
        elif self.provider == "claude":
            self._init_claude(api_key, model)
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")
        
        logger.info(f"✅ Multi-LLM Service initialized (provider: {self.provider}, model: {self.model}, max_daily: {self.max_daily_requests})")
    
    def _init_openai(self, api_key: Optional[str], model: Optional[str]):
        """Initialize OpenAI client."""
        try:
            from openai import AsyncOpenAI
        except ImportError:
            raise ImportError("openai package not installed. Install with: pip install openai")
        
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not found. Set it in environment or pass as argument.")
        
        self.client = AsyncOpenAI(api_key=self.api_key)
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o")
        self._chat_impl = self._chat_openai
    
    def _init_google(self, api_key: Optional[str], model: Optional[str]):
        """Initialize Google Gemini client."""
        try:
            import google.generativeai as genai
        except ImportError:
            raise ImportError("google-generativeai package not installed. Install with: pip install google-generativeai")
        
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError("GOOGLE_API_KEY not found. Set it in environment or pass as argument.")
        
        genai.configure(api_key=self.api_key)
        self.model = model or os.getenv("GOOGLE_MODEL", "gemini-2.5-flash")
        self.client = genai.GenerativeModel(self.model)
        self._chat_impl = self._chat_google
    
    def _init_claude(self, api_key: Optional[str], model: Optional[str]):
        """Initialize Anthropic Claude client."""
        try:
            from anthropic import AsyncAnthropic
        except ImportError:
            raise ImportError("anthropic package not installed. Install with: pip install anthropic")
        
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not found. Set it in environment or pass as argument.")
        
        self.client = AsyncAnthropic(api_key=self.api_key)
        self.model = model or os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")
        self._chat_impl = self._chat_claude
    
    async def chat(
        self,
        prompt: str,
        system_message: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        use_cache: bool = True,
        **kwargs
    ) -> str:
        """
        Send a chat message and get response.
        
        Features:
        - Rate limiting with exponential backoff
        - Response caching to reduce API calls
        - Daily quota tracking
        
        Args:
            prompt: User prompt
            system_message: Optional system message
            temperature: Sampling temperature (0-2)
            max_tokens: Maximum tokens in response
            use_cache: Whether to use cached responses (default: True)
            **kwargs: Additional provider-specific parameters
        
        Returns:
            Response text
        
        Raises:
            ValueError: If daily quota exceeded
            Exception: If all retries exhausted
        """
        # Check daily quota
        today = datetime.now().strftime("%Y-%m-%d")
        if today != self._last_reset_date:
            # Reset daily counter
            self._daily_request_count.clear()
            self._last_reset_date = today
        
        # Check daily quota (soft limit - warn but don't block)
        if self._daily_request_count[today] >= self.max_daily_requests:
            logger.warning(f"⚠️ Daily quota threshold reached ({self._daily_request_count[today]}/{self.max_daily_requests}). Proceeding with caution - API may rate limit.")
            # Don't block - let the API's 429 response trigger retry logic
        
        # Enforce minimum delay between calls (prevent rapid-fire requests)
        current_time = time.time()
        time_since_last_call = current_time - self._last_call_timestamp
        if time_since_last_call < self._min_delay_between_calls:
            delay_needed = self._min_delay_between_calls - time_since_last_call
            logger.debug(f"⏳ Throttling: waiting {delay_needed:.2f}s before next LLM call...")
            await asyncio.sleep(delay_needed)
        
        # Check cache
        if use_cache and self.enable_caching:
            cache_key = self._generate_cache_key(prompt, system_message, temperature, max_tokens)
            if cache_key in self._response_cache:
                cached_response, cached_time = self._response_cache[cache_key]
                age_seconds = (datetime.now() - cached_time).total_seconds()
                if age_seconds < self._cache_ttl_seconds:
                    logger.debug(f"✅ Cache hit for prompt (age: {age_seconds:.1f}s)")
                    return cached_response
                else:
                    # Cache expired, remove it
                    del self._response_cache[cache_key]
        
        # Make API call with retry logic
        for attempt in range(self._max_retries):
            try:
                response = await self._chat_impl(prompt, system_message, temperature, max_tokens, **kwargs)
                
                # Update last call timestamp
                self._last_call_timestamp = time.time()
                
                # Cache successful response
                if use_cache and self.enable_caching:
                    cache_key = self._generate_cache_key(prompt, system_message, temperature, max_tokens)
                    self._response_cache[cache_key] = (response, datetime.now())
                    # Limit cache size (keep last 100 entries)
                    if len(self._response_cache) > 100:
                        oldest_key = min(self._response_cache.keys(), key=lambda k: self._response_cache[k][1])
                        del self._response_cache[oldest_key]
                
                # Increment daily counter
                self._daily_request_count[today] += 1
                logger.debug(f"✅ LLM call successful (daily count: {self._daily_request_count[today]}/{self.max_daily_requests})")
                
                return response
            
            except Exception as e:
                error_str = str(e).lower()
                
                # Check for rate limit error (429)
                if "429" in error_str or "quota" in error_str or "rate limit" in error_str or "resourceexhausted" in error_str:
                    if attempt < self._max_retries - 1:
                        # Exponential backoff: 2^attempt * base_delay (more conservative for Gemini)
                        delay = (2 ** attempt) * self._rate_limit_delay
                        # Add jitter to prevent thundering herd
                        jitter = delay * 0.1 * (time.time() % 1.0)
                        total_delay = delay + jitter
                        logger.warning(f"⚠️ Rate limit hit (attempt {attempt + 1}/{self._max_retries}). Retrying in {total_delay:.1f}s...")
                        await asyncio.sleep(total_delay)
                        continue
                    else:
                        logger.error(f"❌ Rate limit exceeded after {self._max_retries} retries")
                        raise ValueError(f"Rate limit exceeded. Please try again later or upgrade API tier. Error: {e}")
                else:
                    # Non-rate-limit error, re-raise immediately
                    logger.error(f"❌ LLM API error: {e}")
                    raise
        
        # Should never reach here, but just in case
        raise Exception("Max retries exceeded")
    
    def _generate_cache_key(
        self,
        prompt: str,
        system_message: Optional[str],
        temperature: float,
        max_tokens: int
    ) -> str:
        """Generate cache key from prompt and parameters."""
        key_str = f"{prompt}|{system_message or ''}|{temperature}|{max_tokens}"
        return hashlib.md5(key_str.encode()).hexdigest()
    
    async def _chat_openai(
        self,
        prompt: str,
        system_message: Optional[str],
        temperature: float,
        max_tokens: int,
        **kwargs
    ) -> str:
        """OpenAI chat implementation."""
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
            logger.error(f"❌ OpenAI API error: {e}")
            raise
    
    async def _chat_google(
        self,
        prompt: str,
        system_message: Optional[str],
        temperature: float,
        max_tokens: int,
        **kwargs
    ) -> str:
        """Google Gemini chat implementation with rate limit handling."""
        try:
            import google.generativeai as genai
            
            # Combine system message and prompt
            full_prompt = prompt
            if system_message:
                full_prompt = f"{system_message}\n\n{prompt}"
            
            # Configure generation parameters
            generation_config = {
                "temperature": temperature,
                "max_output_tokens": max_tokens,
                **kwargs
            }
            
            response = await self.client.generate_content_async(
                full_prompt,
                generation_config=generation_config
            )
            
            return response.text.strip()
        
        except Exception as e:
            error_str = str(e).lower()
            # Check for specific Gemini rate limit errors
            if "429" in error_str or "quota" in error_str or "resourceexhausted" in error_str:
                # Re-raise as rate limit error for retry logic
                raise ValueError(f"Rate limit exceeded: {e}")
            else:
                logger.error(f"❌ Google Gemini API error: {e}")
                raise
    
    async def _chat_claude(
        self,
        prompt: str,
        system_message: Optional[str],
        temperature: float,
        max_tokens: int,
        **kwargs
    ) -> str:
        """Anthropic Claude chat implementation."""
        try:
            messages = [{"role": "user", "content": prompt}]
            
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_message or "You are a helpful AI assistant specializing in oncology and precision medicine.",
                messages=messages,
                **kwargs
            )
            
            # Claude returns a list of content blocks
            if response.content and len(response.content) > 0:
                return response.content[0].text.strip()
            else:
                return ""
        
        except Exception as e:
            logger.error(f"❌ Claude API error: {e}")
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
        if self.provider == "openai":
            return await self._chat_with_context_openai(messages, temperature, max_tokens, **kwargs)
        elif self.provider == "google":
            return await self._chat_with_context_google(messages, temperature, max_tokens, **kwargs)
        elif self.provider == "claude":
            return await self._chat_with_context_claude(messages, temperature, max_tokens, **kwargs)
    
    async def _chat_with_context_openai(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
        **kwargs
    ) -> str:
        """OpenAI chat with context."""
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
            logger.error(f"❌ OpenAI API error: {e}")
            raise
    
    async def _chat_with_context_google(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
        **kwargs
    ) -> str:
        """Google Gemini chat with context."""
        try:
            # Convert messages to Google format
            # Google Gemini uses a single prompt with conversation history
            conversation = []
            for msg in messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if role == "system":
                    # System messages are prepended
                    conversation.insert(0, content)
                else:
                    conversation.append(f"{role.capitalize()}: {content}")
            
            full_prompt = "\n".join(conversation)
            
            generation_config = {
                "temperature": temperature,
                "max_output_tokens": max_tokens,
                **kwargs
            }
            
            response = await self.client.generate_content_async(
                full_prompt,
                generation_config=generation_config
            )
            
            return response.text.strip()
        
        except Exception as e:
            logger.error(f"❌ Google Gemini API error: {e}")
            raise
    
    async def _chat_with_context_claude(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
        **kwargs
    ) -> str:
        """Claude chat with context."""
        try:
            # Separate system message from conversation
            system_msg = None
            conversation = []
            
            for msg in messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                
                if role == "system":
                    system_msg = content
                else:
                    conversation.append({"role": role, "content": content})
            
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_msg or "You are a helpful AI assistant specializing in oncology and precision medicine.",
                messages=conversation,
                **kwargs
            )
            
            if response.content and len(response.content) > 0:
                return response.content[0].text.strip()
            else:
                return ""
        
        except Exception as e:
            logger.error(f"❌ Claude API error: {e}")
            raise


# Global service instance
_llm_service: Optional[MultiLLMService] = None


def get_llm_service(
    provider: Optional[LLMProvider] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None
) -> MultiLLMService:
    """
    Get singleton multi-LLM service instance.
    
    Args:
        provider: LLM provider ("openai", "google", "claude")
        api_key: API key (overrides env var)
        model: Model name (overrides env var)
    
    Returns:
        MultiLLMService instance
    """
    global _llm_service
    
    # Determine provider
    selected_provider = provider or os.getenv("LLM_PROVIDER", "openai").lower()
    
    # Create new instance if provider changed or doesn't exist
    if _llm_service is None or _llm_service.provider != selected_provider:
        try:
            _llm_service = MultiLLMService(provider=selected_provider, api_key=api_key, model=model)
        except Exception as e:
            logger.warning(f"Failed to initialize {selected_provider} LLM service: {e}")
            # Fallback to OpenAI if available
            if selected_provider != "openai":
                logger.info("Falling back to OpenAI...")
                try:
                    _llm_service = MultiLLMService(provider="openai", api_key=api_key, model=model)
                except Exception as fallback_error:
                    logger.error(f"Failed to initialize OpenAI fallback: {fallback_error}")
                    raise
    
    return _llm_service


# Backward compatibility: alias for get_gpt_service
def get_gpt_service(api_key: Optional[str] = None) -> MultiLLMService:
    """
    Get LLM service (backward compatibility with gpt_service).
    
    This function maintains backward compatibility while using the new multi-LLM service.
    """
    return get_llm_service(provider="openai", api_key=api_key)

