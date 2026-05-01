"""
Signal Scout 4.0 — Critic Node
Scores pitches on 7 dimensions using Gemini 2.0 Flash (primary)
with DeepSeek R1 7B via Ollama (fallback).

Pipeline position: FIFTH node (Scout -> Analyst -> Researcher -> Strategist -> [Critic])
Model Strategy: Gemini 2.0 Flash primary, DeepSeek R1 7B fallback.
Runs on LOQ.
"""

from __future__ import annotations

import json
import os
import sys
import time
from typing import Optional

import requests
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

from src.core.database import Database

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

console = Console(force_terminal=False)

# Critic prompt template — 7-dimension scoring rubric
CRITIC_PROMPT = """You are a cold outreach quality auditor. Score this pitch on 7 dimensions.

Pitch Subject: {subject_line}
Pitch Body:
{pitch_body}

Context:
- Target Company: {company_name}
- Pain Hypothesis: {pain_hypothesis}
- Contact: {contact_name} ({contact_title})

Score each dimension from 1.0 to 10.0:

1. SPECIFICITY: Does it reference specific details about the target company?
2. CONSULTATIVE: Does it position sender as advisor, not vendor?
3. TONE: Is the tone professional but human? (No corporate speak)
4. BREVITY: Is it concise? (Under 120 words = 10, over 200 = 1)
5. VALUE: Does it offer a clear, low-commitment value proposition?
6. CREDIBILITY: Does it establish subtle authority/expertise?
7. HUMANITY: Does it sound like a real human wrote it? (No AI patterns)

Output ONLY valid JSON (no markdown, no backticks):
{{
  "specificity": 0.0,
  "consultative": 0.0,
  "tone": 0.0,
  "brevity": 0.0,
  "value": 0.0,
  "credibility": 0.0,
  "humanity": 0.0,
  "feedback": "One sentence of actionable improvement advice",
  "verdict": "PASS if average >= 6.5, else FAIL"
}}
"""


def _get_gemini_client():
    """Create Gemini client from env."""
    load_dotenv()
    from google import genai
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not set in .env")
    return genai.Client(api_key=api_key)


def _score_with_gemini(prompt: str, model: str = "gemini-2.0-flash") -> Optional[dict]:
    """Score pitch using Gemini."""
    client = _get_gemini_client()
    try:
        response = client.models.generate_content(
            model=model,
            contents=prompt,
        )
        text = response.text.strip()
        # Strip markdown fences
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
        if text.startswith("json"):
            text = text[4:].strip()
        return json.loads(text)
    except Exception as e:
        error_str = str(e)
        if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
            console.print("  [yellow]Critic: Gemini rate limited, falling back to Ollama...[/yellow]")
        else:
            console.print(f"  [yellow]Critic: Gemini failed ({str(e)[:60]}), falling back to Ollama...[/yellow]")
        return None


def _score_with_ollama(prompt: str) -> Optional[dict]:
    """Score pitch using DeepSeek R1 7B via Ollama (fallback)."""
    load_dotenv()
    ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    try:
        r = requests.post(
            f"{ollama_url}/api/generate",
            json={
                "model": "deepseek-r1:7b",
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.3, "num_predict": 500},
            },
            timeout=120,  # Ollama can be slow
        )

        if r.status_code != 200:
            console.print(f"  [red]Critic: Ollama returned {r.status_code}[/red]")
            return None

        data = r.json()
        text = data.get("response", "").strip()

        # DeepSeek R1 may include <think> tags — strip them
        if "<think>" in text:
            # Remove everything between <think> and </think>
            import re
            text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

        # Strip markdown fences
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
        if text.startswith("json"):
            text = text[4:].strip()

        return json.loads(text)

    except requests.exceptions.ConnectionError:
        console.print("  [red]Critic: Ollama not running (install with: ollama serve)[/red]")
    except json.JSONDecodeError:
        console.print("  [yellow]Critic: Ollama returned invalid JSON[/yellow]")
    except Exception as e:
        console.print(f"  [red]Critic: Ollama error: {e}[/red]")

    return None


