"""
Signal Scout 4.0 — Unified LLM Client
Hierarchical fallback: Gemini 2.5 Flash → Groq → Ollama.
Every LLM-calling node uses this instead of direct provider clients.

Key features:
- Per-node model routing (analyst uses different models than critic)
- Pre-flight health checks with 5-minute caching
- Automatic 429 cooldown tracking
- JSON parsing + validation with retry
- Structured logging of every call
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import requests
from rich.console import Console

from src.core.config import get_settings
from src.core.llm_logger import log_llm_call

console = Console(force_terminal=False)


# ============================================
# Types
# ============================================

class LLMProvider(str, Enum):
    GEMINI = "gemini"
    GROQ = "groq"
    OLLAMA = "ollama"


@dataclass
class LLMCallResult:
    """Result of a unified LLM call."""
    text: str                               # Raw response text
    parsed: Optional[dict] = None           # Parsed JSON (None if not JSON)
    provider: str = ""                      # Which provider handled it
    model: str = ""                         # Exact model name
    latency_ms: int = 0                     # Response time
    attempt: int = 1                        # Which attempt succeeded
    fallback_chain: list[str] = field(default_factory=list)  # Providers tried


# ============================================
# Provider Cooldown Tracker
# ============================================

class _CooldownTracker:
    """Track 429'd providers to avoid burning retries on dead quotas."""

    def __init__(self):
        self._cooldowns: dict[str, float] = {}  # provider -> expiry timestamp
        self._default_cooldown = 300  # 5 minutes

    def mark_unavailable(self, provider: str, duration_seconds: int = 300):
        self._cooldowns[provider] = time.time() + duration_seconds

    def is_available(self, provider: str) -> bool:
        expiry = self._cooldowns.get(provider, 0)
        if time.time() > expiry:
            # Cooldown expired, remove it
            self._cooldowns.pop(provider, None)
            return True
        return False

    def remaining(self, provider: str) -> int:
        expiry = self._cooldowns.get(provider, 0)
        remaining = expiry - time.time()
        return max(0, int(remaining))


_cooldown = _CooldownTracker()


# ============================================
# Health Check Cache
# ============================================

_health_cache: dict[str, tuple[bool, float]] = {}  # provider -> (healthy, timestamp)
_HEALTH_CACHE_TTL = 300  # 5 minutes


# ============================================
# JSON Helpers
# ============================================

