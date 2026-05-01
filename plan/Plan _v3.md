# Signal Scout 2.0 — Agentic Lead Generation System
## Plan.md v3.0 | AK 0121 Automation Agency
**Version:** 3.0  
**Date:** 2026-04-24  
**Budget:** ₹0 (Zero-Cost Stack)  
**Architecture:** LangGraph DAG + Multi-Layer Memory  
**Hardware:** Raspberry Pi 4/5 (24/7 Scout) + Lenovo LOQ (Daily Batch Muscle)

---

## 1. Executive Summary

Signal Scout 2.0 is an autonomous, signal-led B2B lead generation engine built for AK 0121. Unlike traditional scrapers that harvest contact lists, Signal Scout operates as a **reasoning agent** that reads public hiring signals, hypothesizes operational pain, enriches decision-maker context, and synthesizes consultative pitches through an iterative critique loop.

**Core Thesis:** A job posting is a confession of operational friction. If a company is hiring three SDRs or a "Data Entry Specialist," they are explicitly broadcasting a manual process they have not automated. Signal Scout listens to these confessions and responds with precision.

**Operating Principles:**
- **Signal-Led:** Every lead originates from a verified pain signal (hiring post).
- **Agentic:** LangGraph DAG enables reasoning, not just filtering.
- **Zero-Cost:** No paid APIs for core operation. Self-hosted infrastructure.
- **Memory-Augmented:** Three-layer memory ensures the agent learns from every interaction.
- **Human-in-the-Loop:** Pitches are reviewed in a Next.js Bento dashboard before dispatch.

---

## 2. Architectural Philosophy

### 2.1 From Waterfall to DAG
The original Signal Scout was a linear pipeline (Step 1 → Step 2). Version 2.0 replaces this with a **Directed Acyclic Graph (DAG)** where nodes can branch, loop, and retry based on reasoning outcomes.

```
                    ┌─────────────┐
                    │   TRIGGER   │
                    │  (Schedule) │
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
       ┌──────────┐ ┌──────────┐ ┌──────────┐
       │  RSS     │ │Greenhouse│ │ SearXNG  │
       │  Scout   │ │  Scout   │ │  Scout   │
       └────┬─────┘ └────┬─────┘ └────┬─────┘
            │            │            │
            └────────────┼────────────┘
                         ▼
                  ┌──────────────┐
                  │   ANALYST    │
                  │  (Brain-1)   │
                  │Pain Hypothesis│
                  └──────┬───────┘
                         │
              ┌──────────┴──────────┐
              │ automatibility >= 7 │
              └──────────┬──────────┘
                         ▼
                  ┌──────────────┐
                  │  RESEARCHER  │
                  │   (Ghost)    │
                  │Entity Resolve│
                  └──────┬───────┘
                         │
                         ▼
                  ┌──────────────┐
                  │  STRATEGIST  │
                  │  (Brain-3)   │
                  │Pitch Synthesis│
                  └──────┬───────┘
                         │
                         ▼
                  ┌──────────────┐
                  │   CRITIC     │
                  │  (Brain-4)   │
                  │  Reflection  │
                  └──────┬───────┘
                         │
              ┌──────────┼──────────┐
              │          │          │
         PASS ▼     FAIL ▼    NEEDS ▼
         HUMAN      LOOP      REVIEW
              │          │          │
              └──────────┼──────────┘
                         ▼
                  ┌──────────────┐
                  │    VAULT     │
                  │  (Supabase)  │
                  └──────┬───────┘
                         │
                         ▼
                  ┌──────────────┐
                  │   FACE       │
                  │  (Next.js)   │
                  │Bento Dashboard│
                  └──────────────┘
```

### 2.2 The AK 0121 Dynamic: Strategist vs. Architect
The system mirrors your agency structure:
- **The Engine (Kundan / Pi):** Handles ingestion, scheduling, and raw data plumbing. Always on.
- **The Muscle (LOQ):** Runs heavy reasoning, LLM inference, and memory consolidation. Daily batch.
- **The Face (Arihant / Next.js):** Reviews, edits, and dispatches approved pitches through the dashboard.

---

## 3. The Agentic Stack

| Layer | Technology | Role | Cost |
|-------|-----------|------|------|
| **Orchestration** | LangGraph (Python) | DAG state machine, branching logic | ₹0 |
| **Fast Brain** | Gemini 2.0 Flash | Volume filtering, tech stack extraction | ₹0 (1,500/day) |
| **Nuance Brain** | Gemini 3 Flash | Pitch synthesis, tone calibration | ₹0 (1,500/day) |
| **Local Brain** | DeepSeek R1 7B (Ollama) | Reflection, critique, reasoning | ₹0 (local GPU) |
| **Embeddings** | nomic-embed-text (Ollama) | Vector search, semantic memory | ₹0 |
| **Database** | Supabase (Postgres) | Structured leads, real-time sync | ₹0 (500MB) |
| **Vector DB** | Supabase pgvector | Semantic search over JDs/pitches | ₹0 |
| **Agent Memory** | Mem0 (self-hosted Chroma) | Cross-session learning, patterns | ₹0 |
| **Search** | SearXNG (Docker) | Meta-search without API keys | ₹0 |
| **Frontend** | Next.js 16 + Tailwind | Bento dashboard, review UI | ₹0 |
| **Email** | Resend (free tier) | Transactional dispatch | ₹0 (3,000/mo) |
| **Cache/Queue** | SQLite (Pi) | Local buffer before Supabase sync | ₹0 |

---

## 4. Hardware Allocation Strategy

### 4.1 Raspberry Pi 4/5 — The Heartbeat
**Role:** 24/7 ingestion, lightweight filtering, SearXNG hosting.

**Runs:**
- SearXNG Docker container (`:8080`)
- Scout Node (Python cron every 4 hours)
- SQLite local cache
- Supabase sync agent (pushes new leads to cloud)

**Does NOT run:**
- LLM inference (too slow, too hot)
- Mem0 (Chroma is too heavy)
- Next.js dev server

**Pi Specs Minimum:**
- 4GB RAM (8GB preferred)
- 64GB SD card (or USB SSD)
- Ethernet connection (WiFi acceptable but less reliable)

### 4.2 Lenovo LOQ — The Muscle
**Role:** Daily batch processing, heavy reasoning, memory consolidation.

