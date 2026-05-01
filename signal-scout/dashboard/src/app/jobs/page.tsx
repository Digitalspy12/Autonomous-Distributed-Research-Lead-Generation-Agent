"use client";

import { useEffect, useState } from "react";
import Sidebar from "@/components/Sidebar";
import { supabase } from "@/lib/supabase";

interface Job {
  id: string;
  title: string;
  status: string;
  source: string;
  location: string;
  pain_hypothesis: string | null;
  automatibility_score: number | null;
  analyst_verdict: string | null;
  pain_keyword_score: number;
  discovered_at: string;
  company_name?: string;
}

const STATUSES = [
  "all", "new", "pre_filtered", "analyzed", "enriched",
  "pitch_written", "pitch_approved", "rejected",
];

export default function JobsPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("all");

  useEffect(() => {
    fetchJobs();
  }, [filter]);

  async function fetchJobs() {
    setLoading(true);
    let query = supabase
      .from("jobs")
      .select("id, title, status, source, location, pain_hypothesis, automatibility_score, analyst_verdict, pain_keyword_score, discovered_at, company_id")
      .order("discovered_at", { ascending: false })
      .limit(100);

    if (filter !== "all") {
      query = query.eq("status", filter);
    }

    const { data } = await query;

    // Resolve company names
    const companyIds = [...new Set((data || []).map(j => j.company_id).filter(Boolean) as string[])];
    let companyMap: Record<string, string> = {};
    if (companyIds.length > 0) {
      const { data: companies } = await supabase
        .from("companies")
        .select("id, name")
        .in("id", companyIds);
      companyMap = Object.fromEntries((companies || []).map(c => [c.id, c.name]));
    }

    setJobs((data || []).map(j => ({
      ...j,
      company_name: companyMap[j.company_id] || "—",
    })));
    setLoading(false);
  }

  return (
    <>
      <Sidebar />
      <main className="main-content">
        <div className="page-header">
          <h2>Jobs</h2>
          <p>All discovered job postings with pain analysis</p>
        </div>

        <div className="filter-tabs">
          {STATUSES.map(s => (
            <button
              key={s}
              className={`filter-tab ${filter === s ? "active" : ""}`}
              onClick={() => setFilter(s)}
            >
              {s.replace(/_/g, " ")}
            </button>
          ))}
        </div>

        <div className="card">
          {loading ? (
            <div style={{ padding: 40, textAlign: "center" }}>
              <span className="loading-pulse" style={{ fontSize: 13, color: "var(--text-muted)" }}>
                Loading jobs...
              </span>
            </div>
          ) : jobs.length === 0 ? (
            <div className="empty-state">
              <div className="icon">💼</div>
              <h3>No jobs found</h3>
              <p>Run the Scout node and sync to see data here.</p>
            </div>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Title</th>
                  <th>Company</th>
                  <th>Source</th>
                  <th>Pain Score</th>
                  <th>Auto Score</th>
                  <th>Verdict</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {jobs.map(job => (
                  <tr key={job.id}>
                    <td style={{ color: "var(--text-primary)", fontWeight: 500, maxWidth: 280 }}>
                      {job.title}
                    </td>
                    <td>{job.company_name}</td>
                    <td>{job.source}</td>
                    <td>{job.pain_keyword_score}</td>
                    <td>
                      {job.automatibility_score !== null ? (
                        <div className="score-bar">
                          <div className="score-track">
                            <div
                              className="score-fill"
                              style={{ width: `${job.automatibility_score * 10}%` }}
                            />
                          </div>
                          <span style={{ fontSize: 11, color: "var(--text-muted)", minWidth: 24 }}>
                            {job.automatibility_score}
                          </span>
                        </div>
                      ) : (
                        <span style={{ color: "var(--text-muted)" }}>—</span>
                      )}
                    </td>
                    <td>
                      {job.analyst_verdict ? (
                        <span className={`badge ${job.analyst_verdict.toLowerCase()}`}>
                          {job.analyst_verdict}
                        </span>
                      ) : "—"}
                    </td>
                    <td>
                      <span className={`badge ${job.status}`}>
                        {job.status.replace(/_/g, " ")}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </main>
    </>
  );
}
