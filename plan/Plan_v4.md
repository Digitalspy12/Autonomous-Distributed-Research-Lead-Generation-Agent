# Signal Scout 4.0 — Research & Qualification Engine
## Plan.md v4.0 | AK 0121 Automation Agency
**Version:** 4.0  
**Date:** 2026-04-27  
**Mode:** RESEARCH ONLY — No Automated Sending  
**Budget:** ₹0 (Zero-Cost Stack)  
**Architecture:** LangGraph DAG + Simple Scraping + Manual Outreach

---

## 1. Executive Summary

Signal Scout 4.0 is a **B2B research and lead qualification engine**. It does not send emails. It does not blast LinkedIn. It discovers public hiring signals, infers operational pain, enriches decision-maker profiles, and presents a curated queue of high-intent leads for **manual outreach** via LinkedIn DM, warm intro, or personal email.

**Core Principle:** The human (Arihant) is the sender. The machine is the researcher.

**What This System Does:**
- Discovers job postings that signal automatable pain
- Generates a Pain Hypothesis for each role
- Finds the founder/VP name, title, and contact signals
- Stores everything in a reviewable dashboard
- Exports a "Daily Lead Queue" for manual action

**What This System Does NOT Do:**
- ❌ Send emails automatically
- ❌ Scrape LinkedIn (violates ToS)
- ❌ Scrape Twitter/X (blocked, legally hostile)
- ❌ Guess emails and blast them (damages reputation)
- ❌ Run deliverability infrastructure (SPF/DKIM/DMARC not needed)

---

## 2. Research-Only Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   SCOUT     │────▶│   ANALYST    │────▶│ RESEARCHER  │
│  (Discover) │     │   (Filter)   │     │  (Enrich)   │
└─────────────┘     └──────────────┘     └──────┬──────┘
                                                 │
                                                 ▼
┌─────────────────────────────────────────────────────────┐
│                      VAULT (Supabase)                   │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐  │
│  │   companies │  │     jobs    │  │    contacts     │  │
│  │   (intel)   │  │   (pain)    │  │  (names, links) │  │
│  └─────────────┘  └─────────────┘  └─────────────────┘  │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│              FACE — Next.js Review Dashboard            │
│                                                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐  │
│  │  Lead Card  │  │ Pain Hypo   │  │  Action Panel   │  │
│  │  (Company)  │  │ (Why them?) │  │ [Copy LinkedIn] │  │
│  └─────────────┘  └─────────────┘  │ [Copy Email]    │  │
│                                     │ [Mark Contacted]│  │
│                                     └─────────────────┘  │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│              HUMAN — Manual Outreach                    │
│  LinkedIn DM / Connection Request / Personal Email      │
└─────────────────────────────────────────────────────────┘
```

### Node Definitions

| Node | Function | Output |
|------|----------|--------|
| **Scout** | Polls public job sources | Raw job posts → SQLite cache |
| **Analyst** | Scores automatibility, writes Pain Hypothesis | Qualified leads with pain narrative |
| **Researcher** | Finds decision-maker names, titles, public contact signals | Enriched contact profiles |
| **Vault** | Stores structured research data | Supabase (companies, jobs, contacts) |
| **Face** | Review dashboard for human curation | Next.js Bento grid |

---

## 3. The Scout Node (Simple Sources Only)

### Philosophy
Use only sources that require **zero JavaScript rendering** and **zero authentication**.

### Approved Sources

#### Tier 1: Structured JSON (Zero Scraping)
```python
# Greenhouse — structured JSON endpoint
# No HTML parsing. No BeautifulSoup. Just requests.
r = requests.get("https://boards.greenhouse.io/{company}.json", timeout=15)
jobs = r.json().get("jobs", [])
```

| Source | Method | Why |
|--------|--------|-----|
| **Greenhouse** | `requests.get()` + `.json()` | Returns clean structured data |
| **Lever** | `requests.get()` + `BeautifulSoup` | Simple HTML, easy parsing |
| **Ashby** | `requests.get()` + `.json()` | Public JSON available |
| **RSS Feeds** | `feedparser` | Text-based, zero CPU |

#### Tier 2: RSS (Zero Scraping)
```python
RSS_FEEDS = [
    "https://weworkremotely.com/remote-jobs.rss",
    "https://jobicy.com/feed/",
]
```

#### Tier 3: Jina AI Reader (Edge Cases Only)
For complex HTML pages that fail with simple requests:
```python
def fetch_clean(url: str) -> str:
    # Free, no-auth, handles light JS. Last resort.
    r = requests.get(f"https://r.jina.ai/http://{url}", timeout=20)
    return r.text if r.status_code == 200 else ""
