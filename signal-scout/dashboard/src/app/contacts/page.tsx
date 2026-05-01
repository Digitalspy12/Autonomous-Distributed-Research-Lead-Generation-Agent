"use client";

import { useEffect, useState } from "react";
import Sidebar from "@/components/Sidebar";
import { supabase } from "@/lib/supabase";

interface Contact {
  id: string;
  name: string;
  title: string;
  email_verified: string | null;
  linkedin_url: string | null;
  linkedin_confidence: string;
  outreach_ready: boolean;
  outreach_status: string;
  created_at: string;
  company_name?: string;
}

export default function ContactsPage() {
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchContacts();
  }, []);

  async function fetchContacts() {
    const { data } = await supabase
      .from("contacts")
      .select("id, name, title, email_verified, linkedin_url, linkedin_confidence, outreach_ready, outreach_status, created_at, company_id")
      .order("created_at", { ascending: false })
      .limit(100);

    const companyIds = [...new Set((data || []).map(c => c.company_id).filter(Boolean) as string[])];
    let companyMap: Record<string, string> = {};
    if (companyIds.length > 0) {
      const { data: companies } = await supabase.from("companies").select("id, name").in("id", companyIds);
      companyMap = Object.fromEntries((companies || []).map(c => [c.id, c.name]));
    }

    setContacts((data || []).map(c => ({
      ...c,
      company_name: companyMap[c.company_id] || "—",
    })));
    setLoading(false);
  }

  return (
    <>
      <Sidebar />
      <main className="main-content">
        <div className="page-header">
          <h2>Contacts</h2>
          <p>Enriched decision-maker contacts for outreach</p>
        </div>

        <div className="card">
          {loading ? (
            <div style={{ padding: 40, textAlign: "center" }}>
              <span className="loading-pulse" style={{ fontSize: 13, color: "var(--text-muted)" }}>Loading contacts...</span>
            </div>
          ) : contacts.length === 0 ? (
            <div className="empty-state">
              <div className="icon">👤</div>
              <h3>No contacts yet</h3>
              <p>Run the Researcher node to enrich jobs with contact data.</p>
            </div>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Title</th>
                  <th>Company</th>
                  <th>Email</th>
                  <th>LinkedIn</th>
                  <th>Ready</th>
                  <th>Outreach</th>
                </tr>
              </thead>
              <tbody>
                {contacts.map(c => (
                  <tr key={c.id}>
                    <td style={{ color: "var(--text-primary)", fontWeight: 500 }}>
                      {c.name || "—"}
                    </td>
                    <td>{c.title || "—"}</td>
                    <td>{c.company_name}</td>
                    <td>
                      {c.email_verified ? (
                        <span style={{ fontSize: 12 }}>{c.email_verified}</span>
                      ) : (
                        <span style={{ color: "var(--text-muted)" }}>—</span>
                      )}
                    </td>
                    <td>
                      {c.linkedin_url ? (
                        <a href={c.linkedin_url} target="_blank" rel="noopener noreferrer"
                           style={{ color: "var(--accent-blue)", textDecoration: "none", fontSize: 12 }}>
                          Profile ↗
                        </a>
                      ) : "—"}
                    </td>
                    <td>
                      {c.outreach_ready ? (
                        <span className="badge pass">Ready</span>
                      ) : (
                        <span className="badge draft">Pending</span>
                      )}
                    </td>
                    <td>
                      <span className={`badge ${c.outreach_status === "not_contacted" ? "new" : "analyzed"}`}>
                        {c.outreach_status.replace(/_/g, " ")}
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
