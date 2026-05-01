"""
Signal Scout 4.0 — RSS Feed Source Adapter
Fetches jobs from RSS feeds using feedparser.
Pi-migratable: runs on both Pi and LOQ.

Covers:
- Remote job boards (WeWorkRemotely, Jobicy, RemoteOK, Remotive)
- India-specific (Indeed India RSS)
- Funding signals (Inc42, YourStory, TechCrunch)
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Optional

import feedparser
from rich.console import Console

from src.core.config import RSS_FEEDS
from src.core.models import RawJob

import sys
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

console = Console(force_terminal=False)


def fetch_rss_jobs(
    feeds: Optional[list[str]] = None,
    max_age_days: int = 7,
    rate_limit: float = 0.5,
) -> list[RawJob]:
    """
    Fetch jobs from RSS feeds.

    Args:
        feeds: List of RSS feed URLs. Defaults to config RSS_FEEDS.
        max_age_days: Only include entries from the last N days.
        rate_limit: Delay between feed fetches.

    Returns:
        List of RawJob objects discovered.
    """
    feeds = feeds or RSS_FEEDS
    all_jobs: list[RawJob] = []
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)

    for feed_url in feeds:
        try:
            feed = feedparser.parse(feed_url)

            if feed.bozo and not feed.entries:
                console.print(f"  [yellow]RSS: {_short_url(feed_url)} - parse error[/yellow]")
                time.sleep(rate_limit)
                continue

            count = 0
            for entry in feed.entries:
                # Check publish date
                published = _parse_date(entry)
                if published and published < cutoff:
                    continue

                title = entry.get("title", "").strip()
                link = entry.get("link", "").strip()

                if not title or not link:
                    continue

                # Extract company name from title or feed
                company_name = _extract_company(entry, feed)

                # Get description
                description = ""
                if "summary" in entry:
                    description = entry.summary[:5000]
                elif "description" in entry:
                    description = entry.description[:5000]

                # Determine source type
                source = _classify_source(feed_url)

                raw = RawJob(
                    title=title,
                    company_name=company_name,
                    job_url=link,
                    source=source,
                    source_url=feed_url,
                    description=description,
                    location="",
                )
                all_jobs.append(raw)
                count += 1

            console.print(
                f"  [green]RSS: {_short_url(feed_url)} - {count} entries[/green]"
            )

        except Exception as e:
            console.print(f"  [red]RSS: {_short_url(feed_url)} - error: {e}[/red]")

        time.sleep(rate_limit)

    return all_jobs


def _parse_date(entry) -> Optional[datetime]:
    """Parse entry publish date to UTC datetime."""
    for field in ("published_parsed", "updated_parsed"):
        parsed = entry.get(field)
        if parsed:
            try:
                from time import mktime
                dt = datetime.fromtimestamp(mktime(parsed), tz=timezone.utc)
                return dt
            except Exception:
                continue
    return None


def _extract_company(entry, feed) -> str:
    """Try to extract company name from RSS entry."""
    # Some feeds put company in author
    author = entry.get("author", "")
    if author:
        return author.strip()

    # WeWorkRemotely format: "Company Name: Job Title"
    title = entry.get("title", "")
    if ":" in title:
        return title.split(":")[0].strip()

    # Fallback to feed title
    return feed.feed.get("title", "Unknown")


def _classify_source(feed_url: str) -> str:
    """Classify the RSS source type."""
    url_lower = feed_url.lower()
    if "indeed" in url_lower:
        return "indeed_india"
    elif "inc42" in url_lower or "yourstory" in url_lower or "techcrunch" in url_lower:
        return "funding_news"
    else:
        return "rss"


def _short_url(url: str) -> str:
    """Shorten URL for display."""
    from urllib.parse import urlparse
    parsed = urlparse(url)
    return parsed.netloc + parsed.path[:30]


if __name__ == "__main__":
    """Test: fetch from first 2 RSS feeds."""
    console.print("\n[bold]Testing RSS adapter...[/bold]\n")
    test_feeds = RSS_FEEDS[:2]
    jobs = fetch_rss_jobs(feeds=test_feeds, max_age_days=14)
    for job in jobs[:5]:
        console.print(f"  {job.title}")
        console.print(f"    Company: {job.company_name}")
        console.print(f"    URL: {job.job_url}")
        console.print()
    console.print(f"\n[bold]Total: {len(jobs)} entries[/bold]\n")