**Runs:**
- Ollama (DeepSeek R1 7B, Qwen 2.5 7B, nomic-embed-text)
- LangGraph batch processor
- Gemini SDK calls (Filter + Pitch)
- Mem0 (Chroma vector store)
- Next.js dev server (during development)

**Daily Batch Schedule:**
```
06:00 AM — Pull "new" and "qualified" leads from Supabase
06:15 AM — Run Analyst (Gemini 2.0 Flash) → Pain Hypotheses
06:45 AM — Run Researcher (Ghost) → Enrichment
07:15 AM — Run Strategist (Gemini 3 Flash) → Pitch Drafts
07:45 AM — Run Critic (DeepSeek R1) → Reflection Loop
08:15 AM — Push approved pitches to Supabase
08:30 AM — Memory consolidation (Mem0 learns from yesterday's data)
```

### 4.3 Why This Split?
| Task | Pi Time | LOQ Time | Winner |
|------|---------|----------|--------|
| HTTP requests (Greenhouse) | Fast | Fast | Pi (always on) |
| SearXNG query | Moderate | Moderate | Pi (local) |
| Gemini API call | Impossible | Fast | LOQ (batch) |
| DeepSeek R1 7B | 5+ min | 15 sec | LOQ (GPU) |
| Chroma vector search | Crashes | Fast | LOQ (RAM/GPU) |

---

## 5. Three-Layer Memory Architecture

LLMs are stateless. Signal Scout uses a persistent memory stack so the agent learns from every pitch, rejection, and reply.

### 5.1 Layer 1: Episodic Memory (Supabase)
**What:** Every lead, pitch, and outcome is a structured record.
**Why:** Prevents duplicate pitching. Enables analytics. Powers the dashboard.

**Schema:** See Section 9.

**Key Queries:**
```sql
-- Prevent duplicate: Have we pitched this company in the last 90 days?
SELECT * FROM leads 
WHERE company_domain = 'razorpay.com' 
  AND status = 'approved' 
  AND discovered_at > NOW() - INTERVAL '90 days';

-- What subject lines got replies?
SELECT pitch_subject, COUNT(*) as replies 
FROM leads 
WHERE response_received = true 
GROUP BY pitch_subject 
ORDER BY replies DESC;
```

### 5.2 Layer 2: Semantic Memory (Supabase pgvector)
**What:** Vector embeddings of job descriptions, pain hypotheses, and approved pitches.
**Why:** Find "similar leads" without keyword matching. Avoid redundant angles.

**Implementation:**
```sql
-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Table for embeddings
CREATE TABLE lead_embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id INTEGER REFERENCES leads(id),
    content TEXT, -- the JD or pitch
    embedding VECTOR(768), -- nomic-embed-text dimension
    created_at TIMESTAMP DEFAULT NOW()
);

-- Similarity search
SELECT lead_id, 1 - (embedding <=> query_embedding) AS similarity
FROM lead_embeddings
WHERE 1 - (embedding <=> query_embedding) > 0.85;
```

### 5.3 Layer 3: Agent Memory (Mem0)
**What:** Unstructured learnings, patterns, tone preferences, strategic insights.
**Why:** The agent gets smarter. It remembers that "Pune founders prefer Hindi-English mixed openings" or "YC companies respond to aggressive tones."

**Mem0 Config (runs on LOQ):**
```python
from mem0 import Memory

m = Memory(config={
    "vector_store": {
        "provider": "chroma",
        "config": {
            "collection_name": "ak0121_memory",
            "path": "./mem0_db"
        }
    },
    "llm": {
        "provider": "ollama",
        "config": {
            "model": "qwen2.5:7b",
            "api_base": "http://localhost:11434"
        }
    },
    "embedder": {
        "provider": "ollama",
        "config": {
            "model": "nomic-embed-text",
            "api_base": "http://localhost:11434"
        }
    }
})

# Store a strategic insight
m.add(
    "Pitches mentioning 'Salesforce-to-Excel reconciliation' to Pune SaaS companies have a 40% reply rate. Use this angle aggressively.",
    user_id="ak0121_strategy",
    metadata={"type": "pattern", "confidence": 0.4, "sample_size": 10}
)

# Retrieve before pitching a new lead
memories = m.search(
    "This company uses Salesforce and manual Excel work in Pune",
    user_id="ak0121_strategy",
    limit=3
)
# Inject memories into the Strategist prompt
```

### 5.4 Memory Rollout Timeline
| Week | Layer | Status |
|------|-------|--------|
| 1 | Episodic (Supabase) | Required from Day 1 |
| 2 | Semantic (pgvector) | Add after first 50 leads |
| 3 | Agent (Mem0) | Add when you have 20+ pitch interactions |

---

## 6. The Scout Node (Multi-Source Ingestion)

### 6.1 Philosophy
The Scout looks for **Growth Anomalies**, not just keywords. A Series A funding announcement + a new SDR hiring post = a company about to hit an operational wall.

### 6.2 Source Configuration

#### Tier 1: Structured JSON (Primary)
```python
GREENHOUSE_TARGETS = [
    # India / India-Remote
    "razorpay", "groww", "zerodha", "phonepe", "cred",
    "sliceit", "upstox", "unacademy", "vedantu", "leapfinance",
    "bharatpe", "pinelabs", "chargebee", "freshworks", "zoho",
    # Global Remote-Friendly
    "stripe", "notion", "linear", "vercel", "figma", "loom",
    "retool", "mercury", "brex", "ramp", "webflow", "framer",
    "supabase", "planetscale", "resend", "calcom", "replicate"
]

def scout_greenhouse(company: str):
    url = f"https://boards.greenhouse.io/{company}.json"
    r = requests.get(url, timeout=15, headers={"User-Agent": "SignalScout/1.0"})
    if r.status_code == 200:
        return r.json().get("jobs", [])
    return []
```

#### Tier 2: RSS Feeds (Lightweight)
```python
RSS_FEEDS = [
    "https://weworkremotely.com/remote-jobs.rss",
    "https://jobicy.com/feed/",
    # Add India-specific if available
]

def scout_rss():
    for feed in RSS_FEEDS:
        fp = feedparser.parse(feed)
        for entry in fp.entries:
            yield {
                "source": "rss",
                "title": entry.title,
                "url": entry.link,
                "description": entry.get("summary", ""),
                "company": entry.title.split(":")[0] if ":" in entry.title else "Unknown"
            }
```

