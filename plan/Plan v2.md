# Signal Scout — Autonomous Lead Generation System
## Plan.md | AK 0121 Automation Agency
**Version:** 1.0  
**Date:** 2026-04-24  
**Budget:** ₹0 (Zero-Cost Stack)  
**Target:** B2B Tech Companies Hiring for Automatable Roles

---

## 1. Executive Summary

Signal Scout is an autonomous, signal-led lead generation engine that discovers high-intent B2B prospects by monitoring public hiring signals. Instead of cold outreach to arbitrary lists, the system identifies companies actively hiring for roles that imply operational friction (Data Entry, Manual QA, SDR work, Operations) and generates personalized automation pitches.

**Core Insight:** A job posting is a confession of pain. If a company is hiring a "Data Entry Specialist," they are explicitly stating they have a manual, repetitive process they haven't automated yet.

**Operating Principle:**
- **Legal:** Only public, unauthenticated data sources.
- **Free:** Zero paid APIs for core operation.
- **Lightweight:** Runs on a Raspberry Pi or GitHub Actions.
- **Signal-Led:** Every lead is validated by evidence of automatable pain.

---

## 2. System Architecture

### 2.1 State Machine Design

The agent operates as a deterministic state machine. Each node is idempotent and can be retried independently.

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   SCOUT     │────▶│    BRAIN     │────▶│   GHOST     │
│  (Discover) │     │   (Filter)   │     │  (Enrich)   │
└─────────────┘     └──────────────┘     └──────┬──────┘
                                                 │
┌─────────────┐     ┌──────────────┐            │
│  REFLECTION │◀────│    BRAIN     │◀───────────┘
│   (Review)  │     │   (Pitch)    │
└──────┬──────┘     └──────────────┘
       │
       ▼
┌─────────────┐
│   OUTPUT    │
│  (Supabase  │
│   / SQLite) │
└─────────────┘
```

### 2.2 Node Definitions

| Node | Codename | Function | Compute |
|------|----------|----------|---------|
| **Lead Discovery** | Scout | Ingests jobs from public sources | Raspberry Pi / GitHub Actions |
| **Filter** | Brain-1 | Scores automatibility via LLM | Google AI Studio (Free) |
| **Entity Resolution** | Ghost | Finds decision-maker names | Local scrape + Free enrichment |
| **Deep OSINT** | Brain-2 | Extracts company tech stack & pain | Public APIs + Job text analysis |
| **Pitch Synthesis** | Brain-3 | Generates personalized pitch | Google AI Studio (Free) |
| **Reflection** | Brain-4 | Self-critiques pitch quality | Google AI Studio (Free) |
| **Storage** | Vault | Persists leads & pitches | SQLite (Local) / Supabase (Free) |

### 2.3 Data Flow

1. **Scout** polls sources every 4 hours → Raw job posts → SQLite (`status: 'new'`)
2. **Brain-1** (Filter) reads `status: 'new'` → Scores pain → Updates `status: 'qualified'` or `status: 'rejected'`
3. **Ghost** reads `status: 'qualified'` → Finds founder/hiring manager name + email pattern → Updates `status: 'enriched'`
4. **Brain-2** (OSINT) reads `status: 'enriched'` → Extracts tech stack from job text + BuiltWith → Updates `status: 'osint_complete'`
5. **Brain-3** (Pitch) reads `status: 'osint_complete'` → Generates Markdown pitch → Updates `status: 'pitched'`
6. **Brain-4** (Reflection) reads `status: 'pitched'` → Evaluates personalization → Pass (`status: 'approved'`) or Fail (`status: 'needs_review'`)
7. **Vault** serves approved pitches for manual send or API dispatch.

---

## 3. The Scout Node (Lead Discovery)

### 3.1 Philosophy
The Scout does not "scrape" in the aggressive sense. It consumes **public feeds** and **structured endpoints** that are designed to be read by machines.

### 3.2 Source Tier List

#### Tier 1: Structured JSON (Highest Fidelity)
These return clean, structured data with zero HTML parsing.

| Source | URL Pattern | Auth | Rate Limit |
|--------|-------------|------|------------|
| **Greenhouse** | `https://boards.greenhouse.io/{company}.json` | None | Be polite (1 req/sec) |
| **Lever** | `https://jobs.lever.co/{company}/` | None | Public HTML, parseable |
| **Ashby** | `https://jobs.ashbyhq.com/{company}` | None | Public JSON available |

