"""
Signal Scout 4.0 — Researcher Node
Enriches analyzed jobs with company data and contacts.
Uses Hunter.io and Apollo.io APIs for email discovery.

Pipeline position: THIRD node (Scout -> Analyst -> [Researcher] -> Strategist -> Critic)
Runs on LOQ (needs internet for enrichment APIs).
"""

from __future__ import annotations

import json
import os
import sys
import time
from typing import Optional

import requests
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

from src.core.database import Database
from src.core.models import Contact

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

console = Console(force_terminal=False)


def _get_env(key: str) -> str:
    load_dotenv()
    return os.getenv(key, "")


# ============================================
# Hunter.io Integration (25 free/month)
# ============================================

def hunter_domain_search(domain: str, api_key: str) -> Optional[dict]:
    """Search for emails at a domain using Hunter.io."""
    if not api_key:
        return None
    try:
        r = requests.get(
            "https://api.hunter.io/v2/domain-search",
            params={"domain": domain, "api_key": api_key, "limit": 5},
            timeout=15,
        )
        if r.status_code == 200:
            return r.json().get("data", {})
        elif r.status_code == 401:
            console.print("  [red]Hunter: invalid API key[/red]")
        elif r.status_code == 429:
            console.print("  [yellow]Hunter: rate limited[/yellow]")
    except Exception as e:
        console.print(f"  [red]Hunter: error: {e}[/red]")
    return None


def hunter_email_verifier(email: str, api_key: str) -> Optional[str]:
    """Verify an email using Hunter.io. Returns status."""
    if not api_key:
        return None
    try:
        r = requests.get(
            "https://api.hunter.io/v2/email-verifier",
            params={"email": email, "api_key": api_key},
            timeout=15,
        )
        if r.status_code == 200:
            data = r.json().get("data", {})
            return data.get("status", "unknown")  # deliverable, undeliverable, risky, unknown
    except Exception:
        pass
    return None


# ============================================
# Apollo.io Integration (50 free/month)
# ============================================

def apollo_people_search(domain: str, api_key: str, titles: Optional[list[str]] = None) -> list[dict]:
    """Search for people at a company using Apollo.io."""
    if not api_key:
        return []
    try:
        # Target decision-maker titles
        target_titles = titles or [
            "CEO", "CTO", "COO", "VP Operations", "Head of Operations",
            "VP Engineering", "Director of Operations", "Founder",
        ]
        r = requests.post(
            "https://api.apollo.io/v1/mixed_people/search",
            json={
                "api_key": api_key,
                "q_organization_domains": domain,
                "person_titles": target_titles,
                "per_page": 5,
            },
            timeout=15,
        )
        if r.status_code == 200:
            data = r.json()
            return data.get("people", [])
    except Exception as e:
        console.print(f"  [red]Apollo: error: {e}[/red]")
    return []


# ============================================
# Free Enrichment (no API key needed)
# ============================================

def build_manual_research_links(company_name: str, domain: str) -> dict:
    """Generate research URLs for manual verification."""
    safe_name = company_name.replace(" ", "+")
    safe_domain = domain or ""
    return {
        "linkedin_company": f"https://www.linkedin.com/company/{safe_domain.replace('.com', '')}/",
        "linkedin_people": f"https://www.linkedin.com/search/results/people/?company={safe_name}&title=operations",
        "crunchbase": f"https://www.crunchbase.com/organization/{safe_domain.replace('.com', '')}",
        "glassdoor": f"https://www.glassdoor.com/Reviews/{safe_name}-Reviews-E0.htm",
        "github": f"https://github.com/{safe_domain.replace('.com', '') if safe_domain else safe_name}",
    }


# ============================================
# Researcher Node Orchestrator
# ============================================