def score_pitch(
    subject_line: str,
    pitch_body: str,
    company_name: str,
    pain_hypothesis: str,
    contact_name: str,
    contact_title: str,
) -> Optional[dict]:
    """
    Score a pitch. Strategy: Gemini primary, Ollama DeepSeek R1 fallback.

    Returns dict with scores + verdict or None on total failure.
    """
    prompt = CRITIC_PROMPT.format(
        subject_line=subject_line,
        pitch_body=pitch_body,
        company_name=company_name,
        pain_hypothesis=pain_hypothesis or "Unknown",
        contact_name=contact_name or "Decision Maker",
        contact_title=contact_title or "Operations Leader",
    )

    # Strategy 1: Gemini 2.0 Flash (primary)
    result = _score_with_gemini(prompt)
    if result and _validate_scores(result):
        result["_model"] = "gemini-2.0-flash"
        return _normalize_result(result)

    # Strategy 2: Ollama DeepSeek R1 (fallback)
    result = _score_with_ollama(prompt)
    if result and _validate_scores(result):
        result["_model"] = "deepseek-r1:7b"
        return _normalize_result(result)

    return None


def _validate_scores(result: dict) -> bool:
    """Check that all 7 score fields exist."""
    required_scores = ["specificity", "consultative", "tone", "brevity", "value", "credibility", "humanity"]
    return all(k in result for k in required_scores)


def _normalize_result(result: dict) -> dict:
    """Normalize scores and compute average/verdict."""
    score_keys = ["specificity", "consultative", "tone", "brevity", "value", "credibility", "humanity"]

    for key in score_keys:
        try:
            result[key] = max(1.0, min(10.0, float(result[key])))
        except (ValueError, TypeError):
            result[key] = 5.0  # Default

    average = sum(result[key] for key in score_keys) / len(score_keys)
    result["average"] = round(average, 1)
    result["verdict"] = "PASS" if average >= 6.5 else "FAIL"

    if "feedback" not in result:
        result["feedback"] = "No feedback provided"

    return result


# ============================================
# Critic Node Orchestrator
# ============================================