#### Tier 2: RSS Feeds (Lightweight, Continuous)
Perfect for Pi deployment. Text-based, low bandwidth.

| Source | URL | Update Freq |
|--------|-----|-------------|
| **We Work Remotely** | `https://weworkremotely.com/remote-jobs.rss` | Hourly |
| **Jobicy** | `https://jobicy.com/feed/` | Hourly |
| **HN Who is Hiring** | Via Algolia API (monthly batch) | Monthly |

#### Tier 3: SearXNG Dorks (Discovery)
Self-hosted SearXNG instance queries search engines without hitting rate limits.

| Dork | Purpose |
|------|---------|
| `site:boards.greenhouse.io "Data Entry" OR "Operations" OR "SDR"` | Find pain roles on Greenhouse |
| `site:jobs.lever.co "Manual" OR "Repetitive" OR "Data Processing"` | Find pain roles on Lever |
| `site:jobs.ashbyhq.com "Operations" OR "Automation" OR "Back Office"` | Find pain roles on Ashby |
| `site:*.com intitle:"careers" ("hiring") ("data entry" OR "manual") filetype:pdf` | Find formal JDs (desperation signal) |
| `site:boards.greenhouse.io ("Pune" OR "Bangalore" OR "Mumbai") ("Operations" OR "Analyst")` | India-specific targeting |

#### Tier 4: India-Specific & Startup
| Source | Method | Notes |
|--------|--------|-------|
| **Wellfound (AngelList)** | Scrape public listing pages | Filter by "Recently Funded" |
| **Instahyre** | Scrape public pages | Pune/Bangalore/Mumbai focus |
| **Hirist** | Scrape public pages | Tech-focused India roles |
| **Entrackr / Inc42** | Scrape funding articles | Timing signal — fund → hire |

### 3.3 Pain Keywords
The Scout pre-filters using these keywords before sending to the LLM. This saves tokens.

```python
PAIN_KEYWORDS = [
    "data entry", "manual", "repetitive", "spreadsheet", "csv",
    "reconciliation", "sdr", "outbound", "list building", "copy paste",
    "operations", "back office", "data processing", "administrative",
    "copying data", "moving data", "manual process", "tedious",
    "time-consuming", "error-prone", "routine", "clerical"
]
```

### 3.4 Pain Scoring (Pre-LLM)
Before any LLM call, the Scout runs a fast regex scorer:
- **Base:** +2 points per keyword hit
- **Frustration bonus:** +1 for "boring", "tedious", "time-consuming", "error-prone"
- **Threshold:** Score >= 4 → Send to LLM for deep evaluation
- **Score < 4:** Reject immediately (saves ~90% of jobs from LLM cost)

---

## 4. The Brain-1 Node (Filter / Automatibility Scoring)

### 4.1 Purpose
Determine if the role is genuinely automatable or if it requires human judgment that AI cannot replace.

### 4.2 LLM Configuration
- **Model:** Gemini 2.0 Flash (Google AI Studio Free Tier)
- **Quota:** 1,500 requests/day
- **Input:** Job title + description
- **Output:** JSON with structured scoring

### 4.3 Prompt Template

```
You are an automation consultant evaluating job postings for automatibility.

JOB TITLE: {title}
COMPANY: {company}
JOB DESCRIPTION:
{description}

Evaluate this role on the following dimensions (1-10 scale):
1. REPETITIVENESS: How repetitive and rule-based are the tasks?
2. DATA_VOLUME: How much manual data movement is involved?
3. SYSTEM_INTEGRATION: Does it involve moving data between apps (e.g., CRM, spreadsheets, databases)?
4. HUMAN_JUDGMENT: Does it require complex human judgment, empathy, or creativity?
5. ROI_POTENTIAL: If automated, would this save significant human hours?

Return ONLY a JSON object:
{
  "automatibility_score": 0-10,
  "confidence": 0-10,
  "primary_pain": "One sentence describing the core pain",
  "tech_stack_mentioned": ["list", "of", "tools"],
  "automation_opportunity": "One sentence on what to automate",
  "verdict": "PASS" or "REJECT"
}

Rules:
- PASS if automatibility_score >= 7 and confidence >= 6
- REJECT if role requires strategic thinking, relationship building, or creative work
- Be conservative. A false positive (pitching a non-automatable role) damages credibility.
```

