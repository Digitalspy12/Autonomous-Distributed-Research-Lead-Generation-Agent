"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const navItems = [
  { href: "/", icon: "📊", label: "Overview" },
  { href: "/jobs", icon: "💼", label: "Jobs" },
  { href: "/pitches", icon: "✉️", label: "Pitches" },
  { href: "/contacts", icon: "👤", label: "Contacts" },
  { href: "/events", icon: "📋", label: "Pipeline Events" },
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="sidebar">
      <div className="sidebar-logo">
        <div className="logo-icon">🔭</div>
        <div>
          <h1>Signal Scout</h1>
          <span>v4.0</span>
        </div>
      </div>

      <nav className="nav-section">
        <div className="nav-section-title">Pipeline</div>
        {navItems.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className={`nav-link ${pathname === item.href ? "active" : ""}`}
          >
            <span className="icon">{item.icon}</span>
            {item.label}
          </Link>
        ))}
      </nav>

      <div style={{ flex: 1 }} />

      <div className="nav-section">
        <div className="nav-section-title">System</div>
        <div className="nav-link" style={{ cursor: "default" }}>
          <span className="icon">🟢</span>
          <span style={{ fontSize: 12 }}>Engine Online</span>
        </div>
      </div>
    </aside>
  );
}
