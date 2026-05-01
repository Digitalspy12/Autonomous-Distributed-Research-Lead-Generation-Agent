"""
Signal Scout 4.0 — Supabase Sync Module
Pushes unsynced records from local SQLite to cloud Supabase.
Runs periodically to keep the dashboard up-to-date.

Design: SQLite (local write-ahead cache) -> Supabase (cloud dashboard).
Each record has a `synced` flag. This module reads synced=0 records
and upserts them to Supabase, then marks them as synced locally.
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

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

console = Console(force_terminal=False)


def _get_supabase_client():
    """Create Supabase client from env."""
    load_dotenv()
    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

    if not url or not key:
        raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in .env")

    from supabase import create_client
    return create_client(url, key)


def _prepare_record(record: dict, json_fields: list[str] = None) -> dict:
    """Prepare a SQLite record for Supabase insertion."""
    clean = {}
    for key, value in record.items():
        if key == "synced":
            continue  # Don't sync the sync flag
        if value is None:
            clean[key] = None
        elif json_fields and key in json_fields:
            # Parse JSON strings into actual arrays/objects
            try:
                clean[key] = json.loads(value) if isinstance(value, str) else value
            except json.JSONDecodeError:
                clean[key] = value
        elif isinstance(value, int) and key in ("outreach_ready",):
            clean[key] = bool(value)  # Convert SQLite int to bool
        else:
            clean[key] = value
    return clean


def sync_table(
    db: Database,
    supabase_client,
    table: str,
    json_fields: Optional[list[str]] = None,
    batch_size: int = 50,
) -> int:
    """
    Sync a single table from SQLite to Supabase.

    Returns number of records synced.
    """
    records = db.get_unsynced(table, limit=batch_size)
    if not records:
        return 0

    synced_ids = []
    errors = 0

    for record in records:
        try:
            clean = _prepare_record(record, json_fields)
            supabase_client.table(table).upsert(clean, on_conflict="id").execute()
            synced_ids.append(record["id"])
        except Exception as e:
            errors += 1
            console.print(f"  [red]Sync {table}: error for {record['id'][:8]}... - {e}[/red]")

    if synced_ids:
        db.mark_synced(table, synced_ids)

    return len(synced_ids)


def run_sync(
    db: Optional[Database] = None,
    batch_size: int = 50,
) -> dict:
    """
    Run the sync module: push all unsynced records to Supabase.

    Args:
        db: Database instance.
        batch_size: Max records per table per sync run.

    Returns:
        Stats dict.
    """
    if db is None:
        db = Database()
        db.init_schema()

    console.print("\n[bold cyan]Supabase Sync -- Local -> Cloud[/bold cyan]\n")

    try:
        supabase = _get_supabase_client()
        console.print("  [green]Supabase connected[/green]\n")
    except ValueError as e:
        console.print(f"  [red]{e}[/red]")
        return {"total": 0, "error": str(e)}
    except Exception as e:
        console.print(f"  [red]Supabase connection failed: {e}[/red]")
        return {"total": 0, "error": str(e)}

    stats = {}

    # Sync each table with appropriate JSON field mappings
    table_configs = {
        "companies": {"json_fields": ["tech_stack"]},
        "jobs": {"json_fields": ["integration_gaps", "tech_stack_inferred"]},
        "contacts": {"json_fields": ["email_sources", "manual_research_links"]},
        "pitches": {"json_fields": []},
        "pipeline_events": {"json_fields": ["metadata"]},
    }

    total = 0
    for table, config in table_configs.items():
        count = sync_table(
            db=db,
            supabase_client=supabase,
            table=table,
            json_fields=config["json_fields"],
            batch_size=batch_size,
        )
        stats[table] = count
        total += count
        if count > 0:
            console.print(f"  {table}: {count} records synced")
        else:
            console.print(f"  {table}: up to date")

    stats["total"] = total
    console.print(f"\n  [bold green]Total: {total} records synced[/bold green]\n")

    return stats


if __name__ == "__main__":
    console.print("\n[bold]Testing Supabase sync...[/bold]")
    db = Database()
    db.init_schema()
    result = run_sync(db=db)
    db.close()