### 4.4 Decision Logic
- `verdict == "PASS"` → Move to Ghost
- `verdict == "REJECT"` → `status: 'rejected'`, log reason
- `confidence < 6` → `status: 'needs_human_review'`

---

## 5. The Ghost Node (Entity Resolution)

### 5.1 Philosophy
Find the decision-maker without scraping LinkedIn or violating ToS. Use public company pages and free enrichment tiers.

### 5.2 Methodology

#### Step 1: Extract Domain
From the job URL or company name, derive the domain:
- Greenhouse: `boards.greenhouse.io/{company}` → Google `{company} careers` → Find domain
- Lever: `jobs.lever.co/{company}` → Domain often in apply flow
- RSS: Usually contains company name in title

#### Step 2: Scrape Public Team Pages
```
https://{domain}/about
https://{domain}/team
https://{domain}/leadership
https://{domain}/company
```
Use `requests` + `BeautifulSoup` to extract names and titles. Look for:
- "Founder", "Co-Founder", "CEO", "CTO", "VP", "Head of", "Director"
- Operations, Engineering, Product, Sales titles

#### Step 3: Free Enrichment APIs
| Service | Free Tier | Best For |
|---------|-----------|----------|
| **Hunter.io** | 25 searches/month | Email pattern finder (`firstname@domain.com`) |
| **Apollo.io** | 50 credits/month | Verified emails + titles |
| **RocketReach** | Limited free lookups | Contact enrichment |
| **Clearbit** | Free tier (limited) | Company data |

#### Step 4: Email Pattern Guessing
If enrichment APIs fail, use common patterns:
- `{first}@domain.com`
- `{first}.{last}@domain.com`
- `{first}{last}@domain.com`
- `founder@domain.com`
- `hello@domain.com` (fallback for small companies)

### 5.3 Output Schema
```json
{
  "decision_maker": {
    "name": "Rahul Sharma",
    "title": "Founder & CEO",
    "confidence": "high"
  },
  "email": {
    "address": "rahul@company.com",
    "verified": false,
    "source": "pattern_guess"
  },
  "company": {
    "domain": "company.com",
    "size_estimate": "10-50",
    "location": "Pune, India"
  }
}
```

### 5.4 Fallback Strategy
If no specific decision-maker is found after 3 attempts:
- Use `founders@domain.com` or `hello@domain.com`
- Mark `confidence: "low"`
- Still generate pitch but flag for manual review before send

---

## 6. The Brain-2 Node (Deep OSINT)

### 6.1 Philosophy
Replace "personal stalking" with "professional signal extraction." The job description itself is the richest OSINT source.

### 6.2 Data Sources (All Free)

#### A. Job Description Analysis (Primary)
The JD already tells you:
- **Tools they use:** "Manage Salesforce records," "Update Airtable," "Process Excel sheets"
- **Processes they struggle with:** "Reconcile data between systems," "Copy leads from LinkedIn to CRM"
- **Volume signals:** "Process 500 records/day," "Manage 10,000 rows"

#### B. BuiltWith / Wappalyzer (Tech Stack)
- **BuiltWith Free:** Limited lookups but sufficient for batch analysis
- **Wappalyzer Browser Extension:** Manual check for high-value leads
- **What to look for:** CRM (Salesforce, HubSpot), Spreadsheets (Google Sheets, Excel), Databases (Airtable, Notion), Communication (Slack, Teams)

#### C. GitHub API (Public Repos)
- `https://api.github.com/orgs/{company}/repos`
- **Rate limit:** 60 requests/hour (no auth)
- **Signal:** Tech stack, engineering maturity, open-source culture