#### Tier 3: SearXNG Dorks (Discovery)
```python
SEARXNG_URL = "http://localhost:8080/search"

SEARXNG_DORKS = [
    'site:boards.greenhouse.io ("Data Entry" OR "Operations Associate" OR "Junior Analyst" OR "Manual Tester" OR "SDR" OR "Sales Development")',
    'site:jobs.lever.co ("Repetitive" OR "Data Processing" OR "Copy Paste" OR "Spreadsheet" OR "CSV" OR "Manual")',
    'site:jobs.ashbyhq.com ("Operations" OR "Automation" OR "Back Office" OR "Administrative" OR "Data")',
    'site:*.com intitle:"careers" ("hiring" OR "join us") ("data entry" OR "manual" OR "operations" OR "reconciliation") filetype:pdf',
    'site:boards.greenhouse.io ("Pune" OR "Bangalore" OR "Mumbai" OR "Hyderabad" OR "Remote India") ("Operations" OR "Analyst" OR "SDR" OR "Data")',
    'site:jobs.lever.co ("Pune" OR "Bangalore") ("Operations" OR "Data" OR "Automation")',
]

def scout_searxng():
    for dork in SEARXNG_DORKS:
        r = requests.get(SEARXNG_URL, params={
            "q": dork, "format": "json", "language": "en"
        }, timeout=30)
        if r.status_code == 200:
            for res in r.json().get("results", []):
                yield {
                    "source": "searxng",
                    "title": res["title"],
                    "url": res["url"],
                    "description": res.get("content", "")
                }
        time.sleep(2)
```

#### Tier 4: Hacker News "Who is Hiring"
```python
def scout_hn_hiring():
    # Algolia HN Search — free, no auth
    url = "https://hn.algolia.com/api/v1/search_by_date"
    params = {
        "query": "Who is hiring",
        "tags": "story",
        "hitsPerPage": 5
    }
    r = requests.get(url, params=params, timeout=15)
    for hit in r.json().get("hits", []):
        if "who is hiring" in hit["title"].lower():
            story_id = hit["objectID"]
            # Fetch top-level comments (job posts)
            comments = requests.get(
                f"https://hn.algolia.com/api/v1/search",
                params={"tags": f"comment,story_{story_id}", "hitsPerPage": 1000}
            ).json()
            for c in comments.get("hits", []):
                yield {
                    "source": "hn_hiring",
                    "title": c["author"], # Usually company name or poster
                    "description": c["text"],
                    "url": f"https://news.ycombinator.com/item?id={c['objectID']}"
                }
```

#### Tier 5: India-Specific & Funding Signals
```python
def scout_wellfound():
    # Scrape public listing pages
    # Wellfound does not have a public API, but listings are public HTML
    pass

def scout_funding_news():
    # Monitor Entrackr, Inc42, YourStory RSS
    feeds = [
        "https://entrackr.com/feed",  # Verify actual RSS URL
        "https://inc42.com/feed",
    ]
    for feed in feeds:
        fp = feedparser.parse(feed)
        for entry in fp.entries:
            if any(x in entry.title.lower() for x in ["funding", "raises", "series a", "seed"]):
                yield {
                    "source": "funding_news",
                    "company": extract_company_from_title(entry.title),
                    "title": entry.title,
                    "url": entry.link,
                    "description": entry.summary
                }
```

### 6.3 Pre-Filter: Pain Scoring
Before any LLM call, run fast regex scoring:

```python
PAIN_KEYWORDS = {
    "data entry": 2, "manual": 2, "repetitive": 2, "spreadsheet": 2,
    "csv": 2, "reconciliation": 2, "sdr": 2, "outbound": 2,
    "list building": 2, "copy paste": 2, "operations": 2,
    "back office": 2, "data processing": 2, "administrative": 2,
    "copying data": 2, "moving data": 2, "manual process": 2,
    "tedious": 2, "time-consuming": 2, "error-prone": 2,
    "routine": 2, "clerical": 2
}

FRUSTRATION_SIGNALS = ["boring", "tedious", "time-consuming", "error-prone", "drudgery"]

def score_pain(text: str) -> tuple[int, list[str]]:
    text_lower = text.lower()
    score = 0
    hits = []
    for kw, points in PAIN_KEYWORDS.items():
        if kw in text_lower:
            score += points
            hits.append(kw)
    for f in FRUSTRATION_SIGNALS:
        if f in text_lower:
            score += 1
            hits.append(f)
    return min(score, 10), hits
```

**Rule:** Score >= 4 → Send to Analyst Node. Score < 4 → Reject immediately.

---

## 7. The Analyst Node (Brain-1 / Pain Hypothesis)

### 7.1 Purpose
Replace the 1-10 automatibility score with a **Pain Hypothesis** — a narrative inference about why the company is hiring and what operational bottleneck they face.

### 7.2 Model: Gemini 2.0 Flash
- **Why:** 6.4x cheaper than Gemini 3 Flash. High FACTS grounding (83.6%) for tech stack extraction.
- **Quota allocation:** 70% of daily budget goes here (volume filtering).

### 7.3 Prompt Template

```
You are an operations analyst at a top-tier automation consultancy.

COMPANY: {company}
JOB TITLE: {title}
JOB DESCRIPTION:
{description}

TASK: Generate a "Pain Hypothesis" — a 2-sentence inference about the operational bottleneck this hiring implies.

RULES:
1. Do not summarize the JD. Infer the *underlying business problem*.
2. Identify the specific manual process they are trying to scale with human labor.
3. Name the tools mentioned (CRM, spreadsheets, databases, etc.).
4. Estimate the "automation ROI" (hours saved per week if automated).
5. Be specific. "They are hiring SDRs because they manually scrape LinkedIn" is better than "They need sales help."

OUTPUT FORMAT (strict JSON):
{
  "pain_hypothesis": "2-sentence inference",
  "primary_process": "The manual process being scaled",
  "tech_stack": ["tool1", "tool2"],
  "integration_gaps": ["gap1", "gap2"],
  "estimated_hours_weekly": integer,
  "automatibility_score": 0-10,
  "confidence": 0-10,
  "verdict": "PASS" or "REJECT",
  "reason": "One sentence explaining verdict"
}

PASS if:
- automatibility_score >= 7
- confidence >= 6
- The role involves moving, copying, or reconciling data between systems

REJECT if:
- The role requires strategic thinking, creative work, or relationship building
- The company is clearly looking for senior leadership, not execution
```