def run_researcher(
    db: Optional[Database] = None,
    batch_size: int = 10,
) -> dict:
    """
    Run the Researcher node: enrich analyzed jobs with contacts.

    Args:
        db: Database instance.
        batch_size: Max jobs to enrich per run.

    Returns:
        Stats dict.
    """
    if db is None:
        db = Database()
        db.init_schema()

    console.print("\n[bold cyan]Researcher Node -- Contact Enrichment[/bold cyan]\n")

    hunter_key = _get_env("HUNTER_API_KEY")
    apollo_key = _get_env("APOLLO_API_KEY")

    console.print(f"  Hunter.io: {'configured' if hunter_key else 'not set (skipping)'}")
    console.print(f"  Apollo.io: {'configured' if apollo_key else 'not set (skipping)'}")
    console.print()

    # Fetch analyzed jobs (passed by Analyst)
    jobs = db.get_jobs_by_status("analyzed", limit=batch_size)

    if not jobs:
        console.print("  [dim]No analyzed jobs to enrich.[/dim]")
        return {"total": 0, "enriched": 0, "contacts_found": 0, "errors": 0}

    console.print(f"  Found {len(jobs)} analyzed jobs\n")

    stats = {"total": len(jobs), "enriched": 0, "contacts_found": 0, "errors": 0}

    for i, job in enumerate(jobs, 1):
        job_id = job["id"]
        company_id = job["company_id"]
        title = job["title"]

        # Get company info
        cursor = db.conn.cursor()
        cursor.execute("SELECT * FROM companies WHERE id = ?", (company_id,))
        company_row = cursor.fetchone()

        if not company_row:
            console.print(f"  [{i}/{len(jobs)}] {title} - no company found, skipping")
            stats["errors"] += 1
            continue

        company = dict(company_row)
        domain = company.get("domain", "")
        company_name = company.get("name", "Unknown")

        console.print(f"  [{i}/{len(jobs)}] {title} @ {company_name} ({domain})")

        contacts_created = 0

        # Try Hunter.io
        if hunter_key and domain:
            hunter_data = hunter_domain_search(domain, hunter_key)
            if hunter_data:
                emails = hunter_data.get("emails", [])
                for email_data in emails[:3]:
                    contact = Contact(
                        company_id=company_id,
                        job_id=job_id,
                        name=f"{email_data.get('first_name', '')} {email_data.get('last_name', '')}".strip(),
                        title=email_data.get("position", ""),
                        email_verified=email_data.get("value", ""),
                        email_sources=["hunter"],
                        linkedin_url=email_data.get("linkedin", ""),
                        linkedin_confidence="verified" if email_data.get("linkedin") else "none",
                        outreach_ready=True,
                    )
                    db.insert_contact(contact)
                    contacts_created += 1
                console.print(f"    Hunter: {len(emails)} emails found")
            time.sleep(2)

        # Try Apollo.io
        if apollo_key and domain:
            people = apollo_people_search(domain, apollo_key)
            for person in people[:3]:
                contact = Contact(
                    company_id=company_id,
                    job_id=job_id,
                    name=person.get("name", ""),
                    title=person.get("title", ""),
                    email_verified=person.get("email", ""),
                    email_sources=["apollo"],
                    linkedin_url=person.get("linkedin_url", ""),
                    linkedin_confidence="verified" if person.get("linkedin_url") else "none",
                    outreach_ready=bool(person.get("email")),
                )
                db.insert_contact(contact)
                contacts_created += 1
            if people:
                console.print(f"    Apollo: {len(people)} contacts found")
            time.sleep(2)

        # Always generate manual research links
        manual_links = build_manual_research_links(company_name, domain)
        if contacts_created == 0:
            # Create a placeholder contact with research links
            contact = Contact(
                company_id=company_id,
                job_id=job_id,
                name="",
                title="Decision Maker (manual research needed)",
                manual_research_links=manual_links,
                outreach_ready=False,
            )
            db.insert_contact(contact)
            contacts_created += 1
            console.print(f"    Manual: research links generated")

        # Update job status
        db.update_job_status(job_id, "enriched")
        db.conn.execute(
            "UPDATE jobs SET enriched_at = ?, synced = 0 WHERE id = ?",
            (time.strftime("%Y-%m-%dT%H:%M:%SZ"), job_id),
        )
        db.conn.commit()

        # Log event
        db.log_event(
            job_id=job_id,
            node="researcher",
            from_status="analyzed",
            to_status="enriched",
            metadata={
                "contacts_found": contacts_created,
                "hunter_used": bool(hunter_key),
                "apollo_used": bool(apollo_key),
            },
        )

        stats["enriched"] += 1
        stats["contacts_found"] += contacts_created

    # Summary
    _print_summary(stats)
    return stats


def _print_summary(stats: dict):
    """Print researcher summary."""
    table = Table(title="Researcher Summary")
    table.add_column("Metric", style="cyan")
    table.add_column("Count", style="green", justify="right")

    table.add_row("Total processed", str(stats["total"]))
    table.add_row("Enriched", str(stats["enriched"]))
    table.add_row("Contacts found", str(stats["contacts_found"]))
    table.add_row("Errors", str(stats["errors"]))

    console.print(table)


if __name__ == "__main__":
    console.print("\n[bold]Testing Researcher node...[/bold]")
    db = Database()
    db.init_schema()
    result = run_researcher(db=db, batch_size=3)
    db.close()
