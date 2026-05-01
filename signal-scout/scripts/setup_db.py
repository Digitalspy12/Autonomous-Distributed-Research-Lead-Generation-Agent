"""
Signal Scout 4.0 — SQLite Database Setup Script
Run once to initialize the local SQLite database.

Usage:
    python scripts/setup_db.py
"""

import sys
from pathlib import Path

# Fix Windows console encoding
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from rich.console import Console
from src.core.database import Database

console = Console()


def main():
    console.print("\n[bold cyan]Signal Scout 4.0 — Database Setup[/bold cyan]\n")

    db = Database()
    console.print(f"  Database path: [dim]{db.db_path}[/dim]")

    db.init_schema()

    stats = db.get_stats()
    console.print(f"\n  Tables initialized:")
    for table, count in stats.items():
        if not table.endswith("_unsynced") and table != "job_statuses":
            console.print(f"    {table}: {count} records")

    db.close()
    console.print("\n[bold green]OK Database ready![/bold green]\n")


if __name__ == "__main__":
    main()
