"""
Signal Scout 4.0 — SearXNG Source Adapter
Uses local SearXNG instance for discovery dorks.
Pi-migratable: SearXNG runs on Pi, this adapter works from both.

Capped at SEARXNG_DAILY_QUOTA queries/day (default 20).
Fallback only — used when Tier 1/2 sources don't cover a niche.
"""

from __future__ import annotations

import re
import time
from typing import Optional

import requests
from rich.console import Console

from src.core.config import get_settings, SEARXNG_DORKS
from src.core.models import RawJob

import sys
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

console = Console(force_terminal=False)


def fetch_searxng_jobs(
    dorks: Optional[list[str]] = None,
    searxng_url: str = "http://localhost:8080",
    max_queries: int = 20,
    rate_limit: float = 2.0,
) -> list[RawJob]:
    """
    Fetch jobs from local SearXNG instance.

    Args:
        dorks: Search queries. Defaults to config SEARXNG_DORKS.
        searxng_url: SearXNG base URL.
        max_queries: Max number of queries to run (daily cap).
        rate_limit: Delay between queries.

    Returns:
        List of RawJob objects discovered.
    """
    dorks = dorks or SEARXNG_DORKS
    all_jobs: list[RawJob] = []
    queries_run = 0

    for dork in dorks:
        if queries_run >= max_queries:
            console.print(f"  [yellow]SearXNG: daily quota reached ({max_queries})[/yellow]")
            break

        try:
            r = requests.get(
                f"{searxng_url}/search",
                params={"q": dork, "format": "json", "categories": "general"},
                timeout=15,
            )

            if r.status_code != 200:
                console.print(f"  [yellow]SearXNG: HTTP {r.status_code} for query[/yellow]")
                queries_run += 1
                time.sleep(rate_limit)
                continue

            data = r.json()
            results = data.get("results", [])

            for result in results:
                url = result.get("url", "")
                title = result.get("title", "")
                content = result.get("content", "")

                # Filter for job-like results
                if not _is_job_url(url):
                    continue

                company_name = _extract_company_from_url(url)

                raw = RawJob(
                    title=title,
                    company_name=company_name,
                    job_url=url,
                    source="searxng",
                    source_url=searxng_url,
                    description=content[:5000],
                    location="",
                )
                all_jobs.append(raw)

            console.print(
                f"  [green]SearXNG: '{dork[:40]}...' - {len(results)} results[/green]"
            )
            queries_run += 1

        except requests.exceptions.ConnectionError:
            console.print("  [dim]SearXNG: not running (skipped)[/dim]")
            break
        except Exception as e:
            console.print(f"  [red]SearXNG: error: {e}[/red]")
            queries_run += 1

        time.sleep(rate_limit)

    return all_jobs


def _is_job_url(url: str) -> bool:
    """Check if URL looks like a job posting."""
    job_patterns = [
        "greenhouse.io", "lever.co", "jobs.", "careers.",
        "workable.com", "ashbyhq.com",
    ]
    return any(p in url.lower() for p in job_patterns)


def _extract_company_from_url(url: str) -> str:
    """Extract company name from job board URL."""
    url_lower = url.lower()
    if "greenhouse.io" in url_lower:
        match = re.search(r"greenhouse\.io/([^/]+)", url)
        return match.group(1) if match else "Unknown"
    elif "lever.co" in url_lower:
        match = re.search(r"lever\.co/([^/]+)", url)
        return match.group(1) if match else "Unknown"
    return "Unknown"
