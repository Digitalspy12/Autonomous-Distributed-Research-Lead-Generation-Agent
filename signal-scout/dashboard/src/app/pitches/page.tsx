"use client";

import { useEffect, useState } from "react";
import Sidebar from "@/components/Sidebar";
import { supabase } from "@/lib/supabase";

interface Pitch {
  id: string;
  subject_line: string;
  pitch_body: string;
  tone_profile: string;
  word_count: number;
  score_average: number | null;
  critic_verdict: string | null;
  critic_feedback: string | null;
  status: string;
  created_at: string;
  job_title?: string;
  company_name?: string;
}

export default function PitchesPage() {
  const [pitches, setPitches] = useState<Pitch[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("all");

  useEffect(() => {
    fetchPitches();
  }, [filter]);

  async function fetchPitches() {
    setLoading(true);
    let query = supabase
      .from("pitches")
      .select("*, job_id")
      .order("created_at", { ascending: false })
      .limit(50);

    if (filter !== "all") {
      query = query.eq("status", filter);
    }

    const { data } = await query;

    // Get job titles and company names
    const jobIds = [...new Set((data || []).map(p => p.job_id).filter(Boolean) as string[])];
    let jobMap: Record<string, { title: string; company_id: string }> = {};
    if (jobIds.length > 0) {
      const { data: jobData } = await supabase
        .from("jobs")
        .select("id, title, company_id")
        .in("id", jobIds);
      jobMap = Object.fromEntries((jobData || []).map(j => [j.id, { title: j.title, company_id: j.company_id }]));
    }

    const companyIds = [...new Set(Object.values(jobMap).map(j => j.company_id).filter(Boolean))];
    let companyMap: Record<string, string> = {};
    if (companyIds.length > 0) {
      const { data: companies } = await supabase
        .from("companies")
        .select("id, name")
        .in("id", companyIds);
      companyMap = Object.fromEntries((companies || []).map(c => [c.id, c.name]));
    }

    setPitches((data || []).map(p => ({
      ...p,
      job_title: jobMap[p.job_id]?.title || "—",
      company_name: companyMap[jobMap[p.job_id]?.company_id] || "—",
    })));
    setLoading(false);
  }

  async function updatePitchStatus(pitchId: string, newStatus: string) {
    await supabase.from("pitches").update({ status: newStatus }).eq("id", pitchId);
    fetchPitches();
  }

  return (
    <>
      <Sidebar />
      <main className="main-content">
        <div className="page-header">
          <h2>Pitches</h2>
          <p>AI-generated outreach emails — review and approve</p>
        </div>

        <div className="filter-tabs">
          {["all", "draft", "approved", "rejected", "sent"].map(s => (
            <button
              key={s}
              className={`filter-tab ${filter === s ? "active" : ""}`}
              onClick={() => setFilter(s)}
            >
              {s}
            </button>
          ))}
        </div>

        {loading ? (
          <div style={{ padding: 40, textAlign: "center" }}>
            <span className="loading-pulse" style={{ fontSize: 13, color: "var(--text-muted)" }}>
              Loading pitches...
            </span>
          </div>
        ) : pitches.length === 0 ? (
          <div className="empty-state">
            <div className="icon">✉️</div>
            <h3>No pitches yet</h3>
            <p>Run the full pipeline (scout → analyst → researcher → strategist → critic → sync) to generate pitches.</p>
          </div>
        ) : (
          pitches.map(pitch => (
            <div key={pitch.id} className="pitch-card">
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 8 }}>
                <div>
                  <div style={{ fontSize: 11, color: "var(--text-muted)", marginBottom: 4 }}>
                    {pitch.job_title} @ {pitch.company_name}
                  </div>
                  <div className="pitch-subject">{pitch.subject_line}</div>
                </div>
                <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                  {pitch.score_average !== null && (
                    <span style={{ fontSize: 13, fontWeight: 700, color: pitch.score_average >= 6.5 ? "var(--accent-emerald)" : "var(--accent-rose)" }}>
                      {pitch.score_average}/10
                    </span>
                  )}
                  <span className={`badge ${pitch.status}`}>{pitch.status}</span>
                </div>
              </div>

              <div className="pitch-body">{pitch.pitch_body}</div>

              {pitch.critic_feedback && (
                <div style={{ fontSize: 12, color: "var(--accent-amber)", marginBottom: 12, fontStyle: "italic" }}>
                  💡 {pitch.critic_feedback}
                </div>
              )}

              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div className="pitch-meta">
                  <span>🎯 {pitch.tone_profile}</span>
                  <span>📝 {pitch.word_count} words</span>
                  {pitch.critic_verdict && (
                    <span className={`badge ${pitch.critic_verdict.toLowerCase()}`}>
                      Critic: {pitch.critic_verdict}
                    </span>
                  )}
                </div>
                {pitch.status === "draft" && (
                  <div style={{ display: "flex", gap: 8 }}>
                    <button
                      onClick={() => updatePitchStatus(pitch.id, "approved")}
                      style={{
                        padding: "6px 16px", borderRadius: 8, fontSize: 12, fontWeight: 600,
                        background: "rgba(16, 185, 129, 0.15)", color: "var(--accent-emerald)",
                        border: "1px solid rgba(16, 185, 129, 0.3)", cursor: "pointer",
                      }}
                    >
                      ✓ Approve
                    </button>
                    <button
                      onClick={() => updatePitchStatus(pitch.id, "rejected")}
                      style={{
                        padding: "6px 16px", borderRadius: 8, fontSize: 12, fontWeight: 600,
                        background: "rgba(244, 63, 94, 0.12)", color: "var(--accent-rose)",
                        border: "1px solid rgba(244, 63, 94, 0.25)", cursor: "pointer",
                      }}
                    >
                      ✗ Reject
                    </button>
                  </div>
                )}
              </div>
            </div>
          ))
        )}
      </main>
    </>
  );
}
