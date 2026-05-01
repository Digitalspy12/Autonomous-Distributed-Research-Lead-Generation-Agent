-- ============================================
-- SIGNAL SCOUT 4.0 — SUPABASE SCHEMA
-- Run this ONCE in Supabase SQL Editor
-- Dashboard → SQL Editor → New Query → Paste → Run
-- ============================================

-- 1. COMPANIES (deduplicated by domain)
CREATE TABLE companies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    domain TEXT UNIQUE,
    size_estimate TEXT,
    location TEXT,
    funding_stage TEXT,
    tech_stack TEXT[],
    industry TEXT,
    crunchbase_url TEXT,
    github_url TEXT,
    linkedin_url TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. JOBS (pain signals, deduplicated by job_url)
CREATE TABLE jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
    source TEXT NOT NULL,         -- 'greenhouse', 'lever', 'rss', etc.
    source_url TEXT,
    title TEXT NOT NULL,
    description TEXT,
    job_url TEXT UNIQUE NOT NULL,
    location TEXT,
    -- Analyst output
    pain_hypothesis TEXT,
    primary_process TEXT,
    integration_gaps TEXT[],
    tech_stack_inferred TEXT[],
    automatibility_score INTEGER CHECK (automatibility_score BETWEEN 0 AND 10),
    analyst_confidence INTEGER CHECK (analyst_confidence BETWEEN 0 AND 10),
    analyst_verdict TEXT CHECK (analyst_verdict IN ('PASS', 'REJECT', NULL)),
    -- Pre-filter
    pain_keyword_score INTEGER DEFAULT 0,
    -- Status machine
    status TEXT DEFAULT 'new' CHECK (status IN (
        'new', 'pre_filtered', 'analyzed', 'rejected',
        'enriched', 'pitch_written', 'pitch_approved',
        'pitch_rejected', 'error'
    )),
    discovered_at TIMESTAMPTZ DEFAULT NOW(),
    analyzed_at TIMESTAMPTZ,
    enriched_at TIMESTAMPTZ,
    pitch_written_at TIMESTAMPTZ,
    pitch_scored_at TIMESTAMPTZ
);

-- 3. CONTACTS (enrichment output)
CREATE TABLE contacts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
    job_id UUID REFERENCES jobs(id) ON DELETE CASCADE,
    name TEXT,
    title TEXT,
    email_verified TEXT,
    email_sources TEXT[],
    linkedin_url TEXT,
    linkedin_confidence TEXT CHECK (linkedin_confidence IN ('verified', 'inferred', 'none')),
    manual_research_links JSONB DEFAULT '{}',
    outreach_ready BOOLEAN DEFAULT FALSE,
    outreach_status TEXT DEFAULT 'not_contacted' CHECK (outreach_status IN (
        'not_contacted', 'linkedin_dm_sent', 'email_sent',
        'warm_intro', 'responded', 'meeting_booked',
        'not_interested', 'archived'
    )),
    outreach_channel TEXT,
    contacted_at TIMESTAMPTZ,
    responded_at TIMESTAMPTZ,
    follow_up_at TIMESTAMPTZ,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4. PITCHES (Strategist + Critic output)
CREATE TABLE pitches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID REFERENCES jobs(id) ON DELETE CASCADE,
    contact_id UUID REFERENCES contacts(id) ON DELETE CASCADE,
    -- Strategist output
    subject_line TEXT,
    pitch_body TEXT,
    tone_profile TEXT,        -- 'direct', 'consultative', 'curious'
    word_count INTEGER,
    -- Critic scores (Gemini primary, DeepSeek R1 fallback)
    score_specificity NUMERIC(3,1),
    score_consultative NUMERIC(3,1),
    score_tone NUMERIC(3,1),
    score_brevity NUMERIC(3,1),
    score_value NUMERIC(3,1),
    score_credibility NUMERIC(3,1),
    score_humanity NUMERIC(3,1),
    score_average NUMERIC(3,1),
    critic_verdict TEXT CHECK (critic_verdict IN ('PASS', 'FAIL')),
    critic_feedback TEXT,
    -- Status
    status TEXT DEFAULT 'draft' CHECK (status IN ('draft', 'approved', 'rejected', 'sent')),
    approved_at TIMESTAMPTZ,
    sent_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 5. PIPELINE EVENTS (audit log)
CREATE TABLE pipeline_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID REFERENCES jobs(id) ON DELETE CASCADE,
    node TEXT NOT NULL,       -- 'scout', 'analyst', 'researcher', 'strategist', 'critic'
    from_status TEXT,
    to_status TEXT,
    metadata JSONB DEFAULT '{}',
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================
-- INDEXES
-- ============================================
CREATE INDEX idx_jobs_status ON jobs(status);
CREATE INDEX idx_jobs_company ON jobs(company_id);
CREATE INDEX idx_jobs_discovered ON jobs(discovered_at DESC);
CREATE INDEX idx_contacts_outreach ON contacts(outreach_status);
CREATE INDEX idx_contacts_ready ON contacts(outreach_ready) WHERE outreach_ready = TRUE;
CREATE INDEX idx_pitches_status ON pitches(status);
CREATE INDEX idx_pipeline_events_job ON pipeline_events(job_id);
CREATE INDEX idx_pipeline_events_created ON pipeline_events(created_at DESC);
CREATE INDEX idx_companies_domain ON companies(domain);

-- ============================================
-- ROW LEVEL SECURITY
-- ============================================
ALTER TABLE companies ENABLE ROW LEVEL SECURITY;
ALTER TABLE jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE contacts ENABLE ROW LEVEL SECURITY;
ALTER TABLE pitches ENABLE ROW LEVEL SECURITY;
ALTER TABLE pipeline_events ENABLE ROW LEVEL SECURITY;

-- Service role (Python backend) can do everything
CREATE POLICY "Service role full access" ON companies
    FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "Service role full access" ON jobs
    FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "Service role full access" ON contacts
    FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "Service role full access" ON pitches
    FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "Service role full access" ON pipeline_events
    FOR ALL USING (auth.role() = 'service_role');

-- Anon key (Dashboard) can read everything
CREATE POLICY "Anon read all" ON companies FOR SELECT USING (true);
CREATE POLICY "Anon read all" ON jobs FOR SELECT USING (true);
CREATE POLICY "Anon read all" ON contacts FOR SELECT USING (true);
CREATE POLICY "Anon read all" ON pitches FOR SELECT USING (true);
CREATE POLICY "Anon read all" ON pipeline_events FOR SELECT USING (true);

-- Anon key can update outreach status + notes on contacts
CREATE POLICY "Anon update contacts" ON contacts
    FOR UPDATE USING (true) WITH CHECK (true);

-- Anon key can update pitch approval status
CREATE POLICY "Anon update pitches" ON pitches
    FOR UPDATE USING (true) WITH CHECK (true);

-- ============================================
-- UPDATED_AT TRIGGER
-- ============================================
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER companies_updated_at
    BEFORE UPDATE ON companies
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
