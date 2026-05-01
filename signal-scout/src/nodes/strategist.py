"""
Signal Scout 4.0 — Strategist Node
Generates personalized cold outreach pitches using the unified LLM client.
Takes enriched jobs + contacts and creates contextual pitches.

Pipeline position: FOURTH node (Scout -> Analyst -> Researcher -> [Strategist] -> Critic)
Fallback chain: Gemini 2.5 Flash -> Groq Llama 3.1 8B -> Ollama Qwen 3.5
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
from src.core.models import Pitch

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

console = Console(force_terminal=False)

# Strategist prompt template
STRATEGIST_PROMPT = """You are an elite B2B cold outreach strategist. Your job is to write
a highly personalized, consultative pitch email that would make the recipient curious.

Context:
- Company: {company_name}
- Job Title: {job_title}
- Pain Hypothesis: {pain_hypothesis}
- Primary Process: {primary_process}
- Integration Gaps: {integration_gaps}
- Tech Stack: {tech_stack}
- Contact Name: {contact_name}
- Contact Title: {contact_title}

Write a cold outreach pitch that:
1. Opens with a specific observation about THEIR situation (not generic)
2. References the pain hypothesis naturally (don't say "I noticed you're hiring")
3. Positions the sender as a consultant, not a vendor
4. Proposes a specific, low-commitment next step (15-min call, async audit)
5. Under 120 words total
6. No fake urgency, no manipulation, no "I hope this finds you well"

Output ONLY valid JSON (no markdown, no backticks):
{{
  "subject_line": "Short, specific subject line (5-8 words)",
  "pitch_body": "The full email body",
  "tone_profile": "direct|consultative|curious",
  "word_count": 0
}}
"""

STRATEGIST_REQUIRED_KEYS = ["subject_line", "pitch_body"]


def generate_pitch(
    company_name: str,
    job_title: str,
    pain_hypothesis: str,
    primary_process: str,
    integration_gaps: list,
    tech_stack: list,
    contact_name: str,
    contact_title: str,
    db=None,
) -> Optional[dict]:
    """Generate a single pitch using the unified LLM client."""
    from src.core.llm_client import call_llm

    prompt = STRATEGIST_PROMPT.format(
        company_name=company_name,
        job_title=job_title,
        pain_hypothesis=pain_hypothesis or "Unknown pain point",
        primary_process=primary_process or "Unknown process",
        integration_gaps=", ".join(integration_gaps) if integration_gaps else "Unknown",
        tech_stack=", ".join(tech_stack) if tech_stack else "Unknown",
        contact_name=contact_name or "Decision Maker",
        contact_title=contact_title or "Operations Leader",
    )

    try:
        result = call_llm(
            prompt=prompt,
            node="strategist",
            required_keys=STRATEGIST_REQUIRED_KEYS,
            max_retries=2,
            db=db,
        )
    except RuntimeError as e:
        console.print(f"  [bold red]Strategist: {e}[/bold red]")
        return None

    if result.parsed is None:
        return None

    parsed = result.parsed

    # Count words
    parsed["word_count"] = len(parsed.get("pitch_body", "").split())
    if "tone_profile" not in parsed:
        parsed["tone_profile"] = "consultative"

    # Attach model metadata
    parsed["_provider"] = result.provider
    parsed["_model"] = result.model
    parsed["_latency_ms"] = result.latency_ms

    return parsed


def run_strategist(
    db: Optional[Database] = None,
    batch_size: int = 10,
) -> dict:
    """
    Run the Strategist node: generate pitches for enriched jobs.

    Args:
        db: Database instance.
        batch_size: Max jobs to process per run.

    Returns:
        Stats dict.
    """
    if db is None:
        db = Database()
        db.init_schema()

    console.print("\n[bold cyan]Strategist Node -- Pitch Generation[/bold cyan]\n")
    console.print(f"  Fallback chain: Gemini 2.5 Flash -> Groq -> Ollama")
    console.print(f"  Batch size: {batch_size}\n")

    # Fetch enriched jobs
    jobs = db.get_jobs_by_status("enriched", limit=batch_size)

    if not jobs:
        console.print("  [dim]No enriched jobs to generate pitches for.[/dim]")
        return {"total": 0, "generated": 0, "errors": 0}

    console.print(f"  Found {len(jobs)} enriched jobs\n")

    stats = {"total": len(jobs), "generated": 0, "errors": 0, "model_usage": {}}

    for i, job in enumerate(jobs, 1):
        job_id = job["id"]
        company_id = job["company_id"]

        # Get company name
        cursor = db.conn.cursor()
        cursor.execute("SELECT name FROM companies WHERE id = ?", (company_id,))
        company_row = cursor.fetchone()
        company_name = company_row["name"] if company_row else "Unknown"

        # Get contacts for this job
        contacts = db.get_contacts_by_job(job_id)
        if not contacts:
            console.print(f"  [{i}/{len(jobs)}] {job['title']} - no contacts, skipping")
            stats["errors"] += 1
            continue

        # Use the best contact (first with email)
        contact = contacts[0]
        for c in contacts:
            if c.get("email_verified"):
                contact = c
                break

        console.print(f"  [{i}/{len(jobs)}] {job['title']} @ {company_name}...")

        # Parse JSON arrays from DB
        integration_gaps = json.loads(job.get("integration_gaps") or "[]")
        tech_stack = json.loads(job.get("tech_stack_inferred") or "[]")

        result = generate_pitch(
            company_name=company_name,
            job_title=job["title"],
            pain_hypothesis=job.get("pain_hypothesis", ""),
            primary_process=job.get("primary_process", ""),
            integration_gaps=integration_gaps,
            tech_stack=tech_stack,
            contact_name=contact.get("name", ""),
            contact_title=contact.get("title", ""),
            db=db,
        )

        if result is None:
            stats["errors"] += 1
            db.log_event(job_id, "strategist", "enriched", "error",
                        error_message="Pitch generation failed")
            continue

        # Track model usage
        model_used = result.pop("_model", "unknown")
        provider_used = result.pop("_provider", "unknown")
        latency = result.pop("_latency_ms", 0)
        model_key = f"{provider_used}/{model_used}"
        stats["model_usage"][model_key] = stats["model_usage"].get(model_key, 0) + 1

        # Insert pitch
        pitch = Pitch(
            job_id=job_id,
            contact_id=contact.get("id"),
            subject_line=result["subject_line"],
            pitch_body=result["pitch_body"],
            tone_profile=result.get("tone_profile", "consultative"),
            word_count=result.get("word_count", 0),
        )
        pitch_id = db.insert_pitch(pitch)

        # Update job status
        db.update_job_status(job_id, "pitch_written")
        db.conn.execute(
            "UPDATE jobs SET pitch_written_at = ?, synced = 0 WHERE id = ?",
            (time.strftime("%Y-%m-%dT%H:%M:%SZ"), job_id),
        )
        db.conn.commit()

        # Log event
        db.log_event(
            job_id=job_id,
            node="strategist",
            from_status="enriched",
            to_status="pitch_written",
            metadata={
                "pitch_id": pitch_id,
                "word_count": result.get("word_count", 0),
                "tone": result.get("tone_profile", ""),
                "model": model_key,
                "latency_ms": latency,
            },
        )

        stats["generated"] += 1
        console.print(f"    [green]Pitch generated[/green] ({result.get('word_count', '?')} words, tone: {result.get('tone_profile', '?')}) via {model_key}")
        console.print(f"    Subject: {result['subject_line']}")

        time.sleep(1)

    _print_summary(stats)
    return stats


def _print_summary(stats: dict):
    """Print strategist summary."""
    table = Table(title="Strategist Summary")
    table.add_column("Metric", style="cyan")
    table.add_column("Count", style="green", justify="right")

    table.add_row("Total processed", str(stats["total"]))
    table.add_row("Pitches generated", str(stats["generated"]))
    table.add_row("Errors", str(stats["errors"]))

    console.print(table)

    # Model usage breakdown
    if stats.get("model_usage"):
        console.print("\n[bold]Model usage:[/bold]")
        for model, count in stats["model_usage"].items():
            console.print(f"  {model}: {count}")


if __name__ == "__main__":
    console.print("\n[bold]Testing Strategist node...[/bold]")
    db = Database()
    db.init_schema()
    result = run_strategist(db=db, batch_size=3)
    db.close()