#### D. Company Blog / Press
- Scrape `/blog` for posts about "scaling operations," "hiring challenges," "growth"
- Check recent press releases for funding or expansion news

### 6.3 Output: The "Hook Document"
```json
{
  "pain_signals": [
    "Manually copying data between Salesforce and Excel",
    "Processing 500+ records daily",
    "Reconciling mismatched data sets"
  ],
  "tech_stack": ["Salesforce", "Excel", "Google Sheets"],
  "integration_gaps": ["Salesforce ↔ Excel", "No API automation"],
  "personalization_hooks": [
    "Recently posted about scaling operations team",
    "Uses Salesforce but no visible integration layer"
  ]
}
```

---

## 7. The Brain-3 Node (Pitch Synthesis)

### 7.1 Purpose
Combine "Job Pain" + "Company Context" + "AK 0121 Solution" into a concise, consultative pitch.

### 7.2 LLM Configuration
- **Model:** Gemini 2.0 Flash
- **Max Output Tokens:** 400
- **Format:** Markdown email

### 7.3 Prompt Template

```
You are a senior automation consultant at AK 0121. Write a cold email to a founder.

RECIPIENT:
- Name: {name}
- Title: {title}
- Company: {company}

CONTEXT:
- Role they are hiring: {job_title}
- Pain from job post: {primary_pain}
- Tech stack: {tech_stack}
- Integration gap: {integration_gaps}
- Company size estimate: {size}

RULES:
1. Subject line must reference their specific pain (not generic).
2. First sentence must quote or paraphrase their job post to prove you read it.
3. Second sentence must identify the automation opportunity.
4. Third sentence must propose a 10-minute call with a specific value proposition.
5. Tone: consultative, helpful, not salesy. No emojis. No exclamation marks.
6. Maximum 120 words.
7. Do NOT mention "AI" more than once.
8. Do NOT use phrases like "I came across your posting" or "I noticed you are hiring." Instead, be direct: "Your posting for X reveals a specific automation gap."

OUTPUT FORMAT:
Subject: [Subject line]

[Body text]

Best,
[Your Name]
AK 0121 Automation
```

### 7.4 Example Output

```markdown
Subject: The Salesforce-to-Excel gap in your Data Analyst role

Your posting for a Junior Data Analyst explicitly mentions manually reconciling Salesforce records with Excel sheets daily. This is a textbook integration gap — one that costs roughly 15-20 hours per week and introduces data drift.

AK 0121 builds lightweight automation bridges between CRMs and spreadsheets. We typically reduce this workload by 80% within two weeks.

Worth a 10-minute call next Tuesday to see if this fits your current workflow?

Best,
[Your Name]
AK 0121 Automation
```

---

## 8. The Brain-4 Node (Reflection)

### 8.1 Purpose
Prevent low-quality pitches from reaching prospects. Self-critique before approval.

### 8.2 Prompt Template

```
You are a quality control editor. Review this cold email pitch.

PITCH:
{pitch_text}

CONTEXT:
- Recipient: {name}, {title} at {company}
- Pain: {primary_pain}

EVALUATE on these criteria (PASS/FAIL):
1. SPECIFICITY: Does it reference a specific detail from the job post?
2. CONSULTATIVE: Does it sound like advice, not a sales pitch?
3. BREVITY: Is it under 120 words?
4. VALUE_FIRST: Does the recipient learn something before being asked for a call?
5. CREDIBILITY: Does it avoid buzzwords and generic claims?

Return JSON:
{
  "overall": "PASS" or "FAIL",
  "scores": {
    "specificity": 0-10,
    "consultative": 0-10,
    "brevity": 0-10,
    "value_first": 0-10,
    "credibility": 0-10
  },
  "issues": ["list of problems if any"],
  "suggested_fix": "One sentence on how to improve"
}

PASS requires:
- overall average score >= 7
- specificity >= 6
- consultative >= 6
```

### 8.3 Decision Logic
- `overall == "PASS"` → `status: 'approved'` → Ready for send
- `overall == "FAIL"` → `status: 'needs_review'` → Queue for manual fix or discard
- **No automatic retry loop.** If it fails once, flag for human. This prevents token waste.

---

## 9. The Vault (Data Layer)