### 7.4 Example Output
```json
{
  "pain_hypothesis": "This company is hiring three junior data analysts to manually reconcile daily transaction reports between their payment gateway dashboard and internal Excel trackers. This suggests they lack an automated ETL pipeline between financial systems.",
  "primary_process": "Daily manual reconciliation of transaction data between payment gateway and Excel",
  "tech_stack": ["Excel", "Payment Gateway (unspecified)", "Internal DB"],
  "integration_gaps": ["Payment Gateway ↔ Excel", "No automated ETL"],
  "estimated_hours_weekly": 120,
  "automatibility_score": 9,
  "confidence": 8,
  "verdict": "PASS",
  "reason": "High-volume manual data reconciliation is a textbook automation target."
}
```

---

## 8. The Researcher Node (Ghost / Entity Resolution)

### 8.1 Purpose
Find the decision-maker and their contact channel without scraping LinkedIn or violating ToS.

### 8.2 Methodology

#### Step 1: Derive Domain
```python
def derive_domain(company_name: str, job_url: str) -> str:
    # Try to extract from job URL
    if "greenhouse.io" in job_url:
        # boards.greenhouse.io/{company}
        pass
    elif "lever.co" in job_url:
        # jobs.lever.co/{company}
        pass
    # Fallback: Google search or manual mapping
    return f"{company_name.lower().replace(' ', '')}.com"
```

#### Step 2: Scrape Public Team Pages
```python
TEAM_PATHS = ["/about", "/team", "/leadership", "/company", "/people"]

TARGET_TITLES = [
    "founder", "co-founder", "ceo", "cto", "vp", "vice president",
    "head of", "director", "chief", "president", "gm", "general manager"
]

def find_decision_maker(domain: str) -> dict:
    for path in TEAM_PATHS:
        url = f"https://{domain}{path}"
        r = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            # Look for name + title patterns
            # This is heuristic and site-specific
            # Extract text blocks containing target titles
            text = soup.get_text()
            for title in TARGET_TITLES:
                if title in text.lower():
                    # Extract surrounding context
                    return {"name": "Extracted Name", "title": title, "source": url}
    return {}
```

#### Step 3: Free Enrichment APIs
```python
import requests

def enrich_with_hunter(domain: str) -> dict:
    # Hunter.io free: 25 searches/month
    r = requests.get(
        "https://api.hunter.io/v2/domain-search",
        params={"domain": domain, "api_key": HUNTER_API_KEY},
        timeout=10
    )
    if r.status_code == 200:
        data = r.json()["data"]
        return {
            "pattern": data.get("pattern"),
            "emails": [e["value"] for e in data.get("emails", [])[:3]]
        }
    return {}

def enrich_with_apollo(company_name: str) -> dict:
    # Apollo.io free: 50 credits/month
    # Use their API or web interface
    pass
```

#### Step 4: Pattern Guessing (Fallback)
```python
EMAIL_PATTERNS = [
    "{first}@{domain}",
    "{first}.{last}@{domain}",
    "{first}{last}@{domain}",
    "{f}{last}@{domain}",
    "founder@{domain}",
    "hello@{domain}"
]

def guess_email(name: str, domain: str) -> list[str]:
    parts = name.lower().split()
    first = parts[0]
    last = parts[-1] if len(parts) > 1 else ""
    f = first[0] if first else ""
    guesses = []
    for pattern in EMAIL_PATTERNS:
        email = pattern.format(first=first, last=last, f=f, domain=domain)
        guesses.append(email)
    return list(set(guesses))
```

### 8.3 Output Schema
```json
{
  "decision_maker": {
    "name": "Rahul Sharma",
    "title": "Founder & CEO",
    "confidence": "high",
    "source": "https://company.com/team"
  },
  "email": {
    "primary": "rahul@company.com",
    "alternatives": ["founder@company.com", "hello@company.com"],
    "verification_status": "pattern_guess",
    "source": "hunter_io"
  },
  "company_intel": {
    "domain": "company.com",
    "size_estimate": "10-50",
    "location": "Pune, India",
    "funding_stage": "Series A (from news)"
  }
}
```

---

## 9. The Strategist Node (Brain-3 / Pitch Synthesis)

### 9.1 Purpose
Synthesize a consultative pitch that combines the Pain Hypothesis + Company Context + AK 0121 Solution.

### 9.2 Model: Gemini 3 Flash
- **Why:** Newer (Dec 2025), 64K output limit, better nuance and tone control.
- **Quota allocation:** 20% of daily budget (quality over quantity).

### 9.3 Tone Profiles
The Strategist selects a tone based on company signals:

| Profile | Trigger | Tone |
|---------|---------|------|
| **Aggressive Startup** | YC-backed, recent funding, high-growth language | Direct, metric-driven, "We fix this in 2 weeks" |
| **Helpful Peer** | Mid-size, established, friendly JD language | Collaborative, "We have seen this exact pattern" |
| **Technical Advisor** | Engineering-heavy, complex tech stack | Precise, architecture-focused, "The integration gap is..." |

### 9.4 Prompt Template

```
You are the lead strategist at AK 0121, an automation agency.

RECIPIENT:
- Name: {name}
- Title: {title}
- Company: {company}
- Company Size: {size}
- Location: {location}

CONTEXT:
- Pain Hypothesis: {pain_hypothesis}
- Primary Process: {primary_process}
- Tech Stack: {tech_stack}
- Integration Gaps: {integration_gaps}
- Estimated Hours Saved: {hours} hours/week

TONE PROFILE: {tone_profile}

STRATEGIC INSIGHTS FROM MEMORY:
{relevant_memories}

RULES:
1. Subject line: Reference the specific integration gap or process. No generic subjects.
2. Opening: Quote or paraphrase their hiring signal to prove relevance. Do NOT say "I came across your posting."
3. Body (2-3 sentences max):
   - Sentence 1: Name the pain and the business cost.
   - Sentence 2: Name the automation bridge AK 0121 builds.
   - Sentence 3: Soft call to action (10-minute call).
4. Tone: {tone_description}
5. Length: 100-120 words.
6. No emojis. No exclamation marks. No buzzwords ("leverage", "synergy", "AI-powered").
7. Use "AK 0121" exactly once.

OUTPUT FORMAT:
Subject: [Subject line]

[Body]

Best,
[Your Name]
AK 0121
```

