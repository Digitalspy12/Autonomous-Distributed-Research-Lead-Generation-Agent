"""
Signal Scout 4.0 — Analyst Node
Generates Pain Hypotheses using the unified LLM client.
Processes pre-filtered jobs (pain_keyword_score >= 4).

Pipeline position: SECOND node (Scout -> [Analyst] -> Researcher -> ...)
Fallback chain: Gemini 2.5 Flash -> Groq Llama 3.1 70B -> Ollama Qwen 3.5
Runs on LOQ (needs internet for cloud LLMs, or local Ollama).
"""

from __future__ import annotations

import sys
import time
from typing import Optional

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

ANALYST_REQUIRED_KEYS = [
    "pain_hypothesis", "primary_process", "automatibility_score",
    "confidence", "verdict",
]


def analyze_job(
    title: str,
    company: str,
    location: str,
    description: str,
    db=None,
) -> Optional[dict]:
    """
    Analyze a single job posting with the unified LLM client.

    Uses hierarchical fallback: Gemini -> Groq -> Ollama.
    Returns parsed JSON dict or None on failure.
    """
    from src.core.llm_client import call_llm

    prompt = ANALYST_PROMPT.format(
        title=title,
        company=company,
        location=location,
        description=(description or "No description available")[:4000],
    )

    try:
        result = call_llm(
            prompt=prompt,
            node="analyst",
            required_keys=ANALYST_REQUIRED_KEYS,
            max_retries=2,
            db=db,
        )
    except RuntimeError as e:
        console.print(f"  [bold red]Analyst: {e}[/bold red]")
        return None

    if result.parsed is None:
        return None

    parsed = result.parsed

    # Normalize and validate fields
    try:
        parsed["automatibility_score"] = max(0, min(10, int(parsed["automatibility_score"])))
        parsed["confidence"] = max(0, min(10, int(parsed["confidence"])))
    except (ValueError, TypeError):
        parsed["automatibility_score"] = 0
        parsed["confidence"] = 0

    parsed["verdict"] = str(parsed.get("verdict", "REJECT")).upper()
    if parsed["verdict"] not in ("PASS", "REJECT"):
        parsed["verdict"] = "REJECT"

    # Attach model metadata for logging
    parsed["_provider"] = result.provider
    parsed["_model"] = result.model
    parsed["_latency_ms"] = result.latency_ms

    return parsed


def run_analyst(
    db=None,
    batch_size: int = 20,
) -> dict:
    """
    Run the Analyst node: process pre-filtered jobs with LLM.

    Args:
        db: Database instance.
        batch_size: Max jobs to process per run.

    Returns:
        Stats dict with pass/reject/error counts.
    """
    from src.core.database import Database

    if db is None:
        db = Database()
        db.init_schema()

    console.print("\n[bold cyan]Analyst Node -- Pain Hypothesis Generation[/bold cyan]\n")
    console.print(f"  Fallback chain: Gemini 2.5 Flash -> Groq -> Ollama")
    console.print(f"  Batch size: {batch_size}\n")

    # Fetch pre-filtered jobs
    jobs = db.get_jobs_by_status("pre_filtered", limit=batch_size)

    if not jobs:
        console.print("  [dim]No pre-filtered jobs to analyze.[/dim]")
        return {"total": 0, "passed": 0, "rejected": 0, "errors": 0}

    console.print(f"  Found {len(jobs)} pre-filtered jobs\n")

    stats = {"total": len(jobs), "passed": 0, "rejected": 0, "errors": 0, "model_usage": {}}

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
            db=db,
        )

        if result is None:
            stats["errors"] += 1
            db.update_job_status(job_id, "error")
            db.log_event(job_id, "analyst", "pre_filtered", "error", error_message="LLM analysis failed")
            continue

        # Track model usage
        model_used = result.pop("_model", "unknown")
        provider_used = result.pop("_provider", "unknown")
        latency = result.pop("_latency_ms", 0)
        model_key = f"{provider_used}/{model_used}"
        stats["model_usage"][model_key] = stats["model_usage"].get(model_key, 0) + 1

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
                "model": model_key,
                "latency_ms": latency,
            },
        )

        if result["verdict"] == "PASS":
            stats["passed"] += 1
            console.print(f"    [green]PASS[/green] (score: {result['automatibility_score']}/10, confidence: {result['confidence']}/10) via {model_key}")
            console.print(f"    Pain: {result['pain_hypothesis'][:80]}...")
        else:
            stats["rejected"] += 1
            console.print(f"    [dim]REJECT[/dim] (score: {result['automatibility_score']}/10) via {model_key}")

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

    # Model usage breakdown
    if stats.get("model_usage"):
        console.print("\n[bold]Model usage:[/bold]")
        for model, count in stats["model_usage"].items():
            console.print(f"  {model}: {count}")


if __name__ == "__main__":
    """Test: analyze first 3 pre-filtered jobs."""
    from src.core.database import Database

    console.print("\n[bold]Testing Analyst node...[/bold]")
    db = Database()
    db.init_schema()
    result = run_analyst(db=db, batch_size=3)
    db.close()
