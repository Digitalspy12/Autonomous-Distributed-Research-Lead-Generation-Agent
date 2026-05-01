"""
Signal Scout 4.0 — Pydantic Data Models
Shared between SQLite (local) and Supabase (cloud).
Pi-migratable: These models are used on both Pi and LOQ.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ============================================
# Enums
# ============================================

class JobStatus(str, Enum):
    """Job processing state machine."""
    NEW = "new"
    PRE_FILTERED = "pre_filtered"
    ANALYZED = "analyzed"
    REJECTED = "rejected"
    ENRICHED = "enriched"
    PITCH_WRITTEN = "pitch_written"
    PITCH_APPROVED = "pitch_approved"
    PITCH_REJECTED = "pitch_rejected"
    ERROR = "error"


class AnalystVerdict(str, Enum):
    PASS = "PASS"
    REJECT = "REJECT"


class OutreachStatus(str, Enum):
    NOT_CONTACTED = "not_contacted"
    LINKEDIN_DM_SENT = "linkedin_dm_sent"
    EMAIL_SENT = "email_sent"
    WARM_INTRO = "warm_intro"
    RESPONDED = "responded"
    MEETING_BOOKED = "meeting_booked"
    NOT_INTERESTED = "not_interested"
    ARCHIVED = "archived"


class LinkedInConfidence(str, Enum):
    VERIFIED = "verified"
    INFERRED = "inferred"
    NONE = "none"


class PitchStatus(str, Enum):
    DRAFT = "draft"
    APPROVED = "approved"
    REJECTED = "rejected"
    SENT = "sent"


class CriticVerdict(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"


class ToneProfile(str, Enum):
    DIRECT = "direct"
    CONSULTATIVE = "consultative"
    CURIOUS = "curious"


# ============================================
# Data Models
# ============================================

class Company(BaseModel):
    """Deduplicated company record. Anchor: domain."""
    id: Optional[str] = None
    name: str
    domain: Optional[str] = None
    size_estimate: Optional[str] = None
    location: Optional[str] = None
    funding_stage: Optional[str] = None
    tech_stack: list[str] = Field(default_factory=list)
    industry: Optional[str] = None
    crunchbase_url: Optional[str] = None
    github_url: Optional[str] = None
    linkedin_url: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class RawJob(BaseModel):
    """Raw job posting as discovered by Scout. Minimal fields."""
    title: str
    company_name: str
    job_url: str
    source: str  # 'greenhouse', 'lever', 'rss', 'hn', 'indeed', 'searxng'
    source_url: Optional[str] = None
    description: Optional[str] = None
    location: Optional[str] = None


class Job(BaseModel):
    """Full job record with analyst output."""
    id: Optional[str] = None
    company_id: Optional[str] = None
    source: str
    source_url: Optional[str] = None
    title: str
    description: Optional[str] = None
    job_url: str
    location: Optional[str] = None
    # Analyst output
    pain_hypothesis: Optional[str] = None
    primary_process: Optional[str] = None
    integration_gaps: list[str] = Field(default_factory=list)
    tech_stack_inferred: list[str] = Field(default_factory=list)
    automatibility_score: Optional[int] = None
    analyst_confidence: Optional[int] = None
    analyst_verdict: Optional[str] = None
    # Pre-filter
    pain_keyword_score: int = 0
    # Status machine
    status: str = JobStatus.NEW.value
    discovered_at: Optional[datetime] = None
    analyzed_at: Optional[datetime] = None
    enriched_at: Optional[datetime] = None
    pitch_written_at: Optional[datetime] = None
    pitch_scored_at: Optional[datetime] = None


class AnalystOutput(BaseModel):
    """Structured output from Gemini Analyst node."""
    pain_hypothesis: str
    primary_process: str
    tech_stack: list[str] = Field(default_factory=list)
    integration_gaps: list[str] = Field(default_factory=list)
    automatibility_score: int = Field(ge=0, le=10)
    confidence: int = Field(ge=0, le=10)
    verdict: AnalystVerdict


class Contact(BaseModel):
    """Enriched contact record for a decision-maker."""
    id: Optional[str] = None
    company_id: Optional[str] = None
    job_id: Optional[str] = None
    name: Optional[str] = None
    title: Optional[str] = None
    email_verified: Optional[str] = None
    email_sources: list[str] = Field(default_factory=list)
    linkedin_url: Optional[str] = None
    linkedin_confidence: str = LinkedInConfidence.NONE.value
    manual_research_links: dict = Field(default_factory=dict)
    outreach_ready: bool = False
    outreach_status: str = OutreachStatus.NOT_CONTACTED.value
    outreach_channel: Optional[str] = None
    contacted_at: Optional[datetime] = None
    responded_at: Optional[datetime] = None
    follow_up_at: Optional[datetime] = None
    notes: Optional[str] = None
    created_at: Optional[datetime] = None


class CriticScores(BaseModel):
    """7-dimension pitch scoring from Critic node."""
    specificity: float = Field(ge=0, le=10)
    consultative: float = Field(ge=0, le=10)
    tone: float = Field(ge=0, le=10)
    brevity: float = Field(ge=0, le=10)
    value: float = Field(ge=0, le=10)
    credibility: float = Field(ge=0, le=10)
    humanity: float = Field(ge=0, le=10)

    @property
    def average(self) -> float:
        scores = [
            self.specificity, self.consultative, self.tone,
            self.brevity, self.value, self.credibility, self.humanity,
        ]
        return round(sum(scores) / len(scores), 1)

    @property
    def verdict(self) -> CriticVerdict:
        return CriticVerdict.PASS if self.average >= 7.0 else CriticVerdict.FAIL


class Pitch(BaseModel):
    """AI-generated pitch with critic scores."""
    id: Optional[str] = None
    job_id: Optional[str] = None
    contact_id: Optional[str] = None
    # Strategist output
    subject_line: Optional[str] = None
    pitch_body: Optional[str] = None
    tone_profile: str = ToneProfile.CONSULTATIVE.value
    word_count: Optional[int] = None
    # Critic scores
    score_specificity: Optional[float] = None
    score_consultative: Optional[float] = None
    score_tone: Optional[float] = None
    score_brevity: Optional[float] = None
    score_value: Optional[float] = None
    score_credibility: Optional[float] = None
    score_humanity: Optional[float] = None
    score_average: Optional[float] = None
    critic_verdict: Optional[str] = None
    critic_feedback: Optional[str] = None
    # Status
    status: str = PitchStatus.DRAFT.value
    approved_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


class PipelineEvent(BaseModel):
    """Audit log entry for pipeline state transitions."""
    id: Optional[str] = None
    job_id: Optional[str] = None
    node: str  # 'scout', 'analyst', 'researcher', 'strategist', 'critic'
    from_status: Optional[str] = None
    to_status: Optional[str] = None
    metadata: dict = Field(default_factory=dict)
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None