### 9.5 Example Output (Aggressive Startup)
```markdown
Subject: The 120-hour weekly reconciliation bottleneck in your Data Analyst hiring

Your hiring of three junior analysts to manually reconcile payment gateway data with Excel trackers is a scaling anti-pattern. At 40 hours per analyst, you are burning ₹2.4L monthly on work a lightweight ETL pipeline eliminates entirely.

AK 0121 builds payment-to-ledger automation for Pune fintechs. Typical deployment: 10 days. Typical ROI: 85% cost reduction.

Worth 10 minutes on Thursday to see the architecture?

Best,
Arihant
AK 0121
```

---

## 10. The Critic Node (Brain-4 / Reflection)

### 10.1 Purpose
Prevent "AI-slop" from reaching prospects. The Critic reviews the pitch against AK 0121 quality standards.

### 10.2 Model: DeepSeek R1 7B (Ollama on LOQ)
- **Why:** Free, private, reasoning-focused. Rivals Gemini 2.5 Pro on critique tasks.
- **Speed:** ~15 seconds per pitch on LOQ GPU.

### 10.3 Prompt Template

```
You are a senior copy editor and sales strategist. Review this cold email.

PITCH:
{pitch_text}

CONTEXT:
- Recipient: {name}, {title} at {company}
- Pain Hypothesis: {pain_hypothesis}
- Tone Target: {tone_profile}

EVALUATE (0-10 scale):
1. SPECIFICITY: Does it reference a unique detail from the hiring signal?
2. CONSULTATIVE: Does it sound like advice, not a sales pitch?
3. TONE_ALIGNMENT: Does it match the requested tone profile?
4. BREVITY: Is it 100-120 words?
5. VALUE_FIRST: Does the recipient learn something before being asked for a call?
6. CREDIBILITY: Are claims specific and verifiable? No vague superlatives?
7. HUMANITY: Does it sound like a human wrote it? Or does it smell like AI?

REASONING: Think step by step. Identify specific flaws.

OUTPUT (strict JSON):
{
  "overall": "PASS" or "FAIL",
  "average_score": 0-10,
  "dimension_scores": {
    "specificity": 0-10,
    "consultative": 0-10,
    "tone_alignment": 0-10,
    "brevity": 0-10,
    "value_first": 0-10,
    "credibility": 0-10,
    "humanity": 0-10
  },
  "flaws": ["specific flaw 1", "specific flaw 2"],
  "rewrite_suggestion": "One sentence on how to fix the biggest flaw",
  "confidence": 0-10
}

PASS requires:
- average_score >= 7.0
- specificity >= 6
- humanity >= 6
- No more than 1 dimension below 5
```

### 10.4 Decision Logic
- **PASS** → `status: 'approved'` → Push to Supabase → Dashboard
- **FAIL** → `status: 'needs_rewrite'` → Queue for manual edit or discard
- **No automatic loop.** If the Critic fails it, a human must review. This prevents infinite token burn.

---

## 11. The Vault (Supabase Schema)

### 11.1 Core Tables

```sql
-- Leads table
CREATE TABLE leads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Source tracking
    source TEXT NOT NULL,
    source_url TEXT,
    source_id TEXT, -- external ID if available

    -- Company
    company_name TEXT NOT NULL,
    company_domain TEXT,
    company_size_estimate TEXT,
    company_location TEXT,
    company_funding_stage TEXT,

    -- Job
    job_title TEXT NOT NULL,
    job_description TEXT,
    job_url TEXT UNIQUE,
    job_location TEXT,
    job_department TEXT,

    -- Pain analysis
    pain_score_pre INTEGER,
    pain_hypothesis TEXT,
    primary_process TEXT,
    tech_stack TEXT[], -- Postgres array
    integration_gaps TEXT[],
    estimated_hours_weekly INTEGER,
    automatibility_score INTEGER,
    analyst_confidence INTEGER,
    analyst_verdict TEXT,

    -- Enrichment
    decision_maker_name TEXT,
    decision_maker_title TEXT,
    decision_maker_confidence TEXT,
    email_primary TEXT,
    email_alternatives TEXT[],
    email_verification_status TEXT,
    enrichment_source TEXT,

    -- Pitch
    tone_profile TEXT,
    pitch_subject TEXT,
    pitch_body TEXT,
    pitch_word_count INTEGER,

    -- Critic
    critic_average_score NUMERIC(3,1),
    critic_dimension_scores JSONB,
    critic_flaws TEXT[],
    critic_rewrite_suggestion TEXT,

    -- State machine
    status TEXT DEFAULT 'new',
    -- new -> discovered
    -- discovered -> analyzed (Analyst done)
    -- analyzed -> enriched (Ghost done)
    -- enriched -> pitched (Strategist done)
    -- pitched -> approved (Critic passed)
    -- pitched -> needs_rewrite (Critic failed)
    -- approved -> sent (Face dispatched)
    -- approved -> rejected (Face rejected)
    -- rejected -> (any stage)

    -- Metadata
    discovered_at TIMESTAMP DEFAULT NOW(),
    analyzed_at TIMESTAMP,
    enriched_at TIMESTAMP,
    pitched_at TIMESTAMP,
    approved_at TIMESTAMP,
    sent_at TIMESTAMP,
    response_received BOOLEAN DEFAULT FALSE,
    response_type TEXT, -- 'reply', 'bounce', 'unsubscribe'

    -- Ownership
    assigned_to TEXT DEFAULT 'ak0121',
    tags TEXT[]
);

-- Create indexes for performance
CREATE INDEX idx_leads_status ON leads(status);
CREATE INDEX idx_leads_company ON leads(company_domain);
CREATE INDEX idx_leads_discovered ON leads(discovered_at DESC);
CREATE INDEX idx_leads_source ON leads(source);

-- Daily stats
CREATE TABLE daily_stats (
    date DATE PRIMARY KEY,
    discovered INTEGER DEFAULT 0,
    analyzed INTEGER DEFAULT 0,
    enriched INTEGER DEFAULT 0,
    pitched INTEGER DEFAULT 0,
    approved INTEGER DEFAULT 0,
    rejected INTEGER DEFAULT 0,
    sent INTEGER DEFAULT 0,
    responses INTEGER DEFAULT 0,
    api_calls_gemini INTEGER DEFAULT 0,
    api_calls_ollama INTEGER DEFAULT 0,
    api_calls_hunter INTEGER DEFAULT 0,
    api_calls_apollo INTEGER DEFAULT 0
);

-- Source health monitoring
CREATE TABLE source_health (
    source TEXT PRIMARY KEY,
    last_check TIMESTAMP,
    jobs_found INTEGER DEFAULT 0,
    jobs_qualified INTEGER DEFAULT 0,
    avg_response_ms INTEGER,
    errors INTEGER DEFAULT 0,
    error_last TEXT,
    is_healthy BOOLEAN DEFAULT TRUE
);

-- Memory log (for audit trail)
CREATE TABLE memory_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id UUID REFERENCES leads(id),
    memory_type TEXT, -- 'episodic', 'semantic', 'agent'
    content TEXT,
    embedding VECTOR(768),
    created_at TIMESTAMP DEFAULT NOW()
);
```