def run_critic(
    db: Optional[Database] = None,
    batch_size: int = 10,
) -> dict:
    """
    Run the Critic node: score generated pitches.

    Args:
        db: Database instance.
        batch_size: Max pitches to score per run.

    Returns:
        Stats dict.
    """
    if db is None:
        db = Database()
        db.init_schema()

    console.print("\n[bold cyan]Critic Node -- Pitch Scoring[/bold cyan]\n")
    console.print("  Strategy: Gemini 2.0 Flash -> DeepSeek R1 7B (Ollama)\n")

    # Fetch pitch_written jobs
    jobs = db.get_jobs_by_status("pitch_written", limit=batch_size)

    if not jobs:
        console.print("  [dim]No pitches to score.[/dim]")
        return {"total": 0, "passed": 0, "failed": 0, "errors": 0}

    console.print(f"  Found {len(jobs)} jobs with pitches\n")

    stats = {"total": 0, "passed": 0, "failed": 0, "errors": 0, "model_usage": {}}

    for i, job in enumerate(jobs, 1):
        job_id = job["id"]
        company_id = job["company_id"]

        # Get company name
        cursor = db.conn.cursor()
        cursor.execute("SELECT name FROM companies WHERE id = ?", (company_id,))
        company_row = cursor.fetchone()
        company_name = company_row["name"] if company_row else "Unknown"

        # Get pitches for this job
        cursor.execute("SELECT * FROM pitches WHERE job_id = ? AND status = 'draft'", (job_id,))
        pitches = [dict(row) for row in cursor.fetchall()]

        if not pitches:
            continue

        for pitch in pitches:
            stats["total"] += 1
            pitch_id = pitch["id"]
            contact_id = pitch.get("contact_id")

            # Get contact info
            contact_name = ""
            contact_title = ""
            if contact_id:
                cursor.execute("SELECT name, title FROM contacts WHERE id = ?", (contact_id,))
                contact_row = cursor.fetchone()
                if contact_row:
                    contact_name = contact_row["name"] or ""
                    contact_title = contact_row["title"] or ""

            console.print(f"  [{i}/{len(jobs)}] Scoring: {pitch['subject_line'][:50]}...")

            result = score_pitch(
                subject_line=pitch["subject_line"] or "",
                pitch_body=pitch["pitch_body"] or "",
                company_name=company_name,
                pain_hypothesis=job.get("pain_hypothesis", ""),
                contact_name=contact_name,
                contact_title=contact_title,
            )

            if result is None:
                stats["errors"] += 1
                db.log_event(job_id, "critic", "pitch_written", "error",
                            error_message="Both Gemini and Ollama failed")
                continue

            # Track model usage
            model_used = result.pop("_model", "unknown")
            stats["model_usage"][model_used] = stats["model_usage"].get(model_used, 0) + 1

            # Update pitch with scores
            scores = {k: result[k] for k in ["specificity", "consultative", "tone", "brevity", "value", "credibility", "humanity"]}
            db.update_pitch_critic(
                pitch_id=pitch_id,
                scores=scores,
                average=result["average"],
                verdict=result["verdict"],
                feedback=result.get("feedback", ""),
            )

            # Update pitch status
            new_status = "approved" if result["verdict"] == "PASS" else "rejected"
            db.conn.execute(
                "UPDATE pitches SET status = ?, synced = 0 WHERE id = ?",
                (new_status, pitch_id),
            )

            # Update job status
            job_new_status = "pitch_approved" if result["verdict"] == "PASS" else "pitch_rejected"
            db.update_job_status(job_id, job_new_status)
            db.conn.execute(
                "UPDATE jobs SET pitch_scored_at = ?, synced = 0 WHERE id = ?",
                (time.strftime("%Y-%m-%dT%H:%M:%SZ"), job_id),
            )
            db.conn.commit()

            # Log event
            db.log_event(
                job_id=job_id,
                node="critic",
                from_status="pitch_written",
                to_status=job_new_status,
                metadata={
                    "pitch_id": pitch_id,
                    "average": result["average"],
                    "verdict": result["verdict"],
                    "model": model_used,
                    "scores": scores,
                },
            )

            if result["verdict"] == "PASS":
                stats["passed"] += 1
                console.print(f"    [green]PASS[/green] avg={result['average']}/10 (via {model_used})")
            else:
                stats["failed"] += 1
                console.print(f"    [red]FAIL[/red] avg={result['average']}/10 (via {model_used})")
            console.print(f"    Feedback: {result.get('feedback', '')[:80]}")

            time.sleep(1)

    _print_summary(stats)
    return stats


def _print_summary(stats: dict):
    """Print critic summary."""
    table = Table(title="Critic Summary")
    table.add_column("Metric", style="cyan")
    table.add_column("Count", style="green", justify="right")

    table.add_row("Total scored", str(stats["total"]))
    table.add_row("PASS (avg >= 6.5)", str(stats["passed"]))
    table.add_row("FAIL (avg < 6.5)", str(stats["failed"]))
    table.add_row("Errors", str(stats["errors"]))

    if stats["model_usage"]:
        console.print()
        console.print("[bold]Model usage:[/bold]")
        for model, count in stats["model_usage"].items():
            console.print(f"  {model}: {count}")

    console.print(table)


if __name__ == "__main__":
    console.print("\n[bold]Testing Critic node...[/bold]")
    db = Database()
    db.init_schema()
    result = run_critic(db=db, batch_size=3)
    db.close()
