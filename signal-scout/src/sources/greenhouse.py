"""
Signal Scout 4.0 — Greenhouse Source Adapter
Fetches jobs from Greenhouse JSON API. Zero scraping, zero auth.
Pi-migratable: runs on both Pi and LOQ.

Greenhouse provides a public JSON endpoint:
  https://boards.greenhouse.io/{company}.json
Returns structured job data — no HTML parsing needed.
"""

from __future__ import annotations

import time
from typing import Optional

import requests
from rich.console import Console

from src.core.config import get_settings, GREENHOUSE_TARGETS
from src.core.models import RawJob

import sys
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

console = Console(force_terminal=False)

# Greenhouse JSON API base (v1 boards API)
BASE_URL = "https://boards-api.greenhouse.io/v1/boards/{company}/jobs"


def fetch_greenhouse_jobs(
    targets: Optional[list[str]] = None,
    rate_limit: float = 1.0,
) -> list[RawJob]:
    """
    Fetch jobs from all Greenhouse targets.

    Args:
        targets: List of company slugs. Defaults to config GREENHOUSE_TARGETS.
        rate_limit: Delay between requests in seconds.

    Returns:
        List of RawJob objects discovered.
    """
    targets = targets or GREENHOUSE_TARGETS
    settings = get_settings()
    all_jobs: list[RawJob] = []

    for company_slug in targets:
        url = BASE_URL.format(company=company_slug)
        try:
            # content=true returns job descriptions in list view
            r = requests.get(
                url,
                params={"content": "true"},
                timeout=settings.request_timeout,
            )

            if r.status_code == 404:
                console.print(f"  [dim]Greenhouse: {company_slug} - no board found[/dim]")
                time.sleep(rate_limit)
                continue

            if r.status_code != 200:
                console.print(
                    f"  [yellow]Greenhouse: {company_slug} - HTTP {r.status_code}[/yellow]"
                )
                time.sleep(rate_limit)
                continue

            data = r.json()
            jobs = data.get("jobs", [])

            for job in jobs:
                # v1 API: location is nested dict or simple name
                location_data = job.get("location", {})
                if isinstance(location_data, dict):
                    location = location_data.get("name", "")
                else:
                    location = str(location_data)

                raw = RawJob(
                    title=job.get("title", "Unknown"),
                    company_name=company_slug.replace("-", " ").title(),
                    job_url=job.get("absolute_url", ""),
                    source="greenhouse",
                    source_url=url,
                    description=_clean_html(job.get("content", "")),
                    location=location,
                )

                if raw.job_url:
                    all_jobs.append(raw)

            console.print(
                f"  [green]Greenhouse: {company_slug} - {len(jobs)} jobs[/green]"
            )

        except requests.exceptions.Timeout:
            console.print(
                f"  [yellow]Greenhouse: {company_slug} - timeout[/yellow]"
            )
        except requests.exceptions.RequestException as e:
            console.print(
                f"  [red]Greenhouse: {company_slug} - error: {e}[/red]"
            )
        except Exception as e:
            console.print(
                f"  [red]Greenhouse: {company_slug} - parse error: {e}[/red]"
            )

        time.sleep(rate_limit)

    return all_jobs


def _clean_html(html: str) -> str:
    """Strip HTML tags from job description. Lightweight, no BS4 needed."""
    import re
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:5000]  # Cap at 5000 chars for LLM context


if __name__ == "__main__":
    """Test: fetch from a single target."""
    console.print("\n[bold]Testing Greenhouse adapter...[/bold]\n")
    jobs = fetch_greenhouse_jobs(targets=["vercel"], rate_limit=0.5)
    for job in jobs[:3]:
        console.print(f"  {job.title} @ {job.company_name}")
        console.print(f"    URL: {job.job_url}")
        console.print(f"    Location: {job.location}")
        console.print(f"    Description: {job.description[:100]}...")
        console.print()
    console.print(f"\n[bold]Total: {len(jobs)} jobs[/bold]\n")