### 11.2 Row Level Security (RLS)
```sql
-- Enable RLS
ALTER TABLE leads ENABLE ROW LEVEL SECURITY;

-- Policy: Users can only see their own leads
CREATE POLICY "Users can view own leads" ON leads
    FOR SELECT USING (auth.uid()::text = assigned_to);

-- Policy: Allow service role full access
CREATE POLICY "Service role has full access" ON leads
    FOR ALL USING (auth.role() = 'service_role');
```

---

## 12. The Face (Next.js 16 Dashboard)

### 12.1 Design Philosophy: Bento Grid
Each lead is a card in a responsive Bento grid. Information density is high but scannable.

### 12.2 Dashboard Layout
```
┌─────────────────────────────────────────────────────────┐
│  Signal Scout 2.0        [Filter: All | New | Approved] │
├─────────────────────────────────────────────────────────┤
│  ┌────────────┐  ┌────────────┐  ┌────────────┐        │
│  │ Stats      │  │ Queue      │  │ Memory     │        │
│  │ 47 Leads   │  │ 12 Pending │  │ 3 Patterns │        │
│  │ 8 Approved │  │ Review     │  │ Learned    │        │
│  └────────────┘  └────────────┘  └────────────┘        │
├─────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────┐    │
│  │ LEAD CARD: Razorpay                             │    │
│  │ ┌──────────┐                                    │    │
│  │ │ Pain     │ "Hiring 3 SDRs for manual lead     │    │
│  │ │ Score: 9 │  scraping. No automation infra."   │    │
│  │ └──────────┘                                    │    │
│  │ ┌──────────┐  ┌──────────┐  ┌──────────┐       │    │
│  │ │ Tech     │  │ Contact  │  │ Pitch    │       │    │
│  │ │ Stack    │  │ Rahul    │  │ Preview  │       │    │
│  │ │ SF,Excel │  │ Founder  │  │ "The..." │       │    │
│  │ └──────────┘  └──────────┘  └──────────┘       │    │
│  │ [Edit Pitch] [Send via Resend] [Reject] [Skip]  │    │
│  └─────────────────────────────────────────────────┘    │
│  ... more cards ...                                     │
└─────────────────────────────────────────────────────────┘
```

### 12.3 Key Features
- **Real-time sync:** Supabase Realtime pushes new leads instantly.
- **One-Click Dispatch:** "Send via Resend" button. No automated blasting.
- **Pitch Editor:** Inline Markdown editor for human tweaks.
- **Memory Panel:** Shows relevant Mem0 insights for the current lead.
- **Analytics:** Response rate, approval rate, source health.

### 12.4 Tech Stack
- **Framework:** Next.js 16 (App Router)
- **Styling:** Tailwind CSS + shadcn/ui
- **State:** Zustand (client) + Supabase (server)
- **Auth:** Supabase Auth
- **Charts:** Recharts or Tremor

---

## 13. Infrastructure & Deployment

### 13.1 Docker Compose (Pi + LOQ)

```yaml
# docker-compose.yml — runs on Raspberry Pi
version: '3.8'

services:
  searxng:
    image: searxng/searxng:latest
    container_name: searxng
    ports:
      - "8080:8080"
    volumes:
      - ./searxng:/etc/searxng
    restart: unless-stopped

  scout:
    build: ./scout
    container_name: signal-scout
    depends_on:
      - searxng
    environment:
      - SEARXNG_URL=http://searxng:8080
      - SUPABASE_URL=${SUPABASE_URL}
      - SUPABASE_KEY=${SUPABASE_KEY}
      - GEMINI_API_KEY=${GEMINI_API_KEY}
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
    restart: unless-stopped
    # Run on cron schedule via host crontab or use ofelia
```

### 13.2 Ollama Setup (LOQ)
```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull models
ollama pull deepseek-r1:7b
ollama pull qwen2.5:7b
ollama pull nomic-embed-text

# Verify
ollama list

# Run API server (binds to localhost:11434)
ollama serve
```

### 13.3 Pi Cron Schedule
```bash
# Edit crontab
crontab -e

# Every 4 hours: Run Scout
0 */4 * * * cd /home/pi/signal-scout && docker-compose run --rm scout python scout.py >> logs/scout.log 2>&1

# Every hour: Sync SQLite to Supabase
0 * * * * cd /home/pi/signal-scout && docker-compose run --rm scout python sync_to_supabase.py >> logs/sync.log 2>&1

# Daily at 5 AM: Health check
0 5 * * * cd /home/pi/signal-scout && docker-compose ps | grep -q "Up" || docker-compose up -d
```

### 13.4 LOQ Daily Batch Script
```bash
#!/bin/bash
# daily_batch.sh — runs on Lenovo LOQ at 6 AM

cd ~/signal-scout-batch
source venv/bin/activate

echo "[$(date)] Starting daily batch..."

# 1. Pull new leads from Supabase
python pull_leads.py

# 2. Run Analyst (Gemini 2.0 Flash)
python nodes/analyst.py

# 3. Run Researcher (Ghost)
python nodes/researcher.py

# 4. Run Strategist (Gemini 3 Flash)
python nodes/strategist.py

# 5. Run Critic (DeepSeek R1 via Ollama)
python nodes/critic.py

# 6. Push approved to Supabase
python push_approved.py

# 7. Memory consolidation
python memory/consolidate.py

echo "[$(date)] Batch complete."
```

---

## 14. Resource Limits & Cost Control

### 14.1 Free Tier Budget

| Service | Free Quota | Daily Allocation | Monthly Total |
|---------|-----------|------------------|---------------|
| **Gemini 2.0 Flash** | 1,500 req/day | 1,000 (Analyst) | 30,000 |
| **Gemini 3 Flash** | 1,500 req/day | 300 (Strategist) | 9,000 |
| **Hunter.io** | 25 searches/mo | 1/day | 25 |
| **Apollo.io** | 50 credits/mo | 2/day | 50 |
| **Resend** | 3,000 emails/mo | 10/day | 300 |
| **Supabase** | 500K req/day | ~2,000 | 60,000 |
| **Ollama (Local)** | Unlimited | ~500 | Unlimited |
| **SearXNG** | Unlimited | ~100 | Unlimited |