```

#### Tier 4: SearXNG (Capped)
```python
# Max 20 queries/day. Fallback only.
SEARXNG_DORKS = [
    'site:boards.greenhouse.io ("Data Entry" OR "Operations" OR "SDR")',
    'site:jobs.lever.co ("Manual" OR "Repetitive" OR "Data Processing")',
]
```

### What to AVOID
| Source | Reason |
|--------|--------|
| **LinkedIn** | ToS violation. Account ban. Legal risk. |
| **Twitter/X** | API costs $42k+/mo. Scraping blocked aggressively. |
| **Workday/SuccessFactors** | Heavy JS. Requires Playwright. Skip big enterprise. |
| **Any site with Cloudflare** | If it blocks you, stop. Find the job on Indeed or Greenhouse instead. |

---

## 4. The Analyst Node (Pain Hypothesis)

**Model:** Gemini 2.0 Flash (free tier)  
**Purpose:** Generate a narrative inference + automatibility score.

### Prompt
```
You are an operations analyst. Generate a "Pain Hypothesis" — a 2-sentence inference about the operational bottleneck this hiring implies.

Output strict JSON:
{
  "pain_hypothesis": "...",
  "primary_process": "...",
  "tech_stack": ["..."],
  "integration_gaps": ["..."],
  "automatibility_score": 0-10,
  "confidence": 0-10,
  "verdict": "PASS" or "REJECT"
}
```

**Rule:** `verdict == "PASS"` → Move to Researcher. Otherwise → Archive.

---

## 5. The Researcher Node (Contact Discovery)

### Philosophy
Find **publicly available** contact signals. Do not scrape LinkedIn. Do not guess emails blindly. Build a "contact profile" that the human reviewer can act on.

### Step 1: Derive Company Domain
```python
def derive_domain(company_name: str, job_url: str) -> str:
    if "greenhouse.io" in job_url:
        company = job_url.split("greenhouse.io/")[1].split("/")[0]
        return f"{company}.com"
    elif "lever.co" in job_url:
        company = job_url.split("jobs.lever.co/")[1].split("/")[0]
        return f"{company}.com"
    return None
```

### Step 2: Scrape Public Team Pages (Simple Only)
```python
TEAM_PATHS = ["/about", "/team", "/leadership", "/company", "/people", "/founders"]

def scrape_team_page(domain: str) -> dict:
    # Simple requests + BeautifulSoup only. No Playwright.
    for path in TEAM_PATHS:
        url = f"https://{domain}{path}"
        try:
            r = requests.get(url, timeout=10, headers={"User-Agent": "SignalScout/1.0"})
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, "html.parser")
                text = soup.get_text(separator="\n")
                for line in text.split("\n"):
                    line = line.strip()
                    if any(title in line for title in ["Founder", "CEO", "CTO", "VP", "Head of"]):
                        return {"raw_text": text, "founder_line": line, "source": url}
        except Exception:
            continue
    return {}
