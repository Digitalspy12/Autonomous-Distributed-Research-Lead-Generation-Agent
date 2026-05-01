"""
Signal Scout 4.0 — Lever Source Adapter
Fetches jobs from Lever career pages. Light HTML parsing with BeautifulSoup.
Pi-migratable: runs on both Pi and LOQ.

Lever career pages are at:
  https://jobs.lever.co/{company}
Simple HTML structure, no JavaScript required.
"""

from __future__ import annotations

import time
from typing import Optional

import requests
from bs4 import BeautifulSoup
from rich.console import Console

from src.core.config import get_settings, LEVER_TARGETS
from src.core.models import RawJob

import sys
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

console = Console(force_terminal=False)

# Lever base URL
BASE_URL = "https://jobs.lever.co/{company}"


def fetch_lever_jobs(
    targets: Optional[list[str]] = None,
    rate_limit: float = 1.0,
) -> list[RawJob]:
    """
    Fetch jobs from all Lever targets.

    Args:
        targets: List of company slugs. Defaults to config LEVER_TARGETS.
        rate_limit: Delay between requests in seconds.

    Returns:
        List of RawJob objects discovered.
    """
    targets = targets or LEVER_TARGETS
    settings = get_settings()
    all_jobs: list[RawJob] = []

    for company_slug in targets:
        url = BASE_URL.format(company=company_slug)
        try:
            r = requests.get(
                url,
                timeout=settings.request_timeout,
                headers={"User-Agent": "SignalScout/4.0"},
            )

            if r.status_code == 404:
                console.print(f"  [dim]Lever: {company_slug} - no board found[/dim]")
                time.sleep(rate_limit)
                continue

            if r.status_code != 200:
                console.print(
                    f"  [yellow]Lever: {company_slug} - HTTP {r.status_code}[/yellow]"
                )
                time.sleep(rate_limit)
                continue

            soup = BeautifulSoup(r.text, "html.parser")
            postings = soup.select(".posting")

            for posting in postings:
                title_el = posting.select_one(".posting-title h5")
                link_el = posting.select_one("a.posting-title")
                location_el = posting.select_one(".sort-by-location .posting-category")

                if not title_el or not link_el:
                    continue

                job_url = link_el.get("href", "")
                title = title_el.get_text(strip=True)
                location = location_el.get_text(strip=True) if location_el else ""

                raw = RawJob(
                    title=title,
                    company_name=company_slug,
                    job_url=job_url,
                    source="lever",
                    source_url=url,
                    description="",  # Full description requires individual page fetch
                    location=location,
                )

                if raw.job_url:
                    all_jobs.append(raw)

            console.print(
                f"  [green]Lever: {company_slug} - {len(postings)} jobs[/green]"
            )

        except requests.exceptions.Timeout:
            console.print(f"  [yellow]Lever: {company_slug} - timeout[/yellow]")
        except requests.exceptions.RequestException as e:
            console.print(f"  [red]Lever: {company_slug} - error: {e}[/red]")
        except Exception as e:
            console.print(f"  [red]Lever: {company_slug} - parse error: {e}[/red]")

        time.sleep(rate_limit)

    return all_jobs


def fetch_lever_job_description(job_url: str) -> str:
    """Fetch full job description from individual Lever posting page."""
    try:
        r = requests.get(
            job_url,
            timeout=15,
            headers={"User-Agent": "SignalScout/4.0"},
        )
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            content = soup.select_one(".section-wrapper .content")
            if content:
                return content.get_text(separator=" ", strip=True)[:5000]
    except Exception:
        pass
    return ""


if __name__ == "__main__":
    """Test: fetch from a single target."""
    console.print("\n[bold]Testing Lever adapter...[/bold]\n")
    jobs = fetch_lever_jobs(targets=["postman"], rate_limit=0.5)
    for job in jobs[:3]:
        console.print(f"  {job.title} @ {job.company_name}")
        console.print(f"    URL: {job.job_url}")
        console.print(f"    Location: {job.location}")
        console.print()
    console.print(f"\n[bold]Total: {len(jobs)} jobs[/bold]\n")
