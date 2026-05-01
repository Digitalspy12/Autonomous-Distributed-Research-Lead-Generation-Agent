"""
Signal Scout 4.0 — Critic Node
Scores pitches on 7 dimensions using the unified LLM client.

Pipeline position: FIFTH node (Scout -> Analyst -> Researcher -> Strategist -> [Critic])
Fallback chain (REVERSED): Ollama Qwen 3.5 -> Groq -> Gemini 2.5 Flash
  - Critic uses local-first because reasoning models run free and unlimited.

Runs on LOQ.
"""

from __future__ import annotations

import json
import sys
import time
from typing import Optional

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

CRITIC_REQUIRED_KEYS = [
    "specificity", "consultative", "tone", "brevity",
    "value", "credibility", "humanity",
]


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


def score_pitch(
    subject_line: str,
    pitch_body: str,
    company_name: str,
    pain_hypothesis: str,
    contact_name: str,
    contact_title: str,
    db=None,
) -> Optional[dict]:
    """
    Score a pitch using the unified LLM client.

    Critic uses REVERSED fallback: Ollama first (best local reasoning),
    then Groq, then Gemini. This is handled by the LLMClient automatically
    based on node="critic".

    Returns dict with scores + verdict or None on total failure.
    """
    from src.core.llm_client import call_llm

    prompt = CRITIC_PROMPT.format(
        subject_line=subject_line,
        pitch_body=pitch_body,
        company_name=company_name,
        pain_hypothesis=pain_hypothesis or "Unknown",
        contact_name=contact_name or "Decision Maker",
        contact_title=contact_title or "Operations Leader",
    )

    try:
        result = call_llm(
            prompt=prompt,
            node="critic",
            required_keys=CRITIC_REQUIRED_KEYS,
            max_retries=2,
            db=db,
        )
    except RuntimeError as e:
        console.print(f"  [bold red]Critic: {e}[/bold red]")
        return None

    if result.parsed is None:
        return None

    parsed = _normalize_result(result.parsed)

    # Attach model metadata
    parsed["_provider"] = result.provider
    parsed["_model"] = result.model
    parsed["_latency_ms"] = result.latency_ms

    return parsed


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
    console.print("  Fallback chain (reversed): Ollama -> Groq -> Gemini\n")

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
                db=db,
            )

            if result is None:
                stats["errors"] += 1
                db.log_event(job_id, "critic", "pitch_written", "error",
                            error_message="All LLM providers failed")
                continue

            # Track model usage
            model_used = result.pop("_model", "unknown")
            provider_used = result.pop("_provider", "unknown")
            latency = result.pop("_latency_ms", 0)
            model_key = f"{provider_used}/{model_used}"
            stats["model_usage"][model_key] = stats["model_usage"].get(model_key, 0) + 1

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
                    "model": model_key,
                    "latency_ms": latency,
                    "scores": scores,
                },
            )

            if result["verdict"] == "PASS":
                stats["passed"] += 1
                console.print(f"    [green]PASS[/green] avg={result['average']}/10 via {model_key}")
            else:
                stats["failed"] += 1
                console.print(f"    [red]FAIL[/red] avg={result['average']}/10 via {model_key}")
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

    console.print(table)

    # Model usage breakdown
    if stats.get("model_usage"):
        console.print("\n[bold]Model usage:[/bold]")
        for model, count in stats["model_usage"].items():
            console.print(f"  {model}: {count}")


if __name__ == "__main__":
    console.print("\n[bold]Testing Critic node...[/bold]")
    db = Database()
    db.init_schema()
    result = run_critic(db=db, batch_size=3)
    db.close()