```

**If the page is React/JS-heavy and returns empty HTML → SKIP.** The lead gets `contact_confidence: "low"` and waits for manual research.

### Step 3: Free Enrichment APIs (Legal, ToS-Compliant)

| Service | Free Tier | What It Gives You | Legal? |
|---------|-----------|-------------------|--------|
| **Hunter.io** | 25 searches/month | Verified email pattern + confirmed emails | Yes, B2B data provider |
| **Apollo.io** | 50 credits/month | Names, titles, LinkedIn URLs, emails | Yes, B2B data provider |
| **RocketReach** | 5 lookups/month | Contact info, social links | Yes |
| **Clearbit** | 20 requests/month | Company intel, domain data | Yes |
| **Lusha** | 5 credits/month | Email/phone verification | Yes |

```python
def enrich_contact(domain: str, company_name: str) -> dict:
    contact = {
        "emails": [],
        "email_confidence": "none",
        "linkedin_urls": [],
        "names": [],
        "titles": [],
        "sources": []
    }

    # Hunter.io — domain search
    if hunter_credits > 0:
        r = requests.get("https://api.hunter.io/v2/domain-search",
                         params={"domain": domain, "api_key": HUNTER_KEY})
        if r.status_code == 200:
            data = r.json()["data"]
            contact["emails"] = [e["value"] for e in data.get("emails", []) if e.get("verification", {}).get("status") == "valid"]
            contact["sources"].append("hunter")

    # Apollo.io — people search
    if apollo_credits > 0:
        r = requests.get("https://api.apollo.io/v1/people/match",
                         headers={"Authorization": f"Bearer {APOLLO_KEY}"},
                         params={"q_organization_domains": domain, "person_titles": ["CEO", "Founder", "CTO", "VP"]})
        if r.status_code == 200:
            people = r.json().get("people", [])
            for p in people[:3]:
                contact["names"].append(p.get("name"))
                contact["titles"].append(p.get("title"))
                contact["linkedin_urls"].append(p.get("linkedin_url"))
                contact["emails"].append(p.get("email"))
            contact["sources"].append("apollo")

    return contact
```

### Step 4: Public Signal Aggregation (No Scraping)
Instead of scraping LinkedIn, aggregate public URLs for manual review:

```python
def aggregate_public_signals(company_name: str, domain: str) -> dict:
    return {
        "linkedin_company_url": f"https://www.linkedin.com/company/{company_name.lower().replace(' ', '-')}/",
        "linkedin_people_search": f"https://www.linkedin.com/search/results/people/?keywords={company_name.replace(' ', '%20')}%20founder",
        "github_org": f"https://github.com/{company_name.lower().replace(' ', '')}",
        "crunchbase": f"https://www.crunchbase.com/organization/{company_name.lower().replace(' ', '-')}",
        "google_news": f"https://news.google.com/search?q={company_name.replace(' ', '%20')}&hl=en-IN&gl=IN&ceid=IN%3Aen"
    }
```

**These are URLs for MANUAL review.** The human opens them, finds the person, and copies the LinkedIn profile URL.

### Step 5: Output Schema
```json
{
  "company": "Razorpay",
  "domain": "razorpay.com",
  "decision_maker": {
    "name": "Harshil Mathur",
    "title": "Co-Founder & CEO",
    "confidence": "high",
    "source": "Apollo.io"
  },
  "contact_signals": {
    "verified_emails": ["harshil@razorpay.com"],
    "email_confidence": "verified",
    "linkedin_url": "https://www.linkedin.com/in/harshil-mathur/",
    "linkedin_confidence": "verified",
    "public_sources": ["Apollo", "Team Page"]
  },
  "manual_research_links": {
    "linkedin_people_search": "https://www.linkedin.com/search/results/people/?keywords=Razorpay%20founder",
    "crunchbase": "https://www.crunchbase.com/organization/razorpay",
    "github_org": "https://github.com/razorpay",
    "google_news": "https://news.google.com/search?q=Razorpay"
  },
  "outreach_ready": true
}
```

**Rule:** `outreach_ready == true` only if name is found AND (email is verified OR LinkedIn URL is verified).

---

## 6. The Vault (Supabase Schema — Research Mode)

### Simplified Schema
```sql
-- Companies (deduplicated)
CREATE TABLE companies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    domain TEXT UNIQUE,
    size_estimate TEXT,
    location TEXT,
    funding_stage TEXT,
    tech_stack TEXT[],
    created_at TIMESTAMP DEFAULT NOW()
);