### 14.2 Cost Control Rules
1. **Pre-filter ruthlessly.** 80% of jobs must die at the regex stage before touching Gemini.
2. **Batch on LOQ, not Pi.** The Pi only scrapes and caches. All LLM calls happen in the daily batch.
3. **No retry loops.** One Analyst call. One Strategist call. One Critic call. If any fail, flag for human.
4. **Prioritize Greenhouse.** 60% of quota to Greenhouse targets. 20% to RSS. 20% to SearXNG.
5. **Mem0 only after Week 3.** Before 20 interactions, there is nothing meaningful to remember.

---

## 15. Compliance & Ethics

### 15.1 Hard Rules
- ❌ **No LinkedIn scraping.** Not via OpenClaw. Not via Selenium. Not via API abuse.
- ❌ **No Twitter/X scraping.** Blocked, expensive, legally hostile.
- ❌ **No personal OSINT.** No Maigret. No finding family photos. No "personal hooks."
- ❌ **No automated email blasting.** Every pitch is reviewed in the dashboard before send.
- ❌ **No storage of sensitive PII.** Names and business emails only. No phone numbers, addresses, or personal data.

### 15.2 What We Do
- ✅ Read public job postings (explicitly published for discovery).
- ✅ Scrape public `/about` and `/team` pages.
- ✅ Use free-tier B2B enrichment (Hunter, Apollo).
- ✅ Generate personalized pitches based on stated business needs.
- ✅ Store data in Supabase with RLS.
- ✅ Honor rate limits (max 1 req/sec per domain).
- ✅ Include unsubscribe in every email.

### 15.3 Email Sending Guidelines
- **Domain:** Use a dedicated domain (e.g., `ak0121.io`) separate from your main business.
- **Warmup:** Week 1: 2-3 emails/day. Week 2: 3-5. Week 3: 5-7. Week 4+: 10.
- **Verification:** Verify emails via Hunter pattern or SMTP check before sending.
- **Unsubscribe:** Clear one-click unsubscribe in every footer.
- **Throttle:** Max 10 cold emails/day. Never more than 50/week.

---

## 16. Build Timeline

### Week 1: Infrastructure (Architect)
- [ ] Set up Raspberry Pi with Docker + SearXNG
- [ ] Initialize Supabase project with schema
- [ ] Set up Next.js 16 project with shadcn/ui
- [ ] Build Scout Node (Greenhouse + RSS)
- [ ] Implement pre-filter scoring
- [ ] Test end-to-end: Scout → SQLite → Supabase sync

### Week 2: Intelligence (Strategist)
- [ ] Integrate Gemini SDK (2.0 Flash for Analyst)
- [ ] Build Analyst Node with Pain Hypothesis output
- [ ] Build Researcher Node (Ghost) with team page scraping
- [ ] Integrate Hunter.io + Apollo free tiers
- [ ] Build Next.js Bento dashboard (read-only)
- [ ] Define 3 Tone Profiles for Strategist

### Week 3: Synthesis & Memory
- [ ] Integrate Gemini 3 Flash for Strategist Node
- [ ] Build Critic Node with DeepSeek R1 (Ollama)
- [ ] Add Mem0 (self-hosted) for agent memory
- [ ] Add pgvector for semantic search
- [ ] Build "Send via Resend" button in dashboard
- [ ] Run first 50 leads through full pipeline
- [ ] Record "Build in Public" Loom video

### Week 4: Optimization
- [ ] Analyze first 50 results (response rates, false positives)
- [ ] Refine Pain Keywords based on data
- [ ] Add India-specific sources (Instahyre, Hirist)
- [ ] Add HN monthly harvester
- [ ] Add funding news scraper (Entrackr/Inc42)
- [ ] Optimize prompts based on Critic feedback

### Week 5: Scale & Polish
- [ ] Add SearXNG dorks to Scout
- [ ] Add Wellfound + YC source scraping
- [ ] Build analytics charts (response rate, source quality)
- [ ] Add memory viewer to dashboard
- [ ] Document system for "Build in Public" content
- [ ] Plan paid tier (if free quota proves viable)

---

## 17. Success Metrics

| Metric | Week 2 Target | Week 4 Target | Week 8 Target |
|--------|--------------|---------------|---------------|
| Jobs Discovered/Day | 30 | 75 | 100 |
| Qualification Rate | 10% | 18% | 20% |
| Enrichment Rate | 50% | 70% | 80% |
| Pitch Approval Rate | 60% | 75% | 80% |
| Emails Sent/Week | 10 | 35 | 50 |
| Response Rate | — | 5% | 8% |
| Meeting Booked Rate | — | 1% | 2% |
| API Cost | ₹0 | ₹0 | ₹0 |

---

## 18. Failure Modes & Mitigation

| Failure | Cause | Mitigation |
|---------|-------|------------|
| **Greenhouse blocks IP** | Too many requests | 2-second delay between requests. Rotate User-Agent. |
| **Gemini quota exhausted** | 1,500/day limit | Fall back to Ollama Qwen 2.5 7B for Analyst. |
| **SearXNG returns empty** | Instance blocked by search engines | Restart container. Check instance health. Rotate SearXNG settings. |
| **DeepSeek R1 too slow** | Pi cannot run 7B | Run only on LOQ. Use 1.5B on Pi for emergency only. |
| **False positives** | Analyst over-scores | Tighten prompt. Add human review gate for first 100. |
| **No decision maker found** | Stealth company / no team page | Skip and log. Do not waste cycles. Use pattern guess as last resort. |
| **Email bounces** | Pattern guess wrong | Verify via Hunter before send. Track bounce rate. Adjust patterns. |
| **Mem0 crashes** | Chroma too heavy for Pi | Run Mem0 ONLY on LOQ. Pi does not touch vector DBs. |
| **Supabase rate limit** | 500K req/day exceeded | Batch operations. Use SQLite as buffer. Sync hourly, not per-lead. |

---

## 19. Appendices

