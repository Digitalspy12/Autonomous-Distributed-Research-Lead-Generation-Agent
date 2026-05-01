"""
Signal Scout 4.0 — Analyst Node
Generates Pain Hypotheses using Gemini 2.0 Flash.
Processes pre-filtered jobs (pain_keyword_score >= 4).

Pipeline position: SECOND node (Scout -> [Analyst] -> Researcher -> ...)
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

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

console = Console(force_terminal=False)

# Analyst prompt template (from Plan v4 Section 4)
ANALYST_PROMPT = """You are an operations analyst specializing in B2B automation opportunities.

Analyze this job posting and generate a "Pain Hypothesis" — a 2-sentence inference
about the operational bottleneck this hiring implies.

Job Title: {title}
Company: {company}
Location: {location}
Description:
{description}

Output ONLY valid JSON (no markdown, no backticks, no extra text):
{{
  "pain_hypothesis": "A 2-sentence inference about what operational pain this hire reveals",
  "primary_process": "The main business process this role supports",
  "tech_stack": ["tools/platforms mentioned or implied"],
  "integration_gaps": ["gaps between systems that cause manual work"],
  "automatibility_score": 0-10,
  "confidence": 0-10,
  "verdict": "PASS or REJECT"
}}

Rules:
- automatibility_score: 0 = not automatable, 10 = fully automatable
- confidence: how sure you are about the pain hypothesis
- verdict: PASS if automatibility_score >= 5 AND confidence >= 4, else REJECT
- Focus on roles that involve manual data entry, repetitive operations, lead scraping, SDR work, reporting
- REJECT engineering/design/product roles that don't involve operational pain
"""


def _get_gemini_client():
    """Create Gemini client from env."""
    load_dotenv()
    from google import genai
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not set in .env")
    return genai.Client(api_key=api_key)


def analyze_job(
    title: str,
    company: str,
    location: str,
    description: str,
    model: str = "gemini-2.0-flash",
    max_retries: int = 3,
) -> Optional[dict]:
    """
    Analyze a single job posting with Gemini.

    Returns parsed JSON dict or None on failure.
    """
    client = _get_gemini_client()

    prompt = ANALYST_PROMPT.format(
        title=title,
        company=company,
        location=location,
        description=(description or "No description available")[:4000],
    )

    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
            )

            text = response.text.strip()

            # Strip markdown code fences if present
            if text.startswith("```"):
                text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()
            if text.startswith("json"):
                text = text[4:].strip()

            result = json.loads(text)

            # Validate required fields
            required = ["pain_hypothesis", "primary_process", "automatibility_score", "confidence", "verdict"]
            if all(k in result for k in required):
                # Ensure score bounds
                result["automatibility_score"] = max(0, min(10, int(result["automatibility_score"])))
                result["confidence"] = max(0, min(10, int(result["confidence"])))
                result["verdict"] = result["verdict"].upper()
                if result["verdict"] not in ("PASS", "REJECT"):
                    result["verdict"] = "REJECT"
                return result

            console.print(f"  [yellow]Analyst: missing fields, retrying ({attempt+1}/{max_retries})[/yellow]")

        except json.JSONDecodeError:
            console.print(f"  [yellow]Analyst: invalid JSON, retrying ({attempt+1}/{max_retries})[/yellow]")
        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                wait = min(30, 10 * (attempt + 1))
                console.print(f"  [yellow]Analyst: rate limited, waiting {wait}s...[/yellow]")
                time.sleep(wait)
            else:
                console.print(f"  [red]Analyst: error: {e}[/red]")
                break

        time.sleep(2)

    return None


def run_analyst(
    db=None,
    batch_size: int = 20,
    model: str = "gemini-2.0-flash",
) -> dict:
    """
    Run the Analyst node: process pre-filtered jobs with Gemini.

    Args:
        db: Database instance.
        batch_size: Max jobs to process per run.
        model: Gemini model to use.

    Returns:
        Stats dict with pass/reject/error counts.
    """
    from src.core.database import Database

    if db is None:
        db = Database()
        db.init_schema()

    console.print("\n[bold cyan]Analyst Node -- Pain Hypothesis Generation[/bold cyan]\n")
    console.print(f"  Model: {model}")
    console.print(f"  Batch size: {batch_size}\n")

    # Fetch pre-filtered jobs
    jobs = db.get_jobs_by_status("pre_filtered", limit=batch_size)

    if not jobs:
        console.print("  [dim]No pre-filtered jobs to analyze.[/dim]")
        return {"total": 0, "passed": 0, "rejected": 0, "errors": 0}

    console.print(f"  Found {len(jobs)} pre-filtered jobs\n")

    stats = {"total": len(jobs), "passed": 0, "rejected": 0, "errors": 0}

    for i, job in enumerate(jobs, 1):
        job_id = job["id"]
        title = job["title"]
        company_id = job["company_id"]

        # Get company name
        company_name = "Unknown"
        if company_id:
            cursor = db.conn.cursor()
            cursor.execute("SELECT name FROM companies WHERE id = ?", (company_id,))
            row = cursor.fetchone()
            if row:
                company_name = row["name"]

        console.print(f"  [{i}/{len(jobs)}] {title} @ {company_name}...")

        result = analyze_job(
            title=title,
            company=company_name,
            location=job.get("location", ""),
            description=job.get("description", ""),
            model=model,
        )

        if result is None:
            stats["errors"] += 1
            db.update_job_status(job_id, "error")
            db.log_event(job_id, "analyst", "pre_filtered", "error", error_message="Gemini analysis failed")
            continue

        # Update job with analyst output
        db.update_job_analyst(
            job_id=job_id,
            pain_hypothesis=result["pain_hypothesis"],
            primary_process=result["primary_process"],
            integration_gaps=result.get("integration_gaps", []),
            tech_stack_inferred=result.get("tech_stack", []),
            automatibility_score=result["automatibility_score"],
            analyst_confidence=result["confidence"],
            analyst_verdict=result["verdict"],
        )

        # Log event
        new_status = "analyzed" if result["verdict"] == "PASS" else "rejected"
        db.log_event(
            job_id=job_id,
            node="analyst",
            from_status="pre_filtered",
            to_status=new_status,
            metadata={
                "automatibility_score": result["automatibility_score"],
                "confidence": result["confidence"],
                "verdict": result["verdict"],
                "pain_hypothesis": result["pain_hypothesis"][:100],
            },
        )

        if result["verdict"] == "PASS":
            stats["passed"] += 1
            console.print(f"    [green]PASS[/green] (score: {result['automatibility_score']}/10, confidence: {result['confidence']}/10)")
            console.print(f"    Pain: {result['pain_hypothesis'][:80]}...")
        else:
            stats["rejected"] += 1
            console.print(f"    [dim]REJECT[/dim] (score: {result['automatibility_score']}/10)")

        # Rate limit: 1 req/sec
        time.sleep(1)

    # Summary
    _print_summary(stats)
    return stats


def _print_summary(stats: dict):
    """Print analyst summary."""
    table = Table(title="Analyst Summary")
    table.add_column("Metric", style="cyan")
    table.add_column("Count", style="green", justify="right")

    table.add_row("Total processed", str(stats["total"]))
    table.add_row("PASS (-> Researcher)", str(stats["passed"]))
    table.add_row("REJECT (archived)", str(stats["rejected"]))
    table.add_row("Errors", str(stats["errors"]))

    if stats["total"] > 0:
        pass_rate = round(stats["passed"] / stats["total"] * 100)
        table.add_row("Pass rate", f"{pass_rate}%")

    console.print(table)


if __name__ == "__main__":
    """Test: analyze first 3 pre-filtered jobs."""
    from src.core.database import Database

    console.print("\n[bold]Testing Analyst node...[/bold]")
    db = Database()
    db.init_schema()
    result = run_analyst(db=db, batch_size=3)
    db.close()