### 9.1 SQLite Schema (Local / Pi)

```sql
-- Main leads table
CREATE TABLE leads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,              -- 'greenhouse', 'rss', 'searxng', 'hn'
    source_url TEXT,
    company TEXT NOT NULL,
    company_domain TEXT,
    job_title TEXT NOT NULL,
    job_description TEXT,
    job_url TEXT UNIQUE,
    location TEXT,

    -- Pain scoring
    pain_score_pre INTEGER,            -- Pre-LLM keyword score
    automatibility_score INTEGER,      -- LLM score 0-10
    confidence INTEGER,                -- LLM confidence 0-10
    primary_pain TEXT,
    tech_stack TEXT,                   -- JSON array

    -- Ghost enrichment
    decision_maker_name TEXT,
    decision_maker_title TEXT,
    email_address TEXT,
    email_verified BOOLEAN DEFAULT 0,
    enrichment_source TEXT,            -- 'apollo', 'hunter', 'pattern', 'manual'

    -- Pitch
    pitch_subject TEXT,
    pitch_body TEXT,

    -- Reflection
    reflection_score INTEGER,
    reflection_issues TEXT,

    -- State machine
    status TEXT DEFAULT 'new',         -- new, qualified, enriched, osint_complete, pitched, approved, rejected, needs_review, needs_human_review

    -- Metadata
    discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP,
    sent_at TIMESTAMP,
    response_received BOOLEAN DEFAULT 0
);

-- Source tracking
CREATE TABLE source_health (
    source TEXT PRIMARY KEY,
    last_check TIMESTAMP,
    jobs_found INTEGER DEFAULT 0,
    jobs_qualified INTEGER DEFAULT 0,
    errors INTEGER DEFAULT 0,
    avg_response_ms INTEGER
);

-- Daily stats
CREATE TABLE daily_stats (
    date TEXT PRIMARY KEY,
    discovered INTEGER DEFAULT 0,
    qualified INTEGER DEFAULT 0,
    enriched INTEGER DEFAULT 0,
    approved INTEGER DEFAULT 0,
    rejected INTEGER DEFAULT 0,
    api_calls INTEGER DEFAULT 0
);
```

### 9.2 Supabase (Optional Cloud Backup)
If you want cloud persistence:
- **Free Tier:** 500MB database, 500K requests/day
- **Use case:** Mirror approved leads for team access
- **Method:** Python `supabase-py` client, insert only approved pitches

---

## 10. Infrastructure & Deployment

### 10.1 Hardware Options

| Option | Cost | Best For |
|--------|------|----------|
| **Raspberry Pi 4/5** | ₹4,500 (one-time) | 24/7 operation, local SearXNG |
| **Old Laptop** | ₹0 | Development, testing |
| **GitHub Actions** | ₹0 | Scheduled execution, no hardware |
| **Google Colab** | ₹0 | LLM processing (if Studio quota hits) |

### 10.2 Recommended Pi Setup

```bash
# 1. OS Setup
sudo apt update && sudo apt upgrade -y
sudo apt install python3-pip python3-venv sqlite3 git cron

# 2. Project Directory
mkdir -p ~/signal-scout && cd ~/signal-scout
python3 -m venv venv
source venv/bin/activate

# 3. Dependencies
pip install requests beautifulsoup4 feedparser

# 4. SearXNG (Docker)
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo docker run -d --name searxng -p 8080:8080   -v "${PWD}/searxng:/etc/searxng"   searxng/searxng

# 5. Cron Schedule (every 4 hours)
crontab -e
# Add: 0 */4 * * * cd ~/signal-scout && venv/bin/python scout.py >> logs/scout.log 2>&1
```

### 10.3 GitHub Actions Alternative
If no Pi available, use GitHub Actions for scheduling:

```yaml
# .github/workflows/scout.yml
name: Signal Scout
on:
  schedule:
    - cron: '0 */4 * * *'  # Every 4 hours
  workflow_dispatch:

jobs:
  scout:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install requests beautifulsoup4 feedparser
      - run: python scout.py
      - uses: actions/upload-artifact@v4
        with:
          name: leads-db
          path: signal_scout.db
```

---

