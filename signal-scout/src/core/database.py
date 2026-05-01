"""
Signal Scout 4.0 — SQLite Database Operations
Local cache that syncs to Supabase. Pi-migratable: this runs on both Pi and LOQ.

Design:
- SQLite is the local write-ahead cache
- Every record gets a `synced` flag (0 = not synced, 1 = synced to Supabase)
- The sync module reads synced=0 records and pushes to Supabase
- Deduplication: jobs are deduped by job_url, companies by domain
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from rich.console import Console

from src.core.config import get_settings

import sys
import io

# Fix Windows console encoding for Rich
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
from src.core.models import (
    Company,
    Contact,
    Job,
    JobStatus,
    Pitch,
    PipelineEvent,
    RawJob,
)

console = Console(force_terminal=False)


def _now_iso() -> str:
    """UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    """Generate a new UUID string."""
    return str(uuid.uuid4())


class Database:
    """SQLite database operations for Signal Scout."""

    def __init__(self, db_path: Optional[str] = None):
        path = db_path or get_settings().sqlite_path
        self.db_path = Path(path).resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: Optional[sqlite3.Connection] = None

    @property
    def conn(self) -> sqlite3.Connection:
        """Lazy connection with row factory."""
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
        return self._conn

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None

    # ============================================
    # Schema Initialization
    # ============================================

    def init_schema(self):
        """Create all tables if they don't exist. Safe to call multiple times."""
        cursor = self.conn.cursor()

        cursor.executescript("""
            -- Companies (deduplicated by domain)
            CREATE TABLE IF NOT EXISTS companies (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                domain TEXT UNIQUE,
                size_estimate TEXT,
                location TEXT,
                funding_stage TEXT,
                tech_stack TEXT,           -- JSON array
                industry TEXT,
                crunchbase_url TEXT,
                github_url TEXT,
                linkedin_url TEXT,
                created_at TEXT,
                updated_at TEXT,
                synced INTEGER DEFAULT 0
            );

            -- Jobs (pain signals, deduplicated by job_url)
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                company_id TEXT REFERENCES companies(id),
                source TEXT NOT NULL,
                source_url TEXT,
                title TEXT NOT NULL,
                description TEXT,
                job_url TEXT UNIQUE NOT NULL,
                location TEXT,
                pain_hypothesis TEXT,
                primary_process TEXT,
                integration_gaps TEXT,      -- JSON array
                tech_stack_inferred TEXT,    -- JSON array
                automatibility_score INTEGER,
                analyst_confidence INTEGER,
                analyst_verdict TEXT,
                pain_keyword_score INTEGER DEFAULT 0,
                status TEXT DEFAULT 'new',
                discovered_at TEXT,
                analyzed_at TEXT,
                enriched_at TEXT,
                pitch_written_at TEXT,
                pitch_scored_at TEXT,
                synced INTEGER DEFAULT 0
            );

            -- Contacts (enrichment output)
            CREATE TABLE IF NOT EXISTS contacts (
                id TEXT PRIMARY KEY,
                company_id TEXT REFERENCES companies(id),
                job_id TEXT REFERENCES jobs(id),
                name TEXT,
                title TEXT,
                email_verified TEXT,
                email_sources TEXT,         -- JSON array
                linkedin_url TEXT,
                linkedin_confidence TEXT DEFAULT 'none',
                manual_research_links TEXT, -- JSON object
                outreach_ready INTEGER DEFAULT 0,
                outreach_status TEXT DEFAULT 'not_contacted',
                outreach_channel TEXT,
                contacted_at TEXT,
                responded_at TEXT,
                follow_up_at TEXT,
                notes TEXT,
                created_at TEXT,
                synced INTEGER DEFAULT 0
            );

            -- Pitches (Strategist + Critic output)
            CREATE TABLE IF NOT EXISTS pitches (
                id TEXT PRIMARY KEY,
                job_id TEXT REFERENCES jobs(id),
                contact_id TEXT REFERENCES contacts(id),
                subject_line TEXT,
                pitch_body TEXT,
                tone_profile TEXT,
                word_count INTEGER,
                score_specificity REAL,
                score_consultative REAL,
                score_tone REAL,
                score_brevity REAL,
                score_value REAL,
                score_credibility REAL,
                score_humanity REAL,
                score_average REAL,
                critic_verdict TEXT,
                critic_feedback TEXT,
                status TEXT DEFAULT 'draft',
                approved_at TEXT,
                sent_at TEXT,
                created_at TEXT,
                synced INTEGER DEFAULT 0
            );

            -- Pipeline events (audit log)
            CREATE TABLE IF NOT EXISTS pipeline_events (
                id TEXT PRIMARY KEY,
                job_id TEXT REFERENCES jobs(id),
                node TEXT NOT NULL,
                from_status TEXT,
                to_status TEXT,
                metadata TEXT,             -- JSON object
                error_message TEXT,
                created_at TEXT,
                synced INTEGER DEFAULT 0
            );

            -- LLM call log (every LLM invocation for debugging/cost tracking)
            CREATE TABLE IF NOT EXISTS llm_call_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                node TEXT NOT NULL,
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                prompt_chars INTEGER,
                response_chars INTEGER,
                latency_ms INTEGER,
                attempt INTEGER DEFAULT 1,
                fallback_chain TEXT,        -- JSON array
                status TEXT NOT NULL,       -- 'success', 'error', 'timeout'
                error_message TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            );

            -- Indexes
            CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
            CREATE INDEX IF NOT EXISTS idx_jobs_company ON jobs(company_id);
            CREATE INDEX IF NOT EXISTS idx_jobs_discovered ON jobs(discovered_at);
            CREATE INDEX IF NOT EXISTS idx_contacts_outreach ON contacts(outreach_status);
            CREATE INDEX IF NOT EXISTS idx_contacts_ready ON contacts(outreach_ready);
            CREATE INDEX IF NOT EXISTS idx_pitches_status ON pitches(status);
            CREATE INDEX IF NOT EXISTS idx_events_job ON pipeline_events(job_id);
            CREATE INDEX IF NOT EXISTS idx_events_created ON pipeline_events(created_at);
            CREATE INDEX IF NOT EXISTS idx_companies_domain ON companies(domain);
            CREATE INDEX IF NOT EXISTS idx_jobs_synced ON jobs(synced);
            CREATE INDEX IF NOT EXISTS idx_contacts_synced ON contacts(synced);
            CREATE INDEX IF NOT EXISTS idx_pitches_synced ON pitches(synced);
            CREATE INDEX IF NOT EXISTS idx_events_synced ON pipeline_events(synced);
            CREATE INDEX IF NOT EXISTS idx_llm_calls_node ON llm_call_log(node);
            CREATE INDEX IF NOT EXISTS idx_llm_calls_provider ON llm_call_log(provider);
            CREATE INDEX IF NOT EXISTS idx_llm_calls_timestamp ON llm_call_log(timestamp);

        """)

        self.conn.commit()
        console.print("[green]OK[/green] SQLite schema initialized")

    # ============================================
    # Company Operations
    # ============================================

    def upsert_company(self, company: Company) -> str:
        """Insert or update a company by domain. Returns company ID."""
        cursor = self.conn.cursor()

        # Check if company exists by domain
        if company.domain:
            cursor.execute(
                "SELECT id FROM companies WHERE domain = ?",
                (company.domain,),
            )
            row = cursor.fetchone()
            if row:
                return row["id"]

        company_id = company.id or _new_id()
        now = _now_iso()

        cursor.execute(
            """INSERT OR IGNORE INTO companies
            (id, name, domain, size_estimate, location, funding_stage,
             tech_stack, industry, crunchbase_url, github_url, linkedin_url,
             created_at, updated_at, synced)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)""",
            (
                company_id,
                company.name,
                company.domain,
                company.size_estimate,
                company.location,
                company.funding_stage,
                json.dumps(company.tech_stack),
                company.industry,
                company.crunchbase_url,
                company.github_url,
                company.linkedin_url,
                now,
                now,
            ),
        )
        self.conn.commit()
        return company_id

    def get_company_by_domain(self, domain: str) -> Optional[dict]:
        """Look up a company by domain."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM companies WHERE domain = ?", (domain,))
        row = cursor.fetchone()
        return dict(row) if row else None

    # ============================================
    # Job Operations
    # ============================================

    def insert_job(self, raw: RawJob, company_id: str, pain_score: int) -> Optional[str]:
        """Insert a job if it doesn't already exist (dedup by job_url). Returns job ID or None."""
        cursor = self.conn.cursor()

        # Dedup check
        cursor.execute("SELECT id FROM jobs WHERE job_url = ?", (raw.job_url,))
        if cursor.fetchone():
            return None  # Already exists

        job_id = _new_id()
        now = _now_iso()
        status = JobStatus.PRE_FILTERED.value if pain_score >= 4 else JobStatus.NEW.value

        cursor.execute(
            """INSERT INTO jobs
            (id, company_id, source, source_url, title, description, job_url,
             location, pain_keyword_score, status, discovered_at, synced)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)""",
            (
                job_id,
                company_id,
                raw.source,
                raw.source_url,
                raw.title,
                raw.description,
                raw.job_url,
                raw.location,
                pain_score,
                status,
                now,
            ),
        )
        self.conn.commit()
        return job_id

    def get_jobs_by_status(self, status: str, limit: int = 50) -> list[dict]:
        """Get jobs by status, ordered by discovered_at DESC."""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM jobs WHERE status = ? ORDER BY discovered_at DESC LIMIT ?",
            (status, limit),
        )
        return [dict(row) for row in cursor.fetchall()]

    def update_job_analyst(
        self,
        job_id: str,
        pain_hypothesis: str,
        primary_process: str,
        integration_gaps: list[str],
        tech_stack_inferred: list[str],
        automatibility_score: int,
        analyst_confidence: int,
        analyst_verdict: str,
    ):
        """Update a job with Analyst output."""
        now = _now_iso()
        status = (
            JobStatus.ANALYZED.value
            if analyst_verdict == "PASS"
            else JobStatus.REJECTED.value
        )

        self.conn.execute(
            """UPDATE jobs SET
                pain_hypothesis = ?, primary_process = ?,
                integration_gaps = ?, tech_stack_inferred = ?,
                automatibility_score = ?, analyst_confidence = ?,
                analyst_verdict = ?, status = ?, analyzed_at = ?, synced = 0
            WHERE id = ?""",
            (
                pain_hypothesis,
                primary_process,
                json.dumps(integration_gaps),
                json.dumps(tech_stack_inferred),
                automatibility_score,
                analyst_confidence,
                analyst_verdict,
                status,
                now,
                job_id,
            ),
        )
        self.conn.commit()

    def update_job_status(self, job_id: str, status: str):
        """Update job status and mark as unsynced."""
        self.conn.execute(
            "UPDATE jobs SET status = ?, synced = 0 WHERE id = ?",
            (status, job_id),
        )
        self.conn.commit()

    # ============================================
    # Contact Operations
    # ============================================

    def insert_contact(self, contact: Contact) -> str:
        """Insert a contact record. Returns contact ID."""
        contact_id = contact.id or _new_id()
        now = _now_iso()

        self.conn.execute(
            """INSERT INTO contacts
            (id, company_id, job_id, name, title, email_verified,
             email_sources, linkedin_url, linkedin_confidence,
             manual_research_links, outreach_ready, outreach_status,
             created_at, synced)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)""",
            (
                contact_id,
                contact.company_id,
                contact.job_id,
                contact.name,
                contact.title,
                contact.email_verified,
                json.dumps(contact.email_sources),
                contact.linkedin_url,
                contact.linkedin_confidence,
                json.dumps(contact.manual_research_links),
                1 if contact.outreach_ready else 0,
                contact.outreach_status,
                now,
            ),
        )
        self.conn.commit()
        return contact_id

    def get_contacts_by_job(self, job_id: str) -> list[dict]:
        """Get contacts associated with a job."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM contacts WHERE job_id = ?", (job_id,))
        return [dict(row) for row in cursor.fetchall()]

    # ============================================
    # Pitch Operations
    # ============================================

    def insert_pitch(self, pitch: Pitch) -> str:
        """Insert a pitch record. Returns pitch ID."""
        pitch_id = pitch.id or _new_id()
        now = _now_iso()

        self.conn.execute(
            """INSERT INTO pitches
            (id, job_id, contact_id, subject_line, pitch_body,
             tone_profile, word_count, status, created_at, synced)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)""",
            (
                pitch_id,
                pitch.job_id,
                pitch.contact_id,
                pitch.subject_line,
                pitch.pitch_body,
                pitch.tone_profile,
                pitch.word_count,
                pitch.status,
                now,
            ),
        )
        self.conn.commit()
        return pitch_id

    def update_pitch_critic(
        self,
        pitch_id: str,
        scores: dict,
        average: float,
        verdict: str,
        feedback: str,
    ):
        """Update a pitch with Critic scores."""
        self.conn.execute(
            """UPDATE pitches SET
                score_specificity = ?, score_consultative = ?,
                score_tone = ?, score_brevity = ?,
                score_value = ?, score_credibility = ?,
                score_humanity = ?, score_average = ?,
                critic_verdict = ?, critic_feedback = ?, synced = 0
            WHERE id = ?""",
            (
                scores.get("specificity"),
                scores.get("consultative"),
                scores.get("tone"),
                scores.get("brevity"),
                scores.get("value"),
                scores.get("credibility"),
                scores.get("humanity"),
                average,
                verdict,
                feedback,
                pitch_id,
            ),
        )
        self.conn.commit()

    # ============================================
    # Pipeline Events
    # ============================================

    def log_event(
        self,
        job_id: str,
        node: str,
        from_status: Optional[str] = None,
        to_status: Optional[str] = None,
        metadata: Optional[dict] = None,
        error_message: Optional[str] = None,
    ):
        """Log a pipeline event."""
        event_id = _new_id()
        now = _now_iso()

        self.conn.execute(
            """INSERT INTO pipeline_events
            (id, job_id, node, from_status, to_status, metadata, error_message, created_at, synced)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)""",
            (
                event_id,
                job_id,
                node,
                from_status,
                to_status,
                json.dumps(metadata or {}),
                error_message,
                now,
            ),
        )
        self.conn.commit()

    # ============================================
    # Sync Helpers (for sync.py)
    # ============================================

    def get_unsynced(self, table: str, limit: int = 100) -> list[dict]:
        """Get unsynced records from a table."""
        cursor = self.conn.cursor()
        cursor.execute(
            f"SELECT * FROM {table} WHERE synced = 0 LIMIT ?",
            (limit,),
        )
        return [dict(row) for row in cursor.fetchall()]

    def mark_synced(self, table: str, record_ids: list[str]):
        """Mark records as synced."""
        if not record_ids:
            return
        placeholders = ",".join("?" for _ in record_ids)
        self.conn.execute(
            f"UPDATE {table} SET synced = 1 WHERE id IN ({placeholders})",
            record_ids,
        )
        self.conn.commit()

    # ============================================
    # Stats
    # ============================================

    def get_stats(self) -> dict:
        """Get pipeline statistics."""
        cursor = self.conn.cursor()
        stats = {}
        for table in ["companies", "jobs", "contacts", "pitches", "pipeline_events"]:
            cursor.execute(f"SELECT COUNT(*) as count FROM {table}")
            stats[table] = cursor.fetchone()["count"]

        # Job status breakdown
        cursor.execute(
            "SELECT status, COUNT(*) as count FROM jobs GROUP BY status"
        )
        stats["job_statuses"] = {row["status"]: row["count"] for row in cursor.fetchall()}

        # Unsynced counts
        for table in ["jobs", "contacts", "pitches", "pipeline_events"]:
            cursor.execute(f"SELECT COUNT(*) as count FROM {table} WHERE synced = 0")
            stats[f"{table}_unsynced"] = cursor.fetchone()["count"]

        return stats
