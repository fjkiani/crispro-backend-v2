import os
import re
import json
from typing import Any, Optional

from google import genai

from .utils import safe_json_loads

class LLMClient:
    def __init__(self, model: Optional[str] = None):
        self.model = model or os.getenv("LLM_MODEL", "gemini-2.5-flash")
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY required. Get from https://aistudio.google.com/app/apikey")
        try:
            self._client = genai.Client(api_key=api_key)
        except Exception as e:
            raise RuntimeError(f"Failed to init Gemini client: {e}")

    def complete_json(self, system_prompt: str, user_prompt: str, max_tokens: int = 800) -> Any:
        try:
            response = self._client.models.generate_content(
                model=self.model,
                contents=[{"role": "user", "parts": [{"text": f"{system_prompt}\n\n{user_prompt}"}]}],
            )
            if not response.text:
                raise RuntimeError("Empty LLM response")
            return safe_json_loads(response.text)
        except Exception as e:
            raise RuntimeError(f"LLM call failed: {e}")