## 11. Resource Limits & Quotas

### 11.1 Free Tier Budget

| Service | Free Quota | Daily Usage Estimate | Monthly Total |
|---------|------------|---------------------|---------------|
| **Gemini Flash** | 1,500 req/day | ~200 leads processed | 6,000 req |
| **Hunter.io** | 25 searches/mo | 1 search per qualified lead | 25 leads |
| **Apollo.io** | 50 credits/mo | 1 credit per lead | 50 leads |
| **GitHub API** | 60 req/hour | Company repo checks | ~1,440 req |
| **SearXNG (self-hosted)** | Unlimited | ~20 dorks per run | Unlimited |
| **SQLite** | Unlimited | All storage | Unlimited |
| **Supabase** | 500K req/day | Backup sync | ~1,000 req |

### 11.2 Cost Control Rules
1. **Pre-filter everything.** Keyword scoring must reject 80%+ of jobs before LLM call.
2. **No retry loops.** One LLM call per node. If it fails, flag for human.
3. **Batch HN monthly.** Don't waste daily quota on monthly threads.
4. **Prioritize Greenhouse.** Highest signal-to-noise ratio. Allocate 50% of quota here.

---

## 12. Compliance & Ethics

### 12.1 What We Do NOT Do
- ❌ Scrape LinkedIn (violates ToS, high ban risk)
- ❌ Scrape Twitter/X (blocked, legally aggressive)
- ❌ Use personal data without business context
- ❌ Run Maigret-style personal OSINT
- ❌ Store data on EU citizens without GDPR consideration
- ❌ Send unsolicited emails to generic inboxes at scale

### 12.2 What We DO
- ✅ Read public job postings (explicitly published for discovery)
- ✅ Scrape public `/about` and `/team` pages
- ✅ Use free-tier B2B enrichment tools (designed for this purpose)
- ✅ Generate personalized, relevant pitches based on stated business needs
- ✅ Store data locally (SQLite) with minimal cloud exposure
- ✅ Honor robots.txt and rate limits (max 1 req/sec per domain)

### 12.3 Email Sending Guidelines
- Verify emails via Hunter.io or pattern matching before sending
- Include clear unsubscribe mechanism
- Do not send more than 10 cold emails per day initially (warm up domain)
- Use a dedicated domain (e.g., `ak0121.io`) separate from main business domain

---

## 13. Build Timeline

### Week 1: Foundation
- [ ] Set up Raspberry Pi or GitHub Actions environment
- [ ] Initialize SQLite database
- [ ] Build Scout node (Greenhouse JSON + RSS)
- [ ] Implement pre-filter keyword scoring
- [ ] Test with 10 target companies

### Week 2: Intelligence
- [ ] Integrate Google AI Studio (Gemini Flash)
- [ ] Build Brain-1 (Filter) with structured JSON output
- [ ] Build Ghost node (team page scraper + Hunter.io)
- [ ] Test end-to-end: Job → Filter → Enrichment

### Week 3: Synthesis
- [ ] Build Brain-2 (OSINT: BuiltWith, GitHub, JD analysis)
- [ ] Build Brain-3 (Pitch Synthesis)
- [ ] Build Brain-4 (Reflection)
- [ ] Create pitch review dashboard (simple HTML or CLI)

### Week 4: Deployment
- [ ] Set up SearXNG locally
- [ ] Add SearXNG dorks to Scout
- [ ] Add India-specific sources (Instahyre, Hirist)
- [ ] Add HN monthly harvester
- [ ] Set up cron scheduling
- [ ] Send first 5 approved pitches manually

### Week 5: Optimization
- [ ] Analyze response rates
- [ ] Refine keywords based on false positives/negatives
- [ ] Add Wellfound and YC source scraping
- [ ] Build simple analytics (daily_stats table queries)

---

## 14. Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Jobs Discovered / Day** | 50-100 | Scout logs |
| **Qualification Rate** | 15-20% | `qualified / discovered` |
| **Enrichment Rate** | 60%+ | `enriched / qualified` |
| **Pitch Approval Rate** | 70%+ | `approved / pitched` |
| **Cold Email Send Rate** | 5-10 / day | Manual send queue |
| **Response Rate** | 5-10% | Tracked in `response_received` |
| **Meeting Booked Rate** | 1-2% | Manual tracking |

