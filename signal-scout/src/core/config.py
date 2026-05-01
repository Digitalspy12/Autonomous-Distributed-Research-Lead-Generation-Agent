"""
Signal Scout 4.0 — Configuration
Loads settings from .env file using Pydantic Settings.
Pi-migratable: Only SQLITE_PATH changes when moving Scout to Pi.
"""

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Google AI Studio (Gemini 2.5 Flash) ---
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    gemini_enabled: bool = True

    # --- Groq Cloud (Free Tier) ---
    groq_api_key: str = ""
    groq_model_analyst: str = "llama-3.3-70b-versatile"
    groq_model_strategist: str = "llama-3.1-8b-instant"
    groq_enabled: bool = True

    # --- Ollama (Local LLM) ---
    ollama_base_url: str = "http://localhost:11434"
    ollama_model_analyst: str = "qwen3.5:latest"
    ollama_model_critic: str = "qwen3.5:latest"
    ollama_enabled: bool = True
    ollama_timeout_seconds: int = 120

    # --- Enrichment APIs ---
    hunter_api_key: str = ""
    apollo_api_key: str = ""

    # --- Supabase (Cloud Database) ---
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""

    # --- Local Database ---
    sqlite_path: str = "./data/signal_scout.db"

    # --- Rate Limits ---
    scout_interval_hours: int = 4
    gemini_daily_quota: int = 20
    hunter_monthly_quota: int = 25
    apollo_monthly_quota: int = 50
    searxng_daily_quota: int = 20

    # --- Request Settings ---
    request_timeout: int = 15
    rate_limit_delay: float = 1.0  # seconds between requests per domain

    # --- LLM Fallback Behavior ---
    llm_fallback_order: str = "gemini,groq,ollama"  # Comma-separated priority
    skip_on_no_llm: bool = True  # True = halt pipeline, False = queue for manual

    @property
    def sqlite_abs_path(self) -> Path:
        """Resolve SQLite path relative to project root."""
        return Path(self.sqlite_path).resolve()

    @property
    def fallback_order_list(self) -> list[str]:
        """Parse fallback order into list."""
        return [p.strip().lower() for p in self.llm_fallback_order.split(",") if p.strip()]


# --- Singleton ---
_settings: Settings | None = None


def get_settings() -> Settings:
    """Get or create the global settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


# --- Source Configuration ---
# These are separate from Settings because they're static config,
# not secrets. Pi migration: copy this file as-is.

GREENHOUSE_TARGETS = [
    # Pune / Maharashtra / India
    "persistent-systems", "emcure", "bajaj-finserv-health",
    "pubmatic", "druva", "icertis",
    # Global (funded startups)
    "vercel", "notion", "linear", "supabase", "postman",
    "razorpay", "zerodha", "cred", "groww", "meesho",
    "freshworks", "zoho", "chargebee", "browserstack",
]

LEVER_TARGETS = [
    "postman", "netlify", "figma", "samsara",
]

RSS_FEEDS = [
    # Remote-first job boards
    "https://weworkremotely.com/remote-jobs.rss",
    "https://jobicy.com/feed/",
    "https://remoteok.com/remote-jobs.rss",
    "https://remotive.com/remote-jobs/feed",
    # India-specific (Indeed RSS)
    "https://www.indeed.com/rss?q=operations+SDR+data+entry&l=Pune",
    "https://www.indeed.com/rss?q=operations+SDR+data+entry&l=Bangalore",
    "https://www.indeed.com/rss?q=operations+SDR+data+entry&l=Mumbai",
    # Funding signals (proactive targeting)
    "https://inc42.com/feed/",
    "https://yourstory.com/feed",
    "https://techcrunch.com/category/startups/feed/",
]

HN_HIRING_API = "https://hn.algolia.com/api/v1/search_by_date?query=Who%20is%20hiring&tags=story"

# Pre-filter keywords with pain scores
# Score < 4 after summing matched keywords → skip (no LLM call)
PAIN_KEYWORDS = {
    "manual": 3, "data entry": 4, "repetitive": 3, "operations": 2,
    "SDR": 4, "BDR": 4, "lead generation": 4, "cold calling": 3,
    "spreadsheet": 3, "reconciliation": 3, "reporting": 2,
    "tedious": 2, "time-consuming": 2, "error-prone": 2,
    "copy paste": 4, "manual process": 4, "data processing": 3,
}

PAIN_SCORE_THRESHOLD = 4

# SearXNG discovery dorks (capped at SEARXNG_DAILY_QUOTA/day)
SEARXNG_DORKS = [
    'site:boards.greenhouse.io ("Data Entry" OR "Operations" OR "SDR")',
    'site:jobs.lever.co ("Manual" OR "Repetitive" OR "Data Processing")',
]

# Team page paths for contact discovery
TEAM_PATHS = ["/about", "/team", "/leadership", "/company", "/people", "/founders"]

# Decision-maker title patterns
DECISION_MAKER_TITLES = [
    "Founder", "Co-Founder", "CEO", "CTO", "COO", "VP",
    "Head of", "Director", "Chief", "Managing Director",
]