def _strip_markdown_fences(text: str) -> str:
    """Remove markdown code fences and 'json' prefix from LLM response."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()
    if text.startswith("json"):
        text = text[4:].strip()
    return text


def _strip_think_tags(text: str) -> str:
    """Remove <think>...</think> tags from DeepSeek R1 / reasoning models."""
    if "<think>" in text:
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    return text


def _parse_json_response(text: str, required_keys: list[str] | None = None) -> Optional[dict]:
    """Parse and validate JSON from LLM response."""
    text = _strip_think_tags(text)
    text = _strip_markdown_fences(text)

    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        return None

    if required_keys:
        if not all(k in result for k in required_keys):
            return None

    return result


# ============================================
# Provider Call Functions
# ============================================

def _call_gemini(prompt: str, model: str) -> str:
    """Call Gemini via google-genai SDK. Returns raw text or raises."""
    from google import genai

    settings = get_settings()
    client = genai.Client(api_key=settings.gemini_api_key)
    response = client.models.generate_content(model=model, contents=prompt)
    return response.text.strip()


def _call_groq(prompt: str, model: str) -> str:
    """Call Groq via groq SDK. Returns raw text or raises."""
    from groq import Groq

    settings = get_settings()
    client = Groq(api_key=settings.groq_api_key)
    chat_completion = client.chat.completions.create(
        messages=[
            {"role": "system", "content": "You are a precise JSON-outputting assistant. Return ONLY valid JSON."},
            {"role": "user", "content": prompt},
        ],
        model=model,
        temperature=0.3,
        max_tokens=1024,
        response_format={"type": "json_object"},
    )
    return chat_completion.choices[0].message.content.strip()


def _call_ollama(prompt: str, model: str) -> str:
    """Call Ollama via /api/chat endpoint. Returns raw text or raises."""
    settings = get_settings()

    r = requests.post(
        f"{settings.ollama_base_url}/api/chat",
        json={
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a precise JSON-only assistant. Return ONLY valid JSON. No markdown code fences. No explanations. No extra text.",
                },
                {"role": "user", "content": prompt},
            ],
            "stream": False,
            "options": {"temperature": 0.3, "num_predict": 2048},
        },
        timeout=settings.ollama_timeout_seconds,
    )

    if r.status_code != 200:
        raise RuntimeError(f"Ollama returned HTTP {r.status_code}: {r.text[:200]}")

    data = r.json()
    return data.get("message", {}).get("content", "").strip()



# ============================================
# Model Selection Per Node
# ============================================

def _get_model_for_node(provider: str, node: str) -> str:
    """Get the correct model name for a given provider + node combination."""
    settings = get_settings()

    if provider == LLMProvider.GEMINI:
        return settings.gemini_model  # gemini-2.5-flash for all nodes

    elif provider == LLMProvider.GROQ:
        if node == "strategist":
            return settings.groq_model_strategist  # llama-3.1-8b-instant (faster)
        else:
            return settings.groq_model_analyst  # llama-3.1-70b-versatile (smarter)

    elif provider == LLMProvider.OLLAMA:
        if node == "critic":
            return settings.ollama_model_critic  # qwen3.5:latest
        else:
            return settings.ollama_model_analyst  # qwen3.5:latest

    return "unknown"


# ============================================
# Fallback Order Per Node
# ============================================

def _get_fallback_order(node: str) -> list[str]:
    """
    Get the provider fallback order for a given node.

    Critic is reversed: Ollama first (best reasoning model locally),
    then Groq, then Gemini.
    """
    settings = get_settings()
    base_order = settings.fallback_order_list  # ["gemini", "groq", "ollama"]

    if node == "critic":
        # Reverse: local-first for critic (reasoning)
        reversed_order = []
        if "ollama" in base_order:
            reversed_order.append("ollama")
        if "groq" in base_order:
            reversed_order.append("groq")
        if "gemini" in base_order:
            reversed_order.append("gemini")
        return reversed_order

    return base_order


# ============================================
# Health Checks
# ============================================

def check_gemini_health() -> bool:
    """Pre-flight: send a tiny prompt to Gemini, check for 429."""
    settings = get_settings()
    if not settings.gemini_enabled or not settings.gemini_api_key:
        return False
    try:
        _call_gemini("Say 'ok'", settings.gemini_model)
        return True
    except Exception as e:
        error_str = str(e)
        if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
            _cooldown.mark_unavailable(LLMProvider.GEMINI, 300)
        return False


def check_groq_health() -> bool:
    """Pre-flight: send a tiny prompt to Groq."""
    settings = get_settings()
    if not settings.groq_enabled or not settings.groq_api_key:
        return False
    try:
        _call_groq("Respond with: {\"status\": \"ok\"}", settings.groq_model_analyst)
        return True
    except Exception:
        return False


def check_ollama_health() -> dict:
    """
    Pre-flight: check Ollama server + verify required models are pulled.

    Returns:
        {
            "server": True/False,
            "models_found": ["qwen3.5:latest", ...],
            "models_missing": ["deepseek-r1:7b", ...],
        }
    """
    settings = get_settings()
    result = {"server": False, "models_found": [], "models_missing": []}

    if not settings.ollama_enabled:
        return result

    try:
        r = requests.get(f"{settings.ollama_base_url}/api/tags", timeout=5)
        if r.status_code != 200:
            return result
        result["server"] = True

        data = r.json()
        available_models = [m.get("name", "") for m in data.get("models", [])]

        # Check required models
        required = set()
        required.add(settings.ollama_model_analyst)
        required.add(settings.ollama_model_critic)

        for model in required:
            # Match both exact and partial (e.g. "qwen3.5:latest" matches "qwen3.5:latest")
            found = any(model in m or m.startswith(model.split(":")[0]) for m in available_models)
            if found:
                result["models_found"].append(model)
            else:
                result["models_missing"].append(model)

    except requests.exceptions.ConnectionError:
        pass
    except Exception:
        pass

    return result


def run_health_check() -> dict[str, dict]:
    """
    Run all provider health checks with caching.

    Returns:
        {
            "gemini": {"available": True/False, "model": "gemini-2.5-flash"},
            "groq": {"available": True/False, "model": "llama-3.1-70b-versatile"},
            "ollama": {"available": True/False, "models_found": [...], "models_missing": [...]},
        }
    """
    settings = get_settings()
    now = time.time()
    results = {}

    # Gemini
    cached = _health_cache.get("gemini")
    if cached and (now - cached[1]) < _HEALTH_CACHE_TTL:
        gemini_ok = cached[0]
    else:
        gemini_ok = check_gemini_health()
        _health_cache["gemini"] = (gemini_ok, now)
    results["gemini"] = {
        "available": gemini_ok,
        "model": settings.gemini_model,
        "enabled": settings.gemini_enabled,
    }

    # Groq
    cached = _health_cache.get("groq")
    if cached and (now - cached[1]) < _HEALTH_CACHE_TTL:
        groq_ok = cached[0]
    else:
        groq_ok = check_groq_health()
        _health_cache["groq"] = (groq_ok, now)
    results["groq"] = {
        "available": groq_ok,
        "model": settings.groq_model_analyst,
        "enabled": settings.groq_enabled,
    }

    # Ollama
    ollama_result = check_ollama_health()
    ollama_ok = ollama_result["server"] and len(ollama_result["models_missing"]) == 0
    _health_cache["ollama"] = (ollama_ok, now)
    results["ollama"] = {
        "available": ollama_ok,
        "server_running": ollama_result["server"],
        "models_found": ollama_result["models_found"],
        "models_missing": ollama_result["models_missing"],
        "enabled": settings.ollama_enabled,
    }

    return results


# ============================================
# Unified LLM Call
# ============================================

def call_llm(
    prompt: str,
    node: str,
    required_keys: list[str] | None = None,
    max_retries: int = 2,
    db=None,
) -> LLMCallResult:
    """
    Call an LLM with automatic fallback chain.

    Tries each provider in the node's fallback order. For each provider:
    - Skips if disabled, no API key, or in cooldown
    - Retries up to max_retries on JSON parse failures
    - On 429/quota errors, marks cooldown and moves to next provider
    - Logs every attempt

    Args:
        prompt: The full prompt string.
        node: Pipeline node name (analyst, strategist, critic).
        required_keys: JSON keys that must be present in response.
        max_retries: Retries per provider for JSON validation failures.
        db: Optional Database instance for DB logging.

    Returns:
        LLMCallResult with parsed JSON or error info.

    Raises:
        RuntimeError: If all providers fail and skip_on_no_llm is True.
    """
    settings = get_settings()
    fallback_order = _get_fallback_order(node)
    tried_providers: list[str] = []

    for provider in fallback_order:
        # Skip disabled providers
        if provider == "gemini" and (not settings.gemini_enabled or not settings.gemini_api_key):
            continue
        if provider == "groq" and (not settings.groq_enabled or not settings.groq_api_key):
            continue
        if provider == "ollama" and not settings.ollama_enabled:
            continue

        # Skip providers in cooldown
        if not _cooldown.is_available(provider):
            remaining = _cooldown.remaining(provider)
            console.print(f"  [dim][{node}] {provider} in cooldown ({remaining}s remaining)[/dim]")
            tried_providers.append(f"{provider}:cooldown")
            continue

        model = _get_model_for_node(provider, node)

        # Dispatch to provider
        call_fn = {
            "gemini": _call_gemini,
            "groq": _call_groq,
            "ollama": _call_ollama,
        }.get(provider)

        if not call_fn:
            continue

        for attempt in range(1, max_retries + 1):
            start_time = time.time()
            raw_text = ""

            try:
                raw_text = call_fn(prompt, model)
                latency_ms = int((time.time() - start_time) * 1000)

                # Parse JSON
                parsed = _parse_json_response(raw_text, required_keys)

                if parsed is not None:
                    # Success!
                    log_entry = log_llm_call(
                        node=node,
                        provider=provider,
                        model=model,
                        prompt_chars=len(prompt),
                        response_chars=len(raw_text),
                        latency_ms=latency_ms,
                        attempt=attempt,
                        fallback_chain=tried_providers.copy(),
                        status="success",
                    )
                    if db:
                        from src.core.llm_logger import log_llm_call_to_db
                        log_llm_call_to_db(db, log_entry)

                    return LLMCallResult(
                        text=raw_text,
                        parsed=parsed,
                        provider=provider,
                        model=model,
                        latency_ms=latency_ms,
                        attempt=attempt,
                        fallback_chain=tried_providers.copy(),
                    )

                # JSON parse failed — retry with same provider
                console.print(
                    f"  [yellow][{node}] {provider}/{model}: invalid JSON "
                    f"(attempt {attempt}/{max_retries})[/yellow]"
                )
                log_llm_call(
                    node=node, provider=provider, model=model,
                    prompt_chars=len(prompt), response_chars=len(raw_text),
                    latency_ms=latency_ms, attempt=attempt,
                    fallback_chain=tried_providers.copy(),
                    status="error", error="invalid_json",
                )

            except Exception as e:
                latency_ms = int((time.time() - start_time) * 1000)
                error_str = str(e)

                # Check for rate limiting
                if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str or "rate_limit" in error_str.lower():
                    console.print(
                        f"  [yellow][{node}] {provider}/{model}: rate limited, "
                        f"cooling down 5 min[/yellow]"
                    )
                    _cooldown.mark_unavailable(provider, 300)
                    log_llm_call(
                        node=node, provider=provider, model=model,
                        prompt_chars=len(prompt), response_chars=0,
                        latency_ms=latency_ms, attempt=attempt,
                        fallback_chain=tried_providers.copy(),
                        status="error", error="rate_limited",
                    )
                    break  # Move to next provider immediately

                # Timeout
                if "timeout" in error_str.lower() or "timed out" in error_str.lower():
                    console.print(f"  [yellow][{node}] {provider}/{model}: timeout[/yellow]")
                    log_llm_call(
                        node=node, provider=provider, model=model,
                        prompt_chars=len(prompt), response_chars=0,
                        latency_ms=latency_ms, attempt=attempt,
                        fallback_chain=tried_providers.copy(),
                        status="timeout", error="timeout",
                    )
                    break  # Move to next provider

                # Other error
                console.print(f"  [red][{node}] {provider}/{model}: {error_str[:80]}[/red]")
                log_llm_call(
                    node=node, provider=provider, model=model,
                    prompt_chars=len(prompt), response_chars=0,
                    latency_ms=latency_ms, attempt=attempt,
                    fallback_chain=tried_providers.copy(),
                    status="error", error=error_str[:200],
                )
                break  # Move to next provider

            # Brief delay between retries
            time.sleep(1)

        tried_providers.append(provider)

    # All providers exhausted
    console.print(f"  [bold red][{node}] ALL LLM PROVIDERS FAILED. Tried: {tried_providers}[/bold red]")
    log_llm_call(
        node=node, provider="none", model="none",
        prompt_chars=len(prompt), response_chars=0,
        latency_ms=0, attempt=0,
        fallback_chain=tried_providers,
        status="error", error="no_llm_available",
    )

    if settings.skip_on_no_llm:
        raise RuntimeError(
            f"[{node}] No LLM available. Tried: {tried_providers}. "
            f"Pipeline halted (SKIP_ON_NO_LLM=true)."
        )

    # Return empty result for manual review queue
    return LLMCallResult(
        text="",
        parsed=None,
        provider="none",
        model="none",
        latency_ms=0,
        fallback_chain=tried_providers,
    )


# ============================================
# Convenience: singleton-style access
# ============================================

def get_llm_client():
    """
    Returns the module itself as the 'client'.
    Usage: from src.core.llm_client import call_llm, run_health_check
    """
    return __import__(__name__)