---

## 15. Failure Modes & Mitigation

| Failure | Cause | Mitigation |
|---------|-------|------------|
| **Greenhouse blocks IP** | Too many requests | Add 2-second delays, rotate User-Agent |
| **Gemini quota exhausted** | 1,500/day limit | Fall back to Ollama local (Mistral 7B) |
| **Hunter/Apollo credits gone** | 25-50/mo limit | Switch to pattern guessing + manual verification |
| **SearXNG returns no results** | Instance blocked | Restart Docker container, check instance health |
| **False positives** | LLM over-scores | Tighten prompt, add human review for first 50 |
| **No decision maker found** | Stealth company | Skip and log; don't waste cycles |

---

## 16. Appendix

### A. SearXNG Dork Library
```python
SEARXNG_DORKS = [
    # Greenhouse - General pain roles
    'site:boards.greenhouse.io ("Data Entry" OR "Operations Associate" OR "Junior Analyst" OR "Manual Tester" OR "SDR" OR "Sales Development")',

    # Lever - Process pain
    'site:jobs.lever.co ("Repetitive" OR "Data Processing" OR "Copy Paste" OR "Spreadsheet" OR "CSV" OR "Manual")',

    # Ashby - Modern startups
    'site:jobs.ashbyhq.com ("Operations" OR "Automation" OR "Back Office" OR "Administrative" OR "Data")',

    # PDF Job Descriptions
    'site:*.com intitle:"careers" ("hiring" OR "join us") ("data entry" OR "manual" OR "operations" OR "reconciliation") filetype:pdf',

    # India-specific
    'site:boards.greenhouse.io ("Pune" OR "Bangalore" OR "Mumbai" OR "Hyderabad" OR "Remote India") ("Operations" OR "Analyst" OR "SDR" OR "Data")',

    # Remote-first companies (often lean, value automation)
    'site:boards.greenhouse.io ("Remote" OR "Worldwide") ("Operations" OR "Data" OR "Automation")',

    # High-growth signals
    'site:jobs.lever.co ("Scale" OR "Growth" OR "Expand") ("Operations" OR "Data" OR "Sales")'
]
```

### B. Target Company Lists (Seed)
```python
GREENHOUSE_TARGETS = [
    # India-based / India-remote
    "razorpay", "groww", "zerodha", "phonepe", "cred",
    "sliceit", "upstox", "unacademy", "vedantu", "leapfinance",

    # Global remote-friendly (high automation maturity)
    "stripe", "notion", "linear", "vercel", "figma", "loom",
    "retool", "mercury", "brex", "ramp", "webflow", "framer",
    "supabase", "planetscale", "resend", "calcom"
]
```

### C. Reflection Scoring Rubric
| Score | Meaning |
|-------|---------|
| 9-10 | Exceptional. Ready to send. |
| 7-8 | Good. Minor tweaks optional. |
| 5-6 | Acceptable. Review before send. |
| <5 | Reject. Regenerate or discard. |

### D. Email Domain Warmup Schedule
| Week | Daily Volume | Action |
|------|--------------|--------|
| 1 | 2-3 emails | Send to warm contacts only |
| 2 | 3-5 emails | Mix warm + cold |
| 3 | 5-7 emails | Add more cold |
| 4+ | 10 emails | Full operation |

---

## 17. Quick Start Checklist

- [ ] Raspberry Pi setup complete (or GitHub Actions configured)
- [ ] Python 3.11+ installed with venv
- [ ] SQLite database initialized (`init_db()`)
- [ ] Google AI Studio API key obtained (free)
- [ ] Hunter.io account created (free tier)
- [ ] Apollo.io account created (free tier)
- [ ] SearXNG Docker container running on `:8080`
- [ ] `scout.py` runs without errors on Greenhouse targets
- [ ] First 5 leads manually reviewed for quality
- [ ] First pitch manually sent and response tracked

---

**Document Owner:** AK 0121  
**Next Review:** After first 100 leads processed  
**Status:** Draft → Ready for Build