-- Jobs (pain signals)
CREATE TABLE jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID REFERENCES companies(id),
    source TEXT NOT NULL,
    source_url TEXT,
    title TEXT NOT NULL,
    description TEXT,
    job_url TEXT UNIQUE,
    location TEXT,
    pain_hypothesis TEXT,
    primary_process TEXT,
    integration_gaps TEXT[],
    automatibility_score INTEGER,
    analyst_confidence INTEGER,
    analyst_verdict TEXT,
    status TEXT DEFAULT 'new',
    discovered_at TIMESTAMP DEFAULT NOW(),
    analyzed_at TIMESTAMP,
    enriched_at TIMESTAMP
);

-- Contacts (enrichment output)
CREATE TABLE contacts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID REFERENCES companies(id),
    job_id UUID REFERENCES jobs(id),
    name TEXT,
    title TEXT,
    email_verified TEXT,
    email_sources TEXT[],
    linkedin_url TEXT,
    linkedin_confidence TEXT,
    manual_research_links JSONB,
    outreach_status TEXT DEFAULT 'not_contacted',
    contacted_at TIMESTAMP,
    responded_at TIMESTAMP,
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Pipeline events (audit log)
CREATE TABLE pipeline_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID REFERENCES jobs(id),
    node TEXT,
    from_status TEXT,
    to_status TEXT,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);
