"""
Signal Scout 4.0 — Supabase Sync Module (v2 — FK-safe)
Pushes unsynced records from local SQLite to cloud Supabase.

Design:
- SQLite (local write-ahead cache) -> Supabase (cloud dashboard).
- Syncs tables in strict FK dependency order: companies → jobs → contacts → pitches → events.
- For child tables, only syncs records whose parent FK exists in Supabase.
- Uses "drain loop" — keeps syncing until all unsynced records are pushed or no progress.
- Each record has a `synced` flag. This module reads synced=0 records
  and upserts them to Supabase, then marks them as synced locally.

Fixes:
- FK constraint violations (23503) by verifying parent existence before child insert.
- batch_size cap no longer orphans child records.
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


def _get_synced_parent_ids(db: Database, parent_table: str) -> set[str]:
    """
    Get IDs that are already synced in a parent table.

    A record is 'synced' if synced=1 (meaning it has been successfully
    pushed to Supabase in a previous or current run).
    """
    cursor = db.conn.cursor()
    cursor.execute(f"SELECT id FROM {parent_table} WHERE synced = 1")
    return {row["id"] for row in cursor.fetchall()}


def _get_unsynced_with_fk_check(
    db: Database,
    table: str,
    fk_column: str,
    parent_synced_ids: set[str],
    limit: int = 100,
) -> tuple[list[dict], list[str]]:
    """
    Get unsynced records from a child table, filtered by parent FK existence.

    Returns:
        (ready_records, skipped_ids) — records whose parent is synced vs not.
    """
    all_unsynced = db.get_unsynced(table, limit=limit * 2)  # Fetch more to filter
    ready = []
    skipped = []

    for record in all_unsynced:
        fk_value = record.get(fk_column)
        if fk_value is None or fk_value in parent_synced_ids:
            ready.append(record)
        else:
            skipped.append(record["id"])

        if len(ready) >= limit:
            break

    return ready, skipped


def sync_table(
    db: Database,
    supabase_client,
    table: str,
    json_fields: Optional[list[str]] = None,
    batch_size: int = 100,
) -> dict:
    """
    Sync a single root table (no FK filtering) from SQLite to Supabase.

    Returns dict: {"synced": N, "errors": N}
    """
    records = db.get_unsynced(table, limit=batch_size)
    if not records:
        return {"synced": 0, "errors": 0}

    synced_ids = []
    errors = 0

    for record in records:
        try:
            clean = _prepare_record(record, json_fields)
            supabase_client.table(table).upsert(clean, on_conflict="id").execute()
            synced_ids.append(record["id"])
        except Exception as e:
            errors += 1
            error_str = str(e)
            # Check for duplicate key (already exists) — mark as synced
            if "23505" in error_str or "duplicate key" in error_str.lower():
                synced_ids.append(record["id"])
            else:
                console.print(f"  [red]Sync {table}: error for {record['id'][:8]}... - {e}[/red]")

    if synced_ids:
        db.mark_synced(table, synced_ids)

    return {"synced": len(synced_ids), "errors": errors}


def sync_child_table(
    db: Database,
    supabase_client,
    table: str,
    fk_column: str,
    parent_table: str,
    json_fields: Optional[list[str]] = None,
    batch_size: int = 100,
) -> dict:
    """
    Sync a child table with FK-safe filtering.

    Only syncs records whose parent FK (fk_column) exists in the
    parent_table with synced=1. Skipped records are left for the next run.

    Returns dict: {"synced": N, "errors": N, "skipped": N}
    """
    # Get set of synced parent IDs
    parent_ids = _get_synced_parent_ids(db, parent_table)

    # Get records that are safe to sync
    ready_records, skipped_ids = _get_unsynced_with_fk_check(
        db, table, fk_column, parent_ids, limit=batch_size
    )

    if not ready_records and not skipped_ids:
        return {"synced": 0, "errors": 0, "skipped": 0}

    synced_ids = []
    errors = 0

    for record in ready_records:
        try:
            clean = _prepare_record(record, json_fields)
            supabase_client.table(table).upsert(clean, on_conflict="id").execute()
            synced_ids.append(record["id"])
        except Exception as e:
            errors += 1
            error_str = str(e)
            # Duplicate key → mark as synced
            if "23505" in error_str or "duplicate key" in error_str.lower():
                synced_ids.append(record["id"])
            # FK violation → skip (parent will sync in next pass)
            elif "23503" in error_str:
                skipped_ids.append(record["id"])
                console.print(f"  [dim]Sync {table}: FK pending for {record['id'][:8]}... (parent not yet synced)[/dim]")
            else:
                console.print(f"  [red]Sync {table}: error for {record['id'][:8]}... - {e}[/red]")

    if synced_ids:
        db.mark_synced(table, synced_ids)

    return {"synced": len(synced_ids), "errors": errors, "skipped": len(skipped_ids)}


def run_sync(
    db: Optional[Database] = None,
    batch_size: int = 100,
    max_passes: int = 5,
) -> dict:
    """
    Run the sync module: push all unsynced records to Supabase.

    Uses a "drain loop" — repeats syncing until no more progress is made
    or max_passes is reached. This ensures child records whose parents
    were synced in an earlier pass get synced too.

    Args:
        db: Database instance.
        batch_size: Max records per table per pass.
        max_passes: Maximum number of drain loop iterations.

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

    total_synced = 0
    total_errors = 0
    total_skipped = 0
    table_totals = {}

    for pass_num in range(1, max_passes + 1):
        pass_synced = 0

        if pass_num > 1:
            console.print(f"\n  [dim]--- Pass {pass_num}/{max_passes} (draining remaining) ---[/dim]")

        # 1. Companies (root table, no FK dependencies)
        result = sync_table(db, supabase, "companies",
                           json_fields=["tech_stack"], batch_size=batch_size)
        pass_synced += result["synced"]
        table_totals["companies"] = table_totals.get("companies", 0) + result["synced"]
        if result["synced"] > 0:
            console.print(f"  companies: {result['synced']} records synced")

        # 2. Jobs (depends on companies)
        result = sync_child_table(db, supabase, "jobs", "company_id", "companies",
                                  json_fields=["integration_gaps", "tech_stack_inferred"],
                                  batch_size=batch_size)
        pass_synced += result["synced"]
        table_totals["jobs"] = table_totals.get("jobs", 0) + result["synced"]
        if result["synced"] > 0:
            console.print(f"  jobs: {result['synced']} records synced")
        if result.get("skipped", 0) > 0:
            console.print(f"  jobs: {result['skipped']} skipped (parent company not synced)")

        # 3. Contacts (depends on companies + jobs)
        result = sync_child_table(db, supabase, "contacts", "job_id", "jobs",
                                  json_fields=["email_sources", "manual_research_links"],
                                  batch_size=batch_size)
        pass_synced += result["synced"]
        table_totals["contacts"] = table_totals.get("contacts", 0) + result["synced"]
        if result["synced"] > 0:
            console.print(f"  contacts: {result['synced']} records synced")
        if result.get("skipped", 0) > 0:
            console.print(f"  contacts: {result['skipped']} skipped (parent job not synced)")

        # 4. Pitches (depends on jobs + contacts)
        result = sync_child_table(db, supabase, "pitches", "job_id", "jobs",
                                  json_fields=[], batch_size=batch_size)
        pass_synced += result["synced"]
        table_totals["pitches"] = table_totals.get("pitches", 0) + result["synced"]
        if result["synced"] > 0:
            console.print(f"  pitches: {result['synced']} records synced")
        if result.get("skipped", 0) > 0:
            console.print(f"  pitches: {result['skipped']} skipped (parent job not synced)")

        # 5. Pipeline events (depends on jobs)
        result = sync_child_table(db, supabase, "pipeline_events", "job_id", "jobs",
                                  json_fields=["metadata"], batch_size=batch_size)
        pass_synced += result["synced"]
        table_totals["pipeline_events"] = table_totals.get("pipeline_events", 0) + result["synced"]
        if result["synced"] > 0:
            console.print(f"  pipeline_events: {result['synced']} records synced")
        if result.get("skipped", 0) > 0:
            console.print(f"  pipeline_events: {result['skipped']} skipped (parent job not synced)")

        total_synced += pass_synced

        # If no records synced in this pass, we're done
        if pass_synced == 0:
            if pass_num > 1:
                console.print(f"  [dim]No more records to sync. Drain complete.[/dim]")
            break

    # Summary
    console.print(f"\n  [bold green]Total: {total_synced} records synced[/bold green]")
    for table, count in table_totals.items():
        if count > 0:
            console.print(f"    {table}: {count}")
    console.print()

    stats = {**table_totals, "total": total_synced}
    return stats


if __name__ == "__main__":
    console.print("\n[bold]Testing Supabase sync...[/bold]")
    db = Database()
    db.init_schema()
    result = run_sync(db=db)
    db.close()
