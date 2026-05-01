"use client";

import { useEffect, useState } from "react";
import Sidebar from "@/components/Sidebar";
import { supabase } from "@/lib/supabase";

interface PipelineEvent {
  id: string;
  node: string;
  from_status: string | null;
  to_status: string | null;
  error_message: string | null;
  created_at: string;
  metadata: Record<string, unknown>;
}

const NODE_ICONS: Record<string, string> = {
  scout: "🔭",
  analyst: "🧠",
  researcher: "🔍",
  strategist: "✉️",
  critic: "⚖️",
};

export default function EventsPage() {
  const [events, setEvents] = useState<PipelineEvent[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchEvents();
  }, []);

  async function fetchEvents() {
    const { data } = await supabase
      .from("pipeline_events")
      .select("id, node, from_status, to_status, error_message, created_at, metadata")
      .order("created_at", { ascending: false })
      .limit(100);

    setEvents(data || []);
    setLoading(false);
  }

  function formatTime(dateStr: string) {
    return new Date(dateStr).toLocaleString("en-IN", {
      month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
    });
  }

  return (
    <>
      <Sidebar />
      <main className="main-content">
        <div className="page-header">
          <h2>Pipeline Events</h2>
          <p>Audit log of all state transitions</p>
        </div>

        <div className="card">
          {loading ? (
            <div style={{ padding: 40, textAlign: "center" }}>
              <span className="loading-pulse" style={{ fontSize: 13, color: "var(--text-muted)" }}>Loading events...</span>
            </div>
          ) : events.length === 0 ? (
            <div className="empty-state">
              <div className="icon">📋</div>
              <h3>No events yet</h3>
              <p>Run any pipeline node and sync to see events here.</p>
            </div>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Node</th>
                  <th>Transition</th>
                  <th>Details</th>
                  <th>Time</th>
                </tr>
              </thead>
              <tbody>
                {events.map(evt => (
                  <tr key={evt.id}>
                    <td>
                      <span style={{ marginRight: 6 }}>{NODE_ICONS[evt.node] || "⚙️"}</span>
                      <span style={{ fontWeight: 500, color: "var(--text-primary)" }}>{evt.node}</span>
                    </td>
                    <td>
                      {evt.from_status && (
                        <span className={`badge ${evt.from_status}`}>
                          {evt.from_status.replace(/_/g, " ")}
                        </span>
                      )}
                      {evt.from_status && evt.to_status && (
                        <span style={{ margin: "0 6px", color: "var(--text-muted)" }}>→</span>
                      )}
                      {evt.to_status && (
                        <span className={`badge ${evt.to_status}`}>
                          {evt.to_status.replace(/_/g, " ")}
                        </span>
                      )}
                    </td>
                    <td style={{ maxWidth: 300 }}>
                      {evt.error_message ? (
                        <span style={{ color: "var(--accent-rose)", fontSize: 12 }}>
                          ⚠ {evt.error_message}
                        </span>
                      ) : evt.metadata && Object.keys(evt.metadata).length > 0 ? (
                        <span style={{ fontSize: 11, color: "var(--text-muted)" }}>
                          {JSON.stringify(evt.metadata).slice(0, 80)}
                        </span>
                      ) : "—"}
                    </td>
                    <td style={{ fontSize: 12, whiteSpace: "nowrap" }}>
                      {formatTime(evt.created_at)}
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
