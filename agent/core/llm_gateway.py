"""
llm_gateway.py — Single abstraction layer for all LLM providers.

Rules:
    - Agents call ONLY llm.generate(). They never import google.generativeai
      or openai directly.
    - Provider, model, authentication, retries, and response normalisation
      are all handled here.
    - Switching providers requires only changing PROVIDER in .env.
    - All calls are recorded in TelemetryService.

Supported providers:
    gemini      → google-generativeai SDK
    openrouter  → openai SDK with custom base_url

Extension point:
    To add a new provider, add a branch in _init_client() and _call_provider().
    The generate() signature is never changed.
"""

import json
import time
from dataclasses import dataclass
from typing import Any


@dataclass
class LLMResponse:
    """Normalised response returned by LLMGateway.generate()."""
    text:              str
    prompt_tokens:     int = 0
    completion_tokens: int = 0
    total_tokens:      int = 0
    raw:               Any = None   # original provider response (for debugging)


class LLMGatewayError(Exception):
    """Raised when all retry attempts fail."""


class LLMGateway:
    """
    Provider-agnostic LLM interface. Agents only call generate().

    Extension point: add new providers in _init_client() and _call_provider()
    without changing any agent code.
    """

    MAX_RETRIES = 3
    RETRY_DELAY = 2.0   # seconds, doubles on each retry

    def __init__(self, config, telemetry, logger):
        self._config    = config
        self._telemetry = telemetry
        self._logger    = logger
        self._provider  = config.provider
        self._model     = config.model
        self._client    = self._init_client()

    # ── Public API ────────────────────────────────────────────────────────────

    def generate(
        self,
        prompt:  str,
        system:  str | None = None,
        schema:  dict | None = None,
        **kwargs,
    ) -> LLMResponse:
        """
        Send a prompt to the configured LLM and return a normalised response.

        Args:
            prompt:  The main user prompt.
            system:  Optional system instruction.
            schema:  Optional JSON schema dict for structured output.
                     If provided, the response .text will be valid JSON.
            **kwargs: Passed through to the provider call (e.g. temperature).

        Returns:
            LLMResponse with .text and token counts.

        Raises:
            LLMGatewayError: if all retries are exhausted.
        """
        delay = self.RETRY_DELAY
        last_error = None

        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                response = self._call_provider(prompt, system, schema, **kwargs)
                self._telemetry.record_llm_call(
                    response.prompt_tokens,
                    response.completion_tokens,
                )
                return response
            except Exception as exc:
                last_error = exc
                self._telemetry.record_retry()
                self._logger.warning(
                    f"LLM attempt {attempt}/{self.MAX_RETRIES} failed: {exc}"
                )
                if attempt < self.MAX_RETRIES:
                    time.sleep(delay)
                    delay *= 2

        raise LLMGatewayError(
            f"All {self.MAX_RETRIES} LLM attempts failed. "
            f"Provider: {self._provider}, Model: {self._model}. "
            f"Last error: {last_error}"
        )

    # ── Provider Initialisation ───────────────────────────────────────────────

    def _init_client(self) -> Any:
        """Initialise the provider SDK client once at startup.

        Extension point: add new provider branches here.
        """
        if self._provider == "gemini":
            import google.generativeai as genai
            genai.configure(api_key=self._config.api_key)
            return genai.GenerativeModel(self._model)

        if self._provider == "openrouter":
            from openai import OpenAI
            return OpenAI(
                api_key=self._config.api_key,
                base_url=self._config.openrouter_base_url,
            )

        raise ValueError(f"Unsupported provider: '{self._provider}'")

    # ── Provider Dispatch ─────────────────────────────────────────────────────

    def _call_provider(
        self,
        prompt:  str,
        system:  str | None,
        schema:  dict | None,
        **kwargs,
    ) -> LLMResponse:
        """Route to the correct provider implementation.

        Extension point: add new provider branches here.
        """
        if self._provider == "gemini":
            return self._call_gemini(prompt, system, schema, **kwargs)
        if self._provider == "openrouter":
            return self._call_openrouter(prompt, system, schema, **kwargs)
        raise ValueError(f"Unsupported provider: '{self._provider}'")

    # ── Gemini ────────────────────────────────────────────────────────────────

    def _call_gemini(self, prompt, system, schema, **kwargs) -> LLMResponse:
        import google.generativeai as genai

        full_prompt = f"{system}\n\n{prompt}" if system else prompt

        if schema:
            # Structured output: ask for JSON and parse it
            json_prompt = (
                f"{full_prompt}\n\n"
                f"Respond ONLY with valid JSON matching this schema:\n"
                f"{json.dumps(schema, indent=2)}"
            )
            resp = self._client.generate_content(json_prompt)
        else:
            resp = self._client.generate_content(full_prompt)

        text = resp.text.strip()

        # Extract token counts (available on some Gemini versions)
        usage = getattr(resp, "usage_metadata", None)
        pt = getattr(usage, "prompt_token_count", 0) or 0
        ct = getattr(usage, "candidates_token_count", 0) or 0

        return LLMResponse(text=text, prompt_tokens=pt,
                           completion_tokens=ct, total_tokens=pt + ct, raw=resp)

    # ── OpenRouter ────────────────────────────────────────────────────────────

    def _call_openrouter(self, prompt, system, schema, **kwargs) -> LLMResponse:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        call_kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "max_tokens": 2048,
        }

        if schema:
            call_kwargs["response_format"] = {"type": "json_object"}

        call_kwargs.update(kwargs)
        resp = self._client.chat.completions.create(**call_kwargs)

        text = resp.choices[0].message.content.strip()
        usage = resp.usage
        pt = usage.prompt_tokens if usage else 0
        ct = usage.completion_tokens if usage else 0

        return LLMResponse(text=text, prompt_tokens=pt,
                           completion_tokens=ct, total_tokens=pt + ct, raw=resp)
