"""
Signal Scout 4.0 — LLM Call Logger
Writes structured JSONL logs for every LLM invocation.
Enables debugging: "Why did 15 jobs fail yesterday?"
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional


# Log file location (project root / data / llm_calls.jsonl)
_LOG_DIR = Path(__file__).parent.parent.parent / "data"
_LOG_FILE = _LOG_DIR / "llm_calls.jsonl"


def _ensure_log_dir():
    """Create data dir if it doesn't exist."""
    _LOG_DIR.mkdir(parents=True, exist_ok=True)


def log_llm_call(
    node: str,
    provider: str,
    model: str,
    prompt_chars: int,
    response_chars: int,
    latency_ms: int,
    attempt: int,
    fallback_chain: list[str],
    status: str,
    error: Optional[str] = None,
) -> dict:
    """
    Log a single LLM call to the JSONL file and return the entry.

    Args:
        node: Pipeline node name (analyst, strategist, critic).
        provider: LLM provider (gemini, groq, ollama).
        model: Exact model name used.
        prompt_chars: Approximate prompt character count.
        response_chars: Response character count.
        latency_ms: Response time in milliseconds.
        attempt: Which attempt number succeeded (1-based).
        fallback_chain: List of providers tried before this one.
        status: 'success', 'error', 'timeout'.
        error: Error message if failed.

    Returns:
        The log entry dict.
    """
    _ensure_log_dir()

    entry = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "node": node,
        "provider": provider,
        "model": model,
        "prompt_chars": prompt_chars,
        "response_chars": response_chars,
        "latency_ms": latency_ms,
        "attempt": attempt,
        "fallback_chain": fallback_chain,
        "status": status,
        "error": error,
    }

    try:
        with open(_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        # Don't crash pipeline over log write failure
        pass

    return entry


def log_llm_call_to_db(db, entry: dict):
    """
    Persist an LLM call log entry to the SQLite llm_call_log table.

    Args:
        db: Database instance with conn attribute.
        entry: Dict from log_llm_call().
    """
    try:
        db.conn.execute(
            """INSERT INTO llm_call_log
               (timestamp, node, provider, model, prompt_chars, response_chars,
                latency_ms, attempt, fallback_chain, status, error_message)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                entry["timestamp"],
                entry["node"],
                entry["provider"],
                entry["model"],
                entry["prompt_chars"],
                entry["response_chars"],
                entry["latency_ms"],
                entry["attempt"],
                json.dumps(entry["fallback_chain"]),
                entry["status"],
                entry.get("error"),
            ),
        )
        db.conn.commit()
    except Exception:
        # Don't crash pipeline over log DB write failure
        pass


def read_recent_logs(n: int = 50) -> list[dict]:
    """Read the last N log entries from the JSONL file."""
    if not _LOG_FILE.exists():
        return []

    entries = []
    try:
        with open(_LOG_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))
    except (OSError, json.JSONDecodeError):
        pass

    return entries[-n:]
