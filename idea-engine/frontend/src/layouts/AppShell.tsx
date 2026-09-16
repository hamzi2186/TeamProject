import React, { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import {
  FileText,
  ChevronLeft,
  ChevronRight,
  Sparkles,
} from "lucide-react";

interface AppShellProps {
  children: React.ReactNode;
}

export const AppShell: React.FC<AppShellProps> = ({ children }) => {
  const [collapsed, setCollapsed] = useState(false);
  const location = useLocation();

  const navItems = [
    { label: "Daily Reports", path: "/reports", icon: <FileText size={18} /> },
  ];

  return (
    <div style={{ display: "flex", minHeight: "100vh", backgroundColor: "var(--background)" }}>
      {/* Sidebar */}
      <aside
        style={{
          width: collapsed ? "68px" : "224px",
          backgroundColor: "var(--surface)",
          borderRight: "1px solid var(--border)",
          display: "flex",
          flexDirection: "column",
          transition: "width 0.2s cubic-bezier(0.4, 0, 0.2, 1)",
          position: "sticky",
          top: 0,
          height: "100vh",
          zIndex: 40,
        }}
      >
        {/* Brand Header */}
        <div
          style={{
            height: "58px",
            display: "flex",
            alignItems: "center",
            justifyContent: collapsed ? "center" : "space-between",
            padding: "0 16px",
            borderBottom: "1px solid var(--border)",
          }}
        >
          {!collapsed ? (
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <div
                style={{
                  width: "24px",
                  height: "24px",
                  borderRadius: "6px",
                  backgroundColor: "var(--brand)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontWeight: 700,
                  fontSize: "14px",
                  color: "var(--brand-foreground)",
                }}
              >
                T
              </div>
              <span style={{ fontWeight: 700, fontSize: "16px", letterSpacing: "-0.01em" }}>
                T Rex <span style={{ fontWeight: 400, color: "var(--text-muted)", fontSize: "13px" }}>Idea</span>
              </span>
            </div>
          ) : (
            <div
              style={{
                width: "28px",
                height: "28px",
                borderRadius: "6px",
                backgroundColor: "var(--brand)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontWeight: 700,
                fontSize: "15px",
                color: "var(--brand-foreground)",
              }}
            >
              T
            </div>
          )}
        </div>

        {/* Navigation Items */}
        <nav style={{ padding: "12px 8px", display: "flex", flexDirection: "column", gap: "4px", flex: 1 }}>
          {navItems.map((item) => {
            const active = location.pathname.startsWith(item.path);
            return (
              <Link
                key={item.path}
                to={item.path}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "12px",
                  padding: collapsed ? "10px" : "8px 12px",
                  justifyContent: collapsed ? "center" : "flex-start",
                  borderRadius: "var(--radius-md)",
                  backgroundColor: active ? "var(--surface-subtle)" : "transparent",
                  color: active ? "var(--text-primary)" : "var(--text-secondary)",
                  fontWeight: active ? 600 : 500,
                  fontSize: "13.5px",
                  borderLeft: active ? "3px solid var(--brand-deep)" : "3px solid transparent",
                  transition: "all 0.15s ease",
                }}
              >
                {item.icon}
                {!collapsed && <span>{item.label}</span>}
              </Link>
            );
          })}
        </nav>

        {/* Sidebar Footer */}
        <div
          style={{
            padding: "12px 16px",
            borderTop: "1px solid var(--border)",
            display: "flex",
            alignItems: "center",
            justifyContent: collapsed ? "center" : "space-between",
          }}
        >
          {!collapsed && (
            <div style={{ display: "flex", flexDirection: "column" }}>
              <span style={{ fontSize: "11px", fontWeight: 600, color: "var(--text-primary)" }}>
                Idea Engine
              </span>
              <span style={{ fontSize: "10.5px", color: "var(--text-muted)" }}>
                v1.0 • Connected
              </span>
            </div>
          )}
          <button
            onClick={() => setCollapsed(!collapsed)}
            style={{
              padding: "6px",
              borderRadius: "4px",
              color: "var(--text-muted)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
            title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
          </button>
        </div>
      </aside>

      {/* Main Content Area */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0 }}>
        {/* Topbar */}
        <header
          style={{
            height: "58px",
            backgroundColor: "var(--surface)",
            borderBottom: "1px solid var(--border)",
            padding: "0 28px",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            position: "sticky",
            top: 0,
            zIndex: 30,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "13px", color: "var(--text-muted)" }}>
            <span>T Rex</span>
            <span>/</span>
            <span style={{ fontWeight: 600, color: "var(--text-primary)" }}>Reports</span>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
            <div
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "6px",
                fontSize: "12px",
                fontWeight: 500,
                padding: "6px 12px",
                borderRadius: "var(--radius-md)",
                backgroundColor: "var(--surface-subtle)",
                color: "var(--text-secondary)",
                border: "1px solid var(--border)",
              }}
            >
              <Sparkles size={14} color="var(--brand-deep)" />
              <span>Lead Intelligence Active</span>
            </div>
          </div>
        </header>

        {/* Page Container */}
        <main style={{ padding: "28px", flex: 1, maxWidth: "1440px", width: "100%", margin: "0 auto" }}>
          {children}
        </main>
      </div>
    </div>
  );
};
