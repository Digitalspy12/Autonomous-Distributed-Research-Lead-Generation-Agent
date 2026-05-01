# Signal Scout 4.0

**Autonomous B2B Research & Lead Qualification Engine**

An AI-powered pipeline that discovers job postings as pain signals, generates pain hypotheses with Gemini 2.0 Flash, enriches contacts via Hunter.io/Apollo.io, writes personalized cold pitches, and scores them with a dual-model critic (Gemini primary, DeepSeek R1 via Ollama fallback). All data syncs from a local SQLite cache to a Supabase cloud dashboard.

---

## Table of Contents

- [Architecture](#architecture)
- [Pipeline Nodes](#pipeline-nodes)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Environment Variables](#environment-variables)
- [Database Schema](#database-schema)
- [Usage (CLI)](#usage-cli)
- [Dashboard (Next.js)](#dashboard-nextjs)
- [Supabase Setup](#supabase-setup)
- [Ollama Setup (Critic Fallback)](#ollama-setup-critic-fallback)
- [How It Works](#how-it-works)
- [Rate Limits & Quotas](#rate-limits--quotas)
- [Pi Migration](#pi-migration)

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Signal Scout 4.0 Pipeline                    │
│                                                                 │
│  ┌─────────┐   ┌──────────┐   ┌────────────┐   ┌───────────┐  │
│  │  SCOUT  │──▶│ ANALYST  │──▶│ RESEARCHER │──▶│STRATEGIST │  │
│  │ (Fetch) │   │ (Gemini) │   │(Hunter/API)│   │ (Gemini)  │  │
│  └─────────┘   └──────────┘   └────────────┘   └─────┬─────┘  │
│       │              │              │                  │        │
│       ▼              ▼              ▼                  ▼        │
│  ┌──────────────────────────────────────────────┐ ┌────────┐   │
│  │              SQLite (Local Cache)             │ │ CRITIC │   │
│  │         data/signal_scout.db                  │ │Gemini +│   │
│  └──────────────────┬───────────────────────────┘ │ Ollama │   │
│                     │ sync.py                      └────────┘   │
│                     ▼                                           │
│  ┌──────────────────────────────────────────────┐               │
│  │         Supabase (Cloud Database)             │               │
│  │     + Next.js Dashboard (npm run dev)         │               │
│  └──────────────────────────────────────────────┘               │
└─────────────────────────────────────────────────────────────────┘
```

---

## Pipeline Nodes

| # | Node | Role | Model/API | Input Status | Output Status |
|---|------|------|-----------|-------------|---------------|
| 1 | **Scout** | Discovers jobs from 5 source types | Greenhouse API, Lever HTML, RSS, HN Algolia, SearXNG | — | `new` / `pre_filtered` |
| 2 | **Analyst** | Generates pain hypothesis | Gemini 2.0 Flash | `pre_filtered` | `analyzed` / `rejected` |
| 3 | **Researcher** | Enriches with contacts | Hunter.io, Apollo.io | `analyzed` | `enriched` |
| 4 | **Strategist** | Writes cold outreach pitch | Gemini 2.0 Flash | `enriched` | `pitch_written` |
| 5 | **Critic** | Scores pitch on 7 dimensions | Gemini (primary) → DeepSeek R1 via Ollama (fallback) | `pitch_written` | `pitch_approved` / `pitch_rejected` |

### Job Status Flow

```
new → pre_filtered → analyzed → enriched → pitch_written → pitch_approved
                  ↘ rejected                            ↘ pitch_rejected
```

---

## Project Structure

```
signal-scout/
├── src/
│   ├── core/
│   │   ├── config.py          # Pydantic settings + source target lists
│   │   ├── database.py        # SQLite CRUD, dedup, synced flag system
│   │   ├── models.py          # Pydantic data models (Company, Job, Contact, Pitch)
│   │   └── sync.py            # SQLite → Supabase batch push
│   ├── nodes/
│   │   ├── scout.py           # Job discovery orchestrator + pre-filter
│   │   ├── analyst.py         # Pain hypothesis via Gemini
│   │   ├── researcher.py      # Contact enrichment (Hunter/Apollo/manual)
│   │   ├── strategist.py      # Pitch generation via Gemini
│   │   └── critic.py          # 7-dimension scoring (Gemini → Ollama fallback)
│   ├── sources/
│   │   ├── greenhouse.py      # Greenhouse v1 Boards API (JSON)
│   │   ├── lever.py           # Lever career pages (HTML/BeautifulSoup)
│   │   ├── rss.py             # RSS feeds via feedparser
│   │   ├── hn_hiring.py       # HN "Who is Hiring" via Algolia API
│   │   └── searxng.py         # Local SearXNG instance (optional)
│   └── enrichment/            # (reserved for future enrichment modules)
├── scripts/
│   ├── setup_db.py            # Initialize SQLite schema (run once)
│   └── run_pipeline.py        # CLI entry point for all nodes
├── sql/
│   └── supabase_schema.sql    # Cloud DB schema (paste into Supabase SQL Editor)
├── dashboard/                 # Next.js dashboard (see Dashboard section)
├── data/
│   └── signal_scout.db        # Auto-created SQLite database
├── tests/                     # Test directory
├── requirements.txt           # Python dependencies
├── .env.example               # Environment variable template
├── .env                       # Your actual secrets (git-ignored)
└── .gitignore
```

---

## Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| **Python** | 3.11+ | Pipeline engine |
| **Node.js** | 18+ | Dashboard (Next.js) |
| **Ollama** | latest | Local LLM fallback for Critic node |
| **Git** | any | Version control |

### API Keys Required

| Service | Free Tier | Purpose | Required? |
|---------|-----------|---------|-----------|
| **Google AI Studio** | 1500 req/day | Gemini 2.0 Flash (Analyst, Strategist, Critic) | **Yes** |
| **Supabase** | 500MB DB | Cloud database + dashboard | **Yes** |
| **Hunter.io** | 25 req/month | Email discovery | Optional |
| **Apollo.io** | 50 req/month | Contact enrichment | Optional |
| **Ollama + DeepSeek R1** | Unlimited (local) | Critic fallback when Gemini quota exhausted | Recommended |

---

## Installation

### 1. Clone & Setup Virtual Environment

```powershell
cd "Autonomous Distributed Research & Lead Generation Agent"
cd signal-scout

# Create virtual environment
python -m venv venv

# Activate (Windows PowerShell)
.\venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

> **Note:** If `supabase` install fails with a C++ build error, run:
> ```powershell
> pip install "supabase>=2.0,<2.20"
> ```

### 2. Configure Environment

```powershell
# Copy template
copy .env.example .env

# Edit .env with your API keys
notepad .env
```

### 3. Initialize Local Database

```powershell
python scripts/setup_db.py
```

Expected output:
```
Signal Scout 4.0 — Database Setup
  Database path: ...\data\signal_scout.db
OK SQLite schema initialized
  Tables initialized:
    companies: 0 records
    jobs: 0 records
    contacts: 0 records
    pitches: 0 records
    pipeline_events: 0 records
OK Database ready!
```

---

## Environment Variables

Create a `.env` file in the project root with these variables:

```env
# === Signal Scout 4.0 — Environment Variables ===

# Google AI Studio (Gemini 2.0 Flash)
# Get key: https://aistudio.google.com/apikey
GEMINI_API_KEY=your_gemini_api_key_here

# Enrichment APIs (optional — pipeline works without them)
HUNTER_API_KEY=
APOLLO_API_KEY=

# Supabase (Cloud Database)
# Get from: Supabase Dashboard → Settings → API
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your_anon_key
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key

# Ollama (Local LLM — fallback for Critic)
OLLAMA_BASE_URL=http://localhost:11434

# Local Database
SQLITE_PATH=./data/signal_scout.db

# Rate Limits
SCOUT_INTERVAL_HOURS=4
GEMINI_DAILY_QUOTA=1500
HUNTER_MONTHLY_QUOTA=25
APOLLO_MONTHLY_QUOTA=50
SEARXNG_DAILY_QUOTA=20
```

---

## Database Schema

### Local Database (SQLite)

The local SQLite database (`data/signal_scout.db`) mirrors the cloud schema with an extra `synced` flag on every record. Auto-created by `scripts/setup_db.py`.

### Cloud Database (Supabase — PostgreSQL)

The cloud schema is defined in `sql/supabase_schema.sql`. It consists of **5 tables**, **9 indexes**, **RLS policies**, and an `updated_at` trigger.

#### Table: `companies`

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID (PK) | Auto-generated |
| `name` | TEXT | Company name |
| `domain` | TEXT (UNIQUE) | Dedup anchor (e.g. `stripe.com`) |
| `size_estimate` | TEXT | Small/Medium/Large |
| `location` | TEXT | HQ location |
| `funding_stage` | TEXT | Seed/Series A/B/C etc. |
| `tech_stack` | TEXT[] | Array of technologies |
| `industry` | TEXT | Industry vertical |
| `crunchbase_url` | TEXT | Crunchbase profile |
| `github_url` | TEXT | GitHub org URL |
| `linkedin_url` | TEXT | LinkedIn company page |
| `created_at` | TIMESTAMPTZ | Auto-set |
| `updated_at` | TIMESTAMPTZ | Auto-updated via trigger |

#### Table: `jobs`

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID (PK) | Auto-generated |
| `company_id` | UUID (FK → companies) | Parent company |
| `source` | TEXT | `greenhouse`, `lever`, `rss`, `hn_hiring`, `searxng` |
| `source_url` | TEXT | URL of the source feed/board |
| `title` | TEXT | Job title |
| `description` | TEXT | Full job description (max 5000 chars) |
| `job_url` | TEXT (UNIQUE) | Dedup anchor — unique job posting URL |
| `location` | TEXT | Job location |
| `pain_hypothesis` | TEXT | Analyst output: 2-sentence pain inference |
| `primary_process` | TEXT | Analyst output: main business process |
| `integration_gaps` | TEXT[] | Analyst output: system gaps |
| `tech_stack_inferred` | TEXT[] | Analyst output: inferred tech |
| `automatibility_score` | INTEGER (0-10) | How automatable is this role? |
| `analyst_confidence` | INTEGER (0-10) | Analyst confidence in hypothesis |
| `analyst_verdict` | TEXT | `PASS` or `REJECT` |
| `pain_keyword_score` | INTEGER | Pre-filter keyword match score |
| `status` | TEXT | State machine (see Job Status Flow) |
| `discovered_at` | TIMESTAMPTZ | When Scout found it |
| `analyzed_at` | TIMESTAMPTZ | When Analyst processed it |
| `enriched_at` | TIMESTAMPTZ | When Researcher enriched it |
| `pitch_written_at` | TIMESTAMPTZ | When Strategist wrote pitch |
| `pitch_scored_at` | TIMESTAMPTZ | When Critic scored pitch |

**Status values:** `new` → `pre_filtered` → `analyzed` / `rejected` → `enriched` → `pitch_written` → `pitch_approved` / `pitch_rejected` / `error`

#### Table: `contacts`

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID (PK) | Auto-generated |
| `company_id` | UUID (FK → companies) | Parent company |
| `job_id` | UUID (FK → jobs) | Associated job posting |
| `name` | TEXT | Contact full name |
| `title` | TEXT | Job title / role |
| `email_verified` | TEXT | Verified email address |
| `email_sources` | TEXT[] | Where email was found (`hunter`, `apollo`) |
| `linkedin_url` | TEXT | LinkedIn profile URL |
| `linkedin_confidence` | TEXT | `verified`, `inferred`, or `none` |
| `manual_research_links` | JSONB | Links for manual research (LinkedIn, Crunchbase, etc.) |
| `outreach_ready` | BOOLEAN | True if email verified + ready to contact |
| `outreach_status` | TEXT | `not_contacted` → `email_sent` → `responded` → `meeting_booked` |
| `outreach_channel` | TEXT | `email`, `linkedin`, `warm_intro` |
| `contacted_at` | TIMESTAMPTZ | When outreach was sent |
| `responded_at` | TIMESTAMPTZ | When they replied |
| `follow_up_at` | TIMESTAMPTZ | Scheduled follow-up date |
| `notes` | TEXT | Free-form notes |

#### Table: `pitches`

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID (PK) | Auto-generated |
| `job_id` | UUID (FK → jobs) | Source job |
| `contact_id` | UUID (FK → contacts) | Target contact |
| `subject_line` | TEXT | Email subject line |
| `pitch_body` | TEXT | Full email body (under 120 words) |
| `tone_profile` | TEXT | `direct`, `consultative`, or `curious` |
| `word_count` | INTEGER | Body word count |
| `score_specificity` | NUMERIC(3,1) | Critic: company-specific details (1-10) |
| `score_consultative` | NUMERIC(3,1) | Critic: advisor vs vendor tone (1-10) |
| `score_tone` | NUMERIC(3,1) | Critic: professional but human (1-10) |
| `score_brevity` | NUMERIC(3,1) | Critic: conciseness (1-10) |
| `score_value` | NUMERIC(3,1) | Critic: clear value proposition (1-10) |
| `score_credibility` | NUMERIC(3,1) | Critic: authority/expertise (1-10) |
| `score_humanity` | NUMERIC(3,1) | Critic: sounds like a real human (1-10) |
| `score_average` | NUMERIC(3,1) | Average of all 7 scores |
| `critic_verdict` | TEXT | `PASS` (avg ≥ 6.5) or `FAIL` |
| `critic_feedback` | TEXT | One-sentence improvement advice |
| `status` | TEXT | `draft` → `approved` / `rejected` → `sent` |

#### Table: `pipeline_events`

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID (PK) | Auto-generated |
| `job_id` | UUID (FK → jobs) | Related job |
| `node` | TEXT | `scout`, `analyst`, `researcher`, `strategist`, `critic` |
| `from_status` | TEXT | Previous status |
| `to_status` | TEXT | New status |
| `metadata` | JSONB | Node-specific metadata (scores, counts, etc.) |
| `error_message` | TEXT | Error details if failed |
| `created_at` | TIMESTAMPTZ | Event timestamp |

### Entity Relationship Diagram

```
┌──────────────┐       ┌──────────────┐       ┌──────────────┐
│  companies   │       │    jobs       │       │   contacts   │
│──────────────│       │──────────────│       │──────────────│
│ id (PK)      │◄──┐   │ id (PK)      │◄──┐   │ id (PK)      │
│ name         │   │   │ company_id   │───┘   │ company_id   │
│ domain (UQ)  │   │   │ title        │       │ job_id       │
│ tech_stack[] │   │   │ job_url (UQ) │       │ name         │
│ ...          │   │   │ status       │       │ email        │
└──────────────┘   │   │ pain_hypo... │       │ outreach_... │
                   │   └──────────────┘       └──────┬───────┘
                   │          │                      │
                   │          │                      │
                   │   ┌──────▼───────┐       ┌──────▼───────┐
                   │   │  pitches     │       │  pipeline_   │
                   │   │─────────────│       │  events      │
                   │   │ id (PK)      │       │──────────────│
                   │   │ job_id (FK)  │       │ id (PK)      │
                   │   │ contact_id   │       │ job_id (FK)  │
                   │   │ pitch_body   │       │ node         │
                   │   │ score_avg    │       │ metadata     │
                   │   │ verdict      │       └──────────────┘
                   │   └──────────────┘
                   └── (all tables FK to companies)
```

### Indexes

| Index | Table | Column(s) | Purpose |
|-------|-------|-----------|---------|
| `idx_jobs_status` | jobs | status | Filter by pipeline stage |
| `idx_jobs_company` | jobs | company_id | Join with companies |
| `idx_jobs_discovered` | jobs | discovered_at DESC | Recent-first ordering |
| `idx_contacts_outreach` | contacts | outreach_status | Filter by outreach stage |
| `idx_contacts_ready` | contacts | outreach_ready (partial) | Only ready contacts |
| `idx_pitches_status` | pitches | status | Filter drafts/approved |
| `idx_pipeline_events_job` | pipeline_events | job_id | Event history per job |
| `idx_pipeline_events_created` | pipeline_events | created_at DESC | Recent events |
| `idx_companies_domain` | companies | domain | Dedup lookups |

### Row Level Security (RLS)

- **Service Role** (Python backend): Full CRUD on all tables
- **Anon Key** (Dashboard): Read all tables, update contacts (outreach status) and pitches (approval)

---

## Usage (CLI)

All commands must be run from the `signal-scout/` directory with the venv activated:

```powershell
cd signal-scout
.\venv\Scripts\activate
```

### Run Individual Nodes

```powershell
# Discover jobs from all sources (Greenhouse, Lever, RSS, HN, SearXNG)
python scripts/run_pipeline.py --node scout

# Analyze pre-filtered jobs with Gemini (generates pain hypotheses)
python scripts/run_pipeline.py --node analyst

# Enrich analyzed jobs with contacts (Hunter.io / Apollo.io / manual links)
python scripts/run_pipeline.py --node researcher

# Generate cold outreach pitches with Gemini
python scripts/run_pipeline.py --node strategist

# Score pitches (Gemini primary → Ollama DeepSeek R1 fallback)
python scripts/run_pipeline.py --node critic

# Push all unsynced records to Supabase cloud
python scripts/run_pipeline.py --node sync

# View pipeline statistics
python scripts/run_pipeline.py --node stats
```

### Run Full Pipeline

```powershell
# Execute all nodes in sequence: Scout → Analyst → Researcher → Strategist → Critic → Sync
python scripts/run_pipeline.py --node all

# Dry run (validates imports, no API calls)
python scripts/run_pipeline.py --node all --dry-run
```

### Example Output

```
Scout Node -- Job Discovery

Greenhouse (JSON API):
  Greenhouse: pubmatic - 62 jobs
  Greenhouse: druva - 25 jobs
  Greenhouse: vercel - 85 jobs
  Greenhouse: postman - 107 jobs
  Greenhouse: groww - 16 jobs

Raw jobs discovered: 295

           Scout Summary
┌──────────────────────────┬───────┐
│ Metric                   │ Count │
├──────────────────────────┼───────┤
│ Total discovered         │   295 │
│ New (inserted)           │   234 │
│ Pre-filtered (pain >= 4) │    28 │
│ Duplicates (skipped)     │    61 │
└──────────────────────────┴───────┘
```

---

## Dashboard (Next.js)

The dashboard provides a visual interface to review leads, approve pitches, and track outreach.

### Setup

**Easiest way** — double-click the launcher:

```
signal-scout\dashboard\start.bat
```

**Or from PowerShell:**

```powershell
# Build + start (from anywhere):
cmd /c "cd /d C:\Users\Kundan\Downloads\AUTONO~1\signal-scout\dashboard && npx next build && npx next start"

# Or if already built, just start:
cmd /c "cd /d C:\Users\Kundan\Downloads\AUTONO~1\signal-scout\dashboard && npx next start"
```

> **⚠️ Windows Path Note:** The `&` character in the parent folder name
> (`Autonomous Distributed Research & Lead Generation Agent`) crashes Turbopack (`next dev`).
> Use `next build && next start` (production mode) instead, or rename the parent folder to remove the `&`.

Open **http://localhost:3000** in your browser.

### Dashboard Pages

| Page | Description |
|------|-------------|
| `/` | Pipeline overview — job counts by status, source breakdown |
| `/jobs` | Jobs table with status filters (new, analyzed, enriched, etc.) |
| `/pitches` | Pitch review — read AI-generated pitches, approve or reject |
| `/contacts` | Contact list — outreach status, copy pitch to clipboard |
| `/events` | Pipeline audit log — every state transition with timestamps |

### Dashboard Environment

Create `dashboard/.env.local`:

```env
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your_anon_key
```

> **Note:** The dashboard reads from Supabase (cloud). Make sure you've run `python scripts/run_pipeline.py --node sync` to push local data to the cloud first.

---

## Supabase Setup

### 1. Create Project

1. Go to [supabase.com](https://supabase.com) → New Project
2. Copy your **Project URL**, **anon key**, and **service_role key** from Settings → API

### 2. Run Schema SQL

1. Open Supabase Dashboard → **SQL Editor** → **New Query**
2. Paste the entire contents of `sql/supabase_schema.sql`
3. Click **Run**
4. Verify 5 tables appear in the Table Editor

### 3. Test Connection

```powershell
python scripts/run_pipeline.py --node sync
```

Expected output:
```
Supabase Sync -- Local -> Cloud
  Supabase connected

  companies: 5 records synced
  jobs: 234 records synced
  contacts: up to date
  pitches: up to date
  pipeline_events: 234 records synced

  Total: 473 records synced
```

---

## Ollama Setup (Critic Fallback)

The Critic node uses **Gemini 2.0 Flash** as primary scorer. When Gemini quota is exhausted, it falls back to **DeepSeek R1 7B** running locally via Ollama.

### Install Ollama

Download from [ollama.com](https://ollama.com) and install.

### Pull DeepSeek R1

```powershell
ollama pull deepseek-r1:7b
```

### Start Ollama Server

```powershell
ollama serve
```

The Critic node automatically detects Ollama at `http://localhost:11434`. If Ollama isn't running, the Critic gracefully skips the fallback.

---

## How It Works

### 1. Scout — Job Discovery

The Scout node fetches jobs from 5 source types and applies a **pain keyword pre-filter** before spending any LLM tokens:

| Source | Method | Rate Limit |
|--------|--------|------------|
| Greenhouse | `boards-api.greenhouse.io/v1/boards/{slug}/jobs` (JSON) | 1 req/sec |
| Lever | `jobs.lever.co/{slug}` (HTML parsing with BeautifulSoup) | 1 req/sec |
| RSS | feedparser (WeWorkRemotely, Remotive, Indeed India, Inc42) | 0.5 req/sec |
| HN Hiring | Algolia API for monthly "Who is Hiring" threads | 1 req/sec |
| SearXNG | Local search instance (optional, 20 queries/day cap) | 2 req/sec |

**Pre-filter keywords** with weighted scores:

| Keyword | Score | Keyword | Score |
|---------|-------|---------|-------|
| `data entry` | 4 | `SDR` / `BDR` | 4 |
| `lead generation` | 4 | `copy paste` | 4 |
| `manual process` | 4 | `manual` | 3 |
| `repetitive` | 3 | `operations` | 2 |

Jobs with cumulative score **≥ 4** advance to Analyst. The rest are stored but skipped.

### 2. Analyst — Pain Hypothesis (Gemini)

Sends each pre-filtered job to Gemini 2.0 Flash with a structured prompt. Returns:
- **Pain Hypothesis**: 2-sentence inference about operational bottleneck
- **Automatibility Score**: 0-10
- **Verdict**: `PASS` (score ≥ 5 AND confidence ≥ 4) or `REJECT`

### 3. Researcher — Contact Enrichment

For each passed job, enriches with contacts:
1. **Hunter.io** — Domain search for emails (25 free/month)
2. **Apollo.io** — People search targeting decision-maker titles (50 free/month)
3. **Manual links** — Always generates LinkedIn, Crunchbase, Glassdoor research URLs

### 4. Strategist — Pitch Generation (Gemini)

Generates a personalized cold outreach email:
- Under 120 words
- Consultative tone (advisor, not vendor)
- References the specific pain hypothesis
- Low-commitment CTA (15-min call or async audit)

### 5. Critic — Dual-Model Scoring

Scores each pitch on **7 dimensions** (1-10 scale):

| Dimension | What It Measures |
|-----------|-----------------|
| Specificity | References target company details |
| Consultative | Advisor positioning, not vendor |
| Tone | Professional but human |
| Brevity | Conciseness (under 120 words = 10) |
| Value | Clear value proposition |
| Credibility | Subtle authority/expertise |
| Humanity | Sounds like a real person wrote it |

**Pass threshold:** Average ≥ 6.5/10

**Model strategy:** Gemini 2.0 Flash → DeepSeek R1 7B (Ollama) fallback

---

## Rate Limits & Quotas

| Service | Free Tier Limit | Default Config | Reset |
|---------|----------------|----------------|-------|
| Gemini 2.0 Flash | ~1500 req/day | `GEMINI_DAILY_QUOTA=1500` | Daily (midnight UTC) |
| Hunter.io | 25 searches/month | `HUNTER_MONTHLY_QUOTA=25` | Monthly |
| Apollo.io | 50 searches/month | `APOLLO_MONTHLY_QUOTA=50` | Monthly |
| SearXNG | Unlimited (self-hosted) | `SEARXNG_DAILY_QUOTA=20` | Daily |
| Ollama (local) | Unlimited | No limit | N/A |

---

## Pi Migration

Signal Scout is designed to run on a Raspberry Pi for 24/7 autonomous operation.

### What Runs on Pi

- **Scout node** (job discovery — no LLM needed)
- **SearXNG** (local search engine)
- **SQLite** (local database)

### What Stays on LOQ (Local Machine)

- **Analyst, Strategist, Critic** (need Gemini API / GPU)
- **Researcher** (needs Hunter/Apollo API)
- **Dashboard** (Next.js)

### Migration Steps

1. Copy `src/sources/`, `src/nodes/scout.py`, `src/core/` to Pi
2. Set `SQLITE_PATH` in Pi's `.env` to a local path
3. Add a cron job: `*/4 * * * * cd /home/pi/signal-scout && python scripts/run_pipeline.py --node scout`
4. Sync Pi's SQLite to LOQ via `rsync` or shared storage

---

## License

Private project. All rights reserved.

