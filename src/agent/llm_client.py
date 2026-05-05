"""
LLM Client wrapper for the multi-agent system.
Supports OpenAI API with graceful fallback to mock/rule-based mode.
"""

import os
import json
from typing import Optional


class LLMClient:
    """
    Unified LLM interface — uses OpenAI-compatible SDK.
    Provider priority (override with LLM_PROVIDER env: ollama|groq|openai|mock):
      1. LLM_PROVIDER=ollama   → local Ollama at OLLAMA_BASE_URL (no API key needed)
      2. LLM_PROVIDER=mock     → force rule-based fallback
      3. GROQ_API_KEY set      → Groq (Llama/Mixtral, fast inference)
      4. OPENAI_API_KEY set    → OpenAI (gpt-4o-mini)
      5. otherwise             → mock mode
    """

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        forced = (os.getenv("LLM_PROVIDER") or "").lower().strip()
        groq_key = os.getenv("GROQ_API_KEY")
        openai_key = os.getenv("OPENAI_API_KEY")

        if api_key:
            self.provider = "custom"
            self.api_key = api_key
            self.base_url = None
            self.model = model or "gpt-4o-mini"
        elif forced == "mock":
            self.provider = None
            self.api_key = None
            self.base_url = None
            self.model = model or "mock"
        elif forced == "ollama" or (not forced and os.getenv("OLLAMA_BASE_URL")):
            self.provider = "ollama"
            self.api_key = "ollama"  # Ollama ignores it, but the SDK requires non-empty
            self.base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
            self.model = model or os.getenv("OLLAMA_MODEL", "llama3.2:3b")
        elif forced == "groq" or (not forced and groq_key):
            self.provider = "groq"
            self.api_key = groq_key
            self.base_url = "https://api.groq.com/openai/v1"
            self.model = model or os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        elif forced == "openai" or (not forced and openai_key):
            self.provider = "openai"
            self.api_key = openai_key
            self.base_url = None
            self.model = model or "gpt-4o-mini"
        else:
            self.provider = None
            self.api_key = None
            self.base_url = None
            self.model = model or "gpt-4o-mini"

        self.mock_mode = not bool(self.api_key)
        self.client = None
        self._call_count = 0
        self._total_tokens = 0

        if not self.mock_mode:
            try:
                from openai import OpenAI
                kwargs = {"api_key": self.api_key, "timeout": 30.0, "max_retries": 1}
                if self.base_url:
                    kwargs["base_url"] = self.base_url
                self.client = OpenAI(**kwargs)
                print(f"[LLMClient] Initialized · provider={self.provider} · model={self.model}")
            except ImportError:
                print("[LLMClient] openai package not installed. Falling back to mock mode.")
                self.mock_mode = True
            except Exception as e:
                print(f"[LLMClient] Init failed: {e}. Falling back to mock.")
                self.mock_mode = True
        else:
            print("[LLMClient] No API key. Running in MOCK mode (rule-based fallback).")

    def generate(self, system_prompt: str, user_prompt: str,
                 max_tokens: int = 500, temperature: float = 0.3) -> Optional[str]:
        """
        Generate a response from the LLM.
        Returns None in mock mode (caller should use rule-based fallback).
        """
        if self.mock_mode:
            return None

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=max_tokens,
                temperature=temperature
            )
            self._call_count += 1
            if response.usage:
                self._total_tokens += response.usage.total_tokens
            return response.choices[0].message.content
        except Exception as e:
            print(f"[LLMClient] API call failed: {e}")
            return None

    def generate_json(self, system_prompt: str, user_prompt: str,
                      max_tokens: int = 800) -> Optional[dict]:
        """Generate and parse a JSON response from the LLM."""
        json_system = system_prompt + "\n\nRespond ONLY with valid JSON. No markdown wrapping."
        raw = self.generate(json_system, user_prompt, max_tokens=max_tokens, temperature=0.2)
        if raw is None:
            return None
        try:
            cleaned = raw.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
                if cleaned.endswith("```"):
                    cleaned = cleaned[:-3]
                cleaned = cleaned.strip()
            return json.loads(cleaned)
        except json.JSONDecodeError:
            print(f"[LLMClient] JSON parse failed: {raw[:200]}...")
            return None

    @property
    def is_active(self) -> bool:
        return not self.mock_mode

    def get_stats(self) -> dict:
        return {
            "mode": "llm" if not self.mock_mode else "mock",
            "provider": self.provider,
            "model": self.model,
            "calls": self._call_count,
            "total_tokens": self._total_tokens
        }
