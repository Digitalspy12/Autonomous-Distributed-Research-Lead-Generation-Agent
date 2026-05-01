"""
Signal Scout 4.0 — Pipeline Runner (CLI Entry Point)
Run individual nodes or the full pipeline.

Usage:
    python scripts/run_pipeline.py --node all
    python scripts/run_pipeline.py --node scout
    python scripts/run_pipeline.py --node analyst
    python scripts/run_pipeline.py --node stats
"""

import argparse
import sys
from pathlib import Path

# Fix Windows encoding
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

console = Console(force_terminal=False)


def run_node(node_name: str, db: Database, dry_run: bool = False):
    """Run a specific pipeline node."""

    if node_name == "scout":
        from src.nodes.scout import run_scout
        if dry_run:
            console.print("[dim]DRY RUN: Scout would fetch from all sources[/dim]")
            return
        return run_scout(db=db)

    elif node_name == "analyst":
        from src.nodes.analyst import run_analyst
        if dry_run:
            console.print("[dim]DRY RUN: Analyst would process pre-filtered jobs[/dim]")
            return
        return run_analyst(db=db)

    elif node_name == "researcher":
        from src.nodes.researcher import run_researcher
        if dry_run:
            console.print("[dim]DRY RUN: Researcher would enrich analyzed jobs[/dim]")
            return
        return run_researcher(db=db)

    elif node_name == "strategist":
        from src.nodes.strategist import run_strategist
        if dry_run:
            console.print("[dim]DRY RUN: Strategist would generate pitches[/dim]")
            return
        return run_strategist(db=db)

    elif node_name == "critic":
        from src.nodes.critic import run_critic
        if dry_run:
            console.print("[dim]DRY RUN: Critic would score pitches[/dim]")
            return
        return run_critic(db=db)

    elif node_name == "sync":
        from src.core.sync import run_sync
        if dry_run:
            console.print("[dim]DRY RUN: Sync would push to Supabase[/dim]")
            return
        return run_sync(db=db)

    elif node_name == "stats":
        stats = db.get_stats()
        console.print("\n[bold cyan]Pipeline Stats[/bold cyan]\n")
        for key, value in stats.items():
            if isinstance(value, dict):
                console.print(f"  [bold]{key}:[/bold]")
                for k, v in value.items():
                    console.print(f"    {k}: {v}")
            else:
                console.print(f"  {key}: {value}")
        console.print()

    elif node_name == "all":
        console.print("\n[bold cyan]Running Full Pipeline[/bold cyan]\n")
        run_node("scout", db, dry_run)
        run_node("analyst", db, dry_run)
        run_node("researcher", db, dry_run)
        run_node("strategist", db, dry_run)
        run_node("critic", db, dry_run)
        run_node("sync", db, dry_run)
        run_node("stats", db, dry_run)

    else:
        console.print(f"[red]Unknown node: {node_name}[/red]")
        console.print("Available: scout, analyst, researcher, strategist, critic, sync, stats, all")


def main():
    parser = argparse.ArgumentParser(description="Signal Scout 4.0 Pipeline Runner")
    parser.add_argument(
        "--node",
        type=str,
        default="stats",
        help="Node to run: scout, analyst, researcher, strategist, critic, sync, stats, all",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry run mode (no actual API calls)",
    )
    args = parser.parse_args()

    console.print("\n[bold cyan]Signal Scout 4.0 -- Pipeline Runner[/bold cyan]")
    console.print(f"  Node: {args.node}")
    console.print(f"  Dry run: {args.dry_run}\n")

    db = Database()
    db.init_schema()

    try:
        run_node(args.node, db, args.dry_run)
    finally:
        db.close()


if __name__ == "__main__":
    main()