```

---

## 7. The Face (Next.js Review Dashboard)

### Purpose
A human reviews every enriched lead before any outreach happens.

### Layout
```
┌─────────────────────────────────────────────────────────┐
│  Signal Scout — Research Queue        [Filter: Ready]   │
├─────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────┐    │
│  │ HIGH PRIORITY: Razorpay                         │    │
│  │                                                 │    │
│  │ Pain: Hiring 3 SDRs for manual lead scraping.   │    │
│  │ Score: 9/10 | Confidence: 8/10                  │    │
│  │                                                 │    │
│  │ Contact: Harshil Mathur (Co-Founder & CEO)      │    │
│  │ Email: harshil@razorpay.com (Apollo verified)   │    │
│  │ LinkedIn: linkedin.com/in/harshil-mathur        │    │
│  │                                                 │    │
│  │ [Open LinkedIn] [Copy Email] [Skip]             │    │
│  │ [Mark as Contacted] [Add Notes] [Archive]       │    │
│  └─────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
```

### Actions Available
| Button | Action |
|--------|--------|
| **Open LinkedIn** | Opens their LinkedIn profile in new tab |
| **Copy Email** | Copies verified email to clipboard |
| **Copy Pain Hypothesis** | Copies AI-generated pain narrative for your DM |
| **Mark as Contacted** | Moves to `outreach_status: 'linkedin_dm_sent'` |
| **Add Notes** | Free-text notes |
| **Skip** | Archives lead with reason |

---

## 8. Manual Outreach Workflow

### Step 1: Review the Queue (Morning)
- Open dashboard.
- Filter by `outreach_status: 'not_contacted'` + `outreach_ready: true`.
- Pick 3-5 leads.

### Step 2: LinkedIn Research (2 minutes per lead)
- Click "Open LinkedIn".
- Check recent posts, activity, mutual connections.
- Note any "personal hooks" (recent funding, tech stack post, hiring announcement).

### Step 3: Craft Outreach (Using AI-Generated Pain Hypothesis)
- Copy the Pain Hypothesis from the dashboard.
- Write a LinkedIn connection request or DM:
  ```
  Hi [Name], saw Razorpay is scaling the SDR team. 
  Curious — are you handling lead enrichment manually right now, 
  or is there an automation layer in place? 
  We just helped a Pune fintech cut 80% of that overhead. 
  Happy to share the architecture if useful.
  ```
- Or send a personal email from your main domain (not automated).

### Step 4: Log the Action
- Click "Mark as Contacted" in dashboard.
- Select channel: `LinkedIn DM`, `Email`, `Warm Intro`, `Other`.
- Add date and notes.

### Step 5: Follow-Up
- Dashboard shows "Contacted 3 days ago, no response" reminders.
- You decide on follow-up timing and tone.

---

## 9. Compliance & Ethics (Research Mode)

### Hard Rules
- ❌ **No LinkedIn scraping.** Not with OpenClaw. Not with n8n. Not with Selenium. LinkedIn prohibits automated data collection.
- ❌ **No Twitter/X scraping.** API is $42k+/mo. Scraping is aggressively blocked.
- ❌ **No email blasting.** Verified emails are for manual, personalized outreach only.
- ❌ **No storing personal data beyond business context.** No family info, no personal photos.
- ❌ **No selling contact data.** Internal research only.

### What We Do
- ✅ Read public job postings.
- ✅ Scrape public `/about` and `/team` pages.
- ✅ Use B2B enrichment APIs (Apollo, Hunter) with free tiers.
- ✅ Aggregate public URLs for manual review.
- ✅ Store only business contact info (name, title, work email, company LinkedIn).
- ✅ Honor rate limits (1 req/sec per domain).

---

## 10. Build Timeline (Research Mode)

### Week 1: Core Pipeline
- [ ] Set up Pi with Docker + SearXNG
- [ ] Build Scout (Greenhouse + RSS)
- [ ] Build Analyst (Gemini 2.0 Flash)
- [ ] SQLite schema + Supabase sync
- [ ] Run first 20 leads end-to-end

### Week 2: Enrichment
- [ ] Build Researcher (team page scraper + Hunter/Apollo)
- [ ] Add public signal aggregation (LinkedIn search URLs, Crunchbase)
- [ ] Build Next.js dashboard (read-only lead cards)
- [ ] Manually verify 10 leads

### Week 3: Outreach Integration
- [ ] Add "Mark as Contacted" workflow
- [ ] Add notes + follow-up tracking
- [ ] Test manual outreach using dashboard data
- [ ] Refine Pain Hypothesis based on real conversations

### Week 4: Scale
- [ ] Add India-specific sources (Instahyre, Hirist)
- [ ] Add HN monthly harvester
- [ ] Add funding news signals (Entrackr/Inc42)
- [ ] Build analytics (response rate by source, by pain type)

---

## 11. Resource Limits (Research Only)

| Service | Free Quota | Usage | Monthly |
|---------|-----------|-------|---------|
| Gemini 2.0 Flash | 1,500/day | ~200 jobs | 6,000 |
| Hunter.io | 25/mo | 25 domains | 25 |
| Apollo.io | 50/mo | 50 contacts | 50 |
| Supabase | 500K req/day | ~1,000 | 30,000 |
| SearXNG | Unlimited | ~20/day | 600 |

**No Resend. No domain warmup. No email infrastructure.**

---


## 12. Appendix B: Simple Scraping Rules

| Source | Tool | Complexity |
|--------|------|------------|
| Greenhouse JSON | `requests` | None |
| Lever HTML | `requests + BeautifulSoup` | Low |
| RSS Feeds | `feedparser` | None |
| Company `/about` | `requests + BeautifulSoup` | Low |
| Complex JS pages | **Jina AI Reader** | Low (external) |
| Multi-page crawls | **crawl4ai** (last resort) | Medium |
| LinkedIn | **Manual only** | N/A |
| Twitter/X | **Skip entirely** | N/A |

**Rule:** If `requests + BeautifulSoup` fails, try Jina AI Reader. If Jina fails, **skip the source**. Do not escalate to Playwright or anti-bot tools.

---

## 13. Quick Start Checklist

- [ ] Pi setup with Raspberry Pi OS Lite
- [ ] Docker + SearXNG running on `:8080`
- [ ] Supabase project with v4 schema
- [ ] Google AI Studio API key
- [ ] Hunter.io free account
- [ ] Apollo.io free account
- [ ] Next.js 16 project initialized
- [ ] First Scout run discovers 10+ jobs
- [ ] First Analyst run generates Pain Hypotheses
- [ ] First Researcher run finds 3+ verified contacts
- [ ] Dashboard displays lead cards correctly
- [ ] Manual outreach test: 1 LinkedIn DM sent using dashboard data

 I see the confusion. The v4.0 Plan.md I wrote **removed the detailed hardware split section** that was in v3.0. Let me clarify both questions with the full context.

---

## 1. Why SQLite AND Supabase?

| Database | Role | Why Both? |
|----------|------|-----------|
| **SQLite** | **Local cache on the Pi** | Fast, zero-config, works without internet. The Pi writes here first. |
| **Supabase** | **Cloud master database** | Real-time sync, Next.js dashboard reads from here, team access, backups. |

### The Data Flow

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│   Scout     │────▶│   SQLite     │────▶│  Supabase    │
│  (Pi, 24/7) │     │  (Pi local)  │     │  (Cloud)     │
└─────────────┘     └──────────────┘     └──────────────┘
                                              │
                                              ▼
                                       ┌──────────────┐
                                       │  Next.js     │
                                       │  Dashboard   │
                                       │  (Your LOQ)  │
                                       └──────────────┘
```

