"""
Signal Scout 4.0 — Scout Node
Orchestrates all source adapters, applies pre-filtering, deduplication,
and inserts into SQLite.

Pi-migratable: This is the primary module that runs on Pi (24/7 polling).
On LOQ, it runs as part of the full pipeline.

Pipeline position: FIRST node (Scout -> Analyst -> Researcher -> ...)
"""

from __future__ import annotations

import re
from typing import Optional

from rich.console import Console
from rich.table import Table

from src.core.config import PAIN_KEYWORDS, PAIN_SCORE_THRESHOLD
from src.core.database import Database
from src.core.models import Company, RawJob

from src.sources.greenhouse import fetch_greenhouse_jobs
from src.sources.lever import fetch_lever_jobs
from src.sources.rss import fetch_rss_jobs
from src.sources.hn_hiring import fetch_hn_hiring_jobs
from src.sources.searxng import fetch_searxng_jobs

import sys
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

console = Console(force_terminal=False)


def run_scout(
    db: Optional[Database] = None,
    sources: Optional[list[str]] = None,
    rate_limit: float = 1.0,
) -> dict:
    """
    Run the Scout node: discover jobs from all sources.

    Args:
        db: Database instance. Creates one if not provided.
        sources: List of source names to activate. None = all.
                 Options: 'greenhouse', 'lever', 'rss', 'hn', 'searxng'
        rate_limit: Delay between requests.

    Returns:
        Dict with statistics: total_discovered, new_inserted, pre_filtered, duplicates
    """
    if db is None:
        db = Database()
        db.init_schema()

    sources = sources or ["greenhouse", "lever", "rss", "hn", "searxng"]

    console.print("\n[bold cyan]Scout Node -- Job Discovery[/bold cyan]\n")

    all_raw_jobs: list[RawJob] = []

    # === Fetch from all sources ===
    if "greenhouse" in sources:
        console.print("[bold]Greenhouse (JSON API):[/bold]")
        jobs = fetch_greenhouse_jobs(rate_limit=rate_limit)
        all_raw_jobs.extend(jobs)

    if "lever" in sources:
        console.print("[bold]Lever (HTML):[/bold]")
        jobs = fetch_lever_jobs(rate_limit=rate_limit)
        all_raw_jobs.extend(jobs)

    if "rss" in sources:
        console.print("[bold]RSS Feeds:[/bold]")
        jobs = fetch_rss_jobs(rate_limit=rate_limit * 0.5)
        all_raw_jobs.extend(jobs)

    if "hn" in sources:
        console.print("[bold]HN Who is Hiring:[/bold]")
        jobs = fetch_hn_hiring_jobs()
        all_raw_jobs.extend(jobs)

    if "searxng" in sources:
        console.print("[bold]SearXNG (Local):[/bold]")
        jobs = fetch_searxng_jobs(rate_limit=rate_limit * 2)
        all_raw_jobs.extend(jobs)

    console.print(f"\n[bold]Raw jobs discovered: {len(all_raw_jobs)}[/bold]\n")

    # === Pre-filter + Dedup + Insert ===
    stats = {
        "total_discovered": len(all_raw_jobs),
        "new_inserted": 0,
        "pre_filtered": 0,
        "duplicates": 0,
        "by_source": {},
    }

    for raw_job in all_raw_jobs:
        # Normalize URL for dedup
        raw_job.job_url = _normalize_url(raw_job.job_url)

        if not raw_job.job_url:
            continue

        # Calculate pain keyword score
        pain_score = calculate_pain_score(raw_job)

        # Upsert company
        domain = _derive_domain(raw_job.company_name, raw_job.job_url)
        company = Company(name=raw_job.company_name, domain=domain)
        company_id = db.upsert_company(company)

        # Insert job (dedup by job_url)
        job_id = db.insert_job(raw_job, company_id, pain_score)

        if job_id is None:
            stats["duplicates"] += 1
        else:
            stats["new_inserted"] += 1
            if pain_score >= PAIN_SCORE_THRESHOLD:
                stats["pre_filtered"] += 1

            # Log event
            db.log_event(
                job_id=job_id,
                node="scout",
                from_status=None,
                to_status="pre_filtered" if pain_score >= PAIN_SCORE_THRESHOLD else "new",
                metadata={
                    "source": raw_job.source,
                    "pain_score": pain_score,
                    "company": raw_job.company_name,
                },
            )

        # Track by source
        source = raw_job.source
        if source not in stats["by_source"]:
            stats["by_source"][source] = 0
        stats["by_source"][source] += 1

    # === Print summary ===
    _print_summary(stats)

    return stats


def calculate_pain_score(job: RawJob) -> int:
    """
    Calculate pain keyword score for pre-filtering.
    Matches keywords against title + description.
    Score >= PAIN_SCORE_THRESHOLD means the job goes to Analyst.
    """
    text = f"{job.title} {job.description or ''}".lower()
    score = 0

    for keyword, weight in PAIN_KEYWORDS.items():
        pattern = re.compile(re.escape(keyword.lower()), re.IGNORECASE)
        matches = pattern.findall(text)
        if matches:
            score += weight

    return score


def _derive_domain(company_name: str, job_url: str) -> Optional[str]:
    """Derive company domain from job URL or company name."""
    url_lower = job_url.lower()

    if "greenhouse.io" in url_lower:
        try:
            slug = job_url.split("greenhouse.io/")[1].split("/")[0]
            return f"{slug}.com"
        except (IndexError, AttributeError):
            pass
    elif "lever.co" in url_lower:
        try:
            slug = job_url.split("lever.co/")[1].split("/")[0]
            return f"{slug}.com"
        except (IndexError, AttributeError):
            pass

    # Fallback: slugify company name
    if company_name and company_name != "Unknown":
        slug = re.sub(r"[^a-z0-9]", "", company_name.lower())
        if slug:
            return f"{slug}.com"

    return None


def _normalize_url(url: str) -> str:
    """Normalize URL for deduplication."""
    if not url:
        return ""
    # Remove trailing slashes and query params for dedup
    url = url.split("?")[0].rstrip("/")
    # Remove fragments
    url = url.split("#")[0]
    return url


def _print_summary(stats: dict):
    """Print a summary table of Scout results."""
    table = Table(title="Scout Summary")
    table.add_column("Metric", style="cyan")
    table.add_column("Count", style="green", justify="right")

    table.add_row("Total discovered", str(stats["total_discovered"]))
    table.add_row("New (inserted)", str(stats["new_inserted"]))
    table.add_row("Pre-filtered (pain >= 4)", str(stats["pre_filtered"]))
    table.add_row("Duplicates (skipped)", str(stats["duplicates"]))

    console.print(table)

    if stats["by_source"]:
        console.print("\n[bold]By source:[/bold]")
        for source, count in sorted(stats["by_source"].items()):
            console.print(f"  {source}: {count}")


if __name__ == "__main__":
    """Test: run scout with just Greenhouse and RSS."""
    console.print("\n[bold]Testing Scout node...[/bold]")
    db = Database()
    db.init_schema()
    result = run_scout(db=db, sources=["greenhouse", "rss"])
    console.print(f"\nDB stats: {db.get_stats()}")
    db.close()
