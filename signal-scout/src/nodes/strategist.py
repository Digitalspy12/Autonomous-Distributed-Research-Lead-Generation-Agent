"""
Signal Scout 4.0 — Strategist Node
Generates personalized cold outreach pitches using Gemini.
Takes enriched jobs + contacts and creates contextual pitches.

Pipeline position: FOURTH node (Scout -> Analyst -> Researcher -> [Strategist] -> Critic)
Runs on LOQ (needs internet for Gemini API).
"""

from __future__ import annotations

import json
import os
import sys
import time
from typing import Optional

from dotenv import load_dotenv
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


def _get_gemini_client():
    """Create Gemini client from env."""
    load_dotenv()
    from google import genai
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not set in .env")
    return genai.Client(api_key=api_key)


def generate_pitch(
    company_name: str,
    job_title: str,
    pain_hypothesis: str,
    primary_process: str,
    integration_gaps: list,
    tech_stack: list,
    contact_name: str,
    contact_title: str,
    model: str = "gemini-2.0-flash",
    max_retries: int = 3,
) -> Optional[dict]:
    """Generate a single pitch using Gemini."""
    client = _get_gemini_client()

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

    for attempt in range(max_retries):
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

            result = json.loads(text)

            required = ["subject_line", "pitch_body"]
            if all(k in result for k in required):
                # Count words
                result["word_count"] = len(result["pitch_body"].split())
                if "tone_profile" not in result:
                    result["tone_profile"] = "consultative"
                return result

        except json.JSONDecodeError:
            console.print(f"  [yellow]Strategist: invalid JSON ({attempt+1}/{max_retries})[/yellow]")
        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                wait = min(30, 10 * (attempt + 1))
                console.print(f"  [yellow]Strategist: rate limited, waiting {wait}s...[/yellow]")
                time.sleep(wait)
            else:
                console.print(f"  [red]Strategist: error: {e}[/red]")
                break
        time.sleep(2)

    return None


def run_strategist(
    db: Optional[Database] = None,
    batch_size: int = 10,
    model: str = "gemini-2.0-flash",
) -> dict:
    """
    Run the Strategist node: generate pitches for enriched jobs.

    Args:
        db: Database instance.
        batch_size: Max jobs to process per run.
        model: Gemini model to use.

    Returns:
        Stats dict.
    """
    if db is None:
        db = Database()
        db.init_schema()

    console.print("\n[bold cyan]Strategist Node -- Pitch Generation[/bold cyan]\n")
    console.print(f"  Model: {model}")
    console.print(f"  Batch size: {batch_size}\n")

    # Fetch enriched jobs
    jobs = db.get_jobs_by_status("enriched", limit=batch_size)

    if not jobs:
        console.print("  [dim]No enriched jobs to generate pitches for.[/dim]")
        return {"total": 0, "generated": 0, "errors": 0}

    console.print(f"  Found {len(jobs)} enriched jobs\n")

    stats = {"total": len(jobs), "generated": 0, "errors": 0}

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
            model=model,
        )

        if result is None:
            stats["errors"] += 1
            db.log_event(job_id, "strategist", "enriched", "error",
                        error_message="Pitch generation failed")
            continue

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
            },
        )

        stats["generated"] += 1
        console.print(f"    [green]Pitch generated[/green] ({result.get('word_count', '?')} words, tone: {result.get('tone_profile', '?')})")
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


if __name__ == "__main__":
    console.print("\n[bold]Testing Strategist node...[/bold]")
    db = Database()
    db.init_schema()
    result = run_strategist(db=db, batch_size=3)
    db.close()