**Why not write directly to Supabase from the Pi?**
- The Pi might lose WiFi. SQLite buffers data locally.
- Supabase has rate limits. SQLite batches writes.
- If Supabase goes down, the Pi keeps working.

**The sync script (runs hourly on Pi):**
```python
# sync_to_supabase.py
import sqlite3
from supabase import create_client

# Read new leads from SQLite
conn = sqlite3.connect("signal_scout.db")
cursor = conn.cursor()
cursor.execute("SELECT * FROM leads WHERE synced = 0")
new_leads = cursor.fetchall()

# Batch insert to Supabase
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
supabase.table("jobs").insert(new_leads).execute()

# Mark as synced
cursor.execute("UPDATE leads SET synced = 1 WHERE synced = 0")
conn.commit()
```

---

## 2. Hardware Split: What Each Machine Does

The v3.0 had this split. v4.0 simplified it but the logic still applies. Here is the full picture:

### Raspberry Pi — The Heartbeat (24/7)

**What it runs:**
| Service | Purpose | Why on Pi? |
|---------|---------|------------|
| **Scout Node** | Polls Greenhouse/RSS every 4 hours | Always-on, low power |
| **SearXNG** | Local search engine (`:8080`) | No rate limits, privacy |
| **SQLite** | Local cache | Zero-config, survives WiFi drops |
| **Sync Agent** | Pushes SQLite → Supabase hourly | Batches writes, respects quotas |

**What it does NOT run:**
- ❌ LLM inference (too slow, too hot)
- ❌ Ollama (not enough RAM)
- ❌ Next.js dev server
- ❌ Mem0 / Chroma (vector DB too heavy)

**Pi Specs Needed:**
- 4GB RAM minimum (8GB preferred)
- 64GB SD card or USB SSD
- Ethernet connection

---

### Lenovo LOQ — The Muscle (Daily Batch)

**What it runs:**
| Service | Purpose | Why on LOQ? |
|---------|---------|-------------|
| **Analyst Node** | Gemini 2.0 Flash API calls | Needs GPU for fast inference? No — API calls need internet + power |
| **Researcher Node** | Apollo/Hunter API calls + team page scraping | Needs Windows + browser |
| **Next.js Dashboard** | Dev server + build | Needs RAM, fast CPU |
| **Ollama** | DeepSeek R1 7B (Critic node) | Needs GPU (your LOQ has one) |
| **Mem0** | Agent memory (Chroma) | Needs RAM + disk |

