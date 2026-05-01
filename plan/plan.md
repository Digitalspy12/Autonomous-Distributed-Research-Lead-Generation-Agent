# 🎯 Project: Signal Scout (v1.0)
**Autonomous Distributed Research & Lead Generation Agent**

## 1. Project Overview
**Signal Scout** is an agentic AI system designed to operate autonomously for hours to identify "High-Intent" B2B leads. Unlike standard scrapers, it detects **Hiring Signals** (friction), performs deep **OSINT** on decision-makers, and generates **Strategic Automation Pitches**.

### Core Philosophy:
* **Zero Budget:** Utilize free tiers and local hardware to eliminate API costs.
* **Distributed Power:** Split tasks between mobile, edge, and high-performance hardware.
* **Agentic Persistence:** Use stateful graphs to ensure the agent self-corrects and finishes complex objectives.

---

## 2. Hardware Architecture (The Three Tiers)

| Tier | Name | Hardware | Role | Key Responsibility |
| :--- | :--- | :--- | :--- | :--- |
| **1** | **The Ghost** | Android 8.1 (8-Core, 3GB RAM) | **Stealth Gateway** | Bypass bot-detection using Mobile IPs & OpenClaw. |
| **2** | **The Scout** | Raspberry Pi 4B (8GB RAM) | **The Central Hub** | 24/7 Search monitoring, Task Queuing (Redis), and SearXNG. |
| **3** | **The Brain** | Lenovo LOQ (RTX 3050 6GB) | **Reasoning Engine** | Deep OSINT synthesis, LangGraph logic, and Pitch generation. |

---

## 3. Software & Tech Stack

### Intelligence (LLMs)
* **Reasoning (Local):** **Ollama** running **Llama 3.1 8B** or **Qwen-2.5 7B** (Lenovo LOQ).
* **Synthesis (Cloud):** **Gemini 2.0 Flash** (Free Tier via AI Studio) for 1M+ token context analysis.

### Orchestration & Logic
* **Framework:** **LangGraph** (Python).
* **Persistence:** **SQLite** (Saver) to store checkpoints and allow the agent to resume after power/network loss.
* **Communication:** **Tailscale** (Mesh VPN) for secure P2P connection between devices.

### Search & OSINT Tools
* **Search Engine:** **SearXNG** (Self-hosted on Pi via Docker).
* **Person Research:** **Maigret** (CLI) for deep digital footprinting across 3,000+ sites.
* **Web Scraping:** **Crawl4AI** or **Trafilatura** for cleaning messy HTML into Markdown.

### Data Storage
* **Task Queue:** **Redis** (Running on Pi).
* **Final Lead Storage:** **Supabase** (Shared cloud database for Kundan & Arihant).

---

## 4. The Agentic Logic (LangGraph Decisions)

The agent operates as a **State Machine** with the following nodes:

1.  **Lead Discovery (Scout):** Pi pings SearXNG for hiring keywords. Pushes URLs to Redis.
2.  **Filter Node (Brain):** LLM evaluates the job post. 
    * *Decision:* Is this role automatable? (e.g., Data entry, manual SDR work).
    * *Action:* If yes, proceed. If no, delete task.
3.  **Entity Resolution (Ghost):** Phone opens LinkedIn/X to find the specific Founder/VP name.
4.  **Deep OSINT (Brain):** Maigret scan on the founder. Scrapes GitHub/Twitter for "Personal Hooks" (Tech stack, interests).
5.  **Pitch Synthesis (Brain):** Gemini 2.0 combines "Job Pain" + "Founder Interest" + "AK 0121 Tech" into a Markdown pitch.
6.  **Reflection Node:** The agent reviews its own pitch.
    * *Decision:* Is the pitch personalized enough?
    * *Action:* If no, loop back to OSINT for more data. If yes, push to Supabase.

---

## 5. Communication & Networking Map

* **Network:** All devices connected via **Tailscale**.
* **Discovery:** Pi accessible at `http://ak-scout:8080` (SearXNG) and `ak-scout:6379` (Redis).
* **Command Flow:**
    * Laptop (Brain) -> Pi (Redis) -> Pulls Task.
    * Laptop (Brain) -> Phone (OpenClaw) -> Trigger Mobile Scraping.
    * Laptop (Brain) -> Telegram API -> Send notification to users.

---

## 6. Implementation Roadmap

### Phase 1: Infrastructure (The Foundation)
* [ ] Flash **Raspberry Pi OS Lite (64-bit)**.
* [ ] Install **Docker & SearXNG** on Pi.
* [ ] Setup **Tailscale** mesh network on all 3 devices.

### Phase 2: Tooling (The Hands)
* [ ] Build Python wrapper for **Maigret**.
* [ ] Set up **Ollama** on Lenovo LOQ.
* [ ] Configure **OpenClaw** on Android 8.1 for basic mobile navigation.

### Phase 3: The Brain (The Logic)
* [ ] Develop the **LangGraph** state definition.
* [ ] Implement the **Redis** task queue consumer.
* [ ] Create the **Reflection Node** for pitch quality control.

---

## 7. Risks & Mitigation
* **Hardware Failure:** Use **SQLite Checkpoints** to ensure no data loss if the Pi or Laptop restarts.
* **Bot Detection:** Implement "Human Jitter" (random delays) in OpenClaw mobile automation.
* **Maintenance:** Automated health-checks sent to Telegram every 6 hours.
* **Fire Safety:** Implement battery-level monitoring on the old phone to prevent battery swelling.

---

## 8. Final Goal Metrics
* **Autonomy:** Agent must run for **4+ hours** without human intervention.
* **Quality:** 80% of leads generated must have an **Automation Readiness Score** of >7/10.
* **Cost:** Total monthly operational cost must remain **$0.00**.

***
**Owner:** AK 0121 Agency
**Status:** Approved for Implementation