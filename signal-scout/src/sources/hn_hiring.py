"""
Signal Scout 4.0 — HN "Who is Hiring" Source Adapter
Uses Algolia API to fetch monthly hiring threads from Hacker News.
Pi-migratable: runs on both Pi and LOQ.

API: https://hn.algolia.com/api/v1/search_by_date?query=Who%20is%20hiring&tags=story
"""

from __future__ import annotations

import re
import time
from typing import Optional

import requests
from rich.console import Console

from src.core.config import get_settings, HN_HIRING_API
from src.core.models import RawJob

import sys
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

console = Console(force_terminal=False)

# Algolia API for HN items
ITEM_API = "https://hn.algolia.com/api/v1/items/{item_id}"


def fetch_hn_hiring_jobs(max_comments: int = 100) -> list[RawJob]:
    """
    Fetch jobs from the latest HN "Who is Hiring" thread.

    Args:
        max_comments: Maximum number of top-level comments to process.

    Returns:
        List of RawJob objects from HN hiring thread.
    """
    settings = get_settings()
    all_jobs: list[RawJob] = []

    try:
        # Step 1: Find latest "Who is Hiring" thread
        r = requests.get(HN_HIRING_API, timeout=settings.request_timeout)
        if r.status_code != 200:
            console.print(f"  [yellow]HN: API returned {r.status_code}[/yellow]")
            return []

        data = r.json()
        hits = data.get("hits", [])
        if not hits:
            console.print("  [yellow]HN: No hiring threads found[/yellow]")
            return []

        # Get the most recent thread
        latest = hits[0]
        thread_id = latest.get("objectID")
        thread_title = latest.get("title", "HN Who is Hiring")
        console.print(f"  [dim]HN: Found thread: {thread_title}[/dim]")

        # Step 2: Fetch thread comments
        time.sleep(1)  # Rate limit
        r = requests.get(
            ITEM_API.format(item_id=thread_id),
            timeout=settings.request_timeout,
        )
        if r.status_code != 200:
            console.print(f"  [yellow]HN: Thread fetch failed {r.status_code}[/yellow]")
            return []

        thread = r.json()
        children = thread.get("children", [])[:max_comments]

        for comment in children:
            text = comment.get("text", "")
            if not text:
                continue

            # Parse HN comment format: "Company | Role | Location | ..."
            parsed = _parse_hn_comment(text, comment.get("id"))
            if parsed:
                all_jobs.append(parsed)

        console.print(
            f"  [green]HN: {len(all_jobs)} jobs from {len(children)} comments[/green]"
        )

    except requests.exceptions.RequestException as e:
        console.print(f"  [red]HN: request error: {e}[/red]")
    except Exception as e:
        console.print(f"  [red]HN: parse error: {e}[/red]")

    return all_jobs


def _parse_hn_comment(html_text: str, comment_id: Optional[str] = None) -> Optional[RawJob]:
    """
    Parse a HN hiring comment into a RawJob.
    Format is usually: Company | Role | Location | Remote? | URL
    """
    # Strip HTML
    text = re.sub(r"<[^>]+>", "\n", html_text)
    text = re.sub(r"&[a-z]+;", " ", text)
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    if not lines:
        return None

    # First line usually has: Company | Role | Location
    header = lines[0]
    parts = [p.strip() for p in header.split("|")]

    company_name = parts[0] if len(parts) > 0 else "Unknown"
    title = parts[1] if len(parts) > 1 else header
    location = parts[2] if len(parts) > 2 else ""

    # Build description from remaining lines
    description = "\n".join(lines[1:])[:5000]

    # Build job URL (HN comment permalink)
    job_url = f"https://news.ycombinator.com/item?id={comment_id}" if comment_id else ""

    if not company_name or company_name == "Unknown":
        return None

    return RawJob(
        title=title,
        company_name=company_name,
        job_url=job_url,
        source="hn_hiring",
        source_url=f"https://news.ycombinator.com/item?id={comment_id}",
        description=description,
        location=location,
    )


if __name__ == "__main__":
    """Test: fetch from latest HN hiring thread."""
    console.print("\n[bold]Testing HN Hiring adapter...[/bold]\n")
    jobs = fetch_hn_hiring_jobs(max_comments=20)
    for job in jobs[:5]:
        console.print(f"  {job.title} @ {job.company_name}")
        console.print(f"    Location: {job.location}")
        console.print(f"    URL: {job.job_url}")
        console.print()
    console.print(f"\n[bold]Total: {len(jobs)} jobs[/bold]\n")