**Daily Batch Schedule (6 AM):**
```bash
# On LOQ (Windows — use Task Scheduler or Python schedule library)

06:00  Pull "new" jobs from Supabase
06:15  Run Analyst (Gemini 2.0 Flash) → Pain Hypotheses
06:45  Run Researcher (Hunter/Apollo + team pages) → Contacts
07:15  Run Critic (DeepSeek R1 via Ollama) → Quality check
07:45  Push enriched leads back to Supabase
08:00  Open dashboard, review queue
```

---

## 3. Why This Split Matters

| Task | On Pi | On LOQ | Reason |
|------|-------|--------|--------|
| HTTP requests (Greenhouse) | ✅ Fast | ✅ Fast | Pi wins (always on) |
| SQLite writes | ✅ Instant | N/A | Pi only |
| SearXNG queries | ✅ Local | ❌ Remote | Pi hosts it |
| Gemini API calls | ❌ Slow/timeout | ✅ Fast | LOQ has better internet |
| DeepSeek R1 7B | ❌ 5+ minutes | ✅ 15 seconds | LOQ has GPU |
| Chroma/Mem0 | ❌ Crashes | ✅ Works | LOQ has 16GB+ RAM |
| Next.js dev | ❌ Impossible | ✅ Smooth | LOQ has CPU power |

---

## 4. The Honest Truth About the Pi

**The Pi is not doing heavy work.** It is a **scheduler + cache + lightweight poller**. All the "brain" work happens on your LOQ once per day.

If you don't have a Pi yet, you can **start with just the LOQ**:
- Run Scout as a scheduled Python script (`schedule` library)
- Skip SearXNG initially (use RSS + Greenhouse direct)
- SQLite lives on LOQ
- Add the Pi later for 24/7 operation

---

## 5. Simplified v4.0 Architecture (No Pi Required to Start)

```
┌─────────────────────────────────────────┐
│         Lenovo LOQ (Everything)         │
│                                         │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  │
│  │  Scout  │  │ Analyst │  │Researcher│  │
│  │ (sched) │  │(Gemini) │  │(Apollo) │  │
│  └────┬────┘  └────┬────┘  └────┬────┘  │
│       │            │            │       │
│       └────────────┼────────────┘       │
│                    ▼                    │
│              ┌──────────┐               │
│              │  SQLite  │               │
│              │(local)   │               │
│              └────┬─────┘               │
│                   │                     │
│                   ▼                     │
│              ┌──────────┐               │
│              │ Supabase │               │
│              │ (cloud)  │               │
│              └────┬─────┘               │
│                   │                     │
│                   ▼                     │
│              ┌──────────┐               │
│              │ Next.js  │               │
│              │Dashboard │               │
│              └──────────┘               │
└─────────────────────────────────────────┘
```

**Add the Pi later** when you want:
- 24/7 operation without keeping LOQ on
- SearXNG for discovery dorks
- Redundancy (if LOQ is off, Pi still scouts)

---

## Bottom Line

| Question | Answer |
|----------|--------|
| **Why SQLite?** | Local cache on Pi. Survives internet drops. Batches writes to Supabase. |
| **Why Supabase?** | Cloud master. Real-time dashboard. Team access. Backups. |
| **What does Pi do?** | Scout + SearXNG + SQLite cache + hourly sync. Lightweight, always-on. |
| **What does LOQ do?** | LLM reasoning (Gemini + Ollama) + enrichment APIs + dashboard + daily batch. |
| **Can I start without Pi?** | **Yes.** Run everything on LOQ with scheduled Python scripts. Add Pi later. |

---

**Document Owner:** AK 0121  
**Mode:** Research & Qualification Only  
**Next Review:** After first 50 manual outreaches  
**Status:** Production Ready
