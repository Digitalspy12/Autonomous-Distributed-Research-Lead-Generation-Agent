"use client";

import { useEffect, useState } from "react";
import Sidebar from "@/components/Sidebar";
import { supabase } from "@/lib/supabase";

interface Stats {
  totalJobs: number;
  preFiltered: number;
  analyzed: number;
  enriched: number;
  pitchWritten: number;
  pitchApproved: number;
  rejected: number;
  totalCompanies: number;
  totalContacts: number;
  totalPitches: number;
  recentJobs: Array<{
    id: string;
    title: string;
    status: string;
    source: string;
    discovered_at: string;
    company_name?: string;
  }>;
}

export default function DashboardPage() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchStats();
  }, []);

  async function fetchStats() {
    try {
      // Count jobs by status
      const { data: jobs } = await supabase.from("jobs").select("id, status");
      const { data: companies } = await supabase
        .from("companies")
        .select("id");
      const { data: contacts } = await supabase.from("contacts").select("id");
      const { data: pitches } = await supabase.from("pitches").select("id");

      // Recent jobs with company name
      const { data: recentJobs } = await supabase
        .from("jobs")
        .select("id, title, status, source, discovered_at, company_id")
        .order("discovered_at", { ascending: false })
        .limit(10);

      // Get company names for recent jobs
      const companyIds = [
        ...new Set(
          (recentJobs || [])
            .map((j) => j.company_id)
            .filter(Boolean) as string[]
        ),
      ];
      let companyMap: Record<string, string> = {};
      if (companyIds.length > 0) {
        const { data: companyData } = await supabase
          .from("companies")
          .select("id, name")
          .in("id", companyIds);
        companyMap = Object.fromEntries(
          (companyData || []).map((c) => [c.id, c.name])
        );
      }

      const jobArr = jobs || [];
      const statusCount = (s: string) =>
        jobArr.filter((j) => j.status === s).length;

      setStats({
        totalJobs: jobArr.length,
        preFiltered: statusCount("pre_filtered"),
        analyzed: statusCount("analyzed"),
        enriched: statusCount("enriched"),
        pitchWritten: statusCount("pitch_written"),
        pitchApproved: statusCount("pitch_approved"),
        rejected:
          statusCount("rejected") + statusCount("pitch_rejected"),
        totalCompanies: (companies || []).length,
        totalContacts: (contacts || []).length,
        totalPitches: (pitches || []).length,
        recentJobs: (recentJobs || []).map((j) => ({
          id: j.id,
          title: j.title,
          status: j.status,
          source: j.source,
          discovered_at: j.discovered_at,
          company_name: companyMap[j.company_id] || "—",
        })),
      });
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Failed to fetch";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }

  function timeAgo(dateStr: string) {
    const d = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - d.getTime();
    const mins = Math.floor(diffMs / 60000);
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    return `${Math.floor(hrs / 24)}d ago`;
  }

  return (
    <>
      <Sidebar />
      <main className="main-content">
        <div className="page-header">
          <h2>Pipeline Overview</h2>
          <p>Signal Scout 4.0 — Autonomous B2B Research Engine</p>
        </div>

        {loading ? (
          <div className="stats-grid">
            {[1, 2, 3, 4, 5, 6].map((i) => (
              <div key={i} className="stat-card">
                <div className="skeleton" style={{ width: 80, marginBottom: 12 }} />
                <div className="skeleton" style={{ width: 60, height: 32 }} />
              </div>
            ))}
          </div>
        ) : error ? (
          <div className="empty-state">
            <div className="icon">⚠️</div>
            <h3>Connection Error</h3>
            <p>{error}</p>
            <p style={{ marginTop: 12, fontSize: 12 }}>
              Make sure Supabase schema is set up and <code>.env.local</code> is configured.
            </p>
          </div>
        ) : stats ? (
          <>
            <div className="stats-grid">
              <div className="stat-card blue">
                <div className="stat-label">Total Jobs</div>
                <div className="stat-value">{stats.totalJobs}</div>
                <div className="stat-sub">{stats.totalCompanies} companies</div>
              </div>
              <div className="stat-card cyan">
                <div className="stat-label">Pre-filtered</div>
                <div className="stat-value">{stats.preFiltered}</div>
                <div className="stat-sub">Pain score ≥ 4</div>
              </div>
              <div className="stat-card violet">
                <div className="stat-label">Analyzed</div>
                <div className="stat-value">{stats.analyzed}</div>
                <div className="stat-sub">Pain hypothesis generated</div>
              </div>
              <div className="stat-card emerald">
                <div className="stat-label">Enriched</div>
                <div className="stat-value">{stats.enriched}</div>
                <div className="stat-sub">{stats.totalContacts} contacts</div>
              </div>
              <div className="stat-card amber">
                <div className="stat-label">Pitches Written</div>
                <div className="stat-value">{stats.pitchWritten}</div>
                <div className="stat-sub">{stats.totalPitches} total pitches</div>
              </div>
              <div className="stat-card rose">
                <div className="stat-label">Approved</div>
                <div className="stat-value">{stats.pitchApproved}</div>
                <div className="stat-sub">{stats.rejected} rejected</div>
              </div>
            </div>

            <div className="card">
              <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 16 }}>
                Recent Discoveries
              </h3>
              {stats.recentJobs.length === 0 ? (
                <div className="empty-state">
                  <div className="icon">🔭</div>
                  <h3>No jobs yet</h3>
                  <p>Run <code>python scripts/run_pipeline.py --node scout</code> then <code>--node sync</code></p>
                </div>
              ) : (
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Job Title</th>
                      <th>Company</th>
                      <th>Source</th>
                      <th>Status</th>
                      <th>Discovered</th>
                    </tr>
                  </thead>
                  <tbody>
                    {stats.recentJobs.map((job) => (
                      <tr key={job.id}>
                        <td style={{ color: "var(--text-primary)", fontWeight: 500 }}>
                          {job.title}
                        </td>
                        <td>{job.company_name}</td>
                        <td>{job.source}</td>
                        <td>
                          <span className={`badge ${job.status}`}>
                            {job.status.replace(/_/g, " ")}
                          </span>
                        </td>
                        <td>{timeAgo(job.discovered_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </>
        ) : null}
      </main>
    </>
  );
}