### A. Complete SearXNG Dork Library
```python
SEARXNG_DORKS = [
    # Greenhouse — General pain roles
    'site:boards.greenhouse.io ("Data Entry" OR "Operations Associate" OR "Junior Analyst" OR "Manual Tester" OR "SDR" OR "Sales Development" OR "Business Development Representative")',

    # Lever — Process pain
    'site:jobs.lever.co ("Repetitive" OR "Data Processing" OR "Copy Paste" OR "Spreadsheet" OR "CSV" OR "Manual" OR "Reconciliation")',

    # Ashby — Modern startups
    'site:jobs.ashbyhq.com ("Operations" OR "Automation" OR "Back Office" OR "Administrative" OR "Data" OR "Finance Operations")',

    # PDF Job Descriptions
    'site:*.com intitle:"careers" ("hiring" OR "join us") ("data entry" OR "manual" OR "operations" OR "reconciliation" OR "sdr") filetype:pdf',

    # India-specific Greenhouse
    'site:boards.greenhouse.io ("Pune" OR "Bangalore" OR "Mumbai" OR "Hyderabad" OR "Chennai" OR "Remote India") ("Operations" OR "Analyst" OR "SDR" OR "Data" OR "Finance")',

    # India-specific Lever
    'site:jobs.lever.co ("Pune" OR "Bangalore" OR "Mumbai") ("Operations" OR "Data" OR "Automation" OR "SDR")',

    # Remote-first companies
    'site:boards.greenhouse.io ("Remote" OR "Worldwide" OR "Anywhere") ("Operations" OR "Data" OR "Automation" OR "SDR")',

    # High-growth signals
    'site:jobs.lever.co ("Scale" OR "Growth" OR "Expand" OR "Ramp") ("Operations" OR "Data" OR "Sales" OR "SDR")',

    # Specific pain patterns
    'site:boards.greenhouse.io ("Copying" OR "Transferring" OR "Moving" OR "Extracting") ("Data" OR "Records" OR "Information")',

    # Fintech-specific (Pune hub)
    'site:boards.greenhouse.io ("Pune" OR "Bangalore") ("Reconciliation" OR "Settlement" OR "Transaction" OR "Payment Operations")'
]
```

### B. Target Company Seed Lists

#### India Fintech / SaaS
```python
INDIA_TARGETS = [
    "razorpay", "groww", "zerodha", "phonepe", "cred", "sliceit",
    "upstox", "bharatpe", "pinelabs", "chargebee", "juspay",
    "lazypay", "navi", "fi", "jupiter", "plum", "pazcare",
    "leapfinance", "stilt", "refyne", "kreditbee"
]
```

#### Global Remote-Friendly
```python
GLOBAL_TARGETS = [
    "stripe", "notion", "linear", "vercel", "figma", "loom",
    "retool", "mercury", "brex", "ramp", "webflow", "framer",
    "supabase", "planetscale", "resend", "calcom", "replicate",
    "modal", "flyio", "render", "railway", "vercel"
]
```

#### YC Companies (High Intent)
```python
YC_TARGETS = [
    # Update via YC directory scraping
    # Focus on recent batches (W25, S24)
]
```

### C. Tone Profile Definitions

```python
TONE_PROFILES = {
    "aggressive_startup": {
        "description": "Direct, metric-driven, confident. Assumes the prospect wants to move fast.",
        "opening_style": "Name the cost immediately.",
        "cta_style": "Specific time suggestion. No softening.",
        "example_phrase": "You are burning ₹2.4L monthly on work a pipeline eliminates in 10 days."
    },
    "helpful_peer": {
        "description": "Collaborative, experienced, advisory. Positions AK 0121 as a peer who has solved this before.",
        "opening_style": "Acknowledge the challenge with empathy.",
        "cta_style": "Open-ended offer to share architecture.",
        "example_phrase": "We have seen this exact pattern at three Pune fintechs. The fix is usually a lightweight integration layer."
    },
    "technical_advisor": {
        "description": "Precise, architecture-focused, no fluff. Appeals to CTOs and technical founders.",
        "opening_style": "Name the integration gap in technical terms.",
        "cta_style": "Offer a technical architecture review.",
        "example_phrase": "The Salesforce-to-ledger gap you are filling with manual analysts is solvable via a webhook-driven ETL with idempotent writes."
    }
}
```

### D. Email Domain Warmup Schedule
| Week | Daily Volume | Total Weekly | Notes |
|------|-------------|--------------|-------|
| 1 | 2-3 | 15-20 | Send to warm contacts only. No cold. |
| 2 | 3-5 | 20-35 | Mix warm + low-risk cold (known companies). |
| 3 | 5-7 | 35-50 | Expand to mid-risk targets. |
| 4 | 7-10 | 50-70 | Full operation. Monitor bounce rate. |
| 5+ | 10 | 70 | Steady state. Never exceed 10/day. |

### E. LangGraph State Definition
```python
from typing import TypedDict, Annotated
from langgraph.graph.message import add_messages

class ScoutState(TypedDict):
    # Input
    raw_job: dict

    # Analyst output
    pain_hypothesis: str
    automatibility_score: int
    analyst_verdict: str

    # Researcher output
    decision_maker: dict
    company_intel: dict

    # Strategist output
    tone_profile: str
    pitch_subject: str
    pitch_body: str

    # Critic output
    critic_verdict: str
    critic_score: float
    critic_flaws: list[str]

    # Final
    status: str  # approved, rejected, needs_rewrite
    messages: Annotated[list, add_messages]
```

---

## 20. Quick Start Checklist

- [ ] Raspberry Pi flashed with Raspberry Pi OS Lite (64-bit)
- [ ] Docker + Docker Compose installed on Pi
- [ ] SearXNG container running on `localhost:8080`
- [ ] Supabase project created, schema migrated
- [ ] Next.js 16 project initialized with shadcn/ui
- [ ] Google AI Studio API key (Gemini 2.0 + 3 Flash)
- [ ] Hunter.io free account + API key
- [ ] Apollo.io free account + API key
- [ ] Resend free account + API key
- [ ] Ollama installed on LOQ with deepseek-r1:7b, qwen2.5:7b, nomic-embed-text
- [ ] Python 3.11+ venv on both Pi and LOQ
- [ ] First Scout test run completes without errors
- [ ] First lead appears in Supabase dashboard
- [ ] First pitch manually reviewed and sent

---

**Document Owner:** AK 0121  
**Authors:** Arihant (Strategist) + Kundan (Architect)  
**Next Review:** After first 50 approved pitches  
**Status:** Production Ready — Build Phase 1
